"""Portable TRAKKART paths (family standard: env > frozen data/ > APPDATA > home)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_data_dir() -> Path:
    env = os.environ.get("TRAKKART_DATA_DIR", "").strip()
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    if getattr(sys, "frozen", False):
        p = Path(sys.executable).parent / "data"
        p.mkdir(parents=True, exist_ok=True)
        return p
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        p = Path(appdata) / "TRAKKART"
    else:
        p = Path.home() / ".trakkart"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_db_path() -> Path:
    return get_data_dir() / "trakkart.db"


def get_out_dir() -> Path:
    p = get_data_dir() / "out"
    p.mkdir(parents=True, exist_ok=True)
    return p
