"""Motion from stills: Signal Drift, Paste-Up, MP4 backend.

(No timeline layers, no clip import: animation always runs over the
still image via GIF modes + drift + phase.)
"""

from PIL import Image


def _img(size=48):
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    return im


def test_drift_off_is_noop_and_unknown_safe():
    from app.drift import DRIFT_PATTERNS, apply_drift

    assert len(DRIFT_PATTERNS) == 9
    im = _img()
    assert list(apply_drift(im, "off", 80).get_flattened_data()) == list(im.get_flattened_data())
    assert list(apply_drift(im, "snow", 0).get_flattened_data()) == list(im.get_flattened_data())
    assert list(apply_drift(im, "nope", 80).get_flattened_data()) == list(im.get_flattened_data())


def test_drift_deterministic_and_phased():
    from app.drift import apply_drift

    im = _img()
    a = apply_drift(im, "snow", 60, phase=0)
    b = apply_drift(im, "snow", 60, phase=0)
    c = apply_drift(im, "snow", 60, phase=3)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    assert list(a.get_flattened_data()) != list(im.get_flattened_data())
    assert list(a.get_flattened_data()) != list(c.get_flattened_data())
    for p in ("hum_bar", "roll", "crawl", "weave", "flicker", "moire", "sweep", "jitter"):
        assert apply_drift(im, p, 60, phase=1).size == im.size


def test_pasteup_off_noop_and_deterministic():
    from app.pasteup import PASTE_BLOTS, PASTE_MODES, apply_paste

    assert set(PASTE_MODES) == {"off", "paper", "riso", "fiber"}
    assert set(PASTE_BLOTS) == {"overlay", "multiply", "screen"}
    im = _img()
    assert list(apply_paste(im, "off", 80).get_flattened_data()) == list(im.get_flattened_data())
    assert list(apply_paste(im, "paper", 0).get_flattened_data()) == list(im.get_flattened_data())
    a = apply_paste(im, "riso", 70, blend="multiply")
    b = apply_paste(im, "riso", 70, blend="multiply")
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    assert list(a.get_flattened_data()) != list(im.get_flattened_data())
    assert apply_paste(im, "fiber", 50, blend="screen").size == im.size


def test_video_backend_missing_skips_cleanly():
    import pytest

    from app.video_io import VideoBackendMissing, has_video, write_mp4

    if has_video():
        pytest.skip("video extra installed: missing-backend path not testable here")
    with pytest.raises(VideoBackendMissing):
        write_mp4([_img(16)], "out.mp4")


def test_write_mp4_roundtrip(tmp_path):
    import pytest

    from app.video_io import has_video, write_mp4

    if not has_video():
        pytest.skip("video extra missing: mp4 write not testable here")
    out = write_mp4([_img(64), _img(64)], tmp_path / "anim.mp4", fps=12)
    assert out.exists() and out.stat().st_size > 1000


def test_gif_drift_animates_frames():
    from app.gif import gif_frames
    from app.presets import Preset

    im = _img()
    p = Preset(name="t", method="bayer8", palette="SLIME",
               drift_pattern="snow", drift_amount=40.0)
    frames = gif_frames(im, p, frames=4, mode="phase")
    assert len(frames) == 4
    assert len({tuple(f.get_flattened_data()) for f in frames}) > 1


def test_drift_loop_covers_full_sweep():
    from app.drift import drift_mask_loop

    h, w = 64, 240
    first = drift_mask_loop(h, w, "sweep", 0.0)
    mid = drift_mask_loop(h, w, "sweep", 0.5)
    last = drift_mask_loop(h, w, "sweep", 0.999)
    assert float(mid.max()) > 0.9  # centered: full strength mid-clip
    assert float(first.mean()) < 0.1  # off-screen start: faint edge only
    assert float(last.mean()) < 0.1  # off-screen end: faint edge only
    assert len({tuple(f.tobytes()) for f in (first, mid, last)}) == 3


def test_drift_loop_closes_all_patterns():
    from app.drift import drift_mask_loop

    h, w = 48, 64
    for pattern in ("hum_bar", "roll", "crawl", "snow", "weave",
                    "flicker", "moire", "sweep", "jitter"):
        a = drift_mask_loop(h, w, pattern, 0.0)
        b = drift_mask_loop(h, w, pattern, 1.0)
        assert (a == b).all(), pattern


