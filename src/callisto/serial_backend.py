"""callisto/serial_backend.py

Compatibility facade for the async serial backend.

The concrete implementation now lives in
``callisto.infrastructure.serial_backend``. This module re-exports the public
API so that ``from callisto.serial_backend import AsyncSerialBackend``
continues to work.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

from .infrastructure.serial_backend import AsyncSerialBackend, _AsyncSerialProtocol

__all__ = ["AsyncSerialBackend", "_AsyncSerialProtocol"]
