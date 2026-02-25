"""callisto/examples/zmq_viewer.py

Simple GUI client to visualise spectra published via the Callisto
ZeroMQ PUB interface.

The program subscribes to the multipart frames described in
``callisto/adapters/zmq_pub.py`` and displays the latest matrix as
an updating waterfall plot.

Copyright BINGO Collaboration
Last modified: 2026-02-25
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
from typing import Any

import numpy as np


class ZmqSubscriber(threading.Thread):
    """Background thread that receives frames from a ZMQ PUB socket.

    The layout is expected to match :class:`ZmqPublisher` in
    ``callisto.adapters.zmq_pub``:

    - [0] topic (bytes)
    - [1] JSON metadata (UTF-8)
    - [2] matrix bytes (row-major)
    - [3] freqs_mhz bytes (float64)
    - [4] timestamps_us bytes (int64)
    """

    daemon = True

    def __init__(self, endpoint: str, topic: str, out_queue: queue.Queue) -> None:
        super().__init__(name="ZmqSubscriber")
        self._endpoint = endpoint
        self._topic = topic.encode("ascii", errors="ignore")
        self._queue = out_queue
        self._stop_evt = threading.Event()

    def stop(self) -> None:
        self._stop_evt.set()

    def run(self) -> None:  # pragma: no cover - GUI helper
        try:
            import zmq  # type: ignore
        except Exception as exc:  # pragma: no cover - env specific
            sys.stderr.write(f"pyzmq not available: {exc}\n")
            return

        ctx = zmq.Context.instance()
        sock = ctx.socket(zmq.SUB)
        try:
            sock.connect(self._endpoint)
            sock.setsockopt(zmq.SUBSCRIBE, self._topic)

            while not self._stop_evt.is_set():
                try:
                    parts = sock.recv_multipart(flags=zmq.NOBLOCK)
                except zmq.Again:
                    sock.poll(50)
                    continue
                if len(parts) < 5:
                    continue
                _topic, meta_b, m_b, f_b, t_b = parts[:5]
                try:
                    meta: dict[str, Any] = json.loads(meta_b.decode("utf-8"))
                    shape = tuple(int(x) for x in meta.get("matrix_shape", ()))
                    if not shape:
                        continue
                    matrix = np.frombuffer(m_b, dtype=np.uint8).reshape(shape)
                    freqs = np.frombuffer(f_b, dtype=np.float64)
                    ts_us = np.frombuffer(t_b, dtype=np.int64)
                except Exception:
                    continue

                # Drop old frames if the queue is full; keep UI responsive.
                try:
                    if self._queue.qsize() > 2:
                        _ = self._queue.get_nowait()
                except queue.Empty:
                    pass
                self._queue.put((matrix, freqs, ts_us, meta))
        finally:
            try:
                sock.close(linger=0)
            except Exception:
                pass


def _run_qt(endpoint: str, topic: str) -> int:  # pragma: no cover - GUI helper
    try:
        import pyqtgraph as pg  # type: ignore
        from PyQt5 import QtCore, QtWidgets  # type: ignore
    except Exception as exc:
        sys.stderr.write(
            "PyQt5/pyqtgraph not available. Install with 'pip install PyQt5 pyqtgraph'.\n"
        )
        sys.stderr.write(f"Import error: {exc}\n")
        return 1

    app = QtWidgets.QApplication(sys.argv or ["callisto-zmq-viewer"])

    q: queue.Queue = queue.Queue(maxsize=8)
    sub = ZmqSubscriber(endpoint=endpoint, topic=topic, out_queue=q)
    sub.start()

    win = QtWidgets.QMainWindow()
    win.setWindowTitle(f"Callisto ZMQ viewer - {endpoint} ({topic})")

    cw = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(cw)

    pg.setConfigOptions(antialias=True)
    img_view = pg.ImageView(view=pg.PlotItem())
    img_view.ui.roiBtn.hide()
    img_view.ui.menuBtn.hide()
    layout.addWidget(img_view)

    status = QtWidgets.QLabel("Waiting for frames...")
    layout.addWidget(status)

    win.setCentralWidget(cw)
    win.resize(800, 600)
    win.show()

    def update_from_queue() -> None:
        try:
            matrix, freqs, ts_us, meta = q.get_nowait()
        except queue.Empty:
            return
        img_view.setImage(matrix.T, autoLevels=True)
        img_view.getView().setLabel("bottom", "Sweep index")
        img_view.getView().setLabel("left", "Channel")
        status.setText(
            f"t0={ts_us[0] if ts_us.size else 0} us, "
            f"shape={matrix.shape}, samplerate={meta.get('samplerate', '?')} Hz"
        )

    timer = QtCore.QTimer()
    timer.timeout.connect(update_from_queue)
    timer.start(100)

    def on_close() -> None:
        sub.stop()

    app.aboutToQuit.connect(on_close)
    return app.exec_()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Callisto ZMQ spectrum viewer")
    parser.add_argument(
        "--endpoint",
        default="tcp://127.0.0.1:5556",
        help="ZMQ SUB endpoint to connect to (default: tcp://127.0.0.1:5556)",
    )
    parser.add_argument(
        "--topic",
        default="callisto",
        help="Topic prefix to subscribe to (default: callisto)",
    )
    args = parser.parse_args(argv)

    return _run_qt(endpoint=args.endpoint, topic=args.topic)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    raise SystemExit(main())
