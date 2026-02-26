from __future__ import annotations

import queue

from callisto.serial_backend import AsyncSerialBackend, _AsyncSerialProtocol


def test_protocol_data_received_pushes_chars() -> None:
    q: queue.Queue[str] = queue.Queue(maxsize=10)
    lost: list[Exception | None] = []

    proto = _AsyncSerialProtocol(q, lambda exc: lost.append(exc))
    proto.data_received(b"ABC")

    assert q.get_nowait() == "A"
    assert q.get_nowait() == "B"
    assert q.get_nowait() == "C"


def test_protocol_connection_lost_callback() -> None:
    q: queue.Queue[str] = queue.Queue(maxsize=10)
    lost: list[Exception | None] = []

    proto = _AsyncSerialProtocol(q, lambda exc: lost.append(exc))
    err = RuntimeError("boom")
    proto.connection_lost(err)

    assert lost == [err]


def test_backend_read_char_timeout_without_loop() -> None:
    backend = AsyncSerialBackend(lambda *_: None)
    assert backend.read_char(timeout=0.01) is None


def test_backend_read_char_with_queue() -> None:
    backend = AsyncSerialBackend(lambda *_: None)
    backend._loop = object()  # sinaliza backend ativo para read_char
    backend._read_queue.put("Z")
    assert backend.read_char(timeout=0.01) == "Z"


def test_backend_write_no_transport_is_noop() -> None:
    backend = AsyncSerialBackend(lambda *_: None)
    backend.write("abc")


def test_backend_start_failure_returns_false(monkeypatch) -> None:
    logs: list[str] = []

    def logger(_lvl, fmt, *args):
        logs.append(fmt % args if args else fmt)

    backend = AsyncSerialBackend(logger)

    monkeypatch.setattr(
        backend,
        "_load_serial_asyncio",
        lambda: (_ for _ in ()).throw(RuntimeError("x")),
    )

    assert backend.start("/dev/ttyFAKE") is False
    assert any("init_serial(asyncio) failed" in msg for msg in logs)
