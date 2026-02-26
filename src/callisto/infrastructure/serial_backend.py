"""callisto/infrastructure/serial_backend.py

Async serial backend used by the daemon runtime.

This module owns the concrete asyncio/pyserial integration, implementing
an adapter around the serial port.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

import asyncio
import importlib
import os
import queue
import sys
import threading
from typing import Callable


class _AsyncSerialProtocol(asyncio.Protocol):
    """Protocol that pushes received bytes into a thread-safe queue."""

    def __init__(
        self,
        read_queue: queue.Queue[str],
        on_connection_lost: Callable[[Exception | None], None],
    ) -> None:
        self._read_queue = read_queue
        self._on_connection_lost = on_connection_lost
        self.transport: asyncio.Transport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:  # type: ignore[override]
        self.transport = transport  # type: ignore[assignment]

    def data_received(self, data: bytes) -> None:  # type: ignore[override]
        for b in data:
            try:
                self._read_queue.put_nowait(chr(b))
            except queue.Full:  # pragma: no cover - defensive
                break

    def connection_lost(self, exc: Exception | None) -> None:  # type: ignore[override]
        self._on_connection_lost(exc)


class AsyncSerialBackend:
    """Manage a serial connection in a dedicated asyncio loop."""

    def __init__(self, logger: Callable[[int, str, object | None], None]):
        self._logger = logger
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._transport: asyncio.Transport | None = None
        self._protocol: _AsyncSerialProtocol | None = None
        self._read_queue: queue.Queue[str] = queue.Queue(maxsize=65536)
        self._serial_asyncio = None

    def _import_external_module(self, module_name: str):
        """Import external module while avoiding collision with local ``serial.py``."""

        script_dir = os.path.dirname(os.path.abspath(__file__))
        cwd = os.getcwd()
        removed: list[str] = []

        for p in list(sys.path):
            if p in ("", script_dir, cwd):
                removed.append(p)
                sys.path.remove(p)

        try:
            return importlib.import_module(module_name)
        finally:
            for p in reversed(removed):
                if p not in sys.path:
                    sys.path.insert(0, p)

    def _load_serial_asyncio(self):
        if self._serial_asyncio is None:
            self._serial_asyncio = self._import_external_module("serial_asyncio")
        return self._serial_asyncio

    @staticmethod
    def _serial_loop_worker(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def stop(self) -> None:
        try:
            if self._loop is not None and self._transport is not None:
                self._loop.call_soon_threadsafe(self._transport.close)
        except Exception:  # pragma: no cover - defensive
            pass

        try:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:  # pragma: no cover - defensive
            pass

        try:
            if self._thread is not None:
                self._thread.join(timeout=1.5)
        except Exception:  # pragma: no cover - defensive
            pass

        try:
            if self._loop is not None and not self._loop.is_running():
                self._loop.close()
        except Exception:  # pragma: no cover - defensive
            pass

        self._loop = None
        self._thread = None
        self._transport = None
        self._protocol = None

    def start(self, port: str, baudrate: int = 115200) -> bool:
        self.stop()
        self._read_queue = queue.Queue(maxsize=65536)

        try:
            serial_asyncio = self._load_serial_asyncio()
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._serial_loop_worker,
                args=(self._loop,),
                daemon=True,
            )
            self._thread.start()

            def _on_lost(exc: Exception | None) -> None:
                self._transport = None
                if exc:
                    self._logger(1, "Serial connection lost: %s", exc)

            async def _open():
                return await serial_asyncio.create_serial_connection(
                    self._loop,
                    lambda: _AsyncSerialProtocol(self._read_queue, _on_lost),
                    port,
                    baudrate=baudrate,
                )

            fut = asyncio.run_coroutine_threadsafe(_open(), self._loop)
            self._transport, self._protocol = fut.result(timeout=5.0)
            return True
        except Exception as e:  # pragma: no cover - depends on env
            self._logger(0, "init_serial(asyncio) failed for %s: %s", port, e)
            self.stop()
            return False

    def read_char(self, timeout: float = 1.0) -> str | None:
        if self._loop is None:
            return None
        try:
            return self._read_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def write(self, payload: str) -> None:
        if self._loop is None or self._transport is None:
            return
        try:
            data = payload.encode("ascii", errors="ignore")

            def _write() -> None:
                if self._transport is not None:
                    self._transport.write(data)

            assert self._loop is not None
            self._loop.call_soon_threadsafe(_write)
        except Exception as e:  # pragma: no cover - defensive
            self._logger(0, "write_serial failed: %s", e)


__all__ = ["AsyncSerialBackend", "_AsyncSerialProtocol"]
