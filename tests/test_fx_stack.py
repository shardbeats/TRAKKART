"""v1.2 Stackable FX: jpeg determinista, stack ordenado, migración byte-idéntica."""

from PIL import Image


def _img():
    im = Image.new("RGB", (48, 48))
    px = im.load()
    for y in range(48):
        for x in range(48):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    return im


def test_jpeg_deterministic_and_off():
    from app.fx_jpeg import apply_jpeg

    im = _img()
    assert list(apply_jpeg(im, 0).get_flattened_data()) == list(im.get_flattened_data())
    a = apply_jpeg(im, 60)
    b = apply_jpeg(im, 60)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    assert list(a.get_flattened_data()) != list(im.get_flattened_data())


def test_default_stack_byte_identical_to_legacy():
    from app.pipeline import RenderSpec, render_spec

    im = _img()
    spec_new = RenderSpec(method="bayer4", palette_name="SLIME", grain=20.0,
                          vignette=30.0, glitch_chroma=3, jpeg=0.0)
    out_new = render_spec(im, spec_new)
    spec_old = RenderSpec(method="bayer4", palette_name="SLIME", grain=20.0,
                          vignette=30.0, glitch_chroma=3, jpeg=0.0,
                          fx_stack=[{"id": fid, "enabled": True}
                                    for fid in ("split_tone", "fade", "glow", "grain",
                                                "halftone", "dust", "vignette", "scanlines",
                                                "grille", "border", "letterbox", "chroma",
                                                "slice", "pixelsort", "wave", "mosh",
                                                "jpeg", "post_blur", "post_sharpen")])
    out_old = render_spec(im, spec_old)
    assert list(out_new.get_flattened_data()) == list(out_old.get_flattened_data())


def test_reorder_changes_output():
    from app.pipeline import RenderSpec, render_spec

    im = _img()
    base = dict(method="bayer4", palette_name="SLIME", grain=40.0, vignette=60.0)
    a = render_spec(im, RenderSpec(**base, fx_stack=[
        {"id": "grain", "enabled": True}, {"id": "vignette", "enabled": True}]))
    b = render_spec(im, RenderSpec(**base, fx_stack=[
        {"id": "vignette", "enabled": True}, {"id": "grain", "enabled": True}]))
    assert list(a.get_flattened_data()) != list(b.get_flattened_data())


def test_disable_bypasses_effect():
    from app.pipeline import RenderSpec, render_spec

    im = _img()
    on = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME", grain=50.0,
                                    fx_stack=[{"id": "grain", "enabled": True}]))
    off = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME", grain=50.0,
                                     fx_stack=[{"id": "grain", "enabled": False}]))
    plain = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME"))
    assert list(off.get_flattened_data()) == list(plain.get_flattened_data())
    assert list(on.get_flattened_data()) != list(plain.get_flattened_data())


def test_old_preset_migrates_to_default_stack():
    from app.presets import Preset

    p = Preset.from_dict({"name": "old", "method": "bayer4", "palette": "SLIME"})
    assert p.fx_stack is None
    assert p.jpeg == 0.0 and p.post_blur == 0.0 and p.post_sharpen == 0
    spec_kwargs = p.to_render_kwargs()
    assert spec_kwargs["fx_stack"] is None
