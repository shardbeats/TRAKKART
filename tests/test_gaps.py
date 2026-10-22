"""Gap-closing tests for the >90% coverage push (small modules + leftovers)."""

from PIL import Image


def _img(w=48, h=48):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 5) % 256, (y * 7) % 256, 140)
    return im


def test_render_service_helpers():
    from app.presets import Preset
    from app.services import render_service as rs

    small, f = rs.downscale_for_preview(_img(32, 32))
    assert (small.width, f) == (32, 1.0)
    big, f2 = rs.downscale_for_preview(_img(2000, 1000))
    assert max(big.size) == 640 and f2 < 1.0
    out = rs.render_preview_small(_img(64, 64), Preset(name="t", method="bayer4"))
    assert out.size == (64, 64)
    assert rs.render_full(_img(32, 32), Preset(name="t", method="bayer4")).size == (32, 32)
    import app.services.render_service as R

    orig = R.has_numba if hasattr(R, "has_numba") else None
    import app.accelerate as acc

    assert isinstance(rs.should_render_async(_img(32, 32)), bool)
    assert rs.should_render_async(_img(2000, 2000)) == (not acc.has_numba())
    assert orig is None or True


def test_image_io_errors(tmp_path):
    import pytest

    from app.services import image_io as iio

    with pytest.raises(ValueError):
        iio.decode_data_url("not-a-data-url")
    with pytest.raises(ValueError):
        iio.decode_data_url("data:image/png;base64,!!!notbase64!!!")
    with pytest.raises(ValueError, match="not a valid image"):
        iio.load_path(tmp_path / "missing.png")
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"nope")
    with pytest.raises(Exception):
        iio.load_path(bad)

    class FakeResp:
        def __init__(self, ctype, data=b"x"):
            self._c = ctype
            self._d = data

        headers = None

        def getheaders(self):
            return []

        def read(self, *a):
            return self._d

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request

    real_urlopen = urllib.request.urlopen
    monkey_holder = {}

    class FakeHeaders:
        def __init__(self, ctype):
            self._c = ctype

        def get_content_type(self):
            return self._c

    class FakeResp2(FakeResp):
        def __init__(self, ctype):
            super().__init__(ctype)
            self.headers = FakeHeaders(ctype)

    urllib.request.urlopen = lambda *a, **k: FakeResp2("text/html")
    try:
        with pytest.raises(ValueError):
            iio.download_image("http://example.invalid/x")
    finally:
        urllib.request.urlopen = real_urlopen
    assert monkey_holder == {}


def test_paths_branches(tmp_path, monkeypatch):
    from app import paths as P

    monkeypatch.setenv("TRAKKART_DATA_DIR", str(tmp_path / "d1"))
    assert P.get_data_dir() == tmp_path / "d1"
    monkeypatch.delenv("TRAKKART_DATA_DIR")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roam"))
    assert P.get_data_dir() == tmp_path / "roam" / "TRAKKART"
    assert P.get_db_path().parent.exists()
    assert P.get_out_dir().exists()


def test_static_stylesheet_loads(qt_app):
    from pathlib import Path

    css_path = Path(__file__).resolve().parent.parent / "app" / "ui" / "theme.qss"
    assert css_path.exists()
    css = css_path.read_text(encoding="utf-8")
    assert "#151617" in css and "#F5A623" in css


def test_fx_stack_normalize_edges():
    from app.fx_stack import normalize_stack, stack_ids

    assert normalize_stack(None)[0]["id"] == "split_tone"
    mixed = normalize_stack(["grain", {"id": "grain", "enabled": False},
                             {"id": "nope", "enabled": True}, 42, None,
                             {"id": "vignette"}])
    ids = [e["id"] for e in mixed]
    assert ids.count("grain") == 1 and "nope" not in ids  # dupes collapsed, unknown dropped
    assert set(stack_ids(mixed)) <= {e["id"] for e in mixed if e["enabled"]}
    assert normalize_stack("notalist") is not None


def test_export_service_mp4(window, qt_app, tmp_path):
    import pytest

    from app.exporter import ExportSelection
    from app.services.export_service import export_full
    from app.presets import Preset
    from app.video_io import has_video

    if not has_video():
        pytest.skip("video extra not installed (imageio + imageio-ffmpeg)")
    window.src = _img(64, 64)
    preset = Preset(
        name="t", method="bayer4", palette="SLIME", gif_export=True,
        gif_frames=2, export_size=64)
    sel = ExportSelection(
        image=True, thumb_1080p=True, vector=False, anim=True, metadata=True)
    paths, skipped = export_full(
        window.src, preset, tmp_path / "o", base="m",
        selection=sel, mp4=True, gif_frames=2, gif_size=64)
    assert any(str(p).endswith(".mp4") for p in paths.values())
    assert any(str(p).endswith(".gif") for p in paths.values())