def test_gif_drift_sweep_traverses_independent_of_method():
    from app.gif import gif_frames
    from app.presets import Preset

    im = _img(96)
    for method in ("bayer4", "floyd"):
        p = Preset(name="t", method=method, palette="SLIME",
                   drift_pattern="sweep", drift_amount=80.0, drift_speed=1.0)
        frames = gif_frames(im, p, frames=8, mode="phase")
        flats = {tuple(f.get_flattened_data()) for f in frames}
        assert len(flats) > 4  # full traverse: most frames differ


def test_march_closes_the_loop():
    from app.dither import apply_method
    from app.ordered_maps import _ORDERED_DEFS as DEFS, march_offset

    from PIL import Image

    # Tiled matrices: frame n lands exactly on a full period -> seamless loop.
    for name, (mat, _div) in DEFS.items():
        m = int(mat.shape[0])
        for n in (2, 3, 4, 6, 8, 12, 24):
            for amt in (0.4, 1.0, 2.0, 2.9):
                assert march_offset(name, n, n, amt) % m == 0, (name, n, amt)
    # Unknown maps fall back to the legacy small crawl.
    assert march_offset("nope", 3, 6, 1.0) == 6
    assert march_offset("bayer8", 0, 6, 0.0) == 0
    # Full-period march renders a clean loop on bayer8 / 6 frames.
    im = Image.new("RGB", (32, 32), (120, 90, 200))
    seq = [apply_method(im, method="bayer8", palette=None, phase=march_offset("bayer8", i, 6, 1.0))
           for i in range(6)]
    flats = [tuple(f.get_flattened_data()) for f in seq]
    assert len(set(flats)) > 1  # it visibly marches
    assert flats[0] == tuple(apply_method(
        im, method="bayer8", palette=None,
        phase=march_offset("bayer8", 6, 6, 1.0)).get_flattened_data())  # loop joint


def test_motion_amount_freezes_and_scales():
    from app.gif import gif_frames
    from app.presets import Preset

    im = _img()
    base = dict(name="t", method="bayer8", palette="SLIME")
    still = gif_frames(im, Preset(**base, motion_amount=0.0), frames=4, mode="mix")
    assert len({tuple(f.get_flattened_data()) for f in still}) == 1
    classic = gif_frames(im, Preset(**base, motion_amount=1.0), frames=4, mode="mix")
    assert len({tuple(f.get_flattened_data()) for f in classic}) > 1
    strong = gif_frames(im, Preset(**base, motion_amount=2.0), frames=4, mode="mix")
    assert [tuple(f.get_flattened_data()) for f in strong] != [
        tuple(f.get_flattened_data()) for f in classic]


def test_motion_amount_default_is_legacy():
    from app.presets import Preset

    assert Preset(name="t").motion_amount == 1.0
    assert Preset.from_dict({"name": "t"}).to_dict()["motion_amount"] == 1.0


def test_preset_motion_roundtrip():
    from app.presets import Preset

    p = Preset.from_dict({"name": "old", "method": "bayer4", "palette": "SLIME"})
    assert p.drift_pattern == "off" and p.paste_mode == "off"
    p2 = Preset.from_dict(p.to_dict())
    assert p2.drift_amount == 0.0 and p2.paste_blend == "overlay"


def test_default_stack_includes_pasteup_neutral():
    from app.pipeline import RenderSpec, render_spec

    im = _img()
    out = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME"))
    plain = render_spec(im, RenderSpec(
        method="bayer4", palette_name="SLIME",
        fx_stack=[{"id": fid, "enabled": fid != "pasteup"} for fid in
                  ("split_tone", "fade", "glow", "grain", "halftone", "dust",
                   "vignette", "scanlines", "grille", "border", "letterbox",
                   "chroma", "slice", "pixelsort", "wave", "mosh",
                   "jpeg", "post_blur", "post_sharpen", "pasteup")]))
    assert list(out.get_flattened_data()) == list(plain.get_flattened_data())
