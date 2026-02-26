# LB:COMMENT::Type annotation com tipos primitivos, seguindo PEP 484
"""callisto/domain/models.py

Pydantic domain models representing core Callisto entities.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Buffer(BaseModel):
    """In-memory acquisition buffer.

    Attributes
    ----------
    data:
        Raw byte buffer as ``bytes``.
    size:
        Number of valid bytes in ``data``.
    timestamp:
        Acquisition timestamp in microseconds since Unix epoch.
    """

    data: bytes = Field(default=b"")
    size: int = 0
    timestamp: Optional[int] = None


class OVSItem(BaseModel):
    """Single spectral overview point (frequency, value)."""

    freq: float
    value: int


class Firmware(BaseModel):
    """Firmware and eeprom information reported by the receiver."""

    if_init: float = 0.0
    if_init_correction: float = 0.0
    data10bit: bool = False
    eeprom_info: bool = False
    versionstr: str = "unknown"


class Config(BaseModel):
    """Runtime configuration for a Callisto daemon instance.

    This model is intentionally close to the legacy INI-style configuration
    defined in ``docs/configurations.md`` while remaining small enough to
    be used without a database. Additional fields can be added as the
    integration with BINGO control systems evolves.
    """

    # Core acquisition and scheduling parameters ---------------------------------
    channelfile: str = ""
    serialport: str = "/dev/ttyS0"
    filetime: int = 60
    samplerate: int = 1
    net_port: int = 0
    datadir: str = "/var/lib/callisto"
    logdir: str = "/var/log/callisto"
    ovsdir: str = "/var/lib/callisto/overview"
    schedulefile: str = "schedule.cfg"
    clocksource: int = 1
    agclevel: int = 0
    chargepump: int = 1
    focuscode: int = 1
    nchannels: int = 1
    autostart: bool = False
    instrument: str = "CALLISTO"
    output_format: str = "fits"

    # Fields closely mirroring the legacy ``callisto.cfg`` keys ------------------
    rxcomport: str = "/dev/ttyUSB0"
    calport: str | None = None
    rxbaudrate: int = 115200
    observatory: int = 12
    titlecomment: str = ""
    origin: str = ""
    longitude: str = ""
    latitude: str = ""
    height: float = 0.0
    frqfile: str = "frq00005.cfg"
    mmode: int = 3
    timerinterval: int = 30
    timerpreread: int = 2
    timeouthexdata: int = 1000
    fitsenable: int = 1
    low_band: float = 171.0
    mid_band: float = 450.0
    detector_sens: float = 25.4

    # ZeroMQ PUB (optional). When empty, streaming is disabled.
    zmq_pub_endpoint: str = ""
    zmq_pub_bind: bool = True
    zmq_pub_topic: str = "callisto"
    zmq_pub_hwm: int = 10


class ScheduleEntry(BaseModel):
    """Single scheduler entry.

    Attributes
    ----------
    t:
        Seconds since midnight (UTC).
    action:
        Action code, see ``docs/configurations.md`` measurement modes.
    focuscode:
        Optional focus code to switch to before executing ``action``.
    """

    t: int
    action: int
    focuscode: Optional[int] = None


__all__ = [
    "Buffer",
    "OVSItem",
    "Firmware",
    "Config",
    "ScheduleEntry",
]
