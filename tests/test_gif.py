"""Tests for animated GIF: frames, determinism, anim cap (1200), modes."""

from PIL import Image

from app.gif import GIF_MODES, estimate_gif, gif_frames, save_gif
from app.presets import Preset


def _preset(**kw) -> Preset:
    base = dict(method="bayer4", palette="SLIME", pixel_size=2)
    base.update(kw)
    return Preset(name="g", **base)


def _img(size: int = 128) -> Image.Image:
    im = Image.new("RGB", (size, size), (90, 60, 140))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 3) % 256, (y * 3) % 256, 128)
    return im


def test_frames_count_and_size_cap():
    # Single-anim default 1200: a 1200x800 stays as is, a larger one shrinks to 1200.
    big = Image.new("RGB", (1200, 800), (10, 20, 30))
    frames = gif_frames(big, _preset(), frames=4, mode="phase")
    assert len(frames) == 4
    for f in frames:
        assert max(f.size) <= 1200
    huge = Image.new("RGB", (2400, 2400), (10, 20, 30))
    capped = gif_frames(huge, _preset(), frames=2, mode="phase")
    assert max(capped[0].size) == 1200


def test_frames_deterministic():
    a = gif_frames(_img(), _preset(), frames=3, mode="both")
    b = gif_frames(_img(), _preset(), frames=3, mode="both")
    for fa, fb in zip(a, b):
        assert list(fa.get_flattened_data()) == list(fb.get_flattened_data())


def test_modes_differ_and_invalid_falls_back():
    base = gif_frames(_img(), _preset(), frames=3, mode="phase")
    hue = gif_frames(_img(), _preset(), frames=3, mode="hue")
    assert any(
        list(a.get_flattened_data()) != list(b.get_flattened_data()) for a, b in zip(base, hue)
    )
    fallback = gif_frames(_img(), _preset(), frames=2, mode="nope")
    assert len(fallback) == 2
    assert set(GIF_MODES) == {"phase", "hue", "both", "glitch", "mix", "dissolve", "morph"}


def test_glitch_and_mix_animate_ed_static():
    # Floyd ignores phase: glitch/mix move via FX/DATAMOSH post-fx.
    # Strict 0=off: motion needs explicit values (no forced slices).
    p = _preset(method="floyd", glitch_chroma=8, mosh=30.0)
    a = gif_frames(_img(), p, frames=3, mode="glitch")
    b = gif_frames(_img(), p, frames=3, mode="mix")
    assert any(
        list(x.get_flattened_data()) != list(y.get_flattened_data())
        for x, y in zip(a[1:], a[:-1])
    )
    assert any(
        list(x.get_flattened_data()) != list(y.get_flattened_data())
        for x, y in zip(b[1:], b[:-1])
    )


def test_mix_strict_respects_zero():
    # Clean preset + glitch mode on ED still: no forced slices/chroma.
    p = _preset(method="floyd")
    frames = gif_frames(_img(), p, frames=3, mode="glitch")
    assert all(
        list(x.get_flattened_data()) == list(y.get_flattened_data())
        for x, y in zip(frames[1:], frames[:-1])
    )


def test_pingpong_and_size_and_fps():
    p = _preset(gif_size=320, gif_pingpong=True)
    frames = gif_frames(_img(64), p, frames=4, mode="mix")
    assert len(frames) == 4 + 2  # ping-pong expands
    assert max(frames[0].size) <= 320
    out_frames = gif_frames(_img(64), _preset(), frames=3, mode="phase",
                            max_side=240, pingpong=False)
    assert len(out_frames) == 3
    assert max(out_frames[0].size) <= 240
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        from pathlib import Path

        o = save_gif(out_frames, Path(d) / "x.gif", fps=12)
        assert o.exists()
        with __import__("PIL.Image", fromlist=["open"]).open(o) as im:
            assert im.n_frames == 3


