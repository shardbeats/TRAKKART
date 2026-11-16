"""v2.0 Fase A: clip import (session-only, cap 120f, 720p proxy) + trim."""

import pytest
from PIL import Image


def _anim(path, n=6, size=(64, 48)):
    frames = []
    for i in range(n):
        frames.append(Image.new("RGB", size, (i * 37 % 256, 40, 90)))
    frames[0].save(str(path), save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    return path


def test_import_gif_proxy_and_caps(tmp_path):
    from app.clip import CLIP_MAX_FRAMES, import_clip

    src = _anim(tmp_path / "c.gif", n=6)
    frames, info = import_clip(src)
    assert len(frames) == 6 and info["frames"] == 6
    assert info["fps"] == 10  # 100ms -> 10fps
    assert info["truncated"] is False
    assert max(frames[0].size) <= 720
    # cap respected: 200-frame gif trims to CLIP_MAX_FRAMES
    big = _anim(tmp_path / "big.gif", n=8)
    f2, i2 = import_clip(big, max_frames=5)
    assert len(f2) == 5 and i2["truncated"] is True
    assert CLIP_MAX_FRAMES == 120


def test_import_rejects_bad_path_and_ext(tmp_path):
    from app.clip import import_clip

    with pytest.raises(FileNotFoundError):
        import_clip(tmp_path / "missing.mp4")
    bad = tmp_path / "x.png"
    Image.new("RGB", (8, 8)).save(bad)
    with pytest.raises(ValueError):
        import_clip(bad)


def test_import_deterministic(tmp_path):
    from app.clip import import_clip

    src = _anim(tmp_path / "d.webp", n=4, size=(48, 32))
    f1, _ = import_clip(src)
    f2, _ = import_clip(src)
    assert len(f1) == len(f2) == 4
    for a, b in zip(f1, f2):
        assert a.tobytes() == b.tobytes()


def test_trim_range_and_errors():
    from app.clip import trim_clip

    frames = [Image.new("RGB", (8, 8), (i, 0, 0)) for i in range(5)]
    sub = trim_clip(frames, 1, 3)
    assert len(sub) == 3
    assert sub[0].getpixel((0, 0)) == (1, 0, 0)
    # clamps to bounds
    assert len(trim_clip(frames, -9, 99)) == 5
    with pytest.raises(ValueError):
        trim_clip(frames, 3, 1)
    with pytest.raises(ValueError):
        trim_clip([], 0, 0)


def test_missing_backend_raises_clean(tmp_path, monkeypatch):
    from app import clip as _clip
    from app.video_io import VideoBackendMissing

    monkeypatch.setattr(_clip, "has_clip_io", lambda: False)
    with pytest.raises(VideoBackendMissing):
        _clip.import_clip(tmp_path / "c.mp4")


def _gradient(w=48, h=32):
    import numpy as np

    x = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    arr = np.stack([x, x, x], axis=-1)
    return Image.fromarray(arr, "RGB")


def test_dither_deterministic_and_recipe():
    from app.clip import dither_clip
    from app.presets import Preset

    frames = [_gradient(), _gradient()]
    p = Preset(name="t", method="bayer4", palette="BW", grain=8.0)
    a = dither_clip(frames, p)
    b = dither_clip(frames, p)
    assert len(a) == 2
    for x, y in zip(a, b):
        assert x.tobytes() == y.tobytes()
    q = Preset(name="t", method="floyd", palette="BW", grain=8.0)
    c = dither_clip(frames, q)
    assert any(x.tobytes() != y.tobytes() for x, y in zip(a, c))


def test_dither_index_seed_flicker():
    from app.clip import dither_clip
    from app.presets import Preset

    same = [Image.new("RGB", (32, 32), (120, 120, 120))] * 2
    grainy = Preset(name="t", method="bayer4", palette="BW", grain=30.0)
    out = dither_clip(same, grainy)
    assert out[0].tobytes() != out[1].tobytes()  # flicker aesthetic
    clean = Preset(name="t", method="bayer4", palette="BW")
    flat = dither_clip(same, clean)
    assert flat[0].tobytes() == flat[1].tobytes()  # no seeds -> stable
    with pytest.raises(ValueError):
        dither_clip([], clean)


def test_frame_zip_sequence(tmp_path):
    import zipfile

    from app.clip import save_clip_zip

    frames = [Image.new("RGB", (16, 12), (i * 40, 0, 0)) for i in range(3)]
    out = save_clip_zip(frames, tmp_path / "clip_frames.zip")
    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        assert zf.namelist() == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
        first = Image.open(__import__("io").BytesIO(zf.read("frame_0001.png")))
        assert first.size == (16, 12)
    with pytest.raises(ValueError):
        save_clip_zip([], tmp_path / "empty.zip")


def _wav(path, secs=1.0, rate=8000):
    import math
    import struct
    import wave

    n = int(secs * rate)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(n):
            v = int(12000 * math.sin(2 * math.pi * 440 * i / rate))
            w.writeframes(struct.pack("<h", v))
    return path


def test_mp4_silent_and_mux(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    from app.clip import mux_soundtrack, write_clip_mp4
    from app.video_io import has_video

    if not has_video():
        pytest.skip("no video backend")
    frames = [Image.new("RGB", (64, 48), (i * 60, 20, 20)) for i in range(4)]
    silent = write_clip_mp4(frames, tmp_path / "clip.mp4", fps=10)
    assert silent.is_file() and silent.stat().st_size > 500
    track = _wav(tmp_path / "track.wav")
    final = mux_soundtrack(silent, track, tmp_path / "clip_music.mp4")
    assert final.is_file() and final.stat().st_size > 500
    with pytest.raises(FileNotFoundError):
        mux_soundtrack(silent, tmp_path / "missing.wav", tmp_path / "x.mp4")
    with pytest.raises(FileNotFoundError):
        mux_soundtrack(tmp_path / "missing.mp4", track, tmp_path / "y.mp4")


def test_import_mp4_when_backend(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    from app.clip import import_clip
    from app.video_io import has_video

    if not has_video():
        pytest.skip("no video backend")
    import imageio.v2 as iio2

    import numpy as np

    path = str(tmp_path / "c.mp4")
    w = iio2.get_writer(path, fps=10, codec="libx264", macro_block_size=2)
    for i in range(4):
        w.append_data(np.full((48, 64, 3), (i * 50) % 256, dtype=np.uint8))
    w.close()
    frames, info = import_clip(path)
    assert len(frames) == 4 and info["frames"] == 4
    assert max(frames[0].size) <= 720
    assert info["start_s"] == 0.0


def test_inpoint_seek_gif_skips_frames(tmp_path):
    """GIF in-point: start_s skips round(start*fps) frames, stays honest."""
    from app.clip import import_clip

    src = _anim(tmp_path / "s.gif", n=10)  # 10fps, 1.0s long
    base, binfo = import_clip(src)
    assert binfo["source_duration"] == pytest.approx(1.0)
    assert binfo["start_s"] == 0.0 and binfo["truncated"] is False
    # 0.3s @10fps -> skip 3 frames, first pixel differs.
    seek, sinfo = import_clip(src, start_s=0.3)
    assert len(seek) == 7 and sinfo["start_s"] == pytest.approx(0.3)
    assert sinfo["truncated"] is True
    assert seek[0].tobytes() == base[3].tobytes()
    assert seek[0].tobytes() != base[0].tobytes()
    with pytest.raises(ValueError):
        import_clip(src, start_s=99.0)


def test_inpoint_seek_mp4_uses_input_ss_and_clamps(tmp_path, monkeypatch):
    """MP4 in-point goes through input -ss; past-the-end fails clean."""
    pytest.importorskip("imageio_ffmpeg")
    import numpy as np

    from app import clip as _clip
    from app.video_io import has_video

    if not has_video():
        pytest.skip("no video backend")
    seen = {}

    class FakeReader:
        def __init__(self, **kw):
            seen.update(kw)

        def get_meta_data(self):
            return {"fps": 10, "nframes": 40, "size": (64, 48),
                    "duration": 4.0}

        def __iter__(self):
            for _ in range(40):
                yield np.zeros((48, 64, 3), dtype=np.uint8)

        def close(self):
            pass

    import imageio.v2 as iio2

    monkeypatch.setattr(iio2, "get_reader", lambda *a, **k: FakeReader(**k))
    frames, fps, truncated, start, duration = _clip._read_mp4("x.mp4", 10, 64, 1.5)
    assert seen.get("input_params") == ["-ss", "1.500"]
    assert (start, duration, truncated) == (1.5, 4.0, True)
    assert len(frames) == 10 and fps == 10
    with pytest.raises(ValueError):
        _clip._read_mp4("x.mp4", 10, 64, 99.0)
