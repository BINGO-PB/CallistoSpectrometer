from __future__ import annotations

from pathlib import Path

from callisto.application.config_loader import (
    load_config,
    load_schedule,
    load_schedule_file,
)
from callisto.domain import Config, ScheduleEntry


def test_load_config_from_example(tmp_path: Path) -> None:
    # copy example cfg into a temp dir to test relative path resolution
    root = Path(__file__).resolve().parents[3]
    example = root / "config" / "callisto.cfg"
    cfg_path = tmp_path / "callisto.cfg"
    cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    cfg = load_config(str(cfg_path))
    assert isinstance(cfg, Config)

    # basic fields from example
    assert cfg.rxcomport == "/dev/ttyUSB0"
    assert cfg.rxbaudrate == 115200
    assert cfg.observatory == 12
    assert cfg.instrument.strip() == "BINGO"
    assert cfg.focuscode == 59
    assert cfg.filetime == 900
    assert cfg.frqfile == "frq00005.cfg"
    assert cfg.mmode == 3
    assert cfg.fitsenable == 1
    assert cfg.output_format == "fits"

    # directory aliases resolved relative to cfg file location (tmp_path)
    assert cfg.datadir.startswith(str(tmp_path))
    assert cfg.logdir.startswith(str(tmp_path))


def test_load_config_env_overrides(tmp_path: Path) -> None:
    cfg_path = tmp_path / "callisto.cfg"
    # Write cfg with all three dirs pointing to tmp_path so load_config can create them.
    # Env vars will then override datadir and logdir for the assertions.
    cfg_path.write_text(
        f"[rxcomport]=/dev/ttyUSB1\n"
        f"[datapath]={tmp_path}/data_default/\n"
        f"[logpath]={tmp_path}/log_default/\n"
        f"[ovsdir]={tmp_path}/overview/\n",
        encoding="utf-8",
    )

    env = {
        "CALLISTO_DATADIR": str(tmp_path / "data"),
        "CALLISTO_LOGDIR": str(tmp_path / "logs"),
        "CALLISTO_OUTPUT_FORMAT": "HDF5",
        "CALLISTO_ZMQ_PUB_ENDPOINT": "tcp://127.0.0.1:5556",
    }

    cfg = load_config(str(cfg_path), env=env)

    assert cfg.rxcomport == "/dev/ttyUSB1"
    assert cfg.datadir == env["CALLISTO_DATADIR"]
    assert cfg.logdir == env["CALLISTO_LOGDIR"]
    assert cfg.output_format == "hdf5"
    assert cfg.zmq_pub_endpoint == env["CALLISTO_ZMQ_PUB_ENDPOINT"]


def test_load_schedule_parses_entries() -> None:
    lines = [
        "04:00:00,03,3   // start",
        "12:00:00,03,8   // overview",
        "19:30:00,03,0   // stop",
        "# comment",
        "",
    ]

    entries = load_schedule(lines)
    assert all(isinstance(e, ScheduleEntry) for e in entries)
    assert [e.t for e in entries] == [4 * 3600, 12 * 3600, 19 * 3600 + 30 * 60]
    assert [e.focuscode for e in entries] == [3, 3, 3]
    assert [e.action for e in entries] == [3, 8, 0]


def test_load_schedule_file_uses_path(tmp_path: Path) -> None:
    sched_path = tmp_path / "scheduler.cfg"
    sched_path.write_text("04:00:00,03,3\n", encoding="utf-8")

    entries = load_schedule_file(str(sched_path))
    assert len(entries) == 1
    assert entries[0].t == 4 * 3600
    assert entries[0].focuscode == 3
    assert entries[0].action == 3


def test_load_schedule_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.cfg"
    entries = load_schedule_file(str(missing))
    assert entries == []
