from callisto.constants import MESSAGE_END, MESSAGE_START
from callisto.runtime import _PythonDaemon


def test_extract_frames_single_frame() -> None:
    text = f"noise{MESSAGE_START}ABC{MESSAGE_END}tail"
    frames = _PythonDaemon._extract_frames(text)
    assert frames == ["ABC"]


def test_extract_frames_multiple_and_incomplete() -> None:
    text = f"{MESSAGE_START}A{MESSAGE_END}{MESSAGE_START}BC{MESSAGE_END}{MESSAGE_START}X"
    frames = _PythonDaemon._extract_frames(text)
    assert frames == ["A", "BC"]
