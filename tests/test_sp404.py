"""Unit tests for the Roland SP-404MKII image pack (startup + screensaver)."""

from pathlib import Path

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


def test_sp404_pack_names_counts_and_bmp():
    import tempfile

    from app.sp404 import README_NAME, STARTUP_NAMES, write_sp404_pack

    imgs = [_art(200 + i * 7, 100) for i in range(20)]  # over the caps
    with tempfile.TemporaryDirectory() as d:
        out = write_sp404_pack(imgs, Path(d))
        assert [k for k in out if k.startswith("startup")] == list(STARTUP_NAMES)
        shots = [k for k in out if k.startswith("screen_saver")]
        assert len(shots) == 16
        assert shots[0] == "screen_saver_1.bmp" and shots[-1] == "screen_saver_16.bmp"
        assert README_NAME in out
        for name, path in out.items():
            assert path.exists()
            if name.endswith(".bmp"):
                with Image.open(path) as im:
                    assert im.size == (128, 64)
                    assert im.mode == "1"
        assert "SHIFT + PAD 14" in (Path(d) / README_NAME).read_text(encoding="utf-8")


def test_sp404_pack_single_image_and_errors():
    import tempfile

    import pytest

    from app.sp404 import STARTUP_NAMES, screen_saver_name, write_sp404_pack

    with tempfile.TemporaryDirectory() as d:
        out = write_sp404_pack([_art()], Path(d))
        assert list(out) == [STARTUP_NAMES[0], "README-SP404.txt"]
    with pytest.raises(ValueError):
        write_sp404_pack([], Path("unused"))
    with pytest.raises(ValueError):
        screen_saver_name(0)
    with pytest.raises(ValueError):
        screen_saver_name(17)
    assert screen_saver_name(16) == "screen_saver_16.bmp"


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


def test_sp404_pack_deterministic():
    import tempfile

    from app.sp404 import write_sp404_pack

    imgs = [_art(160, 120), _art(120, 160)]
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        a = write_sp404_pack(imgs, Path(d1))
        b = write_sp404_pack(imgs, Path(d2))
        assert a.keys() == b.keys()
        for k in a:
            assert a[k].read_bytes() == b[k].read_bytes()


def test_export_full_sp404_pack(tmp_path):
    from app.exporter import ExportSelection
    from app.presets import Preset
    from app.services.export_service import export_full

    preset = Preset(name="t", method="bayer8", palette="BW", export_size=64)
    sel = ExportSelection(
        image=True, thumb_1080p=False, vector=False, anim=False, metadata=False)
    paths, skipped = export_full(
        _art(64, 64), preset, tmp_path / "os", base="m",
        selection=sel, sp404=True)
    bmps = sorted(str(p) for p in paths.values() if str(p).endswith(".bmp"))
    assert any("startup_1.bmp" in p for p in bmps)
    assert all("m_sp404" in p for p in bmps)
    assert skipped == []
    from PIL import Image as _Image

    with _Image.open(next(
            p for p in paths.values()
            if str(p).endswith("startup_1.bmp"))) as im:
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
        assert any("_sp404_" in dlg.list_files.item(i).text()
                   for i in range(dlg.list_files.count()))
    finally:
        close_dialog(dlg)
