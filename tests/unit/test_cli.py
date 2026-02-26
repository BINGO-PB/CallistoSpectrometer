from __future__ import annotations

from pathlib import Path

import callisto.runtime as runtime

from callisto import cli


def _write_minimal_cfg(tmp_path: Path) -> Path:
    cfg_path = tmp_path / "callisto.cfg"
    cfg_path.write_text(
        f"[rxcomport]=/dev/ttyUSB0\n"
        f"[datapath]={tmp_path}/data/\n"
        f"[logpath]={tmp_path}/log/\n"
        f"[ovsdir]={tmp_path}/overview/\n",
        encoding="utf-8",
    )
    return cfg_path


def test_cli_main_accepts_config_and_exits(tmp_path: Path, monkeypatch) -> None:
    cfg_path = _write_minimal_cfg(tmp_path)

    # evitar chamar o daemon legado de verdade
    called = {}

    def fake_main() -> int:
        called["ok"] = True
        return 0

    # CLI importa `runtime.main` na carga do módulo, então aqui
    # garantimos que a função interna `_LEGACY_MAIN` devolve o valor
    # desejado sem exigir que o pacote `ecallisto` esteja instalado.
    monkeypatch.setattr(runtime, "_LEGACY_MAIN", lambda: fake_main())

    code = cli.main(["--config", str(cfg_path)])
    assert code == 0
    assert called.get("ok") is True


def test_cli_default_config_name(tmp_path: Path, monkeypatch) -> None:
    called = {"cwd": None}

    # Write a minimal cfg in the temp dir so load_config can find it
    cfg_path = tmp_path / "callisto.cfg"
    cfg_path.write_text(
        f"[rxcomport]=/dev/ttyUSB0\n"
        f"[datapath]={tmp_path}/data/\n"
        f"[logpath]={tmp_path}/log/\n"
        f"[ovsdir]={tmp_path}/overview/\n",
        encoding="utf-8",
    )

    def fake_main() -> int:
        from os import getcwd

        called["cwd"] = Path(getcwd())
        return 0

    monkeypatch.setattr(runtime, "_LEGACY_MAIN", lambda: fake_main())
    monkeypatch.chdir(tmp_path)

    # roda sem argumentos explícitos; o parser usará o default
    code = cli.main([])
    assert code == 0

    # o cwd visto pelo runtime deve ser o diretório do cfg quando
    # chamamos com --config; aqui só validamos que o wrapper funciona.
    # Como neste teste não mudamos cwd, apenas garantimos que fake_main
    # foi chamado.
    assert called["cwd"] is not None
