"""ED kernel tests + new ordered maps."""

from PIL import Image

from app.dither import METHODS, apply_method, error_diffusion, ordered
from app.kernels import COEFFS, ED_METHODS
from app.palettes import get_palette


def _img(size: int = 48) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            v = int(x / (size - 1) * 255)
            px[x, y] = (v, v // 2, 255 - v)
    return im


def test_all_ed_kernels_bw():
    for k in ED_METHODS:
        out = error_diffusion(_img(), kernel=k, palette=None)
        assert set(out.convert("L").get_flattened_data()) <= {0, 255}, k


def test_all_ed_kernels_palette():
    pal = get_palette("SLIME")
    for k in ED_METHODS:
        out = error_diffusion(_img(32), kernel=k, palette=pal)
        assert set(out.get_flattened_data()) <= set(pal), k


def test_invalid_kernel_falls_back_to_floyd():
    out = error_diffusion(_img(32), kernel="nope", palette=None)
    ref = error_diffusion(_img(32), kernel="floyd", palette=None)
    assert list(out.get_flattened_data()) == list(ref.get_flattened_data())


def test_all_methods_dispatch():
    for m in METHODS:
        out = apply_method(_img(32), method=m, palette=None)
        assert out.size == (32, 32), m


def test_ordered_new_maps():
    for name in ("bayer16", "bayer2", "halftone", "cluster", "pattern", "cross", "bluenoise"):
        out = ordered(_img(32), palette=None, map_name=name)
        assert out.size == (32, 32), name
        assert set(out.convert("L").get_flattened_data()) <= {0, 255}
        out = ordered(_img(32), palette=get_palette("VAPOR"), map_name=name)
        assert set(out.get_flattened_data()) <= set(get_palette("VAPOR"))


def test_bluenoise_deterministic():
    a = ordered(_img(32), palette=None, map_name="bluenoise")
    b = ordered(_img(32), palette=None, map_name="bluenoise")
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())


def test_coeffs_present():
    assert set(COEFFS.keys()) == set(ED_METHODS)
