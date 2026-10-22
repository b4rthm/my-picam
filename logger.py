"""Logging setup with a rotating log file."""
import logging
import logging.handlers
import os
import sys

from config import LOG_BACKUP_COUNT, LOG_LEVEL, LOG_MAX_BYTES, LOG_PATH

_configured = False


def setup_logging(name="picam"):
    """Configure the root logger exactly once and return it."""
    global _configured
    if _configured:
        return logging.getLogger(name)

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s: \t%(message)s", "%Y-%m-%d %H:%M:%S")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_PATH, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:  # read-only fs etc. - console logging still works
        logger.warning("Could not open log file %s: %s", LOG_PATH, exc)

    _configured = True
    return logger


def get_logger(name="picam"):
    return setup_logging(name)
