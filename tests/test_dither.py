import pytest
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

    assert len(METHODS) == 38  # 21 ordered/motif + 13 ED + hilbert + 3 special
    for m in METHODS:
        out = apply_method(_img(), method=m, palette=None)
        assert out.size == (64, 64)


def test_engine_roster_frozen_r14():
    # R14 decision: the roster is frozen at 36 (new diffusions add <5%
    # visible for covers, each engine is eternal test/preset surface).
    # Reopened narrowly in v1.9 (owner nov-2026, research-backed):
    # +ostromoukhov (variable-coefficient ED) +dizzy (blue-noise-like ED)
    # + serpentine scan toggle. The list below is exact again.
    from app.dither import METHODS

    assert sorted(METHODS) == [
        "ascii", "atkinson", "bayer16", "bayer2", "bayer32", "bayer4",
        "bayer8", "blocks", "bluenoise", "burkes", "checker", "cluster",
        "cmyk", "columns", "cross", "diag", "dizzy", "edges", "filterlite",
        "floyd", "grid", "halftone", "hilbert", "ign", "jjn", "lines",
        "motif", "ostromoukhov", "pattern", "scan_bayer", "shiaufan", "sierra", "sierra3",
        "sierralite", "stevenson", "stucki", "wave_map", "white_noise",
    ]


def test_v19_engines_deterministic():
    from app.dither import apply_method
    from app.palettes import get_palette

    pal = get_palette("VAPOR")
    for method in ("ostromoukhov", "dizzy"):
        for palette in (None, pal):
            a = apply_method(_img(), method=method, palette=palette)
            b = apply_method(_img(), method=method, palette=palette)
            assert list(a.get_flattened_data()) == list(b.get_flattened_data())
        bw = apply_method(_img(), method=method, palette=None)
        assert set(bw.convert("L").get_flattened_data()) <= {0, 255}
        col = apply_method(_img(), method=method, palette=pal)
        assert set(col.get_flattened_data()) <= set(pal)


def test_v19_engines_distinct():
    from app.dither import apply_method

    floyd = apply_method(_img(), method="floyd", palette=None)
    dizzy = apply_method(_img(), method="dizzy", palette=None)
    assert list(dizzy.get_flattened_data()) != list(floyd.get_flattened_data())
    sierra3 = apply_method(_img(), method="sierra3", palette=None)
    ostro = apply_method(_img(), method="ostromoukhov", palette=None)
    assert list(ostro.get_flattened_data()) != list(sierra3.get_flattened_data())


def test_serpentine_deterministic_and_distinct():
    from app.dither import apply_method

    for method in ("floyd", "ostromoukhov", "dizzy"):
        a = apply_method(_img(), method=method, palette=None, serpentine=True)
        b = apply_method(_img(), method=method, palette=None, serpentine=True)
        assert list(a.get_flattened_data()) == list(b.get_flattened_data())
        plain = apply_method(_img(), method=method, palette=None)
        assert list(a.get_flattened_data()) != list(plain.get_flattened_data())
        assert set(a.convert("L").get_flattened_data()) <= {0, 255}


def test_serpentine_ignored_off_ed():
    from app.dither import apply_method

    a = apply_method(_img(), method="bayer8", palette=None, serpentine=True)
    b = apply_method(_img(), method="bayer8", palette=None)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())


needs_numba = pytest.mark.skipif(
    not __import__("app.accelerate", fromlist=["has_numba"]).has_numba(),
    reason="numba not installed",
)


@needs_numba
def test_v19_numpy_numba_parity():
    import numpy as np

    from app.kernels import run_kernel

    for method in ("ostromoukhov", "dizzy"):
        for palette in (None, [(0, 0, 0), (255, 255, 255)]):
            a = np.array(run_kernel(_img(), method, palette, 128.0, backend="numpy"))
            b = np.array(run_kernel(_img(), method, palette, 128.0, backend="numba"))
            assert np.array_equal(a, b), method
    for serp in (False, True):
        a = np.array(run_kernel(_img(), "floyd", None, 128.0,
                                backend="numpy", serpentine=serp))
        b = np.array(run_kernel(_img(), "floyd", None, 128.0,
                                backend="numba", serpentine=serp))
        assert np.array_equal(a, b)


def test_serpentine_preset_plumbing():
    from app.pipeline import RenderSpec
    from app.presets import Preset

    p = Preset(name="t", method="floyd", serpentine=True)
    p.validate()
    assert Preset.from_dict(p.to_dict()).serpentine is True
    spec = RenderSpec.from_preset(p)
    assert spec.serpentine is True
    assert spec.meta()["serpentine"] is True
    from app.pipeline import render_preset

    assert p.to_dict()["serpentine"] is True
    out = render_preset(_img(), p)
    assert out.size[0] > 0


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
