from PIL import Image

from app.dither import apply_method, floyd_steinberg, ordered_bayer
from app.palettes import get_palette


def _img() -> Image.Image:
    # 64x64 gradient for fast tests
    im = Image.new("RGB", (64, 64))
    px = im.load()
    for y in range(64):
        for x in range(64):
            v = int(x / 63 * 255)
            px[x, y] = (v, v // 2, 255 - v)
    return im


def test_bayer_bw_only_two_colors():
    out = ordered_bayer(_img(), palette=None, matrix="4x4", threshold=128.0)
    colors = set(out.convert("L").get_flattened_data())
    assert colors <= {0, 255}
    assert out.size == (64, 64)


def test_bayer_palette_uses_only_palette_colors():
    pal = get_palette("SLIME")
    assert pal is not None
    out = ordered_bayer(_img(), palette=pal, matrix="4x4")
    assert set(out.get_flattened_data()) <= set(pal)


def test_floyd_bw_only_two_colors():
    out = floyd_steinberg(_img(), palette=None, threshold=128.0)
    assert set(out.convert("L").get_flattened_data()) <= {0, 255}


def test_apply_method_dispatch():
    from app.dither import METHODS

    for m in METHODS:
        out = apply_method(_img(), method=m, palette=None)
        assert out.size == (64, 64)
