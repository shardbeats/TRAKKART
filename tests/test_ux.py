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
    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=0.0, method="bayer8")) is False
    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=0.0, method="floyd")) is True
    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=0.0, method="FLOYD")) is True
    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=0.0, method="hilbert")) is True
    assert is_heavy_preset(None) is False


def test_empty_state_placeholder(window):
    assert "NO IMAGE" in window.lbl_res.text()
    assert window.lbl_res.wordWrap() is True


def test_still_preview_uses_proxy_except_full(window):
    from PIL import Image

    from app.ui import preview_controller as pc

    window._apply_preset("VAPOR_BAYER8")  # ordered: sync path even when large
    window.src = Image.new("RGB", (1200, 900), (200, 50, 90))
    window.viewport_mode = "live"
    window._full_preview = False
    pc.render_still(window)  # ordered default: adaptive proxy
    assert window.result is not None
    assert max(window.result.size) <= max(pc.preview_max_side(window), 1200)
    assert "px" in window.lbl_status.text()
    window.viewport_mode = "full"
    pc.render_still(window)  # Full: exact full-res render
    assert max(window.result.size) > 640
    assert "full-res" in window.lbl_status.text()


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


def test_morph_live_pick_enables_video(window, tmp_path, monkeypatch):
    from PIL import Image
    from PySide6.QtWidgets import QFileDialog

    assert window.morph_src is None
    b = tmp_path / "b.png"
    Image.new("RGB", (32, 32), (10, 200, 90)).save(b)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(b), ""))
    window.cmb_video_mode.setCurrentText("morph")
    assert window._video_on is False
    assert window._on_morph_pick() is True
    assert window.morph_src is not None
    assert len(window.morph_list) == 1
    assert window.morph_list_widget.item(0).text() == "2: b.png"
    assert "1" in window.lbl_morph.text()
    assert window._video_on is True  # live preview turns on by itself
    assert "scrub" in window.lbl_compat.text().lower()
    window._on_morph_clear()
    assert window.morph_src is None
    assert window.morph_list == []
    assert "dissolve" in window.lbl_compat.text().lower()


def test_morph_visual_crop_dialog(window, tmp_path, monkeypatch):
    from PIL import Image
    from PySide6.QtWidgets import QDialog, QFileDialog

    from app.canvas import CUSTOM_RATIO
    from app.ui import params_controller as _par
    from app.ui.crop_editor import CropEditorDialog

    b = tmp_path / "wide.png"
    Image.new("RGB", (64, 32), (10, 200, 90)).save(b)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(b), ""))
    assert window._on_morph_pick() is True
    assert window.morph_list[0]["fx"] == 50.0
    # Fixed-frame dialog: controls locked, values pass through untouched.
    dlg = CropEditorDialog(
        Image.new("RGB", (64, 32)), ratio=CUSTOM_RATIO,
        canvas_w=64, canvas_h=64, fixed_frame=True, parent=None)
    assert dlg.fx == 50.0 and dlg.zoom == 1.0
    assert not dlg.cmb_ratio.isEnabled() and not dlg.cmb_mode.isEnabled()
    assert not dlg.spn_w.isEnabled() and not dlg.spn_h.isEnabled()
    dlg.deleteLater()
    # Accept path: canned user drag writes back to the entry.
    accepted = {"v": False}

    class FakeDlg:
        DialogCode = QDialog.DialogCode
        fx, fy, zoom, turns = 10.0, 80.0, 2.0, 0

        def __init__(self, *a, **k):
            pass

        def exec(self):
            accepted["v"] = True
            return QDialog.DialogCode.Accepted

        def deleteLater(self):
            pass

    monkeypatch.setattr("app.ui.crop_editor.CropEditorDialog", FakeDlg)
    window.morph_list_widget.setCurrentRow(0)
    assert window._on_morph_crop() is True
    assert accepted["v"] is True
    chain = _par.morph_chain_data(window)
    assert (chain[0]["fx"], chain[0]["fy"], chain[0]["zoom"]) == (10.0, 80.0, 2.0)
    assert "wide.png" in window.lbl_morph_crop.text()


def test_morph_playlist_chain_reorders_and_caps(window, tmp_path, monkeypatch):
    from PIL import Image
    from PySide6.QtWidgets import QFileDialog

    from app.disintegrate import MAX_MORPH_IMAGES

    paths = []
    for i, color in enumerate([(10, 200, 90), (200, 40, 90), (90, 90, 200)]):
        p = tmp_path / f"c{i}.png"
        Image.new("RGB", (16, 16), color).save(p)
        paths.append(str(p))
    picks = iter(paths)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (next(picks), ""))
    assert window._on_morph_pick() is True
    assert window._on_morph_pick() is True
    assert window._on_morph_pick() is True
    assert [e["name"] for e in window.morph_list] == ["c0.png", "c1.png", "c2.png"]
    window.morph_list_widget.setCurrentRow(0)
    window._on_morph_down()
    assert [e["name"] for e in window.morph_list] == ["c1.png", "c0.png", "c2.png"]
    window._on_morph_up()
    assert [e["name"] for e in window.morph_list] == ["c0.png", "c1.png", "c2.png"]
    window.morph_list_widget.setCurrentRow(1)
    window._on_morph_remove()
    assert [e["name"] for e in window.morph_list] == ["c0.png", "c2.png"]
    # Fill to the cap: further picks are refused.
    from PIL import Image as _Img

    full = [f"f{i}.png" for i in range(MAX_MORPH_IMAGES)]
    for i, name in enumerate(full):
        _Img.new("RGB", (8, 8), (i * 10, 20, 30)).save(tmp_path / name)
    picks = iter([str(tmp_path / n) for n in full])
    window._on_morph_clear()
    added = sum(1 for _ in full if window._on_morph_pick() is True)
    assert added == MAX_MORPH_IMAGES - 1
    assert window._on_morph_pick() is False


def test_morph_budget_grows_with_chain(window, tmp_path, monkeypatch):
    from PIL import Image
    from PySide6.QtWidgets import QFileDialog

    from app.ui import params_controller as _par

    paths = []
    for i in range(3):
        p = tmp_path / f"g{i}.png"
        Image.new("RGB", (16, 16), (i * 40, 100, 90)).save(p)
        paths.append(str(p))
    picks = iter(paths)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (next(picks), ""))
    window.cmb_video_fps.setCurrentText("12")
    window.cmb_video_frames.setCurrentText("6")
    window.cmb_video_mode.setCurrentText("morph")
    assert window._on_morph_pick() is True  # 1 seg + loop leg -> max(6, 20) = 20
    assert window._anim_combo_int(window.cmb_video_frames, 6, 2, 64) == 20
    assert window._on_morph_pick() is True  # 2 segs + loop leg -> max(20, 30) = 30
    assert window._anim_combo_int(window.cmb_video_frames, 6, 2, 64) == 30
    assert _par.ensure_morph_budget(window) is False  # already enough
    window.cmb_video_mode.setCurrentText("mix")
    window.cmb_video_mode.setCurrentText("morph")  # switch back re-checks
    assert window._anim_combo_int(window.cmb_video_frames, 6, 2, 64) == 30
    # Short budget warns with per-form time.
    window.cmb_video_frames.setCurrentText("8")
    window._sync_anim_ui()
    assert "per form" in window.lbl_compat.text()


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
