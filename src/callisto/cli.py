"""Command-line interface for the Callisto daemon.

This thin wrapper is responsible for parsing CLI options (such as the
``--config`` path) and then delegating to :mod:`callisto.runtime`.

Configuration files are expected to follow the format documented in
``docs/configurations.md``. By default, ``callisto`` will look for a
``callisto.cfg`` file in the current working directory, but a different
file can be selected via ``--config``.

Both ``callisto`` and ``ecallisto`` entry points are wired to this
module, preserving the legacy name while using the new configuration
loader.
"""

from __future__ import annotations

import argparse
import os
from typing import Sequence

from .application.config_loader import load_config, load_schedule_file
from .runtime import main as _main


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="callisto", description="Callisto spectrometer daemon"
    )
    parser.add_argument(
        "-c",
        "--config",
        metavar="PATH",
        default="callisto.cfg",
        help="Path to callisto.cfg configuration file (default: ./callisto.cfg)",
    )
    parser.add_argument(
        "-s",
        "--schedule",
        metavar="PATH",
        default=None,
        help="Optional path to scheduler.cfg file (default: next to config)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by the ``callisto`` and ``ecallisto`` scripts."""

    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    config_path = os.path.abspath(args.config)

    # Parse configuration and schedule mainly for validation and future
    # hexagonal runtime wiring. For now, the legacy daemon still owns the
    # main loop, which reads its own config files from the CWD.
    _cfg = load_config(config_path)

    schedule_path: str | None = args.schedule
    if schedule_path is None:
        schedule_path = os.path.join(os.path.dirname(config_path), "scheduler.cfg")
    _schedule_entries = load_schedule_file(schedule_path)

    # Ensure the legacy runtime sees the chosen config directory as CWD,
    # preserving behaviour of the original e-Callisto daemon.
    cfg_dir = os.path.dirname(config_path) or os.getcwd()
    old_cwd = os.getcwd()
    try:
        os.chdir(cfg_dir)
        result = _main()
    finally:
        os.chdir(old_cwd)

    return int(result) if result is not None else 0
