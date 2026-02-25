"""callisto/control.py

Compatibility facade for the legacy control module.

The actual command-processing logic lives in
``callisto.application.control`` (hexagonal "application" layer). This
module re-exports the public API to avoid breaking existing imports and
tests.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

from typing import Callable, Optional

from .application import control as _app_control


def process_client_command(
    line: str,
    on_start: Callable[[], None],
    on_stop: Callable[[], None],
    on_overview_once: Callable[[], None],
    on_overview_continuous: Callable[[], bool],
    on_overview_off: Callable[[], None],
) -> Optional[str]:
    """Delegate to :func:`callisto.application.control.process_client_command`."""

    return _app_control.process_client_command(
        line,
        on_start,
        on_stop,
        on_overview_once,
        on_overview_continuous,
        on_overview_off,
    )


__all__ = ["process_client_command"]
