"""BDD steps + scenarios: fx, dnd, safety, vector, gif, flow (media features)."""

from pytest_bdd import given, parsers, scenarios, then, when

scenarios(
    "../../features/fx.feature",
    "../../features/dnd.feature",
    "../../features/safety.feature",
    "../../features/vector.feature",
    "../../features/gif.feature",
    "../../features/flow.feature",
)


# -- fx.feature --
@given("a test image with marked rows")
def marked_rows(ctx):
    from PIL import Image as Img

    im = Img.new("RGB", (32, 32), (120, 80, 160))
    ctx["img"] = im
    return im


@when("I apply scanlines every 4 rows")
def scanlines_4(ctx):
    from app.fx import apply_scanlines

    ctx["out"] = apply_scanlines(ctx["img"], every=4, darken=0.5)


@then("row 3 ends up darkened and row 0 intact")
def rows_ok(ctx):
    from PIL import Image as Img2

    ref = Img2.new("RGB", (32, 32), (120, 80, 160))
    px, refpx = ctx["out"].load(), ref.load()
    assert sum(px[0, 3]) < sum(refpx[0, 3])
    assert px[0, 0] == refpx[0, 0]


@given("a fully white test image")
def all_white(ctx):
    from PIL import Image as Img

    ctx["img"] = Img.new("RGB", (16, 16), (255, 255, 255))
    return ctx["img"]


@when("I replace white with #112233")
def replace_white_bdd(ctx):
    from app.fx import replace_white

    ctx["out"] = replace_white(ctx["img"], "#112233")


@then("the whole image ends up in that color")
def all_branded(ctx):
    assert set(ctx["out"].get_flattened_data()) == {(17, 34, 51)}


@when("I apply duotone black to white")
def duotone_bw(ctx):
    from app.grade import gradient_map

    ctx["out"] = gradient_map(ctx["img"], "#000000", "#ffffff")


@then("darks stay dark and lights stay light")
def duotone_order(ctx):
    dark = gradient_map_for(ctx, (0, 0, 0))
    light = gradient_map_for(ctx, (255, 255, 255))
    assert sum(dark) < 128 * 3
    assert sum(light) > 128 * 3


def gradient_map_for(ctx, rgb):
    """Aplica el mismo duotone del step a un color plano (helper, no step)."""
    from PIL import Image as Img

    from app.grade import gradient_map

    return gradient_map(Img.new("RGB", (4, 4), rgb), "#000000", "#ffffff").load()[0, 0]


@when("I apply halftone dots of size 6")
def halftone_6(ctx):
    from app.texture import halftone

    ctx["out"] = halftone(ctx["img"], cell=6)


@then("the image keeps its size and changes")
def size_kept_changed(ctx):
    assert ctx["out"].size == ctx["img"].size
    assert list(ctx["out"].get_flattened_data()) != list(ctx["img"].get_flattened_data())


# -- dnd.feature --
@given(parsers.parse('the text "{url}"'))
def text_url(ctx, url):
    ctx["url"] = url
    return url


@when("I classify the drop")
def classify_drop(ctx):
    from app.dnd import classify_drop

    ctx["kind"] = classify_drop(ctx["url"])


@then(parsers.parse('the action is "{kind}" and not batch'))
def action_not_batch(ctx, kind):
    assert ctx["kind"] == kind
    assert ctx["kind"] not in ("dir", "batch")


# -- safety.feature --
@given("a 9000-pixel-wide image")
def huge_image(ctx):
    from PIL import Image as Img

    ctx["img"] = Img.new("RGB", (9000, 10))
    return ctx["img"]


@when("I validate its size")
def validate_size(ctx):
    from app.safety import TooBigError, check_image

    try:
        check_image(ctx["img"])
        ctx["err"] = None
    except TooBigError as e:
        ctx["err"] = e


@then("it fails with TooBigError")
def fails_toobig(ctx):
    from app.safety import TooBigError

    assert isinstance(ctx["err"], TooBigError)


@given("a 2000x2000 image")
def img_2k(ctx):
    from PIL import Image as Img

    ctx["img"] = Img.new("RGB", (2000, 2000), (1, 2, 3))
    return ctx["img"]


@when("I generate the vector with cell 4")
def vector_c4(ctx):
    from app.presets import Preset
    from app.safety import TooBigError
    from app.vector import vector_bundle

    try:
        vector_bundle(ctx["img"], Preset(name="v", vector_cell=4))
        ctx["err"] = None
    except TooBigError as e:
        ctx["err"] = e


