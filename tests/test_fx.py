"""Tests fx: pre/post, replace, custom palette."""

import pytest
from PIL import Image

from app.fx import (
    apply_denoise,
    apply_glow,
    apply_grain,
    apply_hue,
    apply_pre,
    apply_scanlines,
    apply_smooth,
    apply_vignette,
    normalize_custom_palette,
    parse_hex,
    replace_white,
)


def _img(size: int = 64) -> Image.Image:
    im = Image.new("RGB", (size, size), (120, 80, 160))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 3) % 256, (y * 3) % 256, 128)
    return im


def _flat(im: Image.Image) -> list:
    return list(im.get_flattened_data())


def test_pre_identity_and_change():
    import random

    assert _flat(apply_pre(_img())) == _flat(_img())
    assert _flat(apply_pre(_img(), blur=1.5)) != _flat(_img())
    assert apply_pre(_img(), sharpen=1).size == (64, 64)
    assert _flat(apply_pre(_img(), hue=60)) != _flat(_img())
    noisy = _img()
    px = noisy.load()
    rng = random.Random(7)
    for y in range(64):
        for x in range(64):
            if rng.random() < 0.1:
                px[x, y] = (255, 255, 255)
    assert _flat(apply_pre(noisy, denoise=2)) != _flat(noisy)
    assert _flat(apply_pre(_img(), smooth=2.0)) != _flat(_img())


def test_hue_determinism_and_range():
    assert _flat(apply_hue(_img(), 0)) == _flat(_img())
    a = apply_hue(_img(), 120)
    b = apply_hue(_img(), 120)
    assert _flat(a) == _flat(b)
    assert all(0 <= v <= 255 for px in a.get_flattened_data() for v in px)


def test_denoise_smooth_identity():
    assert _flat(apply_denoise(_img())) == _flat(_img())
    assert _flat(apply_smooth(_img())) == _flat(_img())


def test_glow_identity_and_change():
    assert _flat(apply_glow(_img())) == _flat(_img())
    out = apply_glow(_img(), radius=4, intensity=60)
    assert _flat(out) != _flat(_img())


def test_grain_deterministic_and_identity():
    assert _flat(apply_grain(_img())) == _flat(_img())
    a = apply_grain(_img(), amount=12)
    b = apply_grain(_img(), amount=12)
    assert _flat(a) == _flat(b)
    assert _flat(a) != _flat(_img())


def test_vignette_identity_and_change():
    assert _flat(apply_vignette(_img())) == _flat(_img())
    out = apply_vignette(_img(), strength=60)
    assert _flat(out) != _flat(_img())
    # center lighter than corner
    px = out.load()
    assert sum(px[32, 32]) > sum(px[0, 0])


def test_scanlines_identity_and_rows():
    assert _flat(apply_scanlines(_img())) == _flat(_img())
    assert _flat(apply_scanlines(_img(), every=1)) == _flat(_img())
    out = apply_scanlines(_img(), every=4, darken=0.5)
    px, ref = out.load(), _img().load()
    assert sum(px[0, 3]) < sum(ref[0, 3])  # row 3 darkened
    assert px[0, 0] == ref[0, 0]  # row 0 intact


def test_parse_hex():
    assert parse_hex("#FF00AA") == (255, 0, 170)
    assert parse_hex("00ff00") == (0, 255, 0)
    assert parse_hex("") is None
    assert parse_hex("zzz") is None
    assert parse_hex("#12345") is None


def test_replace_white():
    bw = Image.new("RGB", (16, 16), (255, 255, 255))
    out = replace_white(bw, "#112233")
    assert set(out.get_flattened_data()) == {(17, 34, 51)}
    assert replace_white(bw, "").size == (16, 16)
    dark = Image.new("RGB", (16, 16), (10, 10, 10))
    assert _flat(replace_white(dark, "#112233")) == _flat(dark)


def test_normalize_custom_palette():
    assert normalize_custom_palette(None) is None
    assert normalize_custom_palette([]) is None
    assert normalize_custom_palette([[0, 0, 0], [255, 255, 255]]) == [(0, 0, 0), (255, 255, 255)]
    with pytest.raises(ValueError):
        normalize_custom_palette([[0, 0, 0]])
    with pytest.raises(ValueError):
        normalize_custom_palette([[0, 0, 999], [1, 1, 1]])
    with pytest.raises(ValueError):
        normalize_custom_palette([["a", 0, 0], [1, 1, 1]])
