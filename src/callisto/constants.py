"""Constantes de protocolo e estados de execução.

The values here mirror the legacy C implementation in the original
``e-Callisto`` daemon (see ``callisto.c`` / ``callisto.h``) so that
the pure-Python runtime observes the same on-wire protocol.
"""

RESET_STRING: str = "D0\rGD\rS0\r"
ID_QUERY: str = "S0\r"
ID_RESPONSE: str = "$CRX:Stopped\r"

# Special values used by the legacy hexdata state machine
HEXDATA_RESET: int = -1

# Firmware special characters (messages and data framing)
MESSAGE_START: str = "$"
MESSAGE_END: str = "\r"
DATA_START: str = "2"
DATA_END: str = "&"
EEPROM_READY: str = "]"

MAX_MESSAGE: int = 128
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
