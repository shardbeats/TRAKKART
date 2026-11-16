"""v1.9 Fase B: print-shop (rosettes, LPI tied to DPI, trap, mirror)."""

from PIL import Image


def _img(w=64, h=64):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 4) % 256, (y * 4) % 256, 140)
    return im


def test_rosette_tables_and_fallback():
    from app.cmyk import ROSETTES, rosette_shifts

    assert set(ROSETTES) == {"standard", "alt", "single"}
    assert rosette_shifts("standard") == (0, 13, 29, 47)
    assert rosette_shifts("nope") == rosette_shifts("standard")
    assert rosette_shifts("SINGLE") == (0, 0, 0, 0)


def test_rosette_deterministic_and_distinct():
    from app.cmyk import cmyk_halftone

    a = cmyk_halftone(_img())
    b = cmyk_halftone(_img())
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    for r in ("alt", "single"):
        other = cmyk_halftone(_img(), rosette=r)
        assert list(other.get_flattened_data()) != list(a.get_flattened_data())


def test_rosette_standard_is_legacy():
    from app.cmyk import cmyk_halftone

    a = cmyk_halftone(_img(), threshold=100, phase=3, pixel_size=1)
    b = cmyk_halftone(_img(), threshold=100, phase=3, pixel_size=1,
                      rosette="standard", lpi=0, dpi=300)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())


def test_cell_for_lpi():
    from app.cmyk import cell_for_lpi

    assert cell_for_lpi(0) == 8  # legacy fixed cell
    assert cell_for_lpi(-5) == 8
    assert cell_for_lpi(100) == 3  # 300/100 at reference DPI
    assert cell_for_lpi(150) == 2
    assert cell_for_lpi(35, dpi=600) == 17
    assert cell_for_lpi(1000, dpi=300) == 2  # clamped: no 1px mush
    assert cell_for_lpi(1, dpi=600) == 64  # clamped: no sheet-size cells


def test_lpi_changes_dot_pitch_and_ties_to_dpi():
    from app.cmyk import cmyk_halftone

    ref = cmyk_halftone(_img())
    coarse = cmyk_halftone(_img(), lpi=35)
    assert list(coarse.get_flattened_data()) != list(ref.get_flattened_data())
    d150 = cmyk_halftone(_img(), lpi=100, dpi=150)
    d300 = cmyk_halftone(_img(), lpi=100, dpi=300)
    assert list(d150.get_flattened_data()) != list(d300.get_flattened_data())
    same = cmyk_halftone(_img(), lpi=100, dpi=300)
    assert list(same.get_flattened_data()) == list(d300.get_flattened_data())


def test_preset_plumbing_rosette_lpi():
    from app.pipeline import RenderSpec
    from app.presets import Preset

    p = Preset(name="t", method="cmyk", rosette="alt", cmyk_lpi=100)
    p.validate()
    back = Preset.from_dict(p.to_dict())
    assert (back.rosette, back.cmyk_lpi) == ("alt", 100)
    spec = RenderSpec.from_preset(p, dpi=150)
    assert (spec.rosette, spec.cmyk_lpi, spec.dpi) == ("alt", 100, 150)
    assert spec.meta()["rosette"] == "alt"
    import pytest

    with pytest.raises(ValueError):
        Preset(name="t", rosette="nope").validate()
    with pytest.raises(ValueError):
        Preset(name="t", cmyk_lpi=20).validate()
    assert Preset(name="t", cmyk_lpi=0).cmyk_lpi == 0  # off is legal


def test_render_cmyk_uses_rosette_and_lpi():
    from app.pipeline import render_preset
    from app.presets import Preset

    base = render_preset(_img(), Preset(name="t", method="cmyk"))
    alt = render_preset(_img(), Preset(name="t", method="cmyk", rosette="alt"))
    assert list(alt.get_flattened_data()) != list(base.get_flattened_data())
    lpi = render_preset(_img(), Preset(name="t", method="cmyk", cmyk_lpi=35))
    assert list(lpi.get_flattened_data()) != list(base.get_flattened_data())
    d150 = render_preset(_img(), Preset(name="t", method="cmyk",
                                        cmyk_lpi=100), dpi=150)
    d300 = render_preset(_img(), Preset(name="t", method="cmyk",
                                        cmyk_lpi=100), dpi=300)
    assert list(d150.get_flattened_data()) != list(d300.get_flattened_data())


def test_cmyk_ignores_serpentine_and_palette():
    from app.dither import apply_method

    a = apply_method(_img(), method="cmyk", palette=[(0, 0, 0)], serpentine=True)
    b = apply_method(_img(), method="cmyk")
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
