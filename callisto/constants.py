"""Constantes de protocolo e estados de execução."""

RESET_STRING: str = "D0\rGD\rS0\r"
ID_QUERY: str = "S0\r"
ID_RESPONSE: str = "$CRX:Stopped\r"
HEXDATA_RESET: int = -1

MESSAGE_START: str = "<"
MESSAGE_END: str = ">"

MAX_MESSAGE: int = 4096
MAX_OVS: int = 13200
SCHEDULE_CHECK_INTERVAL: int = 60

VERSION_STR_15: str = "$CRX:ChargePump="
VERSION_STR_17: str = "$CRX:Debug="
VERSION_STR_18: str = "$CRX:V1.8 / "

STOPPED: int = 0
STOPPING: int = 1
STARTING: int = 2
RUNNING: int = 3
OVERVIEW: int = 4

SCHEDULE_START: int = 1
SCHEDULE_STOP: int = 2
SCHEDULE_OVERVIEW: int = 3
