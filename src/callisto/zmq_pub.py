"""callisto/zmq_pub.py

Compatibility facade for the ZeroMQ publisher.

The concrete implementation is located at
``callisto.infrastructure.zmq_pub.ZmqPublisher``.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

from .infrastructure.zmq_pub import ZmqPublisher

__all__ = ["ZmqPublisher"]
