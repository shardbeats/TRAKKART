"""Extra dither coverage: pixel_size, palette floyd, bayer8, fallbacks."""

from PIL import Image

from app.dither import _tile_matrix, apply_method, floyd_steinberg, ordered_bayer
from app.palettes import get_palette


def _img(size: int = 32) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            v = int(x / (size - 1) * 255)
            px[x, y] = (v, v // 2, 255 - v)
    return im


def test_bayer_pixel_size_down_up():
    out = ordered_bayer(_img(), palette=None, matrix="4x4", pixel_size=2)
    assert out.size == (32, 32)


def test_bayer8_palette_pixel_size():
    pal = get_palette("VAPOR")
    out = ordered_bayer(_img(), palette=pal, matrix="8x8", pixel_size=2)
    assert out.size == (32, 32)
    assert set(out.get_flattened_data()) <= set(pal)


def test_floyd_palette_small():
    pal = get_palette("EMBER")
    out = floyd_steinberg(_img(24), palette=pal, threshold=128.0)
    assert out.size == (24, 24)
    assert set(out.get_flattened_data()) <= set(pal)


def test_floyd_pixel_size():
    out = floyd_steinberg(_img(), palette=None, pixel_size=2)
    assert out.size == (32, 32)


def test_apply_method_unknown_falls_back_to_bayer4():
    out = apply_method(_img(), method="no-such", palette=None)
    ref = apply_method(_img(), method="bayer4", palette=None)
    assert list(out.get_flattened_data()) == list(ref.get_flattened_data())


def test_tile_matrix_non_multiple():
    from app.dither import BAYER_4X4

    t = _tile_matrix(BAYER_4X4, 6, 10)
    assert t.shape == (6, 10)
