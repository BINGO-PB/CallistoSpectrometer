"""CLI oficial do pacote callisto."""

from .runtime import main as _main


def main() -> int:
    result = _main()
    return int(result) if result is not None else 0
