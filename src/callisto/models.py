"""callisto/models.py

Backward-compatible re-export of domain models.

The canonical domain definitions live in :mod:`callisto.domain.models`
and are implemented with Pydantic, following the BINGO collaboration
guidelines. This module keeps the public API stable for existing code
(``from callisto.models import Config``, etc.).

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

from .domain import Buffer, Config, Firmware, OVSItem, ScheduleEntry

__all__ = [
    "Buffer",
    "OVSItem",
    "Firmware",
    "Config",
    "ScheduleEntry",
]
