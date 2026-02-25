"""callisto/ports/__init__.py

Hexagonal architecture ports (abstract interfaces).

This module defines the core contracts used by the application layer to
interact with infrastructure concerns such as the serial backend and
data writers. Adapters in :mod:`callisto.adapters` provide concrete
implementations of these ports.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..domain import OVSItem


@runtime_checkable
class SerialBackendPort(Protocol):
    """Abstract serial backend used by the runtime.

    Concrete implementation: :class:`callisto.adapters.serial_backend.AsyncSerialBackend`.
    """

    def start(
        self, port: str, baudrate: int = 115200
    ) -> bool:  # pragma: no cover - structural
        """Open the serial connection.

        Returns ``True`` on success, ``False`` otherwise.
        """

    def stop(self) -> None:  # pragma: no cover - structural
        """Close the serial connection and stop any worker threads/loops."""

    def read_char(
        self, timeout: float = 1.0
    ) -> str | None:  # pragma: no cover - structural
        """Return a single character from the input stream or ``None`` on timeout."""

    def write(self, payload: str) -> None:  # pragma: no cover - structural
        """Write an ASCII payload to the serial line."""


@runtime_checkable
class DataWriterPort(Protocol):
    """Abstract interface for persisting data buffers and overviews.

    Concrete implementation: :class:`callisto.adapters.writers.DataWriterEngine`.
    """

    def fits_init(self) -> bool:  # pragma: no cover - structural
        """Initialise the FITS backend, returning ``True`` on success."""

    def hdf5_init(self) -> bool:  # pragma: no cover - structural
        """Initialise the HDF5 backend, returning ``True`` on success."""

    def write_data_buffer(
        self, buf_bytes: bytes, ts_us: int
    ) -> None:  # pragma: no cover - structural
        """Persist a raw data buffer acquired at ``ts_us`` microseconds since epoch."""

    def save_overview_hdf5(
        self, points: Sequence[OVSItem], ts_epoch: int
    ) -> None:  # pragma: no cover - structural
        """Append a spectral overview snapshot at given epoch seconds."""


__all__ = [
    "SerialBackendPort",
    "DataWriterPort",
]
