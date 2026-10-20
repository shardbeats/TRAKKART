"""Motion from stills: Signal Drift, Paste-Up, opt-in MP4 backend.

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
