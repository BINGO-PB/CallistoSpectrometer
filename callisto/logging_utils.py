"""Infra de logging compartilhada do projeto."""

import logging
import os
import sys

logger = logging.getLogger("e-callisto")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
if not logger.handlers:
    logger.addHandler(_handler)


def set_debug(enabled: bool) -> None:
    logger.setLevel(logging.DEBUG if enabled else logging.INFO)


def logprintf(level: int, fmt: str, *args: object) -> None:
    msg = fmt % args if args else fmt
    if level == 0:
        logger.error(msg)
    elif level == 1:
        logger.warning(msg)
    elif level == 2:
        logger.info(msg)
    elif level == 3:
        logger.debug(msg)
    else:
        logger.info(msg)


def setup_file_logging(logdir: str, log_filename: str = "ecallisto.log") -> str:
    os.makedirs(logdir, exist_ok=True)
    if not os.access(logdir, os.W_OK):
        raise PermissionError(f"Cannot write to log directory: {logdir}")

    logfile = os.path.join(logdir, log_filename)
    fh = logging.FileHandler(logfile)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(fh)
    return logfile
