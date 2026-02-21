"""Controle de comandos de rede do daemon e-Callisto."""

from __future__ import annotations

from typing import Callable


def process_client_command(
    line: str,
    on_start: Callable[[], None],
    on_stop: Callable[[], None],
    on_overview_once: Callable[[], None],
    on_overview_continuous: Callable[[], bool],
    on_overview_off: Callable[[], None],
) -> str | None:
    """Processa um comando textual e retorna resposta do protocolo.

    Retorna:
    - `str`: resposta já formatada para o cliente (inclui terminador em branco).
    - `None`: sinal para encerrar a conexão.
    """

    cmd = (line or "").strip().lower()
    if not cmd:
        return "OK\n\n"

    if cmd == "quit":
        return None

    if cmd == "start":
        on_start()
        return "OK starting new FITS file\n\n"

    if cmd == "stop":
        on_stop()
        return "OK stopping\n\n"

    if cmd == "overview":
        on_overview_once()
        return "OK starting spectral overview\n\n"

    if cmd in ("overview-continuous", "overview-cont"):
        if not on_overview_continuous():
            return "ERROR HDF5 backend unavailable (install python3-h5py)\n\n"
        return "OK starting continuous spectral overview in HDF5 (window=filetime)\n\n"

    if cmd in ("overview-stop", "overview-off"):
        on_overview_off()
        return "OK stopping continuous spectral overview\n\n"

    if cmd == "get":
        return "ERROR no data (yet)\n\n"

    return f"ERROR unrecognized command ({cmd})\n\n"
