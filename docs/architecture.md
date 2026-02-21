# Arquitetura do pacote `callisto`

Este projeto foi estruturado para instalação com `pip` e execução por entrypoint de console.

## Estrutura

- `callisto/constants.py`: constantes de protocolo e estados.
- `callisto/models.py`: dataclasses com tipos primitivos (`int`, `float`, `str`, `bool`, `list`).
- `callisto/logging_utils.py`: logger compartilhado e helpers de log.
- `callisto/time_utils.py`: funções UTC timezone-aware.
- `callisto/cli.py`: comando principal (`callisto` / `ecallisto`).
- `ecallisto.py`: runtime legado, agora consumindo módulos do pacote.

## Estratégia de modularização

1. Extrair definições estáveis (constantes/modelos/logging/tempo).
2. Manter compatibilidade com o daemon legado.
3. Preparar evolução para mover o loop principal para `callisto/runtime.py` em etapa seguinte.

## Tipagem

As anotações foram mantidas em estilo simples com tipos primitivos e compostos básicos:

- `int`, `float`, `str`, `bool`
- `list[T]`, `dict[str, T]`
- `T | None`

## Próximos passos sugeridos

- Dividir `ecallisto.py` em módulos de domínio:
  - `callisto/io/serial_backend.py`
  - `callisto/io/writers.py`
  - `callisto/control/server_commands.py`
  - `callisto/runtime/main_loop.py`
- Adicionar testes de integração para os formatos FITS/HDF5.