def test_video_defaults_1200():
    from app.gif import VIDEO_DEFAULT_SIZE, VIDEO_MAX_SIZE, VIDEO_MIN_SIZE

    assert VIDEO_DEFAULT_SIZE == 1200
    assert (VIDEO_MIN_SIZE, VIDEO_MAX_SIZE) == (480, 1920)
    # Full canvas at 1200: a 1600px one shrinks to 1200, a small one is not upscaled.
    big = Image.new("RGB", (1600, 1600), (10, 20, 30))
    frames = gif_frames(big, _preset(), frames=2, mode="phase", max_side=1200)
    assert max(frames[0].size) == 1200
    small = gif_frames(_img(256), _preset(), frames=2, mode="phase", max_side=1200)
    assert max(small[0].size) == 256


def test_save_gif_valid(tmp_path):
    frames = gif_frames(_img(), _preset(), frames=3, mode="phase")
    out = save_gif(frames, tmp_path / "a_anim.gif", fps=8)
    assert out.exists() and out.stat().st_size > 100
    with Image.open(out) as im:
        assert im.n_frames == 3
        assert im.format == "GIF"


def test_save_gif_empty_raises(tmp_path):
    import pytest

    from app.gif import save_gif

    with pytest.raises(ValueError):
        save_gif([], tmp_path / "x.gif")


def test_estimate():
    assert estimate_gif(6, 120, 120) == 6 * 120 * 120 // 2


def test_solve_hold_for_length():
    from app.gif import solve_hold_for_length

    hold, plan, fits = solve_hold_for_length(64, 1, 30, 7.5)
    assert (round(hold, 2), round(plan["actual_s"], 2), fits) == (2.7, 7.53, True)
    assert plan["total"] == 64 + 81 + 81  # transitions + equal holds
    assert plan["pad"] == 0  # never pads, Hold mandates
    hold, plan, fits = solve_hold_for_length(64, 1, 30, 60.0)
    assert hold == 3.0 and fits is False  # clamped: add Frames/chain
    hold, plan, fits = solve_hold_for_length(64, 1, 30, 0.5)
    assert hold == 0.0 and fits is False  # transitions alone overshoot
    hold, plan, fits = solve_hold_for_length(6, 1, 24, 4.0)
    assert abs(plan["actual_s"] - 4.0) < 0.01 and fits is True
    # Same target, higher fps: same seconds, more frames (quality only).
    hold2, plan2, fits2 = solve_hold_for_length(6, 1, 48, 4.0)
    assert abs(plan2["actual_s"] - 4.0) < 0.05 and fits2 is True
    assert plan2["total"] > plan["total"]


def test_gif_end_to_end_bundle(tmp_path):
    from app.exporter import export_bundle

    p = _preset(gif_export=True, gif_frames=3)
    frames = gif_frames(_img(), p, frames=3, mode="both")
    paths = export_bundle(_img(), tmp_path, base="g", meta=p.meta(), gif_frames=frames)
    assert paths["anim"].exists()
    assert paths["anim"].suffix == ".gif"
    import json

    info = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    assert info["gif"]["frames"] == 3
    assert info["params"]["gif"]["export"] is True


def test_sheen_off_and_loop_perfect():
    from app.fx import sheen_sweep

    img = _img()
    flat = list(img.get_flattened_data())
    assert list(sheen_sweep(img, progress=0.37, amount=0.0).get_flattened_data()) == flat
    a = sheen_sweep(img, progress=0.0, amount=8.0)
    b = sheen_sweep(img, progress=1.0, amount=8.0)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    mid = sheen_sweep(img, progress=0.5, amount=8.0)
    assert list(mid.get_flattened_data()) != flat


def test_hue_freezes_with_zero_motion():
    frozen = gif_frames(_img(), _preset(motion_amount=0.0), frames=3, mode="hue")
    assert all(
        list(x.get_flattened_data()) == list(y.get_flattened_data())
        for x, y in zip(frozen[1:], frozen[:-1])
    )
    moving = gif_frames(_img(), _preset(), frames=4, mode="hue")
    assert any(
        list(x.get_flattened_data()) != list(y.get_flattened_data())
        for x, y in zip(moving[1:], moving[:-1])
    )
