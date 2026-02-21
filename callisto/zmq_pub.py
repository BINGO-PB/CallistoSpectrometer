"""callisto/zmq_pub.py
Publisher ZeroMQ (PUB) para streaming de frames de espectro.

Formato (multipart):
- [0] topic (bytes)
- [1] meta JSON utf-8 (bytes)
- [2] matrix (bytes)  -> numpy array flatten row-major
- [3] freqs_mhz (bytes) -> float64
- [4] timestamps_us (bytes) -> int64
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
        except Exception:
            self.stop()
            return False

    def stop(self) -> None:
        try:
            if self._sock is not None:
                self._sock.close(linger=0)
        except Exception:
            pass
        self._sock = None

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

        meta_bytes = json.dumps(meta, separators=(",", ":"), sort_keys=True).encode("utf-8")
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

