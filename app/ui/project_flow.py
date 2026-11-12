"""New project / Reset settings (keep image).

Both share one reset core: back to the startup recipe (SLIME_FS) plus
neutral view state. New project additionally empties src/result/history.
Display-only flags (SP-404 preview, video, wipe) are always neutralized.
Nothing touches disk or prefs.
"""

from __future__ import annotations


def _reset_common(win) -> None:
    try:
        win.crop_fx = 50.0
        win.crop_fy = 50.0
        win.crop_zoom = 1.0
    except Exception:  # noqa: BLE001
        pass
    try:
        win._sp404_preview = False
        if getattr(win, "act_sp404", None) is not None:
            win.act_sp404.setChecked(False)
        btn = getattr(win, "btn_sp404_preview", None)
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(False)
            try:
                btn.setText("SP-404 OLED Preview: OFF")
            except Exception:  # noqa: BLE001
                pass
            btn.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass
    try:
        win._video_on = False
        win._video_frames = []
        win._video_idx = 0
    except Exception:  # noqa: BLE001
        pass
    try:
        if getattr(win, "sld_wipe", None) is not None:
            win.sld_wipe.blockSignals(True)
            win.sld_wipe.setValue(0)
            win.sld_wipe.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass
    try:
        win.morph_src = None
        win.morph_path = ""
        win.morph_list = []
    except Exception:  # noqa: BLE001
        pass
    try:
        win._apply_preset("SLIME_FS")
    except Exception:  # noqa: BLE001
        pass
    try:
        win._sync_crop_label()
    except Exception:  # noqa: BLE001
        pass


def reset_settings_keep_image(win) -> None:
    """Back to init recipe, image kept. Confirm only if an image is loaded."""
    from PySide6.QtWidgets import QMessageBox

    if getattr(win, "src", None) is not None:
        ans = QMessageBox.question(
            win, "Reset settings",
            "Reset all settings to defaults? The image is kept.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Ok:
            return
    _reset_common(win)
    try:
        win.refresh()
    except Exception:  # noqa: BLE001
        pass
    try:
        win._status("Settings reset to defaults.")
    except Exception:  # noqa: BLE001
        pass


def new_project(win) -> None:
    """Empty project: clear image + back to init recipe."""
    from PySide6.QtWidgets import QMessageBox

    if getattr(win, "src", None) is not None:
        ans = QMessageBox.question(
            win, "New project",
            "Start an empty project? Image and settings are cleared.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Ok:
            return
    _reset_common(win)
    try:
        win.history.clear()
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ops import ImageHistory

        win.history = ImageHistory()
    except Exception:  # noqa: BLE001
        pass
    win.src = None
    win.result = None
    win.src_name = "trakkart_cover"
    try:
        win._preview_token += 1
        win._preview_pending = False
        win._preview_worker = None
    except Exception:  # noqa: BLE001
        pass
    try:
        win.lbl_res.setText("No image — open one to start")
    except Exception:  # noqa: BLE001
        pass
    try:
        win.lbl_res_title.setText("DITHER")
    except Exception:  # noqa: BLE001
        pass
    try:
        win._status("New empty project. Open an image to start.")
    except Exception:  # noqa: BLE001
        pass
