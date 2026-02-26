"""Utilitários de tempo com UTC timezone-aware."""

import datetime
import time


def get_usecs() -> int:
    return int(time.time() * 1_000_000)


def utc_iso_from_us(ts_us: int) -> str:
    dt = datetime.datetime.fromtimestamp(ts_us / 1_000_000, tz=datetime.timezone.utc)
    return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")
