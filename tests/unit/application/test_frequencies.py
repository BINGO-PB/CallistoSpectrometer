from __future__ import annotations

from pathlib import Path

from callisto.application.frequencies import (
    load_frequencies,
    load_frequencies_from_lines,
)


def test_load_frequencies_from_lines_orders_and_parses() -> None:
    lines = [
        "[target]=CALLISTO",
        "[number_of_measurements_per_sweep]=8",
        "[0002]=0045.250,0",
        "[0001]=0045.000,0",
        "[0008]=0046.750,0 // comment",
        "# comment",
    ]

    freqs = load_frequencies_from_lines(lines)
    assert freqs == [45.0, 45.25, 46.75]


def test_load_frequencies_uses_example(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    example = root / "examples" / "frq00005.cfg"
    tmp_frq = tmp_path / "frq00005.cfg"
    tmp_frq.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    freqs = load_frequencies(str(tmp_frq))

    # Example file documents eight frequencies from 45.000 to 46.750 MHz.
    assert len(freqs) == 8
    assert freqs[0] == 45.0
    assert freqs[-1] == 46.75
