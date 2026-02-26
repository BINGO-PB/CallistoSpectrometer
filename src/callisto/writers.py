"""callisto/writers.py

Compatibility facade for data writers.

The concrete implementation now lives in
``callisto.infrastructure.writers.DataWriterEngine`` (hexagonal infrastructure
layer). This module re-exports the class for existing imports and
tests.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

from .infrastructure.writers import DataWriterEngine

__all__ = ["DataWriterEngine"]
