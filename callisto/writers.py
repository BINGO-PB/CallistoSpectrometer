"""Writers de aquisição (FITS/HDF5) e spectral overview (HDF5)."""

from __future__ import annotations

import datetime
import importlib
import os
from typing import Callable

from .models import Config, OVSItem


class DataWriterEngine:
    """Encapsula estado e rotatividade de arquivos de saída."""

    def __init__(
        self,
        config: Config,
        get_channel_frequencies: Callable[[], list[float]],
        utc_iso_from_us: Callable[[int], str],
        logger: Callable[[int, str, object], None],
    ):
        self._config = config
        self._get_channel_frequencies = get_channel_frequencies
        self._utc_iso_from_us = utc_iso_from_us
        self._logger = logger

        self._astropy_fits = None
        self._h5py = None

        self._fits_current_path: str | None = None
        self._fits_current_start = 0
        self._fits_seq = 0

        self._ovs_hdf5_current_path: str | None = None
        self._ovs_hdf5_current_start = 0
        self._ovs_hdf5_seq = 0

    @staticmethod
    def normalized_output_format(value: str) -> str:
        v = (value or "fits").strip().lower()
        if v in ("hdf5", "h5"):
            return "hdf5"
        return "fits"

    def fits_init(self) -> bool:
        try:
            from astropy.io import fits as _fits

            self._astropy_fits = _fits
            self._logger(2, "FITS backend loaded: astropy=%s", _fits.__name__)
            return True
        except Exception as e:
            self._logger(0, "FITS dependency missing or invalid (astropy): %s", e)
            return False

    def hdf5_init(self) -> bool:
        try:
            import h5py as _h5

            self._h5py = _h5
            self._logger(2, "HDF5 backend loaded: h5py=%s", _h5.__name__)
            return True
        except Exception as e:
            self._logger(0, "HDF5 dependency missing or invalid (h5py): %s", e)
            return False

    def _fits_new_path(self, ts_us: int) -> str:
        dt = datetime.datetime.fromtimestamp(
            ts_us / 1_000_000, tz=datetime.timezone.utc
        )
        stamp = dt.strftime("%Y%m%d_%H%M%S")
        ext = (
            "h5"
            if self.normalized_output_format(self._config.output_format) == "hdf5"
            else "fits"
        )
        name = f"CALLISTO_{self._config.instrument}_{stamp}.{ext}"
        return os.path.join(self._config.datadir, name)

    def _fits_prepare_header(self, ts_us: int, end_ts_us: int):
        hdr = self._astropy_fits.Header()
        hdr["INSTRUME"] = str(self._config.instrument)
        hdr["DATE-OBS"] = self._utc_iso_from_us(ts_us)
        hdr["DATE-END"] = self._utc_iso_from_us(end_ts_us)
        hdr["TIMEZONE"] = "UTC"
        hdr["SAMPRATE"] = int(self._config.samplerate)
        hdr["NCHAN"] = int(self._config.nchannels)
        hdr["FOCUSCOD"] = int(self._config.focuscode)
        hdr["AGCLEVEL"] = int(self._config.agclevel)
        hdr["CHGPUMP"] = int(self._config.chargepump)
        hdr["CLOCKSRC"] = int(self._config.clocksource)
        return hdr

    def _hdf5_prepare_attrs(self, ts_us: int) -> dict:
        return {
            "INSTRUME": str(self._config.instrument),
            "DATE-OBS": self._utc_iso_from_us(ts_us),
            "TIMEZONE": "UTC",
            "SAMPRATE": int(self._config.samplerate),
            "NCHAN": int(self._config.nchannels),
            "FOCUSCOD": int(self._config.focuscode),
            "AGCLEVEL": int(self._config.agclevel),
            "CHGPUMP": int(self._config.chargepump),
            "CLOCKSRC": int(self._config.clocksource),
        }

    def _hdf5_prepare_overview_attrs(self, ts_us: int) -> dict:
        return {
            "INSTRUME": str(self._config.instrument),
            "DATE-OBS": self._utc_iso_from_us(ts_us),
            "TIMEZONE": "UTC",
            "TYPE": "SPECTRAL_OVERVIEW",
            "AGCLEVEL": int(self._config.agclevel),
            "CLOCKSRC": int(self._config.clocksource),
            "FILETIME": int(self._config.filetime),
        }

    def _fits_rotate_if_needed(self, ts_us: int):
        if self._fits_current_path is None or self._fits_current_start <= 0:
            self._fits_current_start = ts_us
            self._fits_current_path = self._fits_new_path(ts_us)
            return

        elapsed = (ts_us - self._fits_current_start) / 1_000_000
        if elapsed >= max(1, int(self._config.filetime)):
            self._fits_current_start = ts_us
            self._fits_current_path = self._fits_new_path(ts_us)

    def _build_matrix_and_axes(self, buf_bytes: bytes, ts_us: int):
        np = importlib.import_module("numpy")
        raw = np.frombuffer(buf_bytes, dtype=np.uint8)

        nchan = max(1, int(self._config.nchannels))
        if raw.size < nchan:
            matrix = raw.reshape(1, raw.size)
        else:
            nsweeps = raw.size // nchan
            trimmed = raw[: nsweeps * nchan]
            matrix = trimmed.reshape(nsweeps, nchan)

        used_nchan = int(matrix.shape[1]) if matrix.ndim == 2 else int(raw.size)

        channel_frequencies_mhz = self._get_channel_frequencies()
        freqs = []
        for i in range(used_nchan):
            if i < len(channel_frequencies_mhz):
                freqs.append(float(channel_frequencies_mhz[i]))
            else:
                freqs.append(float(i))

        nsweeps = int(matrix.shape[0]) if matrix.ndim == 2 else 1
        step_us = int(1_000_000 / max(1, int(self._config.samplerate)))
        timestamps_us = np.array(
            [int(ts_us) + i * step_us for i in range(nsweeps)], dtype=np.int64
        )
        timestamps_iso = np.array(
            [self._utc_iso_from_us(int(t)) for t in timestamps_us], dtype="S32"
        )

        return matrix, np.array(freqs, dtype=np.float64), timestamps_us, timestamps_iso

    def _fits_write_buffer(self, buf_bytes: bytes, ts_us: int):
        if not buf_bytes:
            return

        self._fits_rotate_if_needed(ts_us)
        os.makedirs(self._config.datadir, exist_ok=True)

        matrix, freqs, timestamps_us, timestamps_iso = self._build_matrix_and_axes(
            buf_bytes, ts_us
        )
        end_ts_us = int(timestamps_us[-1]) if timestamps_us.size else int(ts_us)

        path = self._fits_current_path
        extname = f"DATA{self._fits_seq:05d}"
        freq_ext = f"FREQ{self._fits_seq:05d}"
        time_ext = f"TIME{self._fits_seq:05d}"
        self._fits_seq += 1
        hdr = self._fits_prepare_header(ts_us, end_ts_us)
        hdr["EXTNAME"] = extname

        freq_hdu = self._astropy_fits.BinTableHDU.from_columns(
            [
                self._astropy_fits.Column(
                    name="CHANNEL", format="J", array=list(range(1, len(freqs) + 1))
                ),
                self._astropy_fits.Column(
                    name="FREQUENCY_MHZ", format="D", array=freqs
                ),
            ],
            name=freq_ext,
        )

        time_hdu = self._astropy_fits.BinTableHDU.from_columns(
            [
                self._astropy_fits.Column(
                    name="SWEEP", format="J", array=list(range(len(timestamps_us)))
                ),
                self._astropy_fits.Column(
                    name="UNIX_US", format="K", array=timestamps_us
                ),
                self._astropy_fits.Column(
                    name="UTC_ISO", format="32A", array=timestamps_iso
                ),
            ],
            name=time_ext,
        )

        if not os.path.exists(path):
            hdu = self._astropy_fits.PrimaryHDU(data=matrix, header=hdr)
            hdul = self._astropy_fits.HDUList([hdu, freq_hdu, time_hdu])
            hdul.writeto(path, overwrite=True)
        else:
            hdu = self._astropy_fits.ImageHDU(data=matrix, header=hdr, name=extname)
            with self._astropy_fits.open(path, mode="append", memmap=False) as hdul:
                hdul.append(hdu)
                hdul.append(freq_hdu)
                hdul.append(time_hdu)
                hdul.flush()

    def _hdf5_write_buffer(self, buf_bytes: bytes, ts_us: int):
        if not buf_bytes:
            return

        self._fits_rotate_if_needed(ts_us)
        os.makedirs(self._config.datadir, exist_ok=True)

        matrix, freqs, timestamps_us, timestamps_iso = self._build_matrix_and_axes(
            buf_bytes, ts_us
        )
        attrs = self._hdf5_prepare_attrs(ts_us)

        path = self._fits_current_path
        group_name = f"DATA{self._fits_seq:05d}"
        self._fits_seq += 1

        with self._h5py.File(path, "a") as h5f:
            grp = h5f.create_group(group_name)
            grp.create_dataset("matrix", data=matrix, dtype="u1")
            grp.create_dataset("frequencies_mhz", data=freqs, dtype="f8")
            grp.create_dataset("timestamps_unix_us", data=timestamps_us, dtype="i8")
            grp.create_dataset("timestamps_utc", data=timestamps_iso, dtype="S32")
            for k, v in attrs.items():
                grp.attrs[k] = v

    def write_data_buffer(self, buf_bytes: bytes, ts_us: int):
        backend = self.normalized_output_format(self._config.output_format)
        if backend == "hdf5":
            self._hdf5_write_buffer(buf_bytes, ts_us)
        else:
            self._fits_write_buffer(buf_bytes, ts_us)

    def _overview_hdf5_new_path(self, ts_us: int) -> str:
        dt = datetime.datetime.fromtimestamp(
            ts_us / 1_000_000, tz=datetime.timezone.utc
        )
        stamp = dt.strftime("%Y%m%d_%H%M%S")
        name = f"OVS_{self._config.instrument}_{stamp}.h5"
        return os.path.join(self._config.ovsdir, name)

    def _overview_hdf5_rotate_if_needed(self, ts_us: int):
        if self._ovs_hdf5_current_path is None or self._ovs_hdf5_current_start <= 0:
            self._ovs_hdf5_current_start = ts_us
            self._ovs_hdf5_current_path = self._overview_hdf5_new_path(ts_us)
            return

        elapsed = (ts_us - self._ovs_hdf5_current_start) / 1_000_000
        if elapsed >= max(1, int(self._config.filetime)):
            self._ovs_hdf5_current_start = ts_us
            self._ovs_hdf5_current_path = self._overview_hdf5_new_path(ts_us)

    def save_overview_hdf5(self, points: list[OVSItem], ts_epoch: int):
        if not points:
            return

        ts_us = int(ts_epoch * 1_000_000)
        self._overview_hdf5_rotate_if_needed(ts_us)
        os.makedirs(self._config.ovsdir, exist_ok=True)

        np = importlib.import_module("numpy")
        freqs = np.array([float(p.freq) for p in points], dtype=np.float64)
        matrix = np.array([[float(p.value) for p in points]], dtype=np.float64)
        timestamps_us = np.array([ts_us], dtype=np.int64)
        timestamps_iso = np.array([self._utc_iso_from_us(ts_us)], dtype="S32")
        attrs = self._hdf5_prepare_overview_attrs(ts_us)

        path = self._ovs_hdf5_current_path
        dset_name = f"OVERVIEW{self._ovs_hdf5_seq:05d}"
        self._ovs_hdf5_seq += 1

        with self._h5py.File(path, "a") as h5f:
            grp = h5f.create_group(dset_name)
            grp.create_dataset("matrix", data=matrix, dtype="f8")
            grp.create_dataset("frequencies_mhz", data=freqs, dtype="f8")
            grp.create_dataset("timestamps_unix_us", data=timestamps_us, dtype="i8")
            grp.create_dataset("timestamps_utc", data=timestamps_iso, dtype="S32")
            grp.attrs["COLUMNS"] = "frequency_mhz,amplitude"
            for k, v in attrs.items():
                grp.attrs[k] = v
