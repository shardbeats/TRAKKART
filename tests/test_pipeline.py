"""Tests pipeline: render completo + meta_dict."""

from PIL import Image

from app.adjust import Adjust
from app.pipeline import meta_dict, render


def _img() -> Image.Image:
    return Image.new("RGB", (64, 64), (90, 60, 120))


def test_render_full_pipeline():
    out = render(
        _img(), method="bayer4", palette_name="SLIME", threshold=128,
        pixel_size=2, adjust=Adjust(brightness=1.2),
    )
    assert out.size == (64, 64)


def test_render_without_title_and_adjust():
    out = render(_img(), method="floyd", palette_name="BW")
    assert out.size == (64, 64)


def test_render_with_ratio():
    out = render(Image.new("RGB", (400, 300), (10, 20, 30)), ratio="9:16", crop_mode="cover")
    assert abs(out.size[0] / out.size[1] - 9 / 16) < 0.02


def test_render_with_replace_and_custom_palette():
    out = render(
        _img(), method="bayer4",
        custom_palette=[[0, 0, 0], [255, 255, 255], [255, 0, 0]],
        replace_color="#112233",
    )
    assert out.size == (64, 64)
    assert set(out.get_flattened_data()) <= {(0, 0, 0), (255, 255, 255), (255, 0, 0), (17, 34, 51)}


def test_render_with_post_fx_runs():
    out = render(
        _img(), method="bayer8", scanlines=4, glow_intensity=40, glow_radius=4,
        grain=6, vignette=20, pre_blur=1.0, pre_sharpen=1,
    )
    assert out.size == (64, 64)
    m = meta_dict("floyd", "VAPOR", 128, 2, Adjust())
    assert m["method"] == "floyd"
    assert m["adjust"]["brightness"] == 1.0
    assert "title" not in m


def test_render_with_glitch():
    out = render(_img(), method="bayer4", glitch_chroma=4, glitch_slice_bands=4, glitch_slice_max=8)
    assert out.size == (64, 64)
    plain = render(_img(), method="bayer4")
    assert list(out.get_flattened_data()) != list(plain.get_flattened_data())


def test_render_with_grade_and_texture():
    from app.presets import Preset

    p = Preset(
        name="t", method="bayer4", palette="SLIME",
        duotone_dark="#101020", duotone_light="#f0e0c0", duotone_mid=50.0,
        posterize=4, split_tone=30.0, fade=10.0, glow_radius=8.0,
        glow_intensity=20.0, glow_threshold=200,
        halftone=6, halftone_shape="dots", dust=10.0, vignette=20.0,
        scanlines=4, grille=3, border=4, border_color="#ffffff", letterbox=10,
        pixelsort=100, wave=4, mosh=20.0,
    )
    p.validate()
    out = render(_img(), **p.to_render_kwargs())
    assert out.size == (64 + 8, 64 + 8)  # borde de 4px por lado
    plain = render(_img(), method="bayer4", palette_name="SLIME")
    assert list(out.get_flattened_data()) != list(plain.get_flattened_data())
