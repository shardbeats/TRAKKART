"""Portable TRAKKART paths (SUITE standard: env > frozen data/ > APPDATA > home)."""

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


def get_presets_dir() -> Path:
    """User presets (writable). Bundled ones are seeded here on startup."""
    p = get_data_dir() / "presets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_palettes_dir() -> Path:
    """User palettes (writable). Builtins are seeded here on startup."""
    p = get_data_dir() / "palettes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def bundle_path(*parts: str) -> Path:
    """File shipped next to the code (dev) or inside the bundle (frozen).

    Covers MANUAL.md, icons, samples: in dev they live in the repo root,
    frozen (PyInstaller onedir) they come from sys._MEIPASS via --add-data.
    """
    base = Path(getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent)
    return base.joinpath(*parts)


def find_app_icon(name: str = "icon.png") -> Path | None:
    """Runtime app icon with frozen-layout fallback (never raises).

    Order: _MEIPASS/name (PyInstaller --add-data) -> exe dir/name ->
    exe dir/_internal/name -> dev root/name. Returns None when missing
    so callers can skip silently (same as before, but no longer blind
    to the onedir exe-dir layout).
    """
    cands: list[Path] = []
    try:
        cands.append(bundle_path(name))
    except Exception:  # noqa: BLE001
        pass
    try:
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            cands.append(exe_dir / name)
            cands.append(exe_dir / "_internal" / name)
    except Exception:  # noqa: BLE001
        pass
    try:
        cands.append(Path(__file__).resolve().parent.parent / name)
    except Exception:  # noqa: BLE001
        pass
    seen: set[str] = set()
    for c in cands:
        key = str(c).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            if c.is_file():
                return c
        except Exception:  # noqa: BLE001
            continue
    return None
