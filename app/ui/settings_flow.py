"""Settings flow: dialog orchestration + prefs persist + live apply.

File > Settings reuses the same pattern as export_flow/batch_flow:
the window keeps a thin `open_settings()` delegating here; this module
holds the behavior. Dialog construction lives in settings_dialog
(one builder per group); helpers in dialog_fields.
"""

from __future__ import annotations


def open_settings(win) -> None:
    """Show Settings, save prefs and apply them to the window."""
    from app.export_prefs import load_prefs, normalize_prefs, save_prefs
    from app.paths import get_data_dir
    from app.recent import load_recent
    from app.ui.settings_dialog import SettingsDialog

    try:
        prefs = load_prefs(win._prefs_path)
    except Exception:  # noqa: BLE001
        prefs = load_prefs(None)
    try:
        recent_n = len(load_recent(win._prefs_path))
    except Exception:  # noqa: BLE001
        recent_n = 0
    try:
        data_dir = get_data_dir()
    except Exception:  # noqa: BLE001
        data_dir = ""
    dlg = SettingsDialog(prefs, data_dir=data_dir, recent_count=recent_n,
                         parent=win, prefs_path=getattr(win, "_prefs_path", None))
    try:
        if dlg.exec() != dlg.DialogCode.Accepted:
            dlg.deleteLater()
            win._status("Settings cancelled")
            return
        v = dlg.values()
    finally:
        try:
            dlg.deleteLater()
        except Exception:  # noqa: BLE001
            pass
    # -- persist (keep per-image/base/gif/recent unless cleared) --
    from app.export_prefs import apply_dialog_values

    apply_dialog_values(prefs, v)
    try:
        normalize_prefs(prefs)
    except Exception:  # noqa: BLE001
        pass
    try:
        save_prefs(prefs, win._prefs_path)
    except Exception:  # noqa: BLE001
        pass
    apply_settings(win, prefs)


def apply_settings(win, prefs) -> None:
    """Apply saved prefs to a live window (no dialog, no save)."""
    from app.export_prefs import resolve_out_dir

    try:
        win.out_dir = resolve_out_dir(getattr(prefs, "out_dir", "") or None)
    except Exception:  # noqa: BLE001
        pass
    try:
        win.spn_jobs.setValue(int(prefs.jobs))
    except Exception:  # noqa: BLE001
        pass
    try:
        win.chk_batch_drop.setChecked(bool(prefs.drop_batch))
    except Exception:  # noqa: BLE001
        pass
    try:
        win.set_viewport_mode(str(prefs.viewport))
    except Exception:  # noqa: BLE001
        pass
    win._status(f"Settings saved · output: {win.out_dir}")


__all__ = ["apply_settings", "open_settings"]
