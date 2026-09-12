"""Shared logging setup for Space Jumper.

Every module obtains its logger through :func:`get_logger` so that the whole
project writes to one configured handler instead of scattering ``print``
calls (or silently swallowing errors) around the codebase.
"""

from __future__ import annotations

import logging
import os

_configured = False

_LOG_FORMAT = "%(levelname)-8s %(name)s: %(message)s"

_LEVEL_BY_NAME = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging(debug: bool = False) -> None:
    """Configure the root logger once.

    The ``SPACE_JUMPER_LOG_LEVEL`` environment variable overrides *debug*,
    which keeps development runs verbose without editing code.

    Args:
        debug: When True, log DEBUG messages; otherwise INFO and above.
    """
    global _configured
    if _configured:
        return

    level = logging.DEBUG if debug else logging.INFO
    override = os.environ.get("SPACE_JUMPER_LOG_LEVEL", "").upper()
    if override in _LEVEL_BY_NAME:
        level = _LEVEL_BY_NAME[override]

    logging.basicConfig(level=level, format=_LOG_FORMAT)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return the logger for *name*, configuring logging on first use."""
    configure_logging()
    return logging.getLogger(name)
