"""Generador de paletas: determinismo, validez y calidad perceptual."""

import time

import pytest

pytestmark = pytest.mark.slow


def test_seed_deterministic():
    from app.palette_gen import generate_palette

    for style in ("ramp", "harmony"):
        assert generate_palette(6, style, seed=7) == generate_palette(6, style, seed=7)
        assert generate_palette(6, style, seed=7) != generate_palette(6, style, seed=8)


def test_valid_and_clamped():
    from app.palette_gen import MAX_COLORS, MIN_COLORS, generate_palette

    assert len(generate_palette(1, seed=1)) == MIN_COLORS
    assert len(generate_palette(99, seed=1)) == MAX_COLORS
    for style in ("ramp", "harmony", "weird"):
        pal = generate_palette(8, style, seed=3)
        assert len(pal) == 8
        assert len(set(pal)) == 8  # sin duplicados
        for c in pal:
            assert len(c) == 3 and all(isinstance(v, int) and 0 <= v <= 255 for v in c)


def test_ramp_spread_and_order():
    import numpy as np

    from app.palette_gen import _luminance_spread, generate_palette, rgb_to_oklch

    pal = generate_palette(6, "ramp", seed=11)
    assert _luminance_spread(np.array(pal)) > 0.35  # el dither necesita rango
    lum = rgb_to_oklch(np.array(pal))[:, 0]
    assert bool((np.diff(lum) >= -0.02).all())  # oscuro -> claro


def test_harmony_separation_and_hues():
    import numpy as np

    from app.palette_gen import MIN_DIST, _min_pairwise_dist, generate_palette, rgb_to_oklch

    pal = generate_palette(6, "harmony", seed=5)
    assert _min_pairwise_dist(np.array(pal)) >= MIN_DIST
    hues = rgb_to_oklch(np.array(pal))[:, 2]
    assert float(hues.std()) > 10.0  # más de una familia de tono


def test_oklch_roundtrip_stable():
    import numpy as np

    from app.palette_gen import oklch_to_rgb, rgb_to_oklch

    rgb = np.array([(200, 50, 90), (10, 18, 12), (245, 230, 190)])
    back = oklch_to_rgb(rgb_to_oklch(rgb))
    assert np.abs(back.astype(int) - rgb.astype(int)).max() <= 2


def test_generation_is_fast():
    t = time.time()
    from app.palette_gen import generate_palette

    for style in ("ramp", "harmony"):
        generate_palette(16, style, seed=9)
    assert time.time() - t < 2.0


def test_gen_button_fills_and_marks_dirty(window, qt_app):
    assert window.cmb_palgen.currentText() == "Ramp"
    window._set_custom_colors([(1, 2, 3), (4, 5, 6)], dirty=False)
    window.cmb_palgen.setCurrentText("Harmony")
    window.gen_palette()
    assert len(window.custom_colors) == 2
    assert len(set(window.custom_colors)) == 2
    assert window.cmb_pal_preset.currentText() == "(Custom)"
    assert window.lbl_custom.text() == "2/16"
    # con tira vacía genera 4
    window._set_custom_colors([], dirty=False)
    window.gen_palette()
    assert len(window.custom_colors) == 4
