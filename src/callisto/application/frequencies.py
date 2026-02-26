"""callisto/application/frequencies.py

Frequency table loader for Callisto receivers.

This module parses legacy ``frq*.cfg`` files and exposes a simple
``load_frequencies`` helper that returns the per-channel centre
frequencies in MHz. It keeps file-format concerns close to the
application layer while the domain model remains agnostic.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

import os
import re
from typing import Iterable

_PAIR_RE = re.compile(r"^\[(?P<key>[^\]]+)\]\s*=\s*(?P<value>.*)$")


def _strip_inline_comment(value: str) -> str:
    for sep in ("//", "#"):
        if sep in value:
            value = value.split(sep, 1)[0]
    return value.strip()


def _parse_freq_value(text: str) -> float | None:
    """Parse ``"0045.250,0"``-style tokens into MHz.

    The first comma-separated field is interpreted as MHz and
    converted to ``float``. Returns ``None`` when parsing fails.
    """

    text = _strip_inline_comment(text)
    if not text:
        return None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None
    try:
        return float(parts[0])
    except ValueError:
        return None


def load_frequencies_from_lines(lines: Iterable[str]) -> list[float]:
    """Parse an iterable of lines from a ``frq*.cfg`` file.

    Lines have the general form::

        [0001]=0045.000,0

    Only entries where the key looks numeric (e.g. ``"0001"``) and the
    value parses as a float in MHz are considered. The resulting list
    is ordered by the numeric key.
    """

    items: list[tuple[int, float]] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        m = _PAIR_RE.match(line)
        if not m:
            continue
        key = m.group("key").strip()
        value = m.group("value")
        if not key.isdigit():
            # skip meta-keys like [target] or [number_of_...]
            continue
        freq_mhz = _parse_freq_value(value)
        if freq_mhz is None:
            continue
        try:
            idx = int(key)
        except ValueError:
            continue
        items.append((idx, freq_mhz))

    items.sort(key=lambda kv: kv[0])
    return [freq for _, freq in items]


def load_frequencies(path: str) -> list[float]:
    """Load channel centre frequencies (MHz) from ``frq*.cfg`` file.

    Missing files simply return an empty list, which callers are
    expected to handle by falling back to synthetic indices.
    """

    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return load_frequencies_from_lines(f.readlines())


__all__ = ["load_frequencies", "load_frequencies_from_lines"]
