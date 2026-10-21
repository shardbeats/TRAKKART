"""File logging: data/trakkart.log (stdlib only, rotating, idempotent).

Tests reset `_INITIALIZED` to point logging at a tmp dir.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "trakkart.log"
_INITIALIZED = False


def log_path(data_dir=None) -> Path:
    from app.paths import get_data_dir

    base = Path(data_dir) if data_dir else get_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / LOG_FILENAME


def setup_logging(data_dir=None) -> Path:
    """Attach a rotating file handler to the `trakkart` logger. Idempotent."""
    global _INITIALIZED
    path = log_path(data_dir)
    if _INITIALIZED:
        return path
    handler = RotatingFileHandler(str(path), maxBytes=256 * 1024,
                                  backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("trakkart")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _INITIALIZED = True
    return path


__all__ = ["LOG_FILENAME", "log_path", "setup_logging"]
