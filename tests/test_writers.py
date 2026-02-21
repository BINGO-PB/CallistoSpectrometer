from __future__ import annotations

import pytest
from callisto.models import Config
from callisto.writers import DataWriterEngine


def _make_engine(tmp_path):
    cfg = Config(
        datadir=str(tmp_path / "data"),
        ovsdir=str(tmp_path / "ovs"),
        filetime=10,
        samplerate=2,
        nchannels=2,
        instrument="UNIT",
        output_format="fits",
    )

    logs: list[tuple[int, str]] = []

    def logger(level: int, fmt: str, *args) -> None:
        msg = fmt % args if args else fmt
        logs.append((level, msg))

    engine = DataWriterEngine(
        config=cfg,
        get_channel_frequencies=lambda: [10.0, 20.0],
        utc_iso_from_us=lambda us: f"TS-{us}",
        logger=logger,
    )
    return engine, cfg, logs


def test_normalized_output_format() -> None:
    assert DataWriterEngine.normalized_output_format("h5") == "hdf5"
    assert DataWriterEngine.normalized_output_format("HDF5") == "hdf5"
    assert DataWriterEngine.normalized_output_format("fits") == "fits"
    assert DataWriterEngine.normalized_output_format("") == "fits"


def test_build_matrix_and_axes(tmp_path) -> None:
    pytest.importorskip("numpy")

    engine, cfg, _ = _make_engine(tmp_path)
    cfg.samplerate = 2
    cfg.nchannels = 2

    matrix, freqs, timestamps_us, timestamps_iso = engine._build_matrix_and_axes(
        bytes([1, 2, 3, 4]),
        1_000_000,
    )

    assert matrix.shape == (2, 2)
    assert list(freqs) == [10.0, 20.0]
    assert list(timestamps_us) == [1_000_000, 1_500_000]
    assert list(timestamps_iso) == [b"TS-1000000", b"TS-1500000"]


def test_rotate_and_path_generation(tmp_path) -> None:
    engine, cfg, _ = _make_engine(tmp_path)
    cfg.output_format = "hdf5"
    p1 = engine._fits_new_path(1_700_000_000_000_000)
    assert p1.endswith(".h5")

    cfg.output_format = "fits"
    p2 = engine._fits_new_path(1_700_000_000_000_000)
    assert p2.endswith(".fits")

    engine._fits_rotate_if_needed(1_000_000)
    first = engine._fits_current_path
    engine._fits_rotate_if_needed(1_000_000 + 1_000_000)
    assert engine._fits_current_path == first

    # força rotação
    engine._fits_rotate_if_needed(1_000_000 + (cfg.filetime + 1) * 1_000_000)
    assert engine._fits_current_path != first


def test_overview_empty_is_noop(tmp_path) -> None:
    engine, _, _ = _make_engine(tmp_path)
    engine.save_overview_hdf5([], 123)
    # sem pontos não deve criar path
    assert engine._ovs_hdf5_current_path is None


def test_fits_hdf5_init_failure_logs(monkeypatch, tmp_path) -> None:
    engine, _, logs = _make_engine(tmp_path)

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("astropy") or name == "h5py":
            raise ImportError("forced")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert engine.fits_init() is False
    assert engine.hdf5_init() is False
    assert any("FITS dependency missing" in msg for _, msg in logs)
    assert any("HDF5 dependency missing" in msg for _, msg in logs)
