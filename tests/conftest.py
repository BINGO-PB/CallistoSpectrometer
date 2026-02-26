"""Shared pytest fixtures for the Callisto test suite.

Copyright BINGO Collaboration
Last Modified: 2026-02-24
"""

from __future__ import annotations

import pytest


@pytest.fixture
def minimal_cfg(tmp_path):
    """Write a minimal callisto.cfg to tmp_path with writable local dirs."""
    cfg_path = tmp_path / "callisto.cfg"
    cfg_path.write_text(
        f"[rxcomport]=/dev/ttyUSB0\n"
        f"[datapath]={tmp_path}/data/\n"
        f"[logpath]={tmp_path}/log/\n"
        f"[ovsdir]={tmp_path}/overview/\n",
        encoding="utf-8",
    )
    return cfg_path
