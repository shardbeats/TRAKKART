"""Datamosh module: 10 modes (identity/determinism/distinct) + wiring."""

from PIL import Image


def _img(w: int = 160, h: int = 120) -> Image.Image:
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (x % 256, y % 256, (x + y) % 256)
    return im


def _flat(im) -> list:
    return list(im.get_flattened_data())


def test_modes_off_identity_and_deterministic():
    from app.mosh import MOSH_MODES, apply_mosh

    solid = Image.new("RGB", (64, 48), (90, 100, 140))
    for mode in MOSH_MODES:
        assert apply_mosh(solid, mode=mode, amount=0) is solid
        a = apply_mosh(_img(), mode=mode, amount=60)
        b = apply_mosh(_img(), mode=mode, amount=60)
        assert _flat(a) == _flat(b)
        assert a.size == (160, 120)


def test_modes_differ_on_content():
    from app.mosh import MOSH_MODES, apply_mosh

    outs = {m: _flat(apply_mosh(_img(), mode=m, amount=60)) for m in MOSH_MODES}
    assert all(v != _flat(_img()) for v in outs.values())
    assert len({str(v) for v in outs.values()}) == len(outs)
    assert _flat(apply_mosh(_img(), mode="nope", amount=60)) == outs["blocks"]


def test_seed_and_size_vary_deterministically():
    from app.mosh import MOSH_MODES, apply_mosh

    for mode in MOSH_MODES:
        a = apply_mosh(_img(), mode=mode, amount=60, seed=7, size=150)
        b = apply_mosh(_img(), mode=mode, amount=60, seed=7, size=150)
        assert _flat(a) == _flat(b)
        ref = _flat(apply_mosh(_img(), mode=mode, amount=60))
        assert _flat(a) != ref  # seed/size move every flavor
        assert _flat(apply_mosh(_img(), mode=mode, amount=60, size=100)) == ref


def test_legacy_wrapper_byte_identical():
    from app.glitch import datamosh as legacy
    from app.mosh import apply_mosh, mosh_blocks

    assert _flat(legacy(_img(), amount=50)) == _flat(mosh_blocks(_img(), amount=50))
    assert _flat(legacy(_img(), amount=50, seed=99)) == _flat(
        apply_mosh(_img(), mode="blocks", amount=50, seed=99 - 0x405))


def test_preset_roundtrip_and_old_default():
    from app.presets import Preset

    p = Preset(name="M", mosh=40.0, mosh_mode="smear", mosh_seed=7, mosh_size=150)
    p.validate()
    back = Preset.from_dict(p.to_dict())
    assert (back.mosh, back.mosh_mode, back.mosh_seed, back.mosh_size) == (40.0, "smear", 7, 150)
    old = Preset.from_dict({"name": "old"})
    assert (old.mosh_mode, old.mosh_seed, old.mosh_size) == ("blocks", 0, 100)
    for bad in ({"mosh_mode": "nope"}, {"mosh_seed": 1000000}, {"mosh_size": 9}):
        try:
            Preset(name="x", **bad).validate()
        except ValueError:
            pass
        else:
            raise AssertionError(f"validation must reject {bad}")


def test_pipeline_carries_mode_and_meta():
    import dataclasses

    from app.pipeline import RenderSpec, render_spec
    from app.presets import Preset

    base = Preset(name="t", mosh=50.0, mosh_mode="blocks")
    other = dataclasses.replace(base, mosh_mode="smear")
    assert RenderSpec.from_preset(other).mosh_mode == "smear"
    assert RenderSpec.from_preset(other).meta()["glitch"]["mosh_mode"] == "smear"
    assert RenderSpec.from_preset(other).meta()["glitch"]["mosh_seed"] == 0
    assert RenderSpec.from_preset(other).meta()["glitch"]["mosh_size"] == 100
    assert _flat(render_spec(_img(), RenderSpec.from_preset(base))) != _flat(
        render_spec(_img(), RenderSpec.from_preset(other)))


def test_mode_combo_defaults_and_binds(window, qt_app):
    assert window.cmb_mosh_mode.currentText() == "blocks"
    assert window.current_params().mosh_mode == "blocks"
    window.cmb_mosh_mode.setCurrentText("rows")
    assert window.current_params().mosh_mode == "rows"
    window.spn_mosh_seed.setValue(42)
    window.sld_mosh_size.setValue(150)
    p = window.current_params()
    assert (p.mosh_seed, p.mosh_size) == (42, 150)
    window.btn_mosh_dice.click()
    assert 0 <= window.spn_mosh_seed.value() <= 999999
    assert "seed" in window.lbl_status.text()


def test_gif_animates_per_mode_deterministically():
    from app.gif import gif_frames
    from app.presets import Preset

    p = Preset(name="t", mosh=30.0, mosh_mode="ghost", motion_amount=1.0)
    a = gif_frames(_img(64, 48), p, frames=3, mode="mix")
    b = gif_frames(_img(64, 48), p, frames=3, mode="mix")
    assert len(a) == 3
    assert [_flat(f) for f in a] == [_flat(f) for f in b]
