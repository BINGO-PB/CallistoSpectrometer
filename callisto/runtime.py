"""Fachada de runtime do pacote callisto.

Este módulo centraliza o ponto de entrada do daemon para uso via pacote
(`pip install`) e mantém compatibilidade com o módulo legado `ecallisto`.
"""

from ecallisto import main as _legacy_main


def main() -> int:
    """Executa o daemon principal e retorna código de saída POSIX."""
    result = _legacy_main()
    return int(result) if result is not None else 0
