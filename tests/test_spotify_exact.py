"""Spotify Canvas strictness: exact 9:16 helpers + preset + export snap.

Spotify rejects inexact ratios ("wrong ratio") while reading its own
"720-1080px tall" rule literally (1080x1920 = 1920 tall is rejected,
576x1024 uploads fine). The legacy default `canvas_size_for("9:16",
3000) == (1688, 3000)` is inexact and stays pinned untouched; the
exact path below only runs at export (MP4) plus one opt-in preset.
"""

from app.canvas import (
    canvas_size_for,
    exact_canvas_size_for,
    is_exact_ratio,
    snap_to_exact_ratio,
)


def _exact_916(w: int, h: int) -> bool:
    return w % 2 == 0 and h % 2 == 0 and w * 16 == h * 9


def test_legacy_default_untouched():
    # The default never moves (presets/docs/7+ tests pin it).
    assert canvas_size_for("9:16", 3000) == (1688, 3000)
    assert not _exact_916(1688, 3000)


def test_is_exact_ratio():
    assert is_exact_ratio(576, 1024, "9:16")
    assert is_exact_ratio(1080, 1920, "9:16")
    assert not is_exact_ratio(1688, 3000, "9:16")
    assert not is_exact_ratio(608, 1080, "9:16")
    assert is_exact_ratio(1080, 1080, "1:1")
    assert not is_exact_ratio(0, 0, "9:16")
    assert not is_exact_ratio(100, 100, "nope")


def test_exact_canvas_size_for():
    # Nearest exact even pair; 3000 is not a multiple of 32 so exact
    # neighbours are 1674x2976 (m=93) and 1692x3008 (m=94, nearer).
    assert exact_canvas_size_for("9:16", 3000) == (1692, 3008)
    assert exact_canvas_size_for("9:16", 1024) == (576, 1024)
    assert exact_canvas_size_for("9:16", 1920) == (1080, 1920)
    assert exact_canvas_size_for("1:1", 3000) == (3000, 3000)
    for long in (720, 1024, 1080, 1920, 3000):
        w, h = exact_canvas_size_for("9:16", long)
        assert _exact_916(w, h), (long, w, h)
    # over=False never grows the request (720p/1080p budgets).
    assert exact_canvas_size_for("9:16", 1080, over=False) == (594, 1056)
    assert exact_canvas_size_for("9:16", 720, over=False) == (396, 704)
    w, h = exact_canvas_size_for("9:16", 1080, over=False)
    assert max(w, h) <= 1080


def test_snap_to_exact_ratio():
    # Exact docs pass through; inexact ~9:16 snaps; far ratios untouched.
    assert snap_to_exact_ratio(576, 1024, "9:16") == (576, 1024)
    assert snap_to_exact_ratio(1080, 1920, "9:16") == (1080, 1920)
    assert snap_to_exact_ratio(1688, 3000, "9:16") == (1692, 3008)
    assert snap_to_exact_ratio(1000, 1000, "9:16") == (1000, 1000)
    assert snap_to_exact_ratio(3000, 3000, "1:1") == (3000, 3000)


def test_mp4_dims_legacy_untouched_and_exact_variant():
    from app.gif import mp4_dims, mp4_dims_exact

    # Legacy keeps its rounding (even, usually inexact) everywhere.
    assert mp4_dims(1080, 1920, "Canvas") == (1080, 1920)
    assert mp4_dims(1688, 3000, "1080p") == (608, 1080)
    assert not _exact_916(*mp4_dims(1688, 3000, "1080p"))
    # Exact variant: Canvas snaps nearest, budgets snap down, rest intact.
    assert mp4_dims_exact(1688, 3000, "Canvas") == (1692, 3008)
    assert mp4_dims_exact(1688, 3000, "1080p") == (594, 1056)
    assert mp4_dims_exact(1688, 3000, "720p") == (396, 704)
    assert mp4_dims_exact(1080, 1920, "Canvas") == (1080, 1920)
    assert mp4_dims_exact(576, 1024, "Canvas") == (576, 1024)
    assert mp4_dims_exact(3000, 3000, "1080p") == (1080, 1080)
    assert mp4_dims_exact(3000, 2000, "1080p") == mp4_dims(3000, 2000, "1080p")
    for w, h in (mp4_dims_exact(1688, 3000, "Canvas"),
                 mp4_dims_exact(1688, 3000, "1080p")):
        assert _exact_916(w, h)


def test_spotify_preset_recipe():
    # 576x1024 exact + mid-window 3-8s loop (uploads where 1080x1920 fails).
    import tempfile
    from pathlib import Path

    from app.gif import plan_dissolve
    from app.presets import ensure_bundled, load_preset

    with tempfile.TemporaryDirectory() as d:
        ensure_bundled(Path(d))
        p = load_preset("SPOTIFY_916", Path(d))
        p.validate()
        assert (p.ratio, p.export_size) == ("9:16", 1024)
        from app.canvas import doc_dimensions

        assert doc_dimensions(p.ratio, p.export_size, p.canvas_w, p.canvas_h) == (576, 1024)
        assert (p.gif_mode, p.gif_frames, p.gif_fps) == ("dissolve", 64, 30)
        plan = plan_dissolve(p.gif_frames, 1, p.gif_fps, p.dissolve_hold, None)
        assert 3.0 <= plan["actual_s"] <= 7.9


def test_export_service_mp4_ships_exact_916(tmp_path):
    import pytest

    from app.exporter import ExportSelection
    from app.presets import Preset
    from app.services.export_service import export_full
    from app.video_io import has_video

    if not has_video():
        pytest.skip("video extra not installed (imageio + imageio-ffmpeg)")
    import imageio.v3 as iio
    from PIL import Image

    # 422x750 is ~9:16 but inexact (422*16 != 750*9); the MP4 must ship
    # the nearest exact even pair (414x736), not legacy even-down.
    src = Image.new("RGB", (422, 750), (90, 40, 140))
    preset = Preset(name="t", method="bayer4", palette="SLIME",
                    gif_export=True, gif_frames=2,
                    ratio="9:16", export_size=3000)
    sel = ExportSelection(image=False, thumb_1080p=False, vector=False,
                          anim=False, metadata=False)
    paths, _ = export_full(src, preset, tmp_path / "o", base="sp",
                           selection=sel, mp4=True, gif_frames=2,
                           gif_size=64, mp4_size="Canvas")
    frame = iio.imread(str(paths["video"]), index=0)
    h, w = int(frame.shape[0]), int(frame.shape[1])
    assert (w, h) == (414, 736)
    assert w * 16 == h * 9
