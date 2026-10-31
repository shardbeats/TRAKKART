"""v1.5 Iteration UX: viewport modes, heavy fast-path, tutorial, static stylesheet."""


def test_viewport_intervals():
    from app.viewport import MODES, mode_label, normalize_mode, resolve_interval

    assert set(MODES) == {"full", "live", "still"}
    assert normalize_mode("FULL") == "full"
    assert normalize_mode("nope") == "live"
    assert resolve_interval("full") == 0
    assert resolve_interval("still") is None
    assert resolve_interval("live", fast=True) == 120
    assert resolve_interval("live", fast=False) == 350
    assert mode_label("still") == "Still"


def test_heavy_preset_detection():
    from types import SimpleNamespace

    from app.viewport import is_heavy_preset

    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=0.0)) is False
    assert is_heavy_preset(SimpleNamespace(pre_blur=2.0, pre_denoise=0, pre_smooth=0.0)) is True
    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=3, pre_smooth=0.0)) is True
    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=1.0)) is True
    assert is_heavy_preset(None) is False


def test_tutorial_steps_and_samples(tmp_path):
    from app.tutorial import STEPS, ensure_samples, first_run_needed, mark_seen

    assert len(STEPS) == 5
    assert all(title and body for title, body in STEPS)
    assert first_run_needed(tmp_path) is True
    paths = ensure_samples(tmp_path)
    assert len(paths) == 3 and all(p.exists() for p in paths)
    assert first_run_needed(tmp_path) is True  # samples != seen
    mark_seen(tmp_path)
    assert first_run_needed(tmp_path) is False
    # Idempotent: second run keeps the same files.
    assert ensure_samples(tmp_path) == paths


def test_static_stylesheet_loads_with_selectors():
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent / "app" / "ui" / "theme.qss").read_text(encoding="utf-8")
    assert css
    for sel in ("QGroupBox", "QPushButton#exportBtn", "QSlider::groove:horizontal",
                "QMenuBar", "QStatusBar", "QLabel#previewFrame"):
        assert sel in css, sel


def test_window_viewport_switch(window, qt_app):
    assert window.viewport_mode == "live"
    assert window.lbl_viewport.text() == "Viewport: Live"
    window.set_viewport_mode("still")
    assert window.viewport_mode == "still"
    assert window.lbl_viewport.text() == "Viewport: Still"
    window.set_viewport_mode("full")
    assert window._act_viewport_full.isChecked()


def test_still_mode_skips_auto_refresh(window, qt_app):
    window.set_viewport_mode("still")
    window._preview_timer.stop()  # isolate: init arms it once via preset apply
    window._schedule_refresh()  # must not re-arm the timer
    assert not window._preview_timer.isActive()
    assert "Still mode" in window.lbl_status.text()


def test_no_timeline_leftovers(window):
    """Trim guard: no layer/clip widgets, drift lives in DATAMOSH."""
    for attr in ("anim_list", "btn_anim_add", "btn_anim_remove", "cmb_anim_prop",
                 "spn_anim_from", "spn_anim_to", "spn_anim_start", "spn_anim_end",
                 "btn_clip_open", "btn_clip_browse", "lbl_clip",
                 "anim_layers_data", "clip_frames"):
        assert not hasattr(window, attr), attr
    assert window.cmb_drift.count() == 10  # off + 9 Signal Drift patterns
    assert window.sld_drift.value() == 0
    assert window.sld_drift_speed.value() == 100  # 1.0x
    assert window.sld_drift_position.value() == 50  # mid-traverse
    from app.presets import Preset

    assert not hasattr(Preset(name="t"), "anim_layers")


def test_anim_compat_hint(window, qt_app):
    from app.gif import mode_desc, mode_label

    assert mode_label("mix") == "Full mix"
    assert "ordered" in mode_desc("phase").lower()
    # ED method + march mode -> hint + helper button.
    window.cmb_method.setCurrentText("floyd")
    window.cmb_video_mode.setCurrentText("phase")
    window._sync_anim_ui()
    assert "frozen" in window.lbl_compat.text().lower()
    assert not window.btn_use_ordered.isHidden()
    assert "march" in window.lbl_mode_desc.text().lower()
    # Ordered method -> no hint; wobble mode on ED -> no hint either.
    window.cmb_method.setCurrentText("bayer8")
    window._sync_anim_ui()
    assert window.lbl_compat.text() == ""
    assert window.btn_use_ordered.isHidden()
    window.cmb_method.setCurrentText("floyd")
    window.cmb_video_mode.setCurrentText("mix")
    window._sync_anim_ui()
    assert window.lbl_compat.text() == ""
    # Helper jumps to an ordered method.
    window.cmb_video_mode.setCurrentText("both")
    window._sync_anim_ui()
    window._use_ordered_method()
    assert window.cmb_method.currentText() == "bayer8"
    # Motion amount round-trips through the panel.
    window.sld_motion.setValue(200)
    assert abs(window.current_params().motion_amount - 2.0) < 1e-9
    window._apply_preset("SLIME_FS")
    assert abs(window.sld_motion.value() / 100.0 - 1.0) < 1e-9


def test_tutorial_dialog_walks_all_steps(qt_app):
    from app.tutorial import STEPS
    from app.ui.tutorial_dialog import TutorialDialog

    dlg = TutorialDialog(parent=None)
    assert dlg.lbl_pos.text() == f"1/{len(STEPS)}"
    assert dlg.btn_back.isEnabled() is False
    for _ in range(len(STEPS) - 1):
        dlg.btn_next.click()
    assert dlg.lbl_pos.text() == f"{len(STEPS)}/{len(STEPS)}"
    assert dlg.btn_next.text() == "Done"
    dlg.btn_back.click()
    assert dlg.lbl_pos.text() == f"{len(STEPS) - 1}/{len(STEPS)}"
    dlg.btn_skip.click()
    assert dlg.result() == TutorialDialog.DialogCode.Rejected
    dlg2 = TutorialDialog(parent=None)
    for _ in range(len(STEPS)):
        dlg2.btn_next.click()
    assert dlg2.result() == TutorialDialog.DialogCode.Accepted
    dlg.close()
    dlg2.close()
