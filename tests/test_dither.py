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

    assert len(METHODS) == 36  # 21 ordered/motif + 11 ED + hilbert + 3 special
    for m in METHODS:
        out = apply_method(_img(), method=m, palette=None)
        assert out.size == (64, 64)


def test_ign_deterministic_and_phased():
    from app.dither import ordered

    a = ordered(_img(), palette=None, map_name="ign")
    b = ordered(_img(), palette=None, map_name="ign")
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    c = ordered(_img(), palette=None, map_name="ign", phase=7)
    assert list(a.get_flattened_data()) != list(c.get_flattened_data())
    assert set(a.convert("L").get_flattened_data()) <= {0, 255}


def test_checker_exact_pattern():
    from app.dither import ordered

    solid = Image.new("RGB", (4, 4), (200, 200, 200))
    out = ordered(solid, palette=None, map_name="checker", threshold=128)
    px = list(out.convert("L").get_flattened_data())
    # Repeated 2x2 board: opposite corners match, adjacent ones differ.
    assert px[0] == px[1 + 4] != px[1] == px[4]


def test_hilbert_dispatch_and_deterministic():
    from app.dither import apply_method, hilbert_diffusion

    a = apply_method(_img(), method="hilbert", palette=None)
    b = hilbert_diffusion(_img(), palette=None)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    assert set(a.convert("L").get_flattened_data()) <= {0, 255}
    pal = get_palette("SLIME")
    assert pal is not None
    c = apply_method(_img(), method="hilbert", palette=pal)
    assert set(c.get_flattened_data()) <= set(pal)
