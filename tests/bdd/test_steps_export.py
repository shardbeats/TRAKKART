"""BDD steps + scenarios: export bundles + canvas ratios (export/canvas features)."""

from PIL import Image
from pytest_bdd import given, scenarios, then, when

from app.exporter import ExportOptions, export_with_options
from app.palettes import PALETTES, get_palette, palette_names

scenarios("../../features/export.feature", "../../features/canvas.feature")


def _bundle(img, tmp, base, ratio="1:1"):
    opts = ExportOptions(base=base)
    paths, _ = export_with_options(img, tmp, opts, meta={"ratio": ratio})
    return paths


@given("the TRAKKART palette catalog")
def catalog(ctx):
    ctx["names"] = palette_names()
    return ctx["names"]


@then("BW exists and resolves to the palette-less fast path")
def bw_fast(ctx):
    assert "BW" in ctx["names"]
    assert get_palette("BW") is None


@then("SLIME holds 4 colors")
def slime_4(ctx):
    assert len(PALETTES["SLIME"]) == 4


@when('I export the image with base "t"')
def export_t(ctx):
    ctx["paths"] = _bundle(ctx["img"], ctx["tmp"], base="t")


@when('I export the image with base "smoke"')
def export_smoke(ctx):
    ctx["paths"] = _bundle(ctx["img"], ctx["tmp"], base="smoke")


@then("image, thumb and metadata exist")
def three_exist(ctx):
    for k in ("image", "thumb_1080p", "metadata"):
        assert ctx["paths"][k].exists(), k


@then("the main image honors the 3000 long side")
def cover_size(ctx):
    with Image.open(ctx["paths"]["image"]) as im:
        assert max(im.size) == 3000


@then("every PNG weighs more than 500 bytes")
def smoke_500(ctx):
    pngs = [p for p in ctx["paths"].values() if str(p).endswith(".png")]
    assert len(pngs) == 2
    for p in pngs:
        assert p.stat().st_size > 500, p


@when('I export the image with 9:16 ratio')
def export_916(ctx):
    from app.canvas import canvas_size_for

    ctx["expected"] = canvas_size_for("9:16", 3000)
    opts = ExportOptions(base="v916")
    paths, _ = export_with_options(ctx["img"], ctx["tmp"], opts, meta={"ratio": "9:16"})
    ctx["paths"] = paths


@then("the main image matches the expected size for 9:16 at 3000")
def cover_916(ctx):
    from PIL import Image as Img

    with Img.open(ctx["paths"]["image"]) as im:
        assert im.size == ctx["expected"]


@when("I crop to 9:16 with out-of-range focus")
def clamp_crop(ctx):
    from app.canvas import to_canvas

    ctx["out"] = to_canvas(ctx["img"], ratio="9:16", fx=999, fy=-99)


@then("the resulting canvas honors the 9:16 ratio")
def canvas_ratio(ctx):
    w, h = ctx["out"].size
    assert abs(w / h - 9 / 16) < 0.02
