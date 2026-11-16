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
