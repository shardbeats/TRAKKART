"""Polish (R12 safe areas + R13 wipe compare)."""

from PIL import Image


def _flat(w, h, color):
    return Image.new("RGB", (w, h), color)


def test_safe_geometry():
    from app.ui.safeareas import TOP_FRAC, band_rows, is_916

    assert is_916(1080, 1920) is True
    assert is_916(1080, 1081) is False
    assert is_916(0, 0) is False
    assert band_rows(1920) == (250, 250)
    assert abs(TOP_FRAC - 250 / 1920) < 1e-9


def test_paint_guides_bands_only_916(qt_app):
    from PySide6.QtGui import QImage, QPixmap

    from app.ui.safeareas import paint_guides

    def white(w, h):
        img = QImage(w, h, QImage.Format_RGB888)
        img.fill(0xFFFFFF)
        return QPixmap.fromImage(img.copy())

    guided = paint_guides(white(90, 160))
    back = guided.toImage()
    assert back.pixelColor(45, 2).red() < 200  # inside top chrome
    assert back.pixelColor(45, 80).red() == 255  # middle untouched
    assert back.pixelColor(45, 157).red() < 200  # inside bottom chrome
    plain = paint_guides(white(100, 100))
    assert plain.toImage().pixelColor(50, 2).red() == 255  # 1:1 untouched


def test_result_guides_toggle(window, qt_app):
    from app.ui import compare_controller as cc

    window.src = _flat(90, 160, (200, 100, 50))
    window.result = _flat(90, 160, (200, 100, 50))
    window._show_safe = True
    cc.paint_result(window)
    assert "DITHER" in window.lbl_res_title.text()
    px = window.lbl_res.pixmap().toImage()
    assert px.pixelColor(45, 2).red() < 200
    window._show_safe = False
    cc.paint_result(window)
    assert window.lbl_res.pixmap().toImage().pixelColor(45, 2).red() == 200
    assert window.act_safe.isCheckable() is True
    window.act_safe.setChecked(False)
    window.toggle_safe_areas()
    assert window._show_safe is False
    assert "DITHER" in window.lbl_res_title.text()


def test_wipe_divider_and_extremes(window, qt_app):
    from app.ui import compare_controller as cc

    window.src = _flat(64, 64, (255, 0, 0))
    window.result = _flat(64, 64, (0, 0, 255))
    window.sld_wipe.setValue(0)
    cc.paint_wipe(window)
    assert "DITHER" in window.lbl_res_title.text()
    window.sld_wipe.setValue(50)
    window._on_wipe_changed()
    assert window.lbl_res_title.text().startswith("WIPE 50%")
    px = window.lbl_res.pixmap().toImage()
    assert px.pixelColor(5, 32).red() > 200  # ORIGINAL (red) left
    assert px.pixelColor(58, 32).blue() > 200  # result (blue) right
    assert cc.wipe_pos(window) == 50
    # Hold wins over wipe while held; video ignores wipe.
    window._compare_pressed()
    assert "ORIGINAL" in window.lbl_res_title.text()
    cc.wipe(window)
    assert "ORIGINAL" in window.lbl_res_title.text()
    window._compare_released()
    assert window.lbl_res_title.text().startswith("WIPE 50%")  # release returns to wipe
    window._video_on = True
    before = window.lbl_res_title.text()
    cc.paint_wipe(window)
    assert window.lbl_res_title.text() == before  # video ignores wipe
    window._video_on = False


def test_wipe_100_keeps_canvas_geometry_and_guides(window, qt_app):
    from app.canvas import to_canvas
    from app.ui import compare_controller as cc

    window._show_safe = True
    window.cmb_ratio.setCurrentText("9:16")
    window._on_ratio_preset()
    window.src = _flat(90, 120, (255, 0, 0))  # raw 3:4
    window.result = to_canvas(window.src, ratio="9:16")  # framed 9:16
    cc.paint_wipe(window, 99)
    p99 = window.lbl_res.pixmap().size().toTuple()
    cc.paint_wipe(window, 100)
    assert window.lbl_res_title.text().startswith("WIPE 100%")
    p100 = window.lbl_res.pixmap().size().toTuple()
    assert p100 == p99  # framed original, never the raw 90x120 source
    assert p100 != (90, 120)
    top = window.lbl_res.pixmap().toImage().pixelColor(30, 2)
    assert top.red() < 200  # safe-area guides stay on the wipe


def test_aligned_orig_cache_invalidates_on_canvas_change(window):
    from app.ui import compare_controller as cc

    window.cmb_ratio.setCurrentText("9:16")
    window._on_ratio_preset()
    window.src = _flat(90, 120, (255, 0, 0))
    first = cc._aligned_orig(window)
    again = cc._aligned_orig(window)
    assert again is first  # wipe drags reuse the aligned frame
    window.cmb_crop.setCurrentText("contain")
    assert cc._aligned_orig(window) is not first


def test_f1_morph_combos_cover_modes(window, qt_app):
    from app.disintegrate import DISINTEGRATE_MODES, EASE_MODES, STAGGER_MODES
    from app.presets import Preset

    modes = [window.cmb_dissolve_mode.itemText(i) for i in range(window.cmb_dissolve_mode.count())]
    assert modes == list(DISINTEGRATE_MODES) and len(modes) == 11
    assert [window.cmb_dissolve_stagger.itemText(i)
            for i in range(window.cmb_dissolve_stagger.count())] == list(STAGGER_MODES)
    assert [window.cmb_dissolve_ease.itemText(i)
            for i in range(window.cmb_dissolve_ease.count())] == list(EASE_MODES)
    # New fields round-trip through the widgets into a preset.
    window.cmb_dissolve_mode.setCurrentText("vortex")
    window.cmb_dissolve_stagger.setCurrentText("sweep")
    window.cmb_dissolve_ease.setCurrentText("linear")
    from app.ui import params_controller as _par

    p = _par.build_params(window) if hasattr(_par, "build_params") else Preset(name="t")
    assert (p.dissolve_mode, p.dissolve_stagger, p.dissolve_ease) == ("vortex", "sweep", "linear")


def test_crop_dialog_safe_flag(window, qt_app):
    from app.ui.crop_editor import CropEditorDialog

    dlg = CropEditorDialog(_flat(64, 64, (10, 20, 30)), parent=window)
    try:
        assert dlg.view.show_safe is True
    finally:
        dlg.deleteLater()
    dlg2 = CropEditorDialog(_flat(64, 64, (10, 20, 30)), parent=window, show_safe=False)
    try:
        assert dlg2.view.show_safe is False
    finally:
        dlg2.deleteLater()