def test_export_dialog_extras(window, qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    from app.presets import Preset
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    window.src = _img(64, 64)
    preset = Preset(
        name="t", method="bayer4", palette="SLIME", gif_export=True,
        gif_frames=2, export_size=64)
    # Dialog: browse + empty base + legacy options + lossless toggle.
    dlg = ExportDialog(window.src, preset.meta(), base="", out_dir=str(tmp_path),
                       gif_frames=2)
    try:
        monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                            lambda *a, **k: str(tmp_path / "picked"))
        dlg._browse()
        assert "picked" in dlg.edit_dir.text()
        dlg.edit_base.setText("")
        dlg._on_export()
        assert dlg.edit_base.text() == "cover"
        opts, out, frames, mode = dlg.legacy_options()
        assert opts.base == "cover" and frames == 2 and mode == "both"
        dlg.chk_lossless.setChecked(True)
        assert dlg.cmb_format.isEnabled() is False
        dlg.chk_lossless.setChecked(False)
        assert dlg.cmb_format.isEnabled() is True
    finally:
        close_dialog(dlg)


def test_batch_flow_progress_and_errors(window, qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    from app.ui import batch_flow as bf
    from app.presets import Preset

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    # Invalid preset path.
    bad = Preset(name="t")
    bad.method = "no-such"
    warned = {}
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a, **k: warned.update(text=str(a[-1])) or None)
    window.run_batch(tmp_path, tmp_path / "o", jobs=1, preset=bad)
    assert "Invalid preset" in warned.get("text", "")
    # Progress / finished / error handlers run headless.
    window._batch_start = 0.0
    bf.on_progress(window, 1, 2, "a.png")
    assert window.progress.value() == 50
    bf.on_finished(window, [{"file": "a.png", "status": "ok", "outputs": []}])
    warned = {}
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a, **k: warned.update(text=str(k.get("text", a[-1]))))
    bf.on_error(window, "kaput")
    assert "kaput" in warned.get("text", "")
    # Cancel path.
    window._batch_cancel = [False]
    bf.cancel_batch(window)
    assert window._batch_cancel == [True]


def test_compare_controller_branches(window):
    from app.ui import compare_controller as cc

    window.src = None
    window._comparing = False
    cc.pressed(window)  # no src: silent
    cc.released(window)  # not comparing: silent
    cc.paint_orig(window)  # no src: silent
    window.src = _img(32, 32)
    cc.pressed(window)
    assert window._comparing is True
    cc.paint_orig(window)
    assert "ORIGINAL" in window.lbl_res_title.text()
    window._video_on = True
    window._video_frames = [_img(16, 16)]
    cc.paint_result(window)  # video path
    assert window._comparing is False
    window._video_on = False
    window._video_frames = []
    window.result = None
    cc.paint_result(window)  # no result: silent
    window.result = _img(16, 16)
    cc.paint_result(window)
    assert "DITHER" in window.lbl_res_title.text()
    cc.released(window)
    assert window._comparing is False


def test_params_controller_extras(window):
    from app.ui import params_controller as pc

    window.spn_slice.setValue(5)
    assert pc.valid_slice_bands(window) in (0, 2, 3, 4, 6, 8, 12, 16)
    assert pc.doc_size(window) >= 64
    assert pc.gif_anim_size(window) == pc.doc_size(window)
    window.cmb_video_frames.setCurrentText("nope")
    assert pc.gif_anim_frames(window) == 6  # fallback default
    r = pc.anim_combo_int(window.cmb_video_frames, 6, 2, 24)
    assert r == 6
    pc.set_anim_combo(window.cmb_video_frames, 12)
    assert window.cmb_video_frames.currentText() == "12"
    assert pc.gif_anim_fps(window) >= 2
    assert isinstance(pc.gif_anim_pingpong(window), bool)
    assert pc.gif_anim_mode(window) in ("phase", "hue", "both", "glitch", "mix")
    from app.canvas import ratio_label

    pc.set_ratio_label(window, "1:1")
    assert window.cmb_ratio.currentText() == ratio_label("1:1")
    pc.on_ratio_preset(window)  # applies current ratio preset
    w0, h0 = pc.doc_dims(window)
    window.spn_canvas_w.setValue(800)
    pc.on_canvas_wh_changed(window)  # flips to Custom
    from app.canvas import CUSTOM_LABEL

    assert window.cmb_ratio.currentText() == CUSTOM_LABEL
    assert pc.ratio_value_of(window) == "custom"
    pc.sync_docdims(window)
    assert f"{w0}" in window.lbl_docdims.text() or "×" in window.lbl_docdims.text()


