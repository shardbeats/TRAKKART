"""Tests glitch pack: chromatic aberration, slice shift, pixel sort, wave, mosh, grille."""

from PIL import Image

from app.glitch import (
    chromatic_aberration,
    datamosh,
    pixel_sort,
    rgb_grille,
    slice_shift,
    wave,
)


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


def test_pixelsort_identity_and_sorts():
    assert _flat(pixel_sort(_img())) == _flat(_img())
    assert _flat(pixel_sort(Image.new("RGB", (8, 8), (9, 9, 9)), threshold=128)) == [(9, 9, 9)] * 64
    out = pixel_sort(_img(), threshold=128)
    assert out.size == (32, 32)
    assert _flat(out) != _flat(_img())
    assert _flat(pixel_sort(_img(), threshold=128)) == _flat(out)  # determinista


def test_wave_identity_and_moves():
    assert _flat(wave(_img())) == _flat(_img())
    assert wave(_img(), amplitude=99).size == (32, 32)  # clamp a 30
    out = wave(_img(), amplitude=8)
    assert _flat(out) != _flat(_img())


def test_mosh_and_grille():
    assert _flat(datamosh(_img())) == _flat(_img())
    a = datamosh(_img(), amount=50)
    assert _flat(a) != _flat(_img())
    assert _flat(datamosh(_img(), amount=50)) == _flat(a)  # determinista
    assert _flat(rgb_grille(_img())) == _flat(_img())
    assert _flat(rgb_grille(_img(), every=1)) == _flat(_img())
    assert _flat(rgb_grille(_img(), every=3)) != _flat(_img())


def test_grille_every2_no_crash_and_tints():
    # Regresión: mask[:, bool, [0, 2]] reventaba en numpy
    # "shape mismatch ... shapes (160,) (2,)".
    for w in (2, 3, 31, 320):
        im = Image.new("RGB", (w, 16), (200, 100, 50))
        out = rgb_grille(im, every=2)
        assert out.size == (w, 16)
        assert list(out.get_flattened_data()) != list(im.get_flattened_data())
    # Columnas pares rojizas (G,B atenuados), impares verdosas (R,B atenuados).
    im = Image.new("RGB", (4, 1), (200, 100, 50))
    px = list(rgb_grille(im, every=2).get_flattened_data())
    assert px[0][0] == 200 and px[0][1] < 100 and px[0][2] < 50
    assert px[1][1] == 100 and px[1][0] < 200 and px[1][2] < 50
    # Determinista.
    a = rgb_grille(_img(), every=2)
    assert _flat(rgb_grille(_img(), every=2)) == _flat(a)
