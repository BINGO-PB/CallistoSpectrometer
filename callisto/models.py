"""Modelos de dados do domínio callisto."""

from dataclasses import dataclass


@dataclass
class Buffer:
    data: bytearray
    size: int = 0
    timestamp: int | None = None


@dataclass
class OVSItem:
    freq: float
    value: int


@dataclass
class Firmware:
    if_init: float = 0.0
    if_init_correction: float = 0.0
    data10bit: bool = False
    eeprom_info: bool = False
    versionstr: str = "unknown"


@dataclass
class Config:
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


@dataclass
class ScheduleEntry:
    t: int
    action: int
    focuscode: int | None = None
