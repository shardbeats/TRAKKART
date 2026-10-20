"""Shared BDD givens/thens used by 2+ domain modules (visible a todo tests/bdd)."""

from PIL import Image
from pytest_bdd import given, then


def _gradient(size: int = 64) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            v = int(x / (size - 1) * 255)
            px[x, y] = (v, v // 2, 255 - v)
    return im


@given("a 64x64 test gradient")
def gradient_64(ctx):
    ctx["img"] = _gradient(64)
    return ctx["img"]


@given("a 128x128 solid test image")
def solid_128(ctx, tmp_path):
    ctx["img"] = Image.new("RGB", (128, 128), (200, 50, 90))
    ctx["tmp"] = tmp_path
    return ctx["img"]


@then("both outputs are identical")
def identical_outputs(ctx):
    assert list(ctx["out_a"].get_flattened_data()) == list(ctx["out_b"].get_flattened_data())


@then("thumb_1080p is 1920x1080")
def thumb_size(ctx):
    with Image.open(ctx["paths"]["thumb_1080p"]) as im:
        assert im.size == (1920, 1080)


@given("a 128x128 test image")
def img_128_global(ctx):
    im = Image.new("RGB", (128, 128))
    px = im.load()
    for y in range(128):
        for x in range(128):
            px[x, y] = ((x * 3) % 256, (y * 3) % 256, 128)
    ctx["img"] = im
    return im


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
