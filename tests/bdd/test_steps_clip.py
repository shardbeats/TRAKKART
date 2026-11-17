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


@when("I plan a full-length export of a 10-frame GIF")
def plan_full_length(ctx, tmp_path):
    from PIL import Image as Img

    from app.clip import clip_full_length

    gif = tmp_path / "full.gif"
    frames = [Img.new("RGB", (48, 48), (i * 25 % 256, 40, 90)) for i in range(10)]
    frames[0].save(str(gif), save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    ctx["plan"] = clip_full_length(gif)
    ctx["plan_capped"] = clip_full_length(gif, max_total=4)


@then("the plan holds 10 frames uncapped from the in-point")
def full_plan_ok(ctx):
    assert ctx["plan"]["total_frames"] == 10
    assert ctx["plan"]["capped"] is False
    assert ctx["plan"]["start_s"] == 0.0
    assert ctx["plan_capped"]["total_frames"] == 4
    assert ctx["plan_capped"]["capped"] is True


@when("I estimate clip MP4 weight quiet versus noisy")
def estimate_clip_weights(ctx):
    from app.gif import estimate_clip_mp4

    ctx["quiet"] = estimate_clip_mp4(720, 405, 120, 0.0)
    ctx["noisy"] = estimate_clip_mp4(720, 405, 120, 30.0)


@then("the noisy estimate is several times the quiet one")
def clip_weights_ok(ctx):
    assert ctx["noisy"] > 5 * ctx["quiet"] > 0


@when("I sign a recipe with and without a grain ramp")
def sign_recipe_envelopes(ctx):
    from app.envelopes import envelopes_signature

    ctx["sig_flat"] = envelopes_signature({})
    ctx["sig_ramp"] = envelopes_signature({"grain": {"kind": "ramp", "v0": 0, "v1": 100.0}})


@then("the envelope key differs")
def envelope_key_differs(ctx):
    assert ctx["sig_flat"] != ctx["sig_ramp"]
    assert ctx["sig_flat"] == "off"


@when("I compare a 3s track against a 10s clip")
def compare_track_clip(ctx):
    from app.clip import track_fit_note

    ctx["fit_note"] = track_fit_note(3.0, 10.0)


@then("the note mentions trailing silence")
def track_note_ok(ctx):
    assert "silence after the track ends" in ctx["fit_note"]


@when("I lay out a 120-frame strip")
def layout_strip(ctx):
    from app.ui.clip_controller import strip_indices

    ctx["strip"] = strip_indices(120)


@then("it holds 10 stops from first to last")
def strip_ok(ctx):
    assert len(ctx["strip"]) == 10
    assert ctx["strip"][0] == 0 and ctx["strip"][-1] == 119


@when("I compare proxy and source estimates")
def compare_estimates(ctx):
    from app.gif import estimate_clip_mp4

    ctx["est_proxy"] = estimate_clip_mp4(720, 405, 10, 0.0, 8)
    ctx["est_source"] = estimate_clip_mp4(1280, 720, 10, 0.0, 8)


@then("the source weight is larger")
def source_heavier(ctx):
    assert ctx["est_source"] > ctx["est_proxy"]
