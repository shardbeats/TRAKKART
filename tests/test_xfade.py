"""Pins for v2.x #7: cross-dissolve frame interpolation (numpy-only).

Optional smoothing between clip/dissolve frames; strict 0=off,
default off (flicker stays the aesthetic). Pins: 0=identity,
determinism, cap behavior + engine legacy bytes.
"""

from __future__ import annotations

from PIL import Image


def _red():
    return Image.new("RGB", (16, 16), (255, 0, 0))


def _blue():
    return Image.new("RGB", (16, 16), (0, 0, 255))


def _flat(frames):
    return [tuple(f.get_flattened_data()) for f in frames]


def test_zero_is_identity():
    from app.xfade import xfade_frames

    frames = [_red(), _blue()]
    assert xfade_frames(frames, amount=0.0) == frames
    assert xfade_frames(frames, amount=0.0, steps=8) == frames
    assert xfade_frames(frames, amount=1.0, steps=0) == frames
    out = xfade_frames(frames)
    assert len(out) == 2 and all(a is b for a, b in zip(out, frames))
    assert xfade_frames([], amount=1.0) == []
    assert xfade_frames([_red()], amount=1.0) == [_red()]


def test_midpoint_and_spacing():
    from app.xfade import xfade_frames, xfade_pair

    mid = xfade_pair(_red(), _blue(), 0.5)
    assert mid.getpixel((0, 0)) == (128, 0, 128)
    assert xfade_pair(_red(), _blue(), 0.0).getpixel((0, 0)) == (255, 0, 0)
    assert xfade_pair(_red(), _blue(), 1.0).getpixel((0, 0)) == (0, 0, 255)
    out = xfade_frames([_red(), _blue()], amount=1.0, steps=2)
    assert len(out) == 4
    assert out[0].getpixel((0, 0)) == (255, 0, 0)
    assert out[-1].getpixel((0, 0)) == (0, 0, 255)
    assert out[1].getpixel((0, 0)) == (170, 0, 85)  # t=1/3
    assert out[2].getpixel((0, 0)) == (85, 0, 170)  # t=2/3


def test_deterministic():
    from app.xfade import xfade_frames

    frames = [_red(), _blue()]
    assert _flat(xfade_frames(frames, amount=1.0, steps=2)) == _flat(
        xfade_frames(frames, amount=1.0, steps=2))


def test_cap_clamps_blends_never_drops():
    from app.xfade import xfade_frames

    frames = [_red(), _blue()]
    assert len(xfade_frames(frames, amount=1.0, steps=8, cap=3)) == 3
    assert len(xfade_frames(frames, amount=1.0, steps=8, cap=2)) == 2
    assert xfade_frames(frames, amount=1.0, steps=8, cap=1) == frames
    out = xfade_frames([_red(), _blue(), _red()], amount=1.0, steps=2, cap=5)
    assert len(out) == 5  # 3 inputs + 2 blends (was 3+4=7 uncapped)


def test_loop_closes_and_stream_matches():
    from app.xfade import xfade_frames, xfade_stream

    frames = [_red(), _blue()]
    looped = xfade_frames(frames, amount=1.0, steps=1, loop=True)
    assert len(looped) == 4
    assert looped[3].getpixel((0, 0)) == (128, 0, 128)  # blue->red wrap
    streamed = list(xfade_stream(iter(frames), amount=1.0, steps=1))
    plain = xfade_frames(frames, amount=1.0, steps=1)
    assert len(streamed) == len(plain) == 3
    assert _flat(streamed) == _flat(plain)


def test_engine_off_is_legacy_and_on_expands():
    from app.disintegrate import dissolve_frames, iter_dissolve, morph_frames

    im = Image.new("RGB", (32, 32))
    px = im.load()
    for y in range(32):
        for x in range(32):
            px[x, y] = ((x * 8) % 256, (y * 8) % 256, 128)
    im2 = Image.new("RGB", (32, 32), (0, 0, 255))
    assert _flat(dissolve_frames(im, method="bayer4", frames=6)) == _flat(
        dissolve_frames(im, method="bayer4", frames=6, xfade=0.0))
    assert _flat(list(iter_dissolve(im, method="bayer4", frames=6))) == _flat(
        list(iter_dissolve(im, method="bayer4", frames=6, xfade=0.0)))
    assert _flat(morph_frames(im, im2, method="bayer4", frames=6)) == _flat(
        morph_frames(im, im2, method="bayer4", frames=6, xfade=0.0))
    assert len(dissolve_frames(im, method="bayer4", frames=6,
                               xfade=1.0, xfade_steps=1)) == 12
    base = morph_frames(im, im2, method="bayer4", frames=6)
    assert len(morph_frames(im, im2, method="bayer4", frames=6,
                            xfade=1.0, xfade_steps=1)) == len(base) * 2 - 1


def test_normalizers_reject_garbage():
    from app.xfade import normalize_xfade, normalize_xfade_steps

    assert normalize_xfade(None) == 0.0
    assert normalize_xfade("junk") == 0.0
    assert normalize_xfade(9.0) == 1.0
    assert normalize_xfade_steps(None) == 0
    assert normalize_xfade_steps("junk") == 0
    assert normalize_xfade_steps(99) == 8
