"""Pins for the clip MP4 resolution/quality selector.

Proxy stays the default (720p session frames, q8); Source re-decodes
at native size (≤1920) and quality maps to the measured imageio q
curve (q5 ~0.5x, q10 ~1.5x of q8). No threads asserted here.
"""

from __future__ import annotations


def _mov(path, n=6, size=(320, 240), fps=10):
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("imageio_ffmpeg")
    import numpy as np
    from PIL import Image as Img
    import imageio.v2 as iio2

    wr = iio2.get_writer(str(path), fps=fps, codec="libx264", quality=8,
                         macro_block_size=2)
    for i in range(n):
        wr.append_data(np.asarray(Img.new("RGB", size, (i * 40 % 256, 30, 90))))
    wr.close()


def test_estimate_scales_with_quality():
    from app.gif import estimate_clip_mp4

    compact = estimate_clip_mp4(720, 405, 10, 30, 5)
    balanced = estimate_clip_mp4(720, 405, 10, 30, 8)
    high = estimate_clip_mp4(720, 405, 10, 30, 10)
    assert 0 < compact < balanced < high
    assert abs(compact / balanced - 0.5) < 0.05
    assert abs(high / balanced - 1.5) < 0.05


def test_source_dims_probe(tmp_path):
    from PIL import Image as Img

    from app.clip import source_dims

    g = tmp_path / "a.gif"
    frames = [Img.new("RGB", (160, 90), (i * 20, 10, 10)) for i in range(3)]
    frames[0].save(str(g), save_all=True, append_images=frames[1:])
    assert source_dims(g) == (160, 90)
    assert source_dims(tmp_path / "missing.mp4") is None


def test_source_dims_mp4(tmp_path):
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("imageio_ffmpeg")
    from app.video_io import has_video

    if not has_video():
        pytest_mod.skip("no video backend")
    from app.clip import source_dims

    p = tmp_path / "s.mp4"
    _mov(p)
    assert source_dims(p) == (320, 240)


def test_trim_source_renders_native(tmp_path):
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("imageio_ffmpeg")
    from app.video_io import has_video

    if not has_video():
        pytest_mod.skip("no video backend")
    from app.clip import (CLIP_PROXY_SIDE, CLIP_SOURCE_SIDE,
                          import_clip, iter_dither_trim_source, iter_source_frames)
    from app.presets import Preset

    p = tmp_path / "s.mp4"
    _mov(p, n=8, size=(1280, 720))
    frames, info = import_clip(p)
    assert frames[0].width <= CLIP_PROXY_SIDE
    native = list(iter_source_frames(p, 0.0, 2, CLIP_SOURCE_SIDE))
    assert native and native[0].width > frames[0].width
    preset = Preset()
    got = list(iter_dither_trim_source(p, preset, float(info["start_s"] or 0.0),
                                       0, 3, CLIP_SOURCE_SIDE, 300, None))
    from app.clip import iter_dither_clip

    proxy = list(iter_dither_clip(frames[:3], preset))
    assert len(got) == 3
    assert got[0].size == (720, 720)  # canvas 1:1 crop of the 1280x720 native
    assert proxy[0].size == (404, 404)  # same crop of the 720p session proxy
    assert got[0].size[0] > proxy[0].size[0]


def test_video_quality_orders_bytes(tmp_path):
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("imageio_ffmpeg")
    from app.video_io import has_video

    if not has_video():
        pytest_mod.skip("no video backend")
    import numpy as np
    from PIL import Image as Img

    from app.video_io import write_mp4_iter

    rng = np.random.default_rng(7)
    frames = [Img.fromarray((rng.random((64, 64, 3)) * 255).astype("uint8"))
              for _ in range(3)]
    sizes = {}
    for q in (5, 8, 10):
        out = tmp_path / f"q{q}.mp4"
        write_mp4_iter(iter(frames), out, fps=10, quality=q)
        sizes[q] = out.stat().st_size
    assert sizes[5] < sizes[8] < sizes[10]


def test_dialog_defaults_proxy_balanced(qt_app, tmp_path):
    from app.ui.export_dialog import ExportDialog
    from PIL import Image as Img

    img = Img.new("RGB", (64, 64), (10, 20, 30))
    ci = {"name": "v", "frames": 10, "fps": 10, "start": 0, "end": 9,
          "span": 10, "duration": 1.0, "start_s": 0.0, "truncated": False,
          "path": "", "size": [320, 240]}
    dlg = ExportDialog(img, {"ratio": "1:1"}, base="d", out_dir=str(tmp_path),
                       clip_info=ci, clip_fps=10)
    assert dlg._clip_res() == "proxy"
    assert dlg._clip_q() == 8
    opts = dlg.clip_options()
    assert opts is None  # nothing checked -> no clip export
    dlg.chk_clip_mp4.setChecked(True)
    opts = dlg.clip_options()
    assert opts["res"] == "proxy" and opts["quality"] == 8
    dlg.cmb_clip_q.setCurrentIndex(2)
    assert dlg._clip_q() == 10
    rows = [dlg.list_files.item(i).text() for i in range(dlg.list_files.count())]
    mp4_rows = [r for r in rows if r.startswith("d_clip.mp4")]
    assert len(mp4_rows) == 1
    assert "720p" in mp4_rows[0] and "q10" in mp4_rows[0]
