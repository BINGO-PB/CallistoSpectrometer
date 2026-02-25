"""callisto/application/config_loader.py

Configuration and schedule loaders for Callisto.

This module bridges legacy ``callisto.cfg`` / ``scheduler.cfg`` files
into the modern :mod:`callisto.domain.models` Pydantic models, keeping
parsing logic close to the application layer.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

import os
import re
from datetime import time
from typing import Iterable, Mapping

from ..domain import Config, ScheduleEntry
from ..logging_utils import logprintf

_KEY_VALUE_RE = re.compile(r"^\[(?P<key>[^\]]+)\]\s*=\s*(?P<value>.*)$")


def _strip_inline_comment(value: str) -> str:
    for sep in ("//", "#"):
        if sep in value:
            value = value.split(sep, 1)[0]
    return value.strip()


def _coerce_value(field: str, text: str, current: Config) -> object:
    """Try to coerce ``text`` into the type of ``Config.field``.

    Falls back to the raw string when coercion is not possible.
    """

    text = text.strip()
    if text == "":
        return text

    field_info = Config.model_fields.get(field)
    if field_info is None or field_info.annotation is None:
        return text

    target = field_info.annotation

    # bools as 0/1 or true/false
    if target is bool or target is (bool | None):  # type: ignore[comparison-overlap]
        lowered = text.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        return bool(text)

    # simple numeric types
    try:
        if target is int or target is (int | None):  # type: ignore[comparison-overlap]
            return int(float(text))
        if target is float or target is (float | None):  # type: ignore[comparison-overlap]
            return float(text)
    except ValueError:
        return text

    # everything else: keep as string
    return text


def _apply_cfg_pair(cfg: Config, key: str, value: str) -> Config:
    key_norm = key.strip().lower()
    raw = _strip_inline_comment(value)

    alias_map: dict[str, str] = {
        "rxcomport": "rxcomport",
        "rxbaudrate": "rxbaudrate",
        "observatory": "observatory",
        "instrument": "instrument",
        "titlecomment": "titlecomment",
        "origin": "origin",
        "longitude": "longitude",
        "latitude": "latitude",
        "height": "height",
        "clocksource": "clocksource",
        "filetime": "filetime",
        "frqfile": "frqfile",
        "focuscode": "focuscode",
        "mmode": "mmode",
        "timerinterval": "timerinterval",
        "timerpreread": "timerpreread",
        "timeouthexdata": "timeouthexdata",
        "fitsenable": "fitsenable",
        "low_band": "low_band",
        "mid_band": "mid_band",
        "chargepump": "chargepump",
        "agclevel": "agclevel",
        "detector_sens": "detector_sens",
        "autostart": "autostart",
        "outputformat": "output_format",
        "net_port": "net_port",
        "datapath": "datadir",
        "logpath": "logdir",
        # handle typo/variant from docs
        "calport": "calport",
        "calpost": "calport",
        # zmq options
        "zmq_pub_endpoint": "zmq_pub_endpoint",
        "zmq_pub_bind": "zmq_pub_bind",
        "zmq_pub_topic": "zmq_pub_topic",
        "zmq_pub_hwm": "zmq_pub_hwm",
    }

    field = alias_map.get(key_norm)
    if field is None:
        return cfg

    current_dict = cfg.model_dump()
    coerced = _coerce_value(field, raw, cfg if isinstance(cfg, Config) else Config())

    updated = dict(current_dict)
    updated[field] = coerced
    return Config(**updated)


def load_config(
    path: str,
    *,
    base_dir: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    """Load a :class:`Config` from ``callisto.cfg``-style file.

    Parameters
    ----------
    path:
        Path to the configuration file. If it does not exist, defaults
        are returned and only environment overrides are applied.
    base_dir:
        Base directory used to resolve relative paths, defaults to the
        directory of ``path``.
    env:
        Optional environment mapping, defaults to :data:`os.environ`.
    """

    env = dict(env or os.environ)
    cfg = Config()

    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(path)) or os.getcwd()

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("//"):
                    continue
                m = _KEY_VALUE_RE.match(line)
                if not m:
                    continue
                key = m.group("key")
                value = m.group("value")
                cfg = _apply_cfg_pair(cfg, key, value)

    # resolve relative directories against base_dir
    if not os.path.isabs(cfg.datadir):
        cfg = cfg.model_copy(update={"datadir": os.path.join(base_dir, cfg.datadir)})
    if not os.path.isabs(cfg.logdir):
        cfg = cfg.model_copy(update={"logdir": os.path.join(base_dir, cfg.logdir)})
    if not os.path.isabs(cfg.ovsdir):
        cfg = cfg.model_copy(update={"ovsdir": os.path.join(base_dir, cfg.ovsdir)})

    # validate that key directories exist or can be created and are writable
    for key in ("datadir", "logdir", "ovsdir"):
        value = getattr(cfg, key, "") or ""
        if not value:
            continue
        try:
            os.makedirs(value, exist_ok=True)
        except Exception as exc:  # pragma: no cover - depends on FS/permissions
            logprintf(0, "Failed to create %s directory %s: %s", key, value, exc)
            raise
        if not os.access(value, os.W_OK):
            logprintf(0, "Directory %s for %s is not writable", value, key)
            raise PermissionError(f"Directory not writable: {value}")

    # simple environment overrides (minimal but useful)
    overrides: dict[str, object] = {}
    if "CALLISTO_DATADIR" in env:
        overrides["datadir"] = env["CALLISTO_DATADIR"].strip()
    if "CALLISTO_LOGDIR" in env:
        overrides["logdir"] = env["CALLISTO_LOGDIR"].strip()
    if "CALLISTO_OUTPUT_FORMAT" in env:
        overrides["output_format"] = env["CALLISTO_OUTPUT_FORMAT"].strip().lower()
    if "CALLISTO_ZMQ_PUB_ENDPOINT" in env and not cfg.zmq_pub_endpoint:
        overrides["zmq_pub_endpoint"] = env["CALLISTO_ZMQ_PUB_ENDPOINT"].strip()

    if overrides:
        cfg = cfg.model_copy(update=overrides)

    return cfg


def _parse_hms(text: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError("Empty time token in scheduler entry")
    parts = text.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid time format: {text!r}")
    h, m, s = (int(p) for p in parts)
    t = time(hour=h, minute=m, second=s)
    return t.hour * 3600 + t.minute * 60 + t.second


def load_schedule(lines: Iterable[str]) -> list[ScheduleEntry]:
    """Parse an iterable of lines into :class:`ScheduleEntry` objects.

    The expected format matches ``scheduler.cfg`` examples::

        04:00:00,03,3   // start acquisition

    where the columns are ``HH:MM:SS,focuscode,action``.
    """

    entries: list[ScheduleEntry] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        # strip inline comments
        line = _strip_inline_comment(line)
        if not line:
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 3:
            continue
        try:
            t_sec = _parse_hms(parts[0])
            focus = int(parts[1])
            action = int(parts[2])
        except ValueError:
            continue
        entries.append(ScheduleEntry(t=t_sec, action=action, focuscode=focus))
    entries.sort(key=lambda e: e.t)
    return entries


def load_schedule_file(path: str) -> list[ScheduleEntry]:
    """Convenience wrapper to load a schedule from a file path."""

    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return load_schedule(f.readlines())
