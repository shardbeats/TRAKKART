"""Tests glitch pack: chromatic aberration + slice shift."""

from PIL import Image

from app.glitch import chromatic_aberration, slice_shift


def _img(size: int = 32) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 8) % 256, (y * 8) % 256, 128)
    return im


def _flat(im: Image.Image) -> list:
    return list(im.get_flattened_data())


def test_chroma_identity_and_shift():
    assert _flat(chromatic_aberration(_img())) == _flat(_img())
    out = chromatic_aberration(_img(), dx=4)
    assert _flat(out) != _flat(_img())
    # R channel shifted right relative to the original
    assert out.load()[4, 0][0] == _img().load()[0, 0][0]
    # G channel intact
    assert out.load()[0, 0][1] == _img().load()[0, 0][1]


def test_slice_identity_and_deterministic():
    assert _flat(slice_shift(_img(), bands=0)) == _flat(_img())
    assert _flat(slice_shift(_img(), bands=1)) == _flat(_img())
    a = slice_shift(_img(), bands=4, max_offset=8)
    b = slice_shift(_img(), bands=4, max_offset=8)
    assert _flat(a) == _flat(b)
    assert _flat(a) != _flat(_img())
    assert a.size == (32, 32)
