"""UI render path: combos, export, adjust/ratio/fx/vector/gif controls, preview workers."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def test_refresh_all_combos(window):
    from app.dither import METHODS
    from app.palette_library import list_palettes

    for method in METHODS:
        window.cmb_method.setCurrentText(method)
        for pal in list_palettes():
            window._on_palette_preset_changed(pal)
            window.spn_pixel.setValue(2)
            window.sld_thr.setValue(100)
            window.refresh()
    assert window.result is not None
    assert window.result.size == (64, 64)


def test_export_bundle_from_ui(window, qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    window.refresh()
    assert window.result is not None
    accept_next_dialog(ExportDialog)
    window.export()
    names = sorted(p.name for p in window.out_dir.glob("*.png"))
    assert names == ["trakkart_cover.png", "trakkart_cover_thumb1080p.png"]


def test_ratio_controls_apply(window, isolated_presets):
    window.cmb_ratio.setCurrentText("9:16")
    window.cmb_crop.setCurrentText("contain")
    window.crop_fx = 20.0
    window.crop_fy = 30.0
    window.crop_zoom = 1.5
    window._sync_crop_label()
    window.refresh()  # signals only schedule (debounce); refresh is explicit
    assert window.result is not None
    assert window.current_params().ratio == "9:16"
    assert window.current_params().focus_x == 20.0
    assert window.current_params().crop_zoom == 1.5
    assert "1.5x" in window.lbl_crop.text()


def test_custom_canvas_free_wh(window, isolated_presets):
    # Photoshop-style: preset rellena W/H; editar W/H salta a Custom.
    window.cmb_ratio.setCurrentText("1:1")
    window._on_ratio_preset()  # gesto de usuario: rellena a escala actual
    assert (window.spn_canvas_w.value(), window.spn_canvas_h.value()) == (3000, 3000)
    assert window.current_params().ratio == "1:1"
    window.spn_canvas_w.setValue(1920)  # teclear W...
    window.spn_canvas_h.setValue(800)   # ...y H salta a Custom
    assert window.cmb_ratio.currentText() == "Custom"
    p = window.current_params()
    assert (p.ratio, p.canvas_w, p.canvas_h) == ("custom", 1920, 800)
    assert "1920×800" in window.lbl_docdims.text()
    window.refresh()
    assert window.result is not None
    assert abs(window.result.width / window.result.height - 1920 / 800) < 0.1


def test_fx_controls_apply(window, isolated_presets, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog

    window.sld_blur.setValue(15)
    window.spn_sharp.setValue(1)
    window.sld_glow.setValue(30)
    window.sld_grain.setValue(10)
    window.sld_vig.setValue(25)
    window.sld_hue.setValue(45)
    window.spn_denoise.setValue(2)
    window.sld_smooth.setValue(15)
    assert window.current_params().pre_hue == 45.0
    assert window.current_params().pre_denoise == 2
    window.spn_scan.setValue(1)  # invalid -> snaps to 2 in current_params
    assert window.current_params().scanlines == 2
    window.spn_scan.setValue(4)
    monkeypatch.setattr(QColorDialog, "getColor", lambda *a, **k: QColor("#112233"))
    window.pick_brand_color()
    assert window.brand_color == "#112233"
    window.add_custom_color()
    n0 = len(window.custom_colors)
    window.add_custom_color()  # duplicates are not repeated
    assert len(window.custom_colors) == n0
    assert window.result is not None
    window.clear_custom_colors()
    assert window.custom_colors == []
    window.set_brand_color("not-hex")
    assert window.brand_color == "#112233"  # keeps the previous one
    window.set_brand_color("")
    assert window.brand_color == ""
    from PySide6.QtWidgets import QInputDialog

    from app.presets import load_preset

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("WithFX", True))
    window.sld_grain.setValue(12)
    window.save_current_preset()
    back = load_preset("WithFX", isolated_presets)
    assert back.grain == 12.0
    window.sld_grain.setValue(0)
    window._apply_preset("WithFX")
    assert window.sld_grain.value() == 12


def test_vector_preset_roundtrip(window, isolated_presets, monkeypatch):
    """Los flags vector/GIF viven en el preset (receta), no en un panel."""
    from PySide6.QtWidgets import QInputDialog

    from app.presets import load_preset

    window._vector_export = True
    window._vector_cell = 12
    assert window.current_params().vector_export is True
    assert window.current_params().vector_cell == 12
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("WithVec", True))
    window.save_current_preset()
    back = load_preset("WithVec", isolated_presets)
    assert back.vector_export is True and back.vector_cell == 12
    window._vector_export = False
    window._apply_preset("WithVec")
    assert window._vector_export is True
    assert window._vector_cell == 12
    assert window.current_params().vector_export is True


def test_gif_preset_roundtrip(window, isolated_presets, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from app.presets import load_preset

    window._gif_export = True
    window._set_anim_combo(window.cmb_video_frames, 4)
    window._set_anim_combo(window.cmb_video_fps, 48)
    window.cmb_video_mode.setCurrentText("hue")
    assert window.current_params().gif_export is True
    assert window.current_params().gif_frames == 4
    assert window.current_params().gif_fps == 48
    assert window.current_params().gif_mode == "hue"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("WithGif", True))
    window.save_current_preset()
    back = load_preset("WithGif", isolated_presets)
    assert back.gif_export is True and back.gif_mode == "hue"
    assert back.gif_frames == 4
    assert back.gif_fps == 48
    window._gif_export = False
    window._apply_preset("WithGif")
    assert window._gif_export is True
    assert window.cmb_video_mode.currentText() == "hue"
    assert window.cmb_video_frames.currentText() == "4"
    assert window.cmb_video_fps.currentText() == "48"
    assert window.current_params().gif_frames == 4


def test_vector_export_via_dialog(window, qt_app):
    """El diálogo Export es la autoridad por operación."""
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    window._vector_export = True  # default del preset en el diálogo
    window.refresh()
    assert window.result is not None
    accept_next_dialog(ExportDialog, lambda dlg: dlg.chk_vector.setChecked(True))
    window.export()
    assert (window.out_dir / "trakkart_cover_vector.svg").exists()


def test_export_settings_follow_preset(window, isolated_presets, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from app.presets import Preset, load_preset

    assert window.current_params().export_size == 3000
    p = Preset(name="Big", export_size=1080, export_format="jpg", export_quality=80)
    from app.presets import save_preset

    save_preset(p, isolated_presets)
    window._apply_preset("Big")
    cur = window.current_params()
    assert (cur.export_size, cur.export_format, cur.export_quality) == (1080, "jpg", 80)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Big2", True))
    window.save_current_preset()
    back = load_preset("Big2", isolated_presets)
    assert (back.export_size, back.export_format) == (1080, "jpg")


def test_fx_pack_roundtrip(window, isolated_presets, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from app.presets import load_preset

    window.set_duotone_color("dark", "#112233")
    window.set_duotone_color("light", "#aabbcc")
    assert "(off)" not in window.lbl_duo.text()
    window.set_duotone_color("dark", "nope")  # inválido: se conserva
    assert window.duotone_dark == "#112233"
    window.sld_duo_mid.setValue(60)
    window.spn_poster.setValue(1)  # inválido -> 2 en current_params
    window.sld_glow.setValue(40)  # sin intensidad no hay radio
    window.spn_glowrad.setValue(12)
    window.sld_split.setValue(30)
    window.sld_fade.setValue(10)
    window.spn_glowthr.setValue(200)
    window.spn_halftone.setValue(2)  # inválido -> 3
    window.cmb_halftone.setCurrentText("lines")
    window.sld_dust.setValue(20)
    window.spn_border.setValue(8)
    window.set_border_color("#ff0000")
    window.spn_letterbox.setValue(10)
    window.spn_pixelsort.setValue(100)
    window.spn_wave.setValue(5)
    window.sld_mosh.setValue(25)
    window.spn_grille.setValue(1)  # inválido -> 2
    window.set_border_color("nope")  # inválido: se conserva
    assert window.border_color == "#FF0000"
    p = window.current_params()
    assert (p.duotone_dark, p.duotone_light, p.duotone_mid) == ("#112233", "#AABBCC", 60.0)
    assert p.posterize == 2 and p.halftone == 3 and p.grille == 2
    assert (p.split_tone, p.fade, p.dust, p.mosh) == (30.0, 10.0, 20.0, 25.0)
    assert (p.border, p.border_color, p.letterbox) == (8, "#FF0000", 10)
    assert (p.pixelsort, p.wave, p.glow_threshold) == (100, 5, 200)
    assert p.glow_radius == 12.0 and p.halftone_shape == "lines"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("WithFX2", True))
    window.save_current_preset()
    back = load_preset("WithFX2", isolated_presets)
    assert (back.posterize, back.grille, back.border) == (2, 2, 8)
    assert (back.duotone_dark, back.halftone_shape) == ("#112233", "lines")
    window.sld_split.setValue(0)
    window._apply_preset("WithFX2")
    assert window.sld_split.value() == 30
    assert window.spn_poster.value() == 2
    assert window.spn_wave.value() == 5
    assert window.duotone_light == "#AABBCC"
    assert window.lbl_duo.text() != "(off)"


def test_debounce_schedules(window):
    assert window._preview_timer.isSingleShot()
    assert window._preview_timer.interval() == 350
    window._schedule_refresh()  # schedules without crashing (the real loop fires it)
    assert window._preview_timer.isActive()
    window.refresh()  # direct call still works
    assert window.result is not None


def test_randomize_runs(window):
    window.randomize()
    assert window.result is not None
    assert "Random applied" in window.lbl_status.text()


def test_zoom_controls(window):
    window._zoom_step(1.25)
    assert window.zoom == 1.25
    window._zoom_fit()
    assert window.zoom == 1.0
    window._zoom_full()
    assert window.zoom == 4.0
    window._zoom_step(100)
    assert window.zoom == 4.0


def test_copy_and_paste(window, qt_app):
    from PySide6.QtGui import QGuiApplication, QImage

    window.refresh()
    assert window.result is not None
    window.copy_result()
    assert "clipboard" in window.lbl_status.text()
    # paste null image
    cb = QGuiApplication.clipboard()
    cb.clear()
    window.paste_image()
    assert "No image" in window.lbl_status.text()
    # paste real image
    qimg = QImage(16, 16, QImage.Format_RGB888)
    qimg.fill(0x112233)
    cb.setImage(qimg)
    window.paste_image()
    assert window.src is not None and window.src.size == (16, 16)


def test_hold_to_compare_single_canvas(window, qt_app):
    window.refresh()
    assert window.result is not None
    assert window.btn_compare.text() == "Hold to compare"
    assert "DITHER" in window.lbl_res_title.text()
    window._compare_pressed()
    assert window._comparing is True
    assert "ORIGINAL (hold)" in window.lbl_res_title.text()
    window._compare_released()
    assert window._comparing is False
    assert "DITHER" in window.lbl_res_title.text()


def test_preview_worker_runs_sync(qt_app):
    from PIL import Image as Img

    from app.ui.main_window import MainWindow  # noqa: F401  (ensures import OK)
    from app.ui.preview_worker import PreviewWorker, preview_params

    small_src = Img.new("RGB", (64, 64), (9, 9, 9))
    cols_img, px = preview_params(small_src, {"pixel_size": 2}, max_side=640)
    assert (cols_img.width, cols_img.height) == (64, 64) and px == 2
    big = Img.new("RGB", (1200, 800), (9, 9, 9))
    small, px = preview_params(big, {"pixel_size": 2})
    assert max(small.size) == 640 and px == 4  # 2 / (640/1200) = 3.75 -> 4

    got: dict = {}
    w = PreviewWorker(small_src, {
        "method": "bayer4", "palette_name": "BW", "threshold": 128, "pixel_size": 1,
        "adjust": None, "ratio": "1:1", "crop_mode": "cover", "focus_x": 50.0, "focus_y": 50.0,
        "crop_zoom": 1.0,
        "pre_blur": 0.0, "pre_sharpen": 0, "pre_hue": 0.0, "pre_denoise": 0, "pre_smooth": 0.0,
        "glow_radius": 0.0, "glow_intensity": 0.0, "grain": 0.0, "vignette": 0.0,
        "scanlines": 0, "replace_color": "", "custom_palette": None, "phase": 0,
        "glitch_chroma": 0, "glitch_slice_bands": 0, "glitch_slice_max": 24,
    }, token=7)
    w.finished_ok.connect(lambda qi, pi, t: got.update(qimg=qi, pil=pi, token=t))
    w.run()  # synchronous, no event loop
    assert got.get("token") == 7
    assert got["pil"].size == (64, 64)
    assert not got["qimg"].isNull()


def test_value_slider_dblclick_resets(window, qt_app):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    assert window.sld_thr.value() == 128
    window.sld_thr.setValue(200)
    assert window.sld_thr.defaultValue() == 128
    QTest.mouseDClick(window.sld_thr, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
    assert window.sld_thr.value() == 128


def test_preview_async_flow(window, qt_app, monkeypatch, tmp_path):
    import time as _t

    import app.accelerate as A
    from PIL import Image as Img
    from PySide6.QtCore import QCoreApplication

    monkeypatch.setattr(A, "has_numba", lambda: False)  # force the async path
    window.src = Img.new("RGB", (900, 900), (90, 60, 140))
    window.refresh()
    assert window._preview_worker is not None
    window._start_preview_async()  # already running -> stays pending
    assert window._preview_pending is True

    for _ in range(600):  # busy wait with event processing (max ~60s)
        QCoreApplication.processEvents()
        if window.result is not None and window.lbl_res_title.text().startswith("DITHER"):
            break
        _t.sleep(0.1)
    else:
        raise AssertionError("async preview did not finish")
    assert window.result is not None
    window._preview_worker.wait(5000)


def test_preview_error_path(window):
    before = window.lbl_status.text()
    window._on_preview_error("boom", token=9999)  # old token: ignored
    assert window.lbl_status.text() == before


def test_worker_run_and_error(tmp_path: Path, qt_app):
    import app.ui.workers as W
    from app.presets import Preset

    src = tmp_path / "in"
    dst = tmp_path / "dst"
    src.mkdir()
    from PIL import Image as Img

    Img.new("RGB", (32, 32), (1, 2, 3)).save(src / "x.png")
    w = W.BatchWorker(src, dst, Preset(name="t", method="bayer4", palette="BW"))
    got: dict = {}
    w.finished.connect(lambda r: got.update(results=r))
    w.run()  # synchronous on the same thread
    assert len(got["results"]) == 1

    bad = W.BatchWorker(tmp_path / "nodir", dst, Preset(name="t"))
    errs: dict = {}
    bad.error.connect(lambda m: errs.update(msg=m))
    bad.run()
    assert "msg" in errs
