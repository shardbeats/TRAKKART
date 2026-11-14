"""Phase D (v1.7): release gates (preset file roundtrip, determinism, no extra)."""

import json

import pytest
from PIL import Image

from app.anim.plan import plan_segments, segment_total


def _img(color=(10, 20, 30), size=(32, 32)):
    return Image.new("RGB", size, color)


def _chain(n=3):
    return [Image.new("RGB", (32, 32), (i * 70, 30, 200 - i * 50))
            for i in range(n)]


def test_preset_file_roundtrip_keeps_v17_fields(tmp_path):
    from app.presets import Preset, load_preset, save_preset

    p = Preset(name="v17", mosh=42.0, mosh_mode="tear", mosh_seed=321,
               mosh_size=140, dissolve_hold=2.2, dissolve_loop=False)
    save_preset(p, tmp_path)
    back = load_preset("v17", tmp_path)
    assert (back.mosh, back.mosh_mode, back.mosh_seed, back.mosh_size) == (
        42.0, "tear", 321, 140)
    assert (back.dissolve_hold, back.dissolve_loop) == (2.2, False)
    meta = back.meta()
    assert meta["glitch"]["mosh_mode"] == "tear"
    assert meta["glitch"]["mosh_seed"] == 321
    assert meta["glitch"]["mosh_size"] == 140


def test_old_preset_defaults_render_byte_identical(tmp_path):
    from app.pipeline import RenderSpec, render_spec
    from app.presets import Preset, load_preset

    old = Preset(name="old", method="bayer8").to_dict()
    for key in ("mosh", "mosh_mode", "mosh_seed", "mosh_size",
                "dissolve_hold", "dissolve_loop"):
        old.pop(key, None)
    (tmp_path / "old.json").write_text(json.dumps(old), encoding="utf-8")

    back = load_preset("old", tmp_path)
    assert (back.mosh, back.mosh_mode, back.mosh_seed, back.mosh_size) == (
        0.0, "blocks", 0, 100)
    assert (back.dissolve_hold, back.dissolve_loop) == (1.0, True)

    src = _img((12, 34, 56), (32, 24))
    fresh = Preset(name="old", method="bayer8")
    assert render_spec(src, RenderSpec.from_preset(back)).tobytes() == (
        render_spec(src, RenderSpec.from_preset(fresh)).tobytes())


def test_morph_repeats_deterministic_and_planned():
    from app.disintegrate import morph_chain_frames

    imgs = _chain(3)
    reps = [2, 3]
    plan = plan_segments(8, 2, repeats=reps)
    a = morph_chain_frames(imgs, method="bayer8", frames=8, seed=7,
                           repeats=reps)
    b = morph_chain_frames(imgs, method="bayer8", frames=8, seed=7,
                           repeats=reps)
    assert len(a) == len(b) == segment_total(plan)
    assert len(a) == sum(s.frames * s.repeat for s in plan)
    assert [f.tobytes() for f in a] == [f.tobytes() for f in b]


def test_morph_frames_wire_repeats_match_plan():
    from app.anim.frames import gif_morph_frames, iter_morph_frames

    imgs = _chain(3)
    entries = [{"img": imgs[1], "repeat": 2},
               {"img": imgs[2], "repeat": 3}]
    plan = plan_segments(8, 2, repeats=[2, 3])
    listed = gif_morph_frames(imgs[0], entries, frames=8, seed=7)
    streamed = list(iter_morph_frames(imgs[0], entries, frames=8, seed=7))
    assert len(listed) == len(streamed) == segment_total(plan)
    assert [f.tobytes() for f in listed] == [f.tobytes() for f in streamed]

    # Repeat 0 / 99 clamp to the same bounds as the plan (1..8).
    low = gif_morph_frames(imgs[0], [{"img": imgs[1], "repeat": 0}],
                           frames=8, seed=7)
    high = gif_morph_frames(imgs[0], [{"img": imgs[1], "repeat": 99}],
                            frames=8, seed=7)
    one = gif_morph_frames(imgs[0], [{"img": imgs[1]}], frames=8, seed=7)
    assert len(low) == len(one)
    assert len(high) == segment_total(plan_segments(8, 1, repeats=[8]))


def test_video_extra_missing_degrades_cleanly(tmp_path, monkeypatch):
    import sys

    from app import extras, video_io

    # Simulate a dev/frozen install without imageio + imageio-ffmpeg.
    monkeypatch.setitem(sys.modules, "imageio", None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    video_io.reset_encoder_cache()
    try:
        assert video_io.has_video() is False
        assert video_io.available_encoders() == [video_io.SOFTWARE_ENCODER]
        assert video_io.resolve_encoder("auto") == video_io.SOFTWARE_ENCODER
        assert video_io.resolve_encoder(None) == video_io.SOFTWARE_ENCODER

        ok, detail = extras.video_status()
        assert not ok and "MP4 disabled" in detail

        # Stills/particles keep working: only the writer asks for video.
        from app.anim.frames import gif_morph_frames

        frames = gif_morph_frames(_chain(3)[0], [_chain(3)[1]], frames=4)
        assert len(frames) > 0

        with pytest.raises(video_io.VideoBackendMissing, match="pip install"):
            video_io.write_mp4([_img()], tmp_path / "x.mp4")
        with pytest.raises(video_io.VideoBackendMissing, match="pip install"):
            video_io.write_mp4_iter(iter([_img()]), tmp_path / "y.mp4")
        assert not (tmp_path / "x.mp4").exists()
        assert not (tmp_path / "y.mp4").exists()
    finally:
        video_io.reset_encoder_cache()
