"""Recent files: last opened images (move-to-front, capped, testable).

Stored inside the prefs JSON (`recent_files`); missing files are filtered
when the menu is built, never at save time.
"""

from __future__ import annotations

from pathlib import Path

MAX_RECENT = 5


def load_recent(prefs_path=None) -> list[str]:
    from app.export_prefs import load_prefs

    try:
        items = list(getattr(load_prefs(prefs_path), "recent_files", []) or [])
    except Exception:  # noqa: BLE001
        return []
    return [str(s) for s in items if str(s).strip()][:MAX_RECENT]


def remember_recent(path, prefs_path=None) -> list[str]:
    """Move `path` to the front (dedup + cap). Returns the new list."""
    from app.export_prefs import load_prefs, save_prefs

    prefs = load_prefs(prefs_path)
    items = [str(path)]
    items += [s for s in (getattr(prefs, "recent_files", []) or []) if str(s) != str(path)]
    prefs.recent_files = [str(s) for s in items if str(s).strip()][:MAX_RECENT]
    try:
        save_prefs(prefs, prefs_path)
    except Exception:  # noqa: BLE001
        pass
    return list(prefs.recent_files)


def existing_recent(prefs_path=None) -> list[Path]:
    """Recents that still exist on disk (for the File menu)."""
    out = []
    for s in load_recent(prefs_path):
        p = Path(s)
        try:
            if p.is_file():
                out.append(p)
        except OSError:
            continue
    return out


__all__ = ["MAX_RECENT", "existing_recent", "load_recent", "remember_recent"]
