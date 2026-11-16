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


@when("I import a 10-frame GIF from 0.3s")
def import_gif_from_offset(ctx, tmp_path):
    from PIL import Image as Img

    from app.clip import import_clip

    gif = tmp_path / "seek.gif"
    frames10 = [Img.new("RGB", (48, 48), (i * 25 % 256, 40, 90)) for i in range(10)]
    frames10[0].save(str(gif), save_all=True, append_images=frames10[1:],
                     duration=100, loop=0)
    frames, info = import_clip(gif, start_s=0.3)
    ctx["seek_frames"] = frames
    ctx["seek_info"] = info
    ctx["seek_total"] = 10
    ctx["seek_head"] = frames10[3].tobytes()


@then("the import starts at the fourth frame and flags truncation")
def seek_import_ok(ctx):
    frames, info = ctx["seek_frames"], ctx["seek_info"]
    assert len(frames) == ctx["seek_total"] - 3
    assert info["start_s"] == 0.3
    assert info["truncated"] is True
    assert frames[0].tobytes() == ctx["seek_head"]


@when("I render a still animation with empty envelopes")
def render_empty_envelopes(ctx):
    from app.gif import gif_frames
    from app.presets import Preset

    preset = Preset(name="e", method="bayer4", palette="BW", grain=40.0)
    ctx["flat"] = gif_frames(ctx["img"], preset, frames=4, mode="both", max_side=48)
    ctx["curved"] = gif_frames(ctx["img"], preset, frames=4, mode="both",
                               max_side=48, envelopes={})


@then("the envelope output matches the flat output")
def empty_envelopes_identical(ctx):
    assert [f.tobytes() for f in ctx["flat"]] == [f.tobytes() for f in ctx["curved"]]


@when("I render a still animation with a grain ramp")
def render_grain_ramp(ctx):
    from app.gif import gif_frames
    from app.presets import Preset

    preset = Preset(name="e", method="bayer4", palette="BW", grain=40.0)
    ctx["flat"] = gif_frames(ctx["img"], preset, frames=4, mode="both", max_side=48)
    env = {"grain": {"kind": "ramp", "v0": 0, "v1": 100.0}}
    ctx["ramp_a"] = gif_frames(ctx["img"], preset, frames=4, mode="both",
                               max_side=48, envelopes=env)
    ctx["ramp_b"] = gif_frames(ctx["img"], preset, frames=4, mode="both",
                               max_side=48, envelopes=env)


@then("the ramp output differs and re-renders identically")
def grain_ramp_moves(ctx):
    flat = [f.tobytes() for f in ctx["flat"]]
    a = [f.tobytes() for f in ctx["ramp_a"]]
    b = [f.tobytes() for f in ctx["ramp_b"]]
    assert a != flat
    assert a == b
