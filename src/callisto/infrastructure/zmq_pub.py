"""callisto/infrastructure/zmq_pub.py

ZeroMQ (PUB) publisher for streaming spectrum frames.

Multipart frame layout
----------------------
- [0] topic (bytes)
- [1] JSON metadata (UTF-8)
- [2] matrix bytes (numpy row-major)
- [3] freqs_mhz bytes (float64)
- [4] timestamps_us bytes (int64)

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

import json
from typing import Any, Optional


class ZmqPublisher:
    def __init__(
        self,
        *,
        endpoint: str,
        bind: bool = True,
        topic: str = "callisto",
        hwm: int = 10,
    ) -> None:
        if not endpoint:
            raise ValueError("endpoint is required")
        self._endpoint = endpoint
        self._bind = bool(bind)
        self._topic = (topic or "callisto").encode("ascii", errors="ignore")
        self._hwm = int(hwm)

        self._zmq = None
        self._ctx = None
        self._sock = None

    def start(self) -> bool:
        if self._sock is not None:
            return True
        try:
            import zmq  # type: ignore

            self._zmq = zmq
            self._ctx = zmq.Context.instance()
            sock = self._ctx.socket(zmq.PUB)
            sock.setsockopt(zmq.SNDHWM, self._hwm)
            if self._bind:
                sock.bind(self._endpoint)
            else:
                sock.connect(self._endpoint)
            self._sock = sock
            return True
        except Exception:  # pragma: no cover - depends on env
            self.stop()
            return False

    def stop(self) -> None:
        try:
            if self._sock is not None:
                self._sock.close(linger=0)
        except Exception:  # pragma: no cover - defensive
            pass
        self._sock = None

    # LB:COMMENT::Ainda vamos discutir o formato exato do frame, e implementar em jsonschema ou algo assim, mas a ideia geral é que seja algo como:
    # {
    def publish_frame(
        self,
        *,
        instrument: str,
        ts_us: int,
        samplerate: int,
        nchannels: int,
        matrix,  # numpy ndarray
        freqs_mhz,  # numpy ndarray
        timestamps_us,  # numpy ndarray
        extra_meta: Optional[dict[str, Any]] = None,
    ) -> None:
        if self._sock is None:
            return
        meta: dict[str, Any] = {
            "schema": "callisto-zmq-1",
            "instrument": str(instrument),
            "ts_us": int(ts_us),
            "samplerate": int(samplerate),
            "nchannels": int(nchannels),
            "matrix_dtype": str(getattr(matrix, "dtype", "u1")),
            "matrix_shape": list(getattr(matrix, "shape", ())),
            "freq_dtype": str(getattr(freqs_mhz, "dtype", "f8")),
            "freq_shape": list(getattr(freqs_mhz, "shape", ())),
            "timestamps_dtype": str(getattr(timestamps_us, "dtype", "i8")),
            "timestamps_shape": list(getattr(timestamps_us, "shape", ())),
        }
        if extra_meta:
            meta.update(extra_meta)

        meta_bytes = json.dumps(meta, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        self._sock.send_multipart(
            [
                self._topic,
                meta_bytes,
                matrix.tobytes(order="C"),
                freqs_mhz.tobytes(order="C"),
                timestamps_us.tobytes(order="C"),
            ],
            copy=False,
        )


__all__ = ["ZmqPublisher"]
