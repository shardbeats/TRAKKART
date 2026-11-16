"""BDD steps: v2.0 clip import (session-only, dithered per frame)."""

from pytest_bdd import given, scenarios, then, when

scenarios("../../features/clip.feature")


@given("a 48x48 gradient image")
def gradient_48(ctx):
    from PIL import Image as Img

    im = Img.new("RGB", (48, 48))
    px = im.load()
    for y in range(48):
        for x in range(48):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    ctx["img"] = im
    return im


@when("I dither a 3-frame clip twice with the same preset")
def dither_clip_twice(ctx):
    from app.clip import dither_clip
    from app.presets import Preset

    frames = [ctx["img"].copy() for _ in range(3)]
    preset = Preset(name="c", method="bayer4", palette="BW", grain=8.0)
    ctx["out_a"] = dither_clip(frames, preset)
    ctx["out_b"] = dither_clip([f.copy() for f in frames], preset)


@then("both clip outputs match frame by frame")
def clip_outputs_match(ctx):
    assert len(ctx["out_a"]) == len(ctx["out_b"]) == 3
    for a, b in zip(ctx["out_a"], ctx["out_b"]):
        assert a.tobytes() == b.tobytes()


@when("I trim a 5-frame clip from 1 to 3")
def trim_clip_range(ctx):
    from PIL import Image as Img

    from app.clip import trim_clip

    frames = [Img.new("RGB", (16, 16), (i, 0, 0)) for i in range(5)]
    ctx["out"] = trim_clip(frames, 1, 3)


@then("the trim holds 3 frames starting with the second")
def trim_range_ok(ctx):
    assert len(ctx["out"]) == 3
    assert ctx["out"][0].getpixel((0, 0)) == (1, 0, 0)
    assert ctx["out"][-1].getpixel((0, 0)) == (3, 0, 0)
