"""BDD steps + scenarios: export bundles + canvas ratios (export/canvas features)."""

from PIL import Image
from pytest_bdd import given, scenarios, then, when

from app.exporter import export_bundle
from app.palettes import PALETTES, get_palette, palette_names

scenarios("../../features/export.feature", "../../features/canvas.feature")


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


@when('I export the bundle with base "t"')
def export_t(ctx):
    ctx["paths"] = export_bundle(ctx["img"], ctx["tmp"], base="t")


@when('I export the bundle with base "smoke"')
def export_smoke(ctx):
    ctx["paths"] = export_bundle(ctx["img"], ctx["tmp"], base="smoke")


@then("cover, small and thumb_1080p exist")
def three_exist(ctx):
    for k in ("cover", "small", "thumb_1080p"):
        assert ctx["paths"][k].exists(), k


@then("cover is 3000x3000")
def cover_size(ctx):
    with Image.open(ctx["paths"]["cover"]) as im:
        assert im.size == (3000, 3000)


@then("every PNG weighs more than 500 bytes")
def smoke_500(ctx):
    pngs = [p for p in ctx["paths"].values() if str(p).endswith(".png")]
    assert len(pngs) == 3
    for p in pngs:
        assert p.stat().st_size > 500, p


@when("I export the bundle with 9:16 ratio")
def export_916(ctx):
    from app.canvas import canvas_size_for
    from app.presets import Preset

    ctx["expected"] = canvas_size_for("9:16", 3000)
    p = Preset(name="v", method="bayer4", palette="SLIME", ratio="9:16")
    ctx["paths"] = export_bundle(ctx["img"], ctx["tmp"], base="v916", meta=p.meta())


@then("cover matches the expected size for 9:16 at 3000")
def cover_916(ctx):
    from PIL import Image as Img

    with Img.open(ctx["paths"]["cover"]) as im:
        assert im.size == ctx["expected"]


@when("I crop to 9:16 with out-of-range focus")
def clamp_crop(ctx):
    from app.canvas import to_canvas

    ctx["out"] = to_canvas(ctx["img"], ratio="9:16", fx=999, fy=-99)


@then("the resulting canvas honors the 9:16 ratio")
def canvas_ratio(ctx):
    w, h = ctx["out"].size
    assert abs(w / h - 9 / 16) < 0.02
