"""Tests grade pack: duotone, posterize, split-tone, fade."""

from PIL import Image

from app.grade import fade, gradient_map, posterize, split_tone


def _img(size: int = 32) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 8) % 256, (y * 8) % 256, 128)
    return im


def _flat(im: Image.Image) -> list:
    return list(im.get_flattened_data())


def test_duotone_identity_and_maps_ends():
    assert _flat(gradient_map(_img())) == _flat(_img())
    assert _flat(gradient_map(_img(), color_dark="#000000")) == _flat(_img())
    out = gradient_map(_img(), "#000000", "#ffffff")
    assert out.size == (32, 32)
    # Negro puro mapea al dark, blanco puro al light.
    assert _flat(gradient_map(Image.new("RGB", (4, 4), (0, 0, 0)), "#112233", "#aabbcc")) == [(17, 34, 51)] * 16
    assert _flat(gradient_map(Image.new("RGB", (4, 4), (255, 255, 255)), "#112233", "#aabbcc")) == [(170, 187, 204)] * 16
    assert _flat(out) != _flat(_img())


def test_posterize_identity_and_levels():
    assert _flat(posterize(_img())) == _flat(_img())
    assert _flat(posterize(_img(), levels=1)) == _flat(_img())
    out = posterize(_img(), levels=2)
    assert out.size == (32, 32)
    assert _flat(out) != _flat(_img())
    assert set(out.get_flattened_data()) == {(0, 0, 255), (0, 255, 255),
                                             (255, 0, 255), (255, 255, 255)}


def test_split_tone_and_fade():
    assert _flat(split_tone(_img())) == _flat(_img())
    assert _flat(fade(_img())) == _flat(_img())
    assert _flat(split_tone(_img(), 50)) != _flat(_img())
    assert _flat(fade(_img(), 50)) != _flat(_img())
    # Fade solo levanta (nunca oscurece).
    import numpy as np

    a = np.array(_img(), dtype=np.int16)
    b = np.array(fade(_img(), 100), dtype=np.int16)
    assert bool((b >= a).all())
