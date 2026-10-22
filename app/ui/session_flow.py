"""Session: reopen where you left off (last image + preset).

Recorded incrementally (image path on every open, preset on close) so a
crash still restores. Startup restore is silent: missing files or a
disabled setting just keep the default empty window.
"""

from __future__ import annotations


def remember_image(win, path) -> None:
    """Persist the last opened image path (alongside the recent list)."""
    try:
        from pathlib import Path

        from app.export_prefs import load_prefs, save_prefs

        prefs = load_prefs(getattr(win, "_prefs_path", None))
        prefs.last_image = str(Path(path))
        save_prefs(prefs, getattr(win, "_prefs_path", None))
    except Exception:  # noqa: BLE001
        pass


def save_on_close(win) -> None:
    """Persist the active preset (and clear a stale image) on close."""
    try:
        from app.export_prefs import load_prefs, save_prefs

        prefs = load_prefs(getattr(win, "_prefs_path", None))
        try:
            prefs.last_preset = str(win.cmb_preset.currentText() or "")
        except Exception:  # noqa: BLE001
            pass
        if getattr(win, "src", None) is None:
            prefs.last_image = ""
        save_prefs(prefs, getattr(win, "_prefs_path", None))
    except Exception:  # noqa: BLE001
        pass


def restore(win) -> bool:
    """Reopen last image + preset if enabled and the file still exists."""
    try:
        from pathlib import Path

        from app.export_prefs import load_prefs

        prefs = load_prefs(getattr(win, "_prefs_path", None))
        if not bool(getattr(prefs, "restore_session", True)):
            return False
        last = Path(str(getattr(prefs, "last_image", "") or ""))
        if not last.is_file():
            return False
        preset = str(getattr(prefs, "last_preset", "") or "")
        if preset:
            try:
                if win.cmb_preset.findText(preset) >= 0:
                    win._apply_preset(preset)
            except Exception:  # noqa: BLE001
                pass
        win._load_path(last)
        if getattr(win, "src", None) is None:
            return False
        win._status(f"Session restored: {last.name}")
        return True
    except Exception:  # noqa: BLE001
        return False


__all__ = ["remember_image", "restore", "save_on_close"]
