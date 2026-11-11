"""Unit tests for the Roland SP-404MKII still export (128x64 1-bit BMP)."""

from PIL import Image


def _art(w=200, h=100):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, 128)
    return im


def test_sp404_frame_exact_size_and_mode():
    from app.sp404 import SP_H, SP_W, sp404_frame

    f = sp404_frame(_art())
    assert (f.width, f.height) == (SP_W, SP_H) == (128, 64)
    assert f.mode == "1"
    # Tall source also cover-fits (no bars, no distortion assert: full bleed).
    assert sp404_frame(_art(60, 300)).size == (128, 64)
    inv = sp404_frame(_art(), invert=True)
    assert inv.tobytes() != f.tobytes()
    import pytest

    with pytest.raises(ValueError):
        sp404_frame(_art().crop((0, 0, 0, 0)))  # empty image


def test_sp404_frame_threshold_direction():
    from app.sp404 import sp404_frame

    dark = Image.new("RGB", (200, 100), (10, 10, 10))
    light = Image.new("RGB", (200, 100), (250, 250, 250))
    assert set(sp404_frame(dark).get_flattened_data()) == {0}
    assert set(sp404_frame(light).get_flattened_data()) == {255}


def test_sp404_install_hint():
    from app.sp404 import install_hint

    hint = install_hint()
    assert "screen_saver_N" in hint and "SHIFT + PAD 14" in hint


def test_sp404_oled_preview_toggle(window, qt_app):
    from app.ui import compare_controller as _cc

    window.src = _art(200, 100)
    window.result = _art(200, 100)
    assert bool(getattr(window, "_sp404_preview", False)) is False
    window.act_sp404.setChecked(True)
    window.toggle_sp404_preview()
    assert window._sp404_preview is True
    _cc.paint_result(window)
    pm = window.lbl_res.pixmap()
    assert pm is not None and pm.width() == 128 and pm.height() == 64
    assert "SP-404" in window.lbl_res_title.text()
    window.act_sp404.setChecked(False)
    window.toggle_sp404_preview()
    assert window._sp404_preview is False
    _cc.paint_result(window)
    assert "SP-404" not in window.lbl_res_title.text()


def test_sp404_canvas_button(window, qt_app):
    window.btn_sp404_canvas.click()
    assert int(window.spn_canvas_w.value()) == 128
    assert int(window.spn_canvas_h.value()) == 64
    assert str(window.cmb_ratio.currentText()) == "Custom"
    # The button also shows the device view: 1-bit OLED preview on.
    assert window._sp404_preview is True
    assert window.act_sp404.isChecked() is True


def test_sp404_frame_deterministic():
    from app.sp404 import sp404_frame

    assert sp404_frame(_art()).tobytes() == sp404_frame(_art()).tobytes()


def test_export_full_sp404_single(tmp_path):
    from app.exporter import ExportSelection
    from app.presets import Preset
    from app.services.export_service import export_full

    preset = Preset(name="t", method="bayer8", palette="BW", export_size=64)
    sel = ExportSelection(
        image=True, thumb_1080p=False, vector=False, anim=False, metadata=False)
    paths, skipped = export_full(
        _art(64, 64), preset, tmp_path / "os", base="m",
        selection=sel, sp404=True)
    singles = [p for p in paths.values() if str(p).endswith("_sp404.bmp")]
    assert len(singles) == 1 and singles[0].name == "m_sp404.bmp"
    assert skipped == []
    from PIL import Image as _Image

    with _Image.open(singles[0]) as im:
        assert im.size == (128, 64) and im.mode == "1"


def test_export_dialog_sp404_checkbox(window, qt_app, tmp_path):
    from app.presets import Preset
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    window.src = _art(64, 64)
    preset = Preset(name="t", method="bayer8", palette="BW", export_size=64)
    dlg = ExportDialog(window.src, preset.meta(), base="m", out_dir=str(tmp_path),
                       preset=preset, gif_frames=2)
    try:
        assert dlg.chk_sp404.isChecked() is False
        assert dlg._gif_opts()["sp404"] is False
        dlg.chk_sp404.setChecked(True)
        assert dlg._gif_opts()["sp404"] is True
        assert any("_sp404.bmp" in dlg.list_files.item(i).text()
                   for i in range(dlg.list_files.count()))
    finally:
        close_dialog(dlg)
