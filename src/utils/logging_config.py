"""Central logging setup. Import get_logger(__name__) anywhere in the app."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from src.config import LOG_DIR, LOG_LEVEL

_CONFIGURED = False


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("shipping_cfo")
    root.setLevel(LOG_LEVEL)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)

    try:
        file_handler = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=2_000_000, backupCount=3)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        # Read-only filesystem or similar — fall back to stdout-only logging rather than crash.
        root.warning("Could not open log file; continuing with console logging only.")

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(f"shipping_cfo.{name}")
