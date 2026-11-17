"""Pins for v2.x #8: animated APNG (Pillow-native, dialog-only extra).

Same frames as the GIF path, full color like WebP. Pins: roundtrip
(n_frames + pixels + default image) + estimate honesty + service
writer (`{base}_anim.png`) + suffix naming.
"""

from __future__ import annotations

from PIL import Image


def _frames():
    return [Image.new("RGB", (64, 64), (i * 40, 100, 150)) for i in range(3)]


def test_apng_roundtrip(tmp_path):
    # v2.x #8: same frames in, same frames out; first frame = still.
    from app.gif import save_apng

    out = save_apng(_frames(), tmp_path / "anim.png", fps=12)
    assert out.exists() and out.stat().st_size > 100
    back = Image.open(out)
    assert back.n_frames == 3
    assert getattr(back, "is_animated", False) is True
    for i, want in enumerate([(0, 100, 150), (40, 100, 150), (80, 100, 150)]):
        back.seek(i)
        assert back.convert("RGB").getpixel((0, 0)) == want


def test_apng_empty_raises(tmp_path):
    import pytest

    from app.gif import save_apng

    with pytest.raises(ValueError, match="no frames"):
        save_apng([], tmp_path / "empty.png")


def test_apng_estimate_and_name():
    # Size note: ~4x the GIF on dithered noise (measured 240px: 4.1x),
    # plan-only upper bound like the rest of the family.
    from app.exporter import APNG_SUFFIX, apng_name
    from app.gif import estimate_apng, estimate_gif

    assert apng_name("cover") == "cover_anim.png"
    assert APNG_SUFFIX == "_anim.png"
    assert estimate_apng(12, 3000, 3000) == estimate_gif(12, 3000, 3000) * 4
    assert estimate_apng(0, 64, 64) == 0


def test_export_service_apng(window, qt_app, tmp_path):
    # Dialog-only extra rides the GIF frames ({base}_anim.png).
    from app.exporter import ExportSelection, apng_name
    from app.presets import Preset
    from app.services.export_service import export_full

    def _img(w, h):
        im = Image.new("RGB", (w, h))
        px = im.load()
        for y in range(h):
            for x in range(w):
                px[x, y] = ((x * 3) % 256, (y * 3) % 256, 128)
        return im

    window.src = _img(64, 64)
    preset = Preset(
        name="t", method="bayer4", palette="SLIME", gif_export=False,
        gif_frames=2, export_size=64)
    sel = ExportSelection(
        image=True, thumb_1080p=False, vector=False, anim=False, metadata=False)
    paths, skipped = export_full(
        window.src, preset, tmp_path / "oa", base="m",
        selection=sel, apng=True, gif_frames=2, gif_size=64)
    assert paths["apng"].name == apng_name("m")
    assert paths["apng"].exists() and paths["apng"].stat().st_size > 100
    back = Image.open(paths["apng"])
    assert back.n_frames == 2
