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
        # Invalidate an in-flight video render: otherwise a late result
        # repopulates frames after the reset (stale video resurrection).
        win._video_token = int(getattr(win, "_video_token", 0) or 0) + 1
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
        from app.ui import envelope_controller as _env

        _env.clear_envelopes(win)
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
    """Empty project: clear image + clip + back to init recipe."""
    from PySide6.QtWidgets import QMessageBox

    try:
        from app.ui import clip_controller as _clip

        has_clip = _clip.has_clip(win)
    except Exception:  # noqa: BLE001
        _clip = None
        has_clip = False
    if getattr(win, "src", None) is not None or has_clip:
        ans = QMessageBox.question(
            win, "New project",
            "Start an empty project? Image, clip and settings are cleared.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Ok:
            return
    _reset_common(win)
    # Cancel any in-flight preview before dropping src: nulling a running
    # QThread reference aborts the process (no traceback).
    try:
        from app.ui import preview_controller as _pc

        _pc.cancel(win)
    except Exception:  # noqa: BLE001
        pass
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
    if _clip is not None:
        try:
            _clip.close_clip(win)  # frees ≤120 proxy frames + dither cache
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
