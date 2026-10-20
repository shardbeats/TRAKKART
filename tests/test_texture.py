"""Tests texture pack: halftone, dust, border, letterbox."""

import pytest
from PIL import Image

from app.texture import border, dust, halftone, letterbox


def _img(size: int = 32) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 8) % 256, (y * 8) % 256, 128)
    return im


def _flat(im: Image.Image) -> list:
    return list(im.get_flattened_data())


def test_halftone_identity_and_dots():
    assert _flat(halftone(_img())) == _flat(_img())
    assert _flat(halftone(_img(), cell=2)) == _flat(_img())  # <3 = off
    out = halftone(_img(), cell=6)
    assert out.size == (32, 32)
    assert _flat(out) != _flat(_img())
    assert _flat(halftone(_img(), cell=6, shape="lines")) != _flat(_img())


def test_dust_deterministic_and_off():
    assert _flat(dust(_img())) == _flat(_img())
    a = dust(_img(), amount=40)
    b = dust(_img(), amount=40)
    assert _flat(a) == _flat(b)
    assert _flat(a) != _flat(_img())


def test_border_and_letterbox():
    assert border(_img()).size == (32, 32)
    assert border(_img(), px=0).size == (32, 32)
    assert border(_img(), px=4).size == (40, 40)
    assert letterbox(_img()).size == (32, 32)
    out = letterbox(_img(), pct=25)
    px = out.load()
    assert px[0, 0] == (0, 0, 0)
    assert px[0, 31] == (0, 0, 0)
    assert px[16, 16] != (0, 0, 0)
    with pytest.raises(ValueError):
        border(_img(), px=4, color="nope")
