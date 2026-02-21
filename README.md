# callisto

Daemon Python para aquisição de dados do receptor e-Callisto.

## Instalação

```bash
pip install .
```

## CLI

Após instalar, os comandos ficam disponíveis:

- `callisto`
- `ecallisto`

## Organização do pacote

- `callisto/constants.py`: constantes e estados do protocolo
- `callisto/models.py`: dataclasses de domínio
- `callisto/logging_utils.py`: logging e utilitários de log
- `callisto/time_utils.py`: utilitários de tempo UTC timezone-aware
- `callisto/runtime.py`: fachada de runtime e compatibilidade com legado
- `callisto/cli.py`: ponto de entrada de linha de comando

## Functionalities



## Exemplos de configuração

Foram adicionados exemplos prontos em `examples/`:

- `examples/callisto.cfg`
- `examples/frq00005.cfg`
- `examples/scheduler.cfg`

Esses arquivos são incluídos no pacote-fonte via `MANIFEST.in` e também
instalados no wheel em `share/callisto/examples`.

## Fontes utilizadas

This project i a python port with added functionalities of the work done by Alec Myczko and available as a debian package as 

Package: callisto
Version: 1.1.0-3
Architecture: i386
Maintainer: Alex Myczko <tar@debian.org>
