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


def test_fx_stack_controller_roundtrip(window):
    from app.fx_stack import normalize_stack
    from app.ui import fx_stack_controller as fx

    fx.set_stack(window, None)  # None -> default order, all enabled
    assert [e["id"] for e in window.fx_stack_data] == [e["id"] for e in normalize_stack(None)]
    assert window.fx_list.count() == len(normalize_stack(None))
    # Disable one via the checklist, ADD combo offers it back.
    fx.set_stack(window, [{"id": "grain", "enabled": False}])
    assert "grain" not in [e["id"] for e in fx.get_stack(window) if e["enabled"]]
    fx.on_add(window, "Grain")
    assert any(e["id"] == "grain" and e["enabled"] for e in window.fx_stack_data)
    # Move selected up/down.
    fx.set_stack(window, [{"id": "grain", "enabled": True},
                          {"id": "vignette", "enabled": True}])
    window.fx_list.setCurrentRow(1)
    fx.move_selected(window, -1)
    assert [e["id"] for e in window.fx_stack_data][:2] == ["vignette", "grain"]
    n = len(window.fx_stack_data)
    window.fx_list.setCurrentRow(n - 1)
    fx.move_selected(window, 1)  # last row: no-op
    fx.move_selected(window, -5)  # out of range: no-op
    assert [e["id"] for e in window.fx_stack_data][:2] == ["vignette", "grain"]
    assert len(window.fx_stack_data) == n
    # Toggle off via checkbox state.
    from PySide6.QtCore import Qt

    window.fx_list.setCurrentRow(0)
    window.fx_list.item(0).setCheckState(Qt.Unchecked)
    fx.on_toggled(window)
    assert window.fx_stack_data[0]["enabled"] is False
    # Empty selection: move/add are no-ops.
    window.fx_list.clearSelection()
    fx.move_selected(window, -1)
    fx.on_add(window, "Not An Effect")
    assert window._palette_base  # window alive, no crash
