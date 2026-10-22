"""v1.1 Color Pro: extract, depth, SOURCE, mid/high, GPL, locks."""

from PIL import Image


def _img_half():
    im = Image.new("RGB", (64, 32))
    px = im.load()
    for y in range(32):
        for x in range(64):
            px[x, y] = (255, 0, 0) if x < 32 else (0, 0, 255)
    return im


def test_extract_two_colors():
    from app.palette_extract import extract_palette

    colors = extract_palette(_img_half(), 2)
    assert len(colors) == 2
    assert set(colors) == {(255, 0, 0), (0, 0, 255)}


def test_extract_deterministic_and_sorted():
    from app.palette_extract import extract_palette

    a = extract_palette(_img_half(), 4)
    b = extract_palette(_img_half(), 4)
    assert a == b
    # dark -> light: blue first
    assert a[0] == (0, 0, 255)


def test_source_mode_renders():
    from app.pipeline import RenderSpec, render_spec

    spec = RenderSpec(method="bayer4", palette_name="SOURCE", palette_depth=2)
    out = render_spec(_img_half(), spec)
    assert out.size == (32, 32)  # default 1:1 canvas crops to a square


def test_depth_truncates_named_palette():
    from app.render_params import apply_palette_depth

    pal = [(0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255)]
    assert apply_palette_depth(pal, 0) == pal
    assert len(apply_palette_depth(pal, 2)) == 2
    assert apply_palette_depth(pal, 2)[0] == (0, 0, 0)
    assert apply_palette_depth(pal, 2)[-1] == (255, 255, 255)


def test_mid_high_identity_and_effect():
    from app.adjust import Adjust, apply_adjust

    gray = Image.new("RGB", (32, 32), (100, 120, 140))
    assert apply_adjust(gray, Adjust()).size == gray.size
    out = apply_adjust(gray, Adjust(midtones=1.5))
    assert list(out.get_flattened_data()) != list(gray.get_flattened_data())
    bright = Image.new("RGB", (32, 32), (200, 210, 220))
    out2 = apply_adjust(bright, {"highlights": 50})
    assert list(out2.get_flattened_data()) != list(bright.get_flattened_data())


def test_gpl_roundtrip(tmp_path):
    from app.palette_library import parse_gpl, to_gpl

    gpl = to_gpl("test", [(255, 0, 0), (0, 0, 255)])
    name, colors = parse_gpl(gpl)
    assert name == "test"
    assert colors == [(255, 0, 0), (0, 0, 255)]


def test_old_preset_still_loads():
    from app.presets import Preset

    p = Preset.from_dict({"name": "old", "method": "bayer4", "palette": "SLIME"})
    assert p.midtones == 1.0 and p.highlights == 0.0 and p.palette_depth == 0
    assert p.adjust().midtones == 1.0
    assert p.to_render_kwargs()["palette_depth"] == 0
