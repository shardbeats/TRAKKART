"""Pins for video ingress (P1): container whitelist + track probe.

Container reads need the video backend (guarded); the audio probe and
the fit note are pure stdlib/ffmpeg-header logic.
"""

from __future__ import annotations


def _mov(path, n=8, size=(160, 90), fps=24):
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("imageio_ffmpeg")
    import numpy as np
    from PIL import Image as Img
    import imageio.v2 as iio2

    wr = iio2.get_writer(str(path), fps=fps, codec="libx264", quality=8,
                         macro_block_size=2)
    for i in range(n):
        wr.append_data(np.asarray(Img.new("RGB", size, (i * 30 % 256, 40, 90))))
    wr.close()


def _wav(path, seconds=2.0, rate=8000):
    import math
    import wave

    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(
            int(10000 * math.sin(2 * math.pi * 440 * i / rate))
            .to_bytes(2, "little", signed=True)
            for i in range(frames)))


def test_mov_imports_like_mp4(tmp_path):
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("imageio_ffmpeg")
    from app.clip import import_clip
    from app.video_io import has_video

    if not has_video():
        pytest_mod.skip("no video backend")
    p = tmp_path / "c.mov"
    _mov(p)
    frames, info = import_clip(p)
    assert len(frames) == 8
    assert info["fps"] == 24
    assert frames[0].size[0] <= 720


def test_bad_container_still_rejected(tmp_path):
    from app.clip import import_clip

    p = tmp_path / "c.txt"
    p.write_text("nope")
    try:
        import_clip(p)
    except ValueError as e:
        assert "clip must be" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_audio_duration_wav(tmp_path):
    from app.clip import audio_duration

    p = tmp_path / "t.wav"
    _wav(p, seconds=2.0)
    dur = audio_duration(p)
    assert dur is not None and abs(dur - 2.0) < 0.1
    assert audio_duration(tmp_path / "missing.wav") is None


def test_track_fit_note_cases():
    from app.clip import track_fit_note

    assert track_fit_note(None, 10.0) == ""
    assert track_fit_note(3.0, None) == ""
    assert track_fit_note(10.0, 10.2) == ""
    short = track_fit_note(3.0, 10.0)
    assert "silence" in short and "3.0s" in short and "10.0s" in short
    long = track_fit_note(12.0, 10.0)
    assert "cut at the clip end" in long
