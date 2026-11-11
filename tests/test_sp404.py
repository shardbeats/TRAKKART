"""Unit tests for the Roland SP-404MKII image pack (startup + screensaver)."""

from pathlib import Path

from PIL import Image


def _art(w=200, h=100):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, 128)
    return im


def test_sp404_frame_exact_size_and_mode():
    from app.sp404 import SP_H, SP_W, sp404_frame

    f = sp404_frame(_art())
    assert (f.width, f.height) == (SP_W, SP_H) == (128, 64)
    assert f.mode == "1"
    # Tall source also cover-fits (no bars, no distortion assert: full bleed).
    assert sp404_frame(_art(60, 300)).size == (128, 64)
    inv = sp404_frame(_art(), invert=True)
    assert inv.tobytes() != f.tobytes()
    import pytest

    with pytest.raises(ValueError):
        sp404_frame(_art().crop((0, 0, 0, 0)))  # empty image


def test_sp404_frame_threshold_direction():
    from app.sp404 import sp404_frame

    dark = Image.new("RGB", (200, 100), (10, 10, 10))
    light = Image.new("RGB", (200, 100), (250, 250, 250))
    assert set(sp404_frame(dark).get_flattened_data()) == {0}
    assert set(sp404_frame(light).get_flattened_data()) == {255}


def test_sp404_pack_names_counts_and_bmp():
    import tempfile

    from app.sp404 import README_NAME, STARTUP_NAMES, write_sp404_pack

    imgs = [_art(200 + i * 7, 100) for i in range(20)]  # over the caps
    with tempfile.TemporaryDirectory() as d:
        out = write_sp404_pack(imgs, Path(d))
        assert [k for k in out if k.startswith("startup")] == list(STARTUP_NAMES)
        shots = [k for k in out if k.startswith("screen_saver")]
        assert len(shots) == 16
        assert shots[0] == "screen_saver_1.bmp" and shots[-1] == "screen_saver_16.bmp"
        assert README_NAME in out
        for name, path in out.items():
            assert path.exists()
            if name.endswith(".bmp"):
                with Image.open(path) as im:
                    assert im.size == (128, 64)
                    assert im.mode == "1"
        assert "SHIFT + PAD 14" in (Path(d) / README_NAME).read_text(encoding="utf-8")


def test_sp404_pack_single_image_and_errors():
    import tempfile

    import pytest

    from app.sp404 import STARTUP_NAMES, screen_saver_name, write_sp404_pack

    with tempfile.TemporaryDirectory() as d:
        out = write_sp404_pack([_art()], Path(d))
        assert list(out) == [STARTUP_NAMES[0], "README-SP404.txt"]
    with pytest.raises(ValueError):
        write_sp404_pack([], Path("unused"))
    with pytest.raises(ValueError):
        screen_saver_name(0)
    with pytest.raises(ValueError):
        screen_saver_name(17)
    assert screen_saver_name(16) == "screen_saver_16.bmp"


def test_sp404_pack_deterministic():
    import tempfile

    from app.sp404 import write_sp404_pack

    imgs = [_art(160, 120), _art(120, 160)]
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        a = write_sp404_pack(imgs, Path(d1))
        b = write_sp404_pack(imgs, Path(d2))
        assert a.keys() == b.keys()
        for k in a:
            assert a[k].read_bytes() == b[k].read_bytes()
