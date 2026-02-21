from callisto.control import process_client_command


def _callback_log():
    calls: list[str] = []

    def on_start() -> None:
        calls.append("start")

    def on_stop() -> None:
        calls.append("stop")

    def on_overview_once() -> None:
        calls.append("overview_once")

    def on_overview_continuous_ok() -> bool:
        calls.append("overview_cont")
        return True

    def on_overview_continuous_fail() -> bool:
        calls.append("overview_cont")
        return False

    def on_overview_off() -> None:
        calls.append("overview_off")

    return (
        calls,
        on_start,
        on_stop,
        on_overview_once,
        on_overview_continuous_ok,
        on_overview_continuous_fail,
        on_overview_off,
    )


def test_process_client_command_start_stop_quit() -> None:
    (
        calls,
        on_start,
        on_stop,
        on_overview_once,
        on_overview_cont_ok,
        _,
        on_overview_off,
    ) = _callback_log()

    assert (
        process_client_command(
            "start",
            on_start,
            on_stop,
            on_overview_once,
            on_overview_cont_ok,
            on_overview_off,
        )
        == "OK starting new FITS file\n\n"
    )
    assert (
        process_client_command(
            "stop",
            on_start,
            on_stop,
            on_overview_once,
            on_overview_cont_ok,
            on_overview_off,
        )
        == "OK stopping\n\n"
    )
    assert (
        process_client_command(
            "quit",
            on_start,
            on_stop,
            on_overview_once,
            on_overview_cont_ok,
            on_overview_off,
        )
        is None
    )
    assert calls == ["start", "stop"]


def test_process_client_command_overview_variants() -> None:
    (
        calls,
        on_start,
        on_stop,
        on_overview_once,
        on_overview_cont_ok,
        on_overview_cont_fail,
        on_overview_off,
    ) = _callback_log()

    ok = process_client_command(
        "overview",
        on_start,
        on_stop,
        on_overview_once,
        on_overview_cont_ok,
        on_overview_off,
    )
    assert ok == "OK starting spectral overview\n\n"

    ok = process_client_command(
        "overview-cont",
        on_start,
        on_stop,
        on_overview_once,
        on_overview_cont_ok,
        on_overview_off,
    )
    assert ok.startswith("OK starting continuous spectral overview")

    err = process_client_command(
        "overview-continuous",
        on_start,
        on_stop,
        on_overview_once,
        on_overview_cont_fail,
        on_overview_off,
    )
    assert err == "ERROR HDF5 backend unavailable (install python3-h5py)\n\n"

    stop_msg = process_client_command(
        "overview-off",
        on_start,
        on_stop,
        on_overview_once,
        on_overview_cont_ok,
        on_overview_off,
    )
    assert stop_msg == "OK stopping continuous spectral overview\n\n"

    assert calls == ["overview_once", "overview_cont", "overview_cont", "overview_off"]


def test_process_client_command_unknown_and_empty() -> None:
    (
        calls,
        on_start,
        on_stop,
        on_overview_once,
        on_overview_cont_ok,
        _,
        on_overview_off,
    ) = _callback_log()

    assert (
        process_client_command(
            "",
            on_start,
            on_stop,
            on_overview_once,
            on_overview_cont_ok,
            on_overview_off,
        )
        == "OK\n\n"
    )
    assert (
        process_client_command(
            "get",
            on_start,
            on_stop,
            on_overview_once,
            on_overview_cont_ok,
            on_overview_off,
        )
        == "ERROR no data (yet)\n\n"
    )
    assert (
        process_client_command(
            "nada",
            on_start,
            on_stop,
            on_overview_once,
            on_overview_cont_ok,
            on_overview_off,
        )
        == "ERROR unrecognized command (nada)\n\n"
    )
    assert calls == []
