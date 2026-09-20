"""Ρύθμιση καταγραφής (logging) της εφαρμογής."""

import logging

from .constants import LOG_PATH

LOGGER = logging.getLogger("smart_backup")


def setup_logging():
    LOGGER.setLevel(logging.INFO)
    if not LOGGER.handlers:
        try:
            handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            LOGGER.addHandler(handler)
        except OSError:
            pass
    return LOGGER
