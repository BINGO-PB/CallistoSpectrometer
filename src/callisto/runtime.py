"""Runtime facade for the Callisto daemon.

At runtime, the package will try to use the legacy C implementation
provided by the Debian ``ecallisto`` module when it is available. If
that module cannot be imported, a pure-Python daemon is started
instead, using the hexagonal components from :mod:`callisto`.

This keeps development and testing self-contained while still allowing
production deployments to rely on the battle-tested C implementation
until the Python runtime reaches feature parity.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from typing import Callable

from .infrastructure.serial_backend import AsyncSerialBackend
from .infrastructure.writers import DataWriterEngine
from .application import control as app_control
from .application.config_loader import load_config, load_schedule_file
from .application.frequencies import load_frequencies
from .constants import (
    DATA_END,
    DATA_START,
    EEPROM_READY,
    ID_QUERY,
    ID_RESPONSE,
    MESSAGE_END,
    MESSAGE_START,
    OVERVIEW,
    RESET_STRING,
    RUNNING,
    SCHEDULE_CHECK_INTERVAL,
    STOPPED,
)
from .domain import Config, ScheduleEntry
from .logging_utils import logprintf, setup_file_logging
from .time_utils import get_usecs, utc_iso_from_us


class _PythonDaemon:
    """Minimal pure-Python Callisto daemon.

    This implementation focuses on wiring configuration, scheduler and
    the TCP control protocol together. Interaction with real hardware
    (serial commands and data acquisition) is intentionally kept very
    small for now and can be extended incrementally.
    """

    def __init__(self, cfg: Config, schedule: list[ScheduleEntry]):
        self._cfg = cfg
        self._schedule = list(schedule)
        self._state = STOPPED
        self._stop_event = threading.Event()
        self._channel_frequencies_cache: list[float] | None = None

        # Preload channel frequencies so that ``nchannels`` in the
        # configuration matches the actual table where possible. This
        # keeps FITS/HDF5 metadata consistent with the spectra.
        freqs = self._get_channel_frequencies()
        if freqs and self._cfg.nchannels != len(freqs):
            self._cfg = self._cfg.model_copy(update={"nchannels": len(freqs)})

        self._serial = AsyncSerialBackend(logprintf)
        self._writer = DataWriterEngine(
            config=self._cfg,
            get_channel_frequencies=self._get_channel_frequencies,
            utc_iso_from_us=utc_iso_from_us,
            logger=logprintf,
        )

        # acquisition state
        self._acq_thread: threading.Thread | None = None
        self._acq_stop = threading.Event()

        # timers derived from legacy configuration (milliseconds)
        try:
            self._timer_preread_s = max(
                0.0, float(getattr(self._cfg, "timerpreread", 0)) / 1000.0
            )
        except Exception:  # pragma: no cover - defensive
            self._timer_preread_s = 0.0
        try:
            self._timeout_hexdata_s = max(
                0.0, float(getattr(self._cfg, "timeouthexdata", 0)) / 1000.0
            )
        except Exception:  # pragma: no cover - defensive
            self._timeout_hexdata_s = 0.0

    # --- frequency helpers -------------------------------------------------

    def _get_channel_frequencies(self) -> list[float]:
        if self._channel_frequencies_cache is not None:
            return self._channel_frequencies_cache

        frqfile = (self._cfg.frqfile or "").strip()
        if not frqfile:
            self._channel_frequencies_cache = []
            return self._channel_frequencies_cache

        base_dir = os.getcwd()
        path = frqfile
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)

        freqs = load_frequencies(path)
        self._channel_frequencies_cache = freqs
        if freqs:
            logprintf(2, "Loaded %d channel frequencies from %s", len(freqs), path)
        else:
            logprintf(1, "No channel frequencies loaded from %s", path)
        return freqs

    # --- serial helpers ---------------------------------------------------

    def _open_serial(self) -> bool:
        port = self._cfg.rxcomport or self._cfg.serialport
        baud = int(getattr(self._cfg, "rxbaudrate", 115200))
        if not port:
            logprintf(0, "No serial port configured (rxcomport/serialport)")
            return False
        ok = self._serial.start(port, baudrate=baud)
        if not ok:
            logprintf(0, "Failed to open serial port %s at %d baud", port, baud)
        else:
            logprintf(2, "Serial port opened on %s at %d baud", port, baud)
        return ok

    def _close_serial(self) -> None:
        """Close the serial backend, tolerating spurious errors."""

        self._serial.stop()

    def _serial_handshake(self, timeout: float = 3.0) -> bool:
        """Send a minimal reset/identify sequence to the hardware.

        Returns ``True`` when an :data:`ID_RESPONSE` trailer is
        observed within *timeout* seconds. On failure, a warning is
        logged and ``False`` is returned so callers can decide whether
        to abort acquisition instead of looping forever on a dead
        device.
        """

        try:
            self._serial.write(RESET_STRING)

            deadline = time.time() + max(0.5, float(timeout))
            seen: list[str] = []
            got_response = False
            while time.time() < deadline:
                ch = self._serial.read_char(timeout=0.2)
                if ch is None:
                    continue
                seen.append(ch)
                joined = "".join(seen)
                if ID_RESPONSE and joined.endswith(ID_RESPONSE):
                    logprintf(2, "Serial ID response detected during handshake", None)
                    got_response = True
                    break

            if not got_response:
                logprintf(1, "No serial ID response detected during handshake", None)

            # Final ID query as done by the legacy daemon.
            if ID_QUERY:
                self._serial.write(ID_QUERY)

            return got_response
        except Exception as exc:  # pragma: no cover - defensive
            logprintf(1, "Serial handshake failed: %s", exc)
            return False

    @staticmethod
    def _extract_frames(text: str) -> list[str]:
        """Extract payloads delimited by MESSAGE_START/END from *text*.

        This helper is intentionally pure to allow unit testing of the
        framing rules independently from the serial backend.
        """

        frames: list[str] = []
        buf: list[str] = []
        inside = False
        for ch in text:
            if ch == MESSAGE_START:
                buf.clear()
                inside = True
                continue
            if ch == MESSAGE_END and inside:
                frames.append("".join(buf))
                buf.clear()
                inside = False
                continue
            if inside:
                buf.append(ch)
        return frames

    def _acquisition_loop(self) -> None:
        """Acquisition loop that mirrors the legacy C daemon.

        The Callisto firmware multiplexes two streams over the same
        serial link:

        * *messages* delimited by :data:`MESSAGE_START` / ``MESSAGE_END``
          (e.g. ``CRX:Started``), and
        * *hex-encoded data* delimited by :data:`DATA_START` /
          :data:`DATA_END`, carrying 8/10-bit samples as four ASCII
          hex digits per value.

        This loop follows the same high-level state machine as the C
        implementation, but delegates actual persistence to
        :class:`DataWriterEngine` instead of hand-written FITS I/O.
        """

        in_message = False
        in_data = False
        message: list[str] = []
        hex_chars: list[str] = []
        data_start_ts_us: int | None = None

        def _flush_data() -> None:
            nonlocal hex_chars, data_start_ts_us
            if not hex_chars:
                data_start_ts_us = None
                return

            # Decode four-hex-digit values into 8-bit samples. The
            # legacy daemon supports both 8-bit and 10-bit firmware;
            # here we always reduce values to 8 bits, matching the
            # original behaviour for 10-bit data (value >> 2).
            text = "".join(hex_chars)
            buf = bytearray()
            # only complete groups of 4 hex chars
            end = (len(text) // 4) * 4
            for i in range(0, end, 4):
                group = text[i : i + 4]
                try:
                    value = int(group, 16)
                except ValueError:
                    logprintf(1, "Invalid hex group %r in data stream", group)
                    continue
                # 0x2323 is used as an internal end marker by the
                # firmware; ignore it here and rely on DATA_END for
                # framing.
                if value == 0x2323:
                    continue
                buf.append((value >> 2) & 0xFF)

            if not buf:
                data_start_ts_us = None
                return

            ts_us = data_start_ts_us or get_usecs()
            try:
                self._writer.write_data_buffer(bytes(buf), ts_us)
            except Exception as exc:  # pragma: no cover - defensive
                logprintf(1, "Failed to persist data buffer: %s", exc)

            logprintf(3, "Received data buffer len=%d at %d", len(buf), ts_us)
            hex_chars = []
            data_start_ts_us = None

        while not self._acq_stop.is_set() and not self._stop_event.is_set():
            ch = self._serial.read_char(timeout=0.5)
            if ch is None:
                continue

            # Message framing (status lines from firmware)
            if in_message and ch == MESSAGE_END:
                msg = "".join(message)
                in_message = False
                message.clear()
                # For now we simply log messages; higher-level state
                # handling (e.g. CRX:Started/Stopped) can be wired in
                # later if needed.
                logprintf(3, "Firmware message: %s", msg)
                continue

            if not in_message and ch == MESSAGE_START:
                in_message = True
                message.clear()
                continue

            if in_message:
                if (
                    len(message) < MAX_MESSAGE
                ):  # LB:COMMENT::Definir MAX_MESSAGE como um valor razoável para evitar consumo excessivo de memória em caso de mensagens malformadas ou ataques.
                    message.append(ch)
                continue

            # Ignore EEPROM-ready notifications
            if ch == EEPROM_READY:
                continue

            # Data framing (ASCII hex stream)
            if not in_data and ch == DATA_START:
                in_data = True
                hex_chars = []
                data_start_ts_us = get_usecs()
                continue

            if in_data and ch == DATA_END:
                _flush_data()
                in_data = False
                continue

            if in_data:
                # Accept only hex characters; anything else is
                # treated as a protocol error and ignored for now.
                if ch.strip():
                    hex_chars.append(ch)
                continue

            # Anything that reaches here is outside known framing.
            logprintf(1, "Unexpected character %r outside message/data", ch)

    # --- high-level actions used by the control protocol -----------------

    def start_recording(self) -> None:
        if self._state == RUNNING:
            return
        logprintf(2, "Starting recording (Python daemon)")
        if not self._open_serial():
            return
        if not self._serial_handshake():
            # Do not keep running in a "zombie" acquisition state when
            # the receiver does not respond at all. We log a clear
            # error, close the port and keep the daemon in STOPPED
            # state so that schedulers or operators can retry later.
            logprintf(0, "Aborting start: receiver did not respond to handshake", None)
            self._close_serial()
            return
        self._acq_stop.clear()
        self._acq_thread = threading.Thread(
            target=self._acquisition_loop,
            name="callisto-acquisition",
            daemon=True,
        )
        self._acq_thread.start()
        self._state = RUNNING

    def stop_recording(self) -> None:
        if self._state == STOPPED:
            return
        logprintf(2, "Stopping recording (Python daemon)")
        # Honour legacy timerpreread by waiting a short, configurable
        # period before actually signalling the acquisition thread to
        # stop. This mirrors the idea of letting pending reads
        # complete before shutdown or mode changes.
        if getattr(self, "_timer_preread_s", 0.0) > 0.0:
            try:
                time.sleep(self._timer_preread_s)
            except Exception:  # pragma: no cover - defensive
                pass
        self._acq_stop.set()
        if self._acq_thread is not None:
            self._acq_thread.join(timeout=2.0)
            self._acq_thread = None
        # After signalling stop and waiting for the acquisition loop
        # to finish, give the serial path a chance to drain remaining
        # data according to timeouthexdata before closing the
        # transport.
        if getattr(self, "_timeout_hexdata_s", 0.0) > 0.0:
            try:
                time.sleep(self._timeout_hexdata_s)
            except Exception:  # pragma: no cover - defensive
                pass
        self._close_serial()
        self._state = STOPPED

    def overview_once(self) -> None:
        logprintf(2, "Starting one-shot spectral overview (Python daemon)")
        # Future work: command the hardware to perform an overview and
        # persist the result via DataWriterEngine.save_overview_hdf5.
        self._state = OVERVIEW

    def overview_continuous(self) -> bool:
        # For now we simply report that HDF5 backend is available if it
        # can be initialised; acquisition itself is not implemented yet.
        ok = self._writer.hdf5_init()
        if ok:
            logprintf(2, "Continuous overview requested (Python daemon)")
        return ok

    def overview_off(self) -> None:
        logprintf(2, "Stopping continuous overview (Python daemon)")
        # No-op for now; state machine can be extended later.
        self._state = RUNNING if self._state != STOPPED else STOPPED

    # --- scheduler --------------------------------------------------------

    def _apply_schedule_action(self, entry: ScheduleEntry) -> None:
        if entry.action == 3:
            self.start_recording()
        elif entry.action == 0:
            self.stop_recording()
        elif entry.action == 8:
            self.overview_once()

    def _scheduler_loop(self) -> None:
        applied: set[int] = set()
        while not self._stop_event.is_set():
            now = time.gmtime()
            t_sec = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
            for idx, entry in enumerate(self._schedule):
                if idx in applied:
                    continue
                if t_sec >= entry.t:
                    logprintf(
                        2,
                        "Applying schedule entry t=%d action=%d",
                        entry.t,
                        entry.action,
                    )
                    self._apply_schedule_action(entry)
                    applied.add(idx)
            self._stop_event.wait(timeout=SCHEDULE_CHECK_INTERVAL)

    # --- TCP control server ----------------------------------------------

    def _handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        logprintf(2, "Client connected from %s:%d", addr[0], addr[1])
        with conn:
            # Banner similar to legacy daemon
            conn.sendall(b"e-Callisto for Python\n")
            f = conn.makefile("rwb", buffering=0)
            try:
                while not self._stop_event.is_set():
                    line = f.readline()
                    if not line:
                        break
                    try:
                        text = line.decode("ascii", errors="ignore")
                    except Exception:
                        continue
                    resp = app_control.process_client_command(
                        text,
                        self.start_recording,
                        self.stop_recording,
                        self.overview_once,
                        self.overview_continuous,
                        self.overview_off,
                    )
                    if resp is None:
                        break
                    f.write(resp.encode("ascii", errors="ignore"))
            finally:
                try:
                    f.flush()
                except Exception:  # pragma: no cover - best effort
                    pass
        logprintf(2, "Client disconnected from %s:%d", addr[0], addr[1])

    def _server_loop(self) -> None:
        if self._cfg.net_port <= 0:
            logprintf(2, "net_port not configured; TCP control server disabled")
            return
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", int(self._cfg.net_port)))
        srv.listen(5)
        logprintf(
            2, "Python Callisto TCP control server listening on %d", self._cfg.net_port
        )
        with srv:
            while not self._stop_event.is_set():
                try:
                    srv.settimeout(1.0)
                    conn, addr = srv.accept()
                except OSError:
                    continue
                threading.Thread(
                    target=self._handle_client, args=(conn, addr), daemon=True
                ).start()

    # --- public API -------------------------------------------------------

    def serve_forever(self) -> int:
        """Run scheduler and TCP server loops until stopped.

        This call blocks and is intended to be the main entry point for
        the pure-Python daemon mode.
        """

        logprintf(2, "Starting Python Callisto daemon: net_port=%d", self._cfg.net_port)
        sched_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        sched_thread.start()

        try:
            self._server_loop()
        finally:
            self._stop_event.set()
            sched_thread.join(timeout=2.0)
        return 0


def _python_daemon_main() -> int:
    """Entry point for the pure-Python daemon.

    The current working directory is expected to be the configuration
    directory, as ensured by :mod:`callisto.cli`.
    """

    cfg_path = os.path.abspath("callisto.cfg")
    cfg = load_config(cfg_path)

    sched_path = os.path.join(os.path.dirname(cfg_path), cfg.schedulefile)
    schedule = load_schedule_file(sched_path)

    # Ensure FITS/HDF5 backends can be initialised on demand.
    cfg = cfg.model_copy(
        update={
            "datadir": cfg.datadir or os.getcwd(),
            "ovsdir": cfg.ovsdir or cfg.datadir or os.getcwd(),
        }
    )

    # Set up file logging in addition to stderr so that daemon activity
    # is persisted even when run under a service manager.
    try:
        logfile = setup_file_logging(cfg.logdir)
        logprintf(2, "File logging initialised at %s", logfile)
    except Exception as exc:  # pragma: no cover - depends on FS/permissions
        logprintf(1, "File logging disabled: %s", exc)

    daemon = _PythonDaemon(cfg, schedule)
    return daemon.serve_forever()


def _import_legacy_main() -> Callable[[], int | None]:
    """Best-effort import of the legacy ``ecallisto.main`` function.

    If the external module is unavailable, the pure-Python daemon is
    used instead. This allows development and tests to run without the
    Debian package installed.
    LB:COMMENT::REMOVE
    """

    try:  # pragma: no cover - depends on system packages
        from ecallisto import main as _legacy_main  # type: ignore[import]

        return _legacy_main
    except Exception:  # pragma: no cover - fallback to Python daemon
        return _python_daemon_main


_LEGACY_MAIN: Callable[[], int | None] = _import_legacy_main()


def main() -> int:
    """Execute the daemon and return a POSIX exit code."""

    result = _LEGACY_MAIN()
    return int(result) if result is not None else 0
