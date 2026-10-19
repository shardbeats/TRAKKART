"""Tests GIF animado: frames, determinismo, tope 480px, modos."""

from PIL import Image

from app.gif import GIF_MODES, estimate_gif, gif_frames, save_gif
from app.presets import Preset


def _preset(**kw) -> Preset:
    base = dict(method="bayer4", palette="SLIME", pixel_size=2)
    base.update(kw)
    return Preset(name="g", **base)


def _img(size: int = 128) -> Image.Image:
    im = Image.new("RGB", (size, size), (90, 60, 140))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 3) % 256, (y * 3) % 256, 128)
    return im


def test_frames_count_and_size_cap():
    big = Image.new("RGB", (1200, 800), (10, 20, 30))
    frames = gif_frames(big, _preset(), frames=4, mode="phase")
    assert len(frames) == 4
    for f in frames:
        assert max(f.size) <= 480


def test_frames_deterministic():
    a = gif_frames(_img(), _preset(), frames=3, mode="both")
    b = gif_frames(_img(), _preset(), frames=3, mode="both")
    for fa, fb in zip(a, b):
        assert list(fa.get_flattened_data()) == list(fb.get_flattened_data())


def test_modes_differ_and_invalid_falls_back():
    base = gif_frames(_img(), _preset(), frames=3, mode="phase")
    hue = gif_frames(_img(), _preset(), frames=3, mode="hue")
    assert any(
        list(a.get_flattened_data()) != list(b.get_flattened_data()) for a, b in zip(base, hue)
    )
    fallback = gif_frames(_img(), _preset(), frames=2, mode="nope")
    assert len(fallback) == 2
    assert set(GIF_MODES) == {"phase", "hue", "both"}


def test_save_gif_valid(tmp_path):
    frames = gif_frames(_img(), _preset(), frames=3, mode="phase")
    out = save_gif(frames, tmp_path / "a_anim.gif", fps=8)
    assert out.exists() and out.stat().st_size > 100
    with Image.open(out) as im:
        assert im.n_frames == 3
        assert im.format == "GIF"


def test_save_gif_empty_raises(tmp_path):
    import pytest

    from app.gif import save_gif

    with pytest.raises(ValueError):
        save_gif([], tmp_path / "x.gif")


def test_estimate():
    assert estimate_gif(6, 120, 120) == 6 * 120 * 120 // 2


def test_gif_end_to_end_bundle(tmp_path):
    from app.exporter import export_bundle

    p = _preset(gif_export=True, gif_frames=3)
    frames = gif_frames(_img(), p, frames=3, mode="both")
    paths = export_bundle(_img(), tmp_path, base="g", meta=p.meta(), gif_frames=frames)
    assert paths["anim"].exists()
    assert paths["anim"].suffix == ".gif"
    import json

    info = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    assert info["gif"]["frames"] == 3
    assert info["params"]["gif"]["export"] is True
