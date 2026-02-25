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

from .adapters.serial_backend import AsyncSerialBackend
from .adapters.writers import DataWriterEngine
from .application import control as app_control
from .application.config_loader import load_config, load_schedule_file
from .application.frequencies import load_frequencies
from .constants import (
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
from .logging_utils import logprintf
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
        self._serial.stop()

    def _serial_handshake(self) -> None:
        """Send a minimal reset/identify sequence to the hardware.

        This follows the high-level behaviour of the legacy daemon
        without assuming details of the response contents.
        """

        try:
            # Reset receiver and try to observe a basic ID response. The
            # call is deliberately best-effort: a missing or unexpected
            # response is logged but does not abort acquisition.
            self._serial.write(RESET_STRING)

            deadline = time.time() + 3.0
            seen: list[str] = []
            while time.time() < deadline:
                ch = self._serial.read_char(timeout=0.2)
                if ch is None:
                    continue
                seen.append(ch)
                joined = "".join(seen)
                if ID_RESPONSE and joined.endswith(ID_RESPONSE):
                    logprintf(2, "Serial ID response detected during handshake", None)
                    break

            # Final ID query as done by the legacy daemon.
            if ID_QUERY:
                self._serial.write(ID_QUERY)
        except Exception as exc:  # pragma: no cover - defensive
            logprintf(1, "Serial handshake failed: %s", exc)

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
        """Very small frame collector from the serial port.

        The exact on-wire protocol is handled by the legacy firmware;
        here we only group payloads between ``MESSAGE_START`` and
        ``MESSAGE_END``. Decoding of the frames into spectra and
        calling :class:`DataWriterEngine` can be implemented in a
        follow-up step without changing the public API.
        """

        buffer: list[str] = []
        inside = False
        while not self._acq_stop.is_set() and not self._stop_event.is_set():
            ch = self._serial.read_char(timeout=0.5)
            if ch is None:
                continue
            if ch == MESSAGE_START:
                buffer.clear()
                inside = True
                continue
            if ch == MESSAGE_END and inside:
                payload = "".join(buffer)
                inside = False
                ts_us = get_usecs()
                try:
                    buf_bytes = payload.encode("latin1", errors="ignore")
                    if buf_bytes:
                        self._writer.write_data_buffer(buf_bytes, ts_us)
                except Exception as exc:  # pragma: no cover - defensive
                    logprintf(1, "Failed to persist data frame: %s", exc)
                logprintf(3, "Received frame len=%d at %d", len(payload), ts_us)
                continue
            if inside:
                buffer.append(ch)

    # --- high-level actions used by the control protocol -----------------

    def start_recording(self) -> None:
        if self._state == RUNNING:
            return
        logprintf(2, "Starting recording (Python daemon)")
        if not self._open_serial():
            return
        self._serial_handshake()
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
        self._acq_stop.set()
        if self._acq_thread is not None:
            self._acq_thread.join(timeout=2.0)
            self._acq_thread = None
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

    daemon = _PythonDaemon(cfg, schedule)
    return daemon.serve_forever()


def _import_legacy_main() -> Callable[[], int | None]:
    """Best-effort import of the legacy ``ecallisto.main`` function.

    If the external module is unavailable, the pure-Python daemon is
    used instead. This allows development and tests to run without the
    Debian package installed.
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
