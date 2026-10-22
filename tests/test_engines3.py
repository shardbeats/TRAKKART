"""v1.3 Engines III: 36 methods, cmyk/ascii/edges/motif, black-vector, stepping."""

from PIL import Image


def _img(size=64):
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            v = int(x / (size - 1) * 255)
            px[x, y] = (v, v // 2, 255 - v)
    return im


def test_method_count_36():
    from app.dither import METHODS

    assert len(METHODS) == 36
    for m in ("bayer32", "lines", "columns", "diag", "grid",
              "white_noise", "blocks", "scan_bayer", "wave_map", "motif",
              "cmyk", "ascii", "edges"):
        assert m in METHODS


def test_new_ordered_render_and_phase():
    from app.dither import ordered

    im = _img()
    for m in ("bayer32", "lines", "columns", "diag", "grid",
              "white_noise", "blocks", "scan_bayer", "wave_map"):
        out = ordered(im, palette=None, map_name=m)
        assert out.size == (64, 64)
        assert set(out.convert("L").get_flattened_data()) <= {0, 255}
    a = ordered(im, palette=None, map_name="wave_map", phase=0)
    b = ordered(im, palette=None, map_name="wave_map", phase=9)
    assert list(a.get_flattened_data()) != list(b.get_flattened_data())


def test_cmyk_deterministic():
    from app.cmyk import cmyk_halftone

    im = _img()
    a = cmyk_halftone(im)
    b = cmyk_halftone(im)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    c = cmyk_halftone(im, phase=5)
    assert list(a.get_flattened_data()) != list(c.get_flattened_data())


def test_ascii_palette_and_phase():
    from app.ascii import ascii_render
    from app.palettes import get_palette

    im = _img()
    a = ascii_render(im, palette=None, phase=0)
    b = ascii_render(im, palette=None, phase=3)
    assert a.size[0] > 0 and b.size[0] > 0
    assert list(a.get_flattened_data()) != list(b.get_flattened_data())
    pal = get_palette("SLIME")
    c = ascii_render(im, palette=pal)
    assert c.size == a.size
    # The palette changes the tint (antialias blends with the background: not an exact subset).
    assert list(c.get_flattened_data()) != list(a.get_flattened_data())


def test_motif_default_and_custom():
    from app.dither import apply_method
    from app.motif import default_config, normalize_config

    im = _img()
    a = apply_method(im, method="motif", palette=None, motif=None)
    b = apply_method(im, method="motif", palette=None, motif=default_config())
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    custom = normalize_config({"bands": [
        {"shape": "ring", "size": 4}, {"shape": "diag", "size": 1},
        {"shape": "square", "size": 3}, {"shape": "line", "size": 2}]})
    c = apply_method(im, method="motif", palette=None, motif=custom)
    assert list(a.get_flattened_data()) != list(c.get_flattened_data())


def test_motif_no_legacy_trace():
    from app.dither import METHODS, apply_method

    assert "shifter" not in METHODS
    assert "motif" in METHODS
    # Unknown legacy name falls back to the bayer4 default instead of matching.
    im = _img()
    a = apply_method(im, method="shifter", palette=None)
    b = apply_method(im, method="bayer4", palette=None)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())


def test_black_vector_ink_only():
    from app.vector import raster_to_svg

    im = Image.new("RGB", (8, 4), (255, 255, 255))
    px = im.load()
    for y in range(4):
        for x in range(4):
            px[x, y] = (0, 0, 0)
    svg = raster_to_svg(im, 8, ink_only=True)
    assert "#000000" in svg
    assert svg.count("<rect") == 4  # ink only, no paper
    svg2 = raster_to_svg(im, 8, ink_only=False)
    assert svg2.count("<rect") == 8


def test_step_method_cycles():
    from app.dither import METHODS

    methods = list(METHODS)
    nxt = methods[(methods.index("bayer4") + 1) % len(methods)]
    assert nxt in METHODS and nxt != "bayer4"