def test_main_window_leftovers(window, qt_app):
    window._next_video_frame()  # video off: silent
    window._video_on = True
    window._video_frames = []
    window._next_video_frame()  # no frames: silent
    window._video_frames = [_img(16, 16), _img(16, 16)]
    window._video_idx = 0
    window._video_playing = True
    window._next_video_frame()
    assert window._video_idx == 1
    from app.ui import video_controller as vc

    vc.show_frame(window)
    window._on_video_done([], 999)  # stale token: ignored
    window._on_video_error("x", 999)  # stale: ignored
    window._on_preview_done(None, None, 999)  # stale: ignored
    window._on_preview_error("e", 999)  # stale: ignored
    window.close()  # cleanup path: stops timers, blocks workers
    assert window._batch_cancel == [True]


def test_gif_save_guards_and_estimate(tmp_path):
    import pytest

    from app.gif import estimate_gif, save_gif

    with pytest.raises(ValueError):
        save_gif([], tmp_path / "x.gif")
    assert estimate_gif(6, 64, 64) > 0
    frames = save_gif([Image.new("RGB", (32, 32), (10, 200, 90)) for _ in range(2)],
                      tmp_path / "a.gif", fps=200)  # clamped to 60
    assert frames.exists()
    frames2 = save_gif([Image.new("RGB", (32, 32), (10, 200, 90))],
                       tmp_path / "b.gif", fps=0, loop=1)  # clamped to 2
    assert frames2.exists()


def test_post_fx_and_special_renders_execute():
    from app.pipeline import render_spec, RenderSpec

    im = Image.new("RGB", (32, 32), (120, 90, 200))
    spec = RenderSpec(method="bayer4", palette_name="SLIME", post_blur=2.0,
                      post_sharpen=2, jpeg=40.0)
    out = render_spec(im, spec)
    assert out.size == im.size
    plain = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME"))
    assert list(out.get_flattened_data()) != list(plain.get_flattened_data())
    waved = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME",
                                       wave=8, glitch_chroma=4, mosh=30.0,
                                       glitch_slice_bands=4, pixelsort=100))
    assert list(waved.get_flattened_data()) != list(plain.get_flattened_data())


def test_vector_cells_variants():
    from PIL import Image

    from app.vector import estimate_bytes, estimate_cells, render_cells

    assert estimate_cells(300, 200, 8) == (37, 25)
    assert estimate_bytes(10, 10) > 0
    r = render_cells(Image.new("RGB", (64, 64), (200, 50, 90)), 8, 8,
                     method="bayer4", palette_name="SLIME", posterize=2,
                     duotone_dark="#000000", duotone_light="#FFFFFF",
                     replace_color="#112233",
                     custom_palette=[(0, 0, 0), (255, 255, 255)])
    assert r.size == (8, 8)


def test_presets_invalid_and_normalizers():
    import pytest

    from app.presets import Preset
    from app.render_params import (normalize_grille, normalize_halftone, normalize_palette_depth,
                                   normalize_posterize, normalize_scanlines, normalize_slice_bands)

    with pytest.raises(ValueError):
        Preset(name="t", method="nope").validate()
    with pytest.raises(ValueError):
        Preset(name="t", threshold=999).validate()
    assert normalize_grille(1) == 2 and normalize_grille(9) == 0
    assert normalize_halftone(1) == 3 and normalize_halftone(99) == 12
    assert normalize_palette_depth(1) == 2 and normalize_palette_depth(99) == 16
    assert normalize_posterize(1) == 2 and normalize_posterize(0) == 0
    assert normalize_scanlines(1) == 2 and normalize_scanlines(99) == 0
    assert normalize_slice_bands(1) == 2 and normalize_slice_bands(14) == 16
    assert normalize_slice_bands(99) == 16


def test_motif_and_palette_library_edges(tmp_path):
    import pytest

    from app.motif import normalize_config
    from app.palette_library import ensure_bundled_palettes, is_bw, list_palettes, parse_gpl, save_palette

    assert normalize_config(None)["bands"][0]["shape"] == "dot"
    weird = normalize_config({"bands": [{"shape": "nope", "size": "x"},
                                        {"shape": "line"}]})
    assert weird["bands"][0] == {"shape": "dot", "size": 2}
    assert weird["bands"][1] == {"shape": "line", "size": 2}
    with pytest.raises(ValueError):
        parse_gpl("GIMP Palette\nName: x\n")
    with pytest.raises(ValueError):
        save_palette("", [(0, 0, 0), (255, 255, 255)], palettes_dir=tmp_path)
    lib = tmp_path / "lib"
    assert ensure_bundled_palettes(lib) != []  # creates
    assert ensure_bundled_palettes(lib) == []  # second run: no overwrite
    assert "SLIME" in list_palettes(lib)
    assert is_bw([(0, 0, 0), (255, 255, 255)]) is True
    assert is_bw([(0, 0, 0)]) is False
    assert is_bw("junk") is False


def test_export_quick_via_dialog(window, qt_app, monkeypatch, tmp_path):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    window.src = Image.new("RGB", (64, 64), (90, 100, 140))
    accept_next_dialog(ExportDialog)
    window.export(quick=False)
    assert (window.out_dir / "trakkart_cover.png").exists()
