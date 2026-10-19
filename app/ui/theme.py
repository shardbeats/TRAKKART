"""TRAKK family theme (QSS with dev/frozen fallback)."""

from __future__ import annotations

from pathlib import Path

THEME_FILE = Path(__file__).with_name("theme.qss")


def load_stylesheet() -> str:
    """Read theme.qss next to this module. Empty if missing (never crashes)."""
    try:
        if THEME_FILE.exists():
            return THEME_FILE.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def accent() -> str:
    return "#F5A623"