@then("it fails with TooBigError without rendering")
def fails_without_render(ctx):
    from app.safety import TooBigError

    assert isinstance(ctx["err"], TooBigError)


# -- vector.feature --
@given("a test image with 2 flat colors")
def two_colors(ctx):
    from PIL import Image as Img

    im = Img.new("RGB", (16, 16))
    px = im.load()
    for y in range(16):
        for x in range(16):
            px[x, y] = (255, 0, 0) if x < 8 else (0, 0, 255)
    ctx["img"] = im
    return im


@when("I generate the SVG with cell 8")
def gen_svg(ctx):
    from app.vector import raster_to_svg

    ctx["svg"] = raster_to_svg(ctx["img"], 8)


@then("the SVG opens with <svg and closes with </svg>")
def svg_wrapped(ctx):
    assert ctx["svg"].startswith("<svg")
    assert ctx["svg"].endswith("</svg>")


@then("it holds one rect per color run")
def svg_rects(ctx):
    assert ctx["svg"].count("<rect") == 32  # 16 rows x 2 runs


# -- gif.feature --
@given("a 128x128 test image")
def img_128(ctx):
    from PIL import Image as Img

    im = Img.new("RGB", (128, 128))
    px = im.load()
    for y in range(128):
        for x in range(128):
            px[x, y] = ((x * 3) % 256, (y * 3) % 256, 128)
    ctx["img"] = im
    return im


@when("I generate 4 frames in phase mode")
def gen_4(ctx):
    from app.gif import gif_frames
    from app.presets import Preset

    ctx["frames"] = gif_frames(ctx["img"], Preset(name="g"), frames=4, mode="phase")


@then("there are 4 frames and none exceeds 480px per side")
def frames_ok(ctx):
    assert len(ctx["frames"]) == 4
    for f in ctx["frames"]:
        assert max(f.size) <= 480


@when("I generate 4 frames in glitch mode")
def gen_glitch(ctx):
    from app.gif import gif_frames
    from app.presets import Preset

    ctx["frames"] = gif_frames(ctx["img"], Preset(name="g", method="floyd"),
                               frames=4, mode="glitch")


@then("the glitch frames differ from each other")
def glitch_differs(ctx):
    datas = [list(f.get_flattened_data()) for f in ctx["frames"]]
    assert any(a != b for a, b in zip(datas[1:], datas[:-1]))


@when("I generate 4 frames in mix ping-pong mode")
def gen_pingpong(ctx):
    from app.gif import gif_frames
    from app.presets import Preset

    ctx["frames"] = gif_frames(ctx["img"], Preset(name="g"),
                               frames=4, mode="mix", pingpong=True)


@then("the ping-pong loop has 6 frames and loops smoothly")
def pingpong_ok(ctx):
    assert len(ctx["frames"]) == 6  # 4 + middle reversed
    first = list(ctx["frames"][0].get_flattened_data())
    last = list(ctx["frames"][-1].get_flattened_data())
    # No hay salto: el último es el segundo frame (ida-vuelta).
    second = list(ctx["frames"][1].get_flattened_data())
    assert last == second and first != second


# -- flow.feature --
@given("a test image with gradient")
def gradient_flow(ctx):
    from PIL import Image as Img

    im = Img.new("RGB", (32, 32))
    px = im.load()
    for y in range(32):
        for x in range(32):
            px[x, y] = ((x * 8) % 256, (y * 8) % 256, 128)
    ctx["img"] = im
    return im


@when("I apply chromatic aberration dx 4")
def chroma_4(ctx):
    from app.glitch import chromatic_aberration

    ctx["out"] = chromatic_aberration(ctx["img"], dx=4)


@then("the R channel shifts and the G channel stays intact")
def channels_ok(ctx):
    px, ref = ctx["out"].load(), ctx["img"].load()
    assert px[4, 0][0] == ref[0, 0][0]
    assert px[0, 0][1] == ref[0, 0][1]


@when("I apply slice shift twice")
def slice_twice(ctx):
    from app.glitch import slice_shift

    ctx["out_a"] = slice_shift(ctx["img"], bands=4, max_offset=8)
    ctx["out_b"] = slice_shift(ctx["img"], bands=4, max_offset=8)


@when("I apply pixel sort with threshold 128")
def pixelsort_128(ctx):
    from app.glitch import pixel_sort

    ctx["out"] = pixel_sort(ctx["img"], threshold=128)
