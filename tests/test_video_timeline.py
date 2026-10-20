"""v1.4 Video timeline: drift, layers, paste-up, opt-in video backend."""

from PIL import Image


def _img(size=48):
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    return im


def test_drift_off_is_noop_and_unknown_safe():
    from app.drift import DRIFT_PATTERNS, apply_drift

    assert len(DRIFT_PATTERNS) == 9
    im = _img()
    assert list(apply_drift(im, "off", 80).get_flattened_data()) == list(im.get_flattened_data())
    assert list(apply_drift(im, "snow", 0).get_flattened_data()) == list(im.get_flattened_data())
    assert list(apply_drift(im, "nope", 80).get_flattened_data()) == list(im.get_flattened_data())


def test_drift_deterministic_and_phased():
    from app.drift import apply_drift

    im = _img()
    a = apply_drift(im, "snow", 60, phase=0)
    b = apply_drift(im, "snow", 60, phase=0)
    c = apply_drift(im, "snow", 60, phase=3)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    assert list(a.get_flattened_data()) != list(im.get_flattened_data())
    assert list(a.get_flattened_data()) != list(c.get_flattened_data())
    for p in ("hum_bar", "roll", "crawl", "weave", "flicker", "moire", "sweep", "jitter"):
        assert apply_drift(im, p, 60, phase=1).size == im.size


def test_pasteup_off_noop_and_deterministic():
    from app.pasteup import PASTE_BLOTS, PASTE_MODES, apply_paste

    assert set(PASTE_MODES) == {"off", "paper", "riso", "fiber"}
    assert set(PASTE_BLOTS) == {"overlay", "multiply", "screen"}
    im = _img()
    assert list(apply_paste(im, "off", 80).get_flattened_data()) == list(im.get_flattened_data())
    assert list(apply_paste(im, "paper", 0).get_flattened_data()) == list(im.get_flattened_data())
    a = apply_paste(im, "riso", 70, blend="multiply")
    b = apply_paste(im, "riso", 70, blend="multiply")
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    assert list(a.get_flattened_data()) != list(im.get_flattened_data())
    assert apply_paste(im, "fiber", 50, blend="screen").size == im.size


def test_timeline_ease_and_normalize():
    from app.timeline import ANIM_PROPS, ease_value, normalize_layers

    assert ease_value("linear", 0.5) == 0.5
    assert ease_value("in", 0.5) == 0.25
    assert ease_value("out", 0.5) == 0.75
    assert ease_value("nope", 0.5) == 0.5
    assert len(ANIM_PROPS) == 10
    layers = normalize_layers([
        {"prop": "threshold", "frm": 0, "to": 500, "ease": "in", "start": 9, "end": 2},
        {"prop": "nope", "frm": 0, "to": 1},
        {"prop": "jpeg", "frm": 10, "to": 20, "ease": "weird", "start": 0, "end": 23},
        "junk",
    ])
    assert len(layers) == 2
    assert layers[0]["start"] == 2 and layers[0]["end"] == 9  # swapped
    assert layers[0]["to"] == 254.0  # clamped to prop max
    assert layers[1]["ease"] == "linear"  # unknown ease falls back


def test_timeline_eval_span_and_rounding():
    from app.timeline import animated_props, eval_layers

    base = {"threshold": 128.0, "pixel_size": 2, "pre_hue": 0.0}
    layers = [{"prop": "threshold", "frm": 100.0, "to": 200.0,
               "ease": "linear", "start": 0, "end": 4}]
    assert eval_layers(layers, base, 0, 5)["threshold"] == 100.0
    assert eval_layers(layers, base, 4, 5)["threshold"] == 200.0
    assert eval_layers(layers, base, 2, 5)["threshold"] == 150.0
    # Outside the span the base value rules.
    assert eval_layers([], base, 3, 5) == base
    # Int props round.
    px = eval_layers([{"prop": "pixel_size", "frm": 1, "to": 2,
                       "ease": "linear", "start": 0, "end": 1}], base, 1, 2)
    assert px["pixel_size"] == 2 and isinstance(px["pixel_size"], int)
    assert animated_props(layers) == ["threshold"]


def test_video_backend_missing_skips_cleanly():
    import pytest

    from app.video_io import VideoBackendMissing, has_video, read_clip, write_mp4

    assert has_video() is False
    with pytest.raises(VideoBackendMissing):
        read_clip("whatever.mp4")
    with pytest.raises(VideoBackendMissing):
        write_mp4([_img(16)], "out.mp4")


def test_gif_layers_and_drift_animate_frames():
    from app.gif import gif_frames
    from app.presets import Preset

    im = _img()
    p = Preset(name="t", method="bayer8", palette="SLIME",
               anim_layers=[{"prop": "threshold", "frm": 60.0, "to": 200.0,
                             "ease": "linear", "start": 0, "end": 3}],
               drift_pattern="snow", drift_amount=40.0)
    frames = gif_frames(im, p, frames=4, mode="phase")
    assert len(frames) == 4
    flats = [tuple(f.get_flattened_data()) for f in frames]
    assert len(set(flats)) > 1  # layers + drift + phase all march


def test_preset_v14_roundtrip():
    from app.presets import Preset

    p = Preset.from_dict({"name": "old", "method": "bayer4", "palette": "SLIME"})
    assert p.anim_layers is None and p.drift_pattern == "off"
    assert p.paste_mode == "off" and p.paste_blend == "overlay"
    d = p.to_dict()
    p2 = Preset.from_dict(d)
    assert p2.anim_layers is None and p2.drift_amount == 0.0


def test_default_stack_includes_pasteup_neutral():
    from app.pipeline import RenderSpec, render_spec

    im = _img()
    out = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME"))
    plain = render_spec(im, RenderSpec(
        method="bayer4", palette_name="SLIME",
        fx_stack=[{"id": fid, "enabled": fid != "pasteup"} for fid in
                  ("split_tone", "fade", "glow", "grain", "halftone", "dust",
                   "vignette", "scanlines", "grille", "border", "letterbox",
                   "chroma", "slice", "pixelsort", "wave", "mosh",
                   "jpeg", "post_blur", "post_sharpen", "pasteup")]))
    assert list(out.get_flattened_data()) == list(plain.get_flattened_data())
