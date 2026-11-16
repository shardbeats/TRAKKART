"""Pins for long-clip streaming (Fase A): windowed source reads + plan.

GIF/WebP need no video backend; MP4 paths are guarded by has_video.
"""

from __future__ import annotations


def _gif(path, n=10, size=48):
    from PIL import Image as Img

    frames = [Img.new("RGB", (size, size), (i * 25 % 256, 40, 90)) for i in range(n)]
    frames[0].save(str(path), save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    return frames


def test_anim_window_matches_single_read(tmp_path):
    from app.clip import _read_anim_frames, import_clip

    p = tmp_path / "w.gif"
    src = _gif(p, n=10)
    frames, _info = import_clip(p)
    assert len(frames) == 10
    part, fps, total = _read_anim_frames(p, 3, 4, 720)
    assert total == 10
    assert [f.tobytes() for f in part] == [f.tobytes() for f in src[3:7]]
    assert fps == 10


def test_iter_source_frames_streams_gif(tmp_path):
    from app.clip import import_clip, iter_source_frames

    p = tmp_path / "s.gif"
    _gif(p, n=10)
    full, _ = import_clip(p)
    assert [f.tobytes() for f in iter_source_frames(p)] == [f.tobytes() for f in full]
    # Windowed: max_total=4 yields the 4-frame prefix, same bytes.
    assert [f.tobytes() for f in iter_source_frames(p, max_total=4)] == \
        [f.tobytes() for f in full[:4]]
    # In-point: start_s=0.3 skips 3 frames at 10fps.
    assert [f.tobytes() for f in iter_source_frames(p, start_s=0.3)] == \
        [f.tobytes() for f in full[3:]]


def test_clip_full_length_plan_gif(tmp_path):
    from app.clip import clip_full_length

    p = tmp_path / "plan.gif"
    _gif(p, n=10)
    plan = clip_full_length(p)
    assert plan["fps"] == 10
    assert plan["total_frames"] == 10
    assert plan["capped"] is False
    capped = clip_full_length(p, max_total=4)
    assert capped["total_frames"] == 4
    assert capped["capped"] is True


def test_iter_dither_source_matches_ram_render(tmp_path):
    from app.clip import dither_clip, import_clip, iter_dither_source
    from app.presets import Preset

    p = tmp_path / "d.gif"
    _gif(p, n=6)
    preset = Preset(name="l", method="bayer4", palette="BW", grain=30.0)
    frames, _ = import_clip(p)
    ram = dither_clip(list(frames), preset)
    streamed = list(iter_dither_source(p, preset))
    assert [f.tobytes() for f in streamed] == [f.tobytes() for f in ram]
    # Same with a grain ramp: identical to the RAM path over the range.
    env = {"grain": {"kind": "ramp", "v0": 0, "v1": 100.0}}
    ram_e = dither_clip(list(frames), preset, envelopes=env)
    streamed_e = list(iter_dither_source(p, preset, envelopes=env))
    assert [f.tobytes() for f in streamed_e] == [f.tobytes() for f in ram_e]


def test_write_clip_mp4_long_gif(tmp_path):
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("imageio_ffmpeg")
    from app.clip import write_clip_mp4_long
    from app.presets import Preset
    from app.video_io import has_video

    if not has_video():
        pytest_mod.skip("no video backend")
    p = tmp_path / "m.gif"
    _gif(p, n=6)
    preset = Preset(name="l", method="bayer4", palette="BW")
    out, n = write_clip_mp4_long(p, tmp_path / "long.mp4", preset, fps=10)
    assert n == 6
    assert out.stat().st_size > 500


def test_mp4_windows_are_contiguous(tmp_path):
    """Adjacent 120f `-ss` windows concatenate byte-identical to one read."""
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("imageio_ffmpeg")
    from app.clip import _read_mp4, iter_source_frames
    from app.video_io import has_video

    if not has_video():
        pytest_mod.skip("no video backend")
    import numpy as np
    from PIL import Image as Img

    p = tmp_path / "contig.mp4"
    import imageio.v2 as iio2

    wr = iio2.get_writer(str(p), fps=24, codec="libx264", quality=8,
                         macro_block_size=2)
    for i in range(200):
        wr.append_data(np.asarray(
            Img.new("RGB", (160, 90), (i * 7 % 256, 100, 30))))
    wr.close()
    gt, fps, *_ = _read_mp4(p, 200, 720, 0.0)
    assert fps == 24
    win = list(iter_source_frames(p, 0.0, 200, 720))
    assert len(win) == len(gt) == 200
    assert [f.tobytes() for f in win] == [f.tobytes() for f in gt]


def test_estimate_clip_mp4_brackets_measured():
    """Estimator brackets the bench points (720x405 bayer4 BW q8).

    Measured: 0.87MB @grain 0, 7.6MB @grain 30 over 120f. The estimate
    is rough (±2x), used for warnings only — pin the bracket, not bytes.
    """
    from app.gif import estimate_clip_mp4

    quiet = estimate_clip_mp4(720, 405, 120, 0.0)
    noisy = estimate_clip_mp4(720, 405, 120, 30.0)
    assert 400_000 < quiet < 1_800_000
    assert 3_800_000 < noisy < 15_200_000
    assert noisy > 5 * quiet
    assert estimate_clip_mp4(720, 405, 0, 30.0) == 0
    assert estimate_clip_mp4(720, 405, 120, "junk") == quiet
