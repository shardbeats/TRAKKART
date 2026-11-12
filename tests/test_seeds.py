"""Seed system: wide ranges, replayable dice, per-file batch seeds."""

from app.batch import SEED_FIELDS, seeded_preset
from app.presets import Preset


def test_mosh_seed_wide_range():
    Preset(name="x", mosh_seed=999999).validate()
    try:
        Preset(name="x", mosh_seed=1000000).validate()
    except ValueError:
        pass
    else:
        raise AssertionError("mosh_seed 1000000 must be rejected")


def test_new_seed_fields_roundtrip():
    kwargs = {f: 123456 for f in SEED_FIELDS}
    p = Preset(name="S", **kwargs)
    p.validate()
    back = Preset.from_dict(p.to_dict())
    for f in SEED_FIELDS:
        assert getattr(back, f) == 123456, f


def test_new_seed_fields_defaults_are_legacy():
    p = Preset(name="S")
    assert (p.grain_seed, p.dust_seed, p.glitch_slice_seed) == (0x7A4B, 0xD57, 0x6A17)
    assert (p.pixelsort_seed, p.wave_seed) == (0x9150, 0x9A9E)
    assert (p.drift_seed, p.paste_seed) == (0xD81F, 0x9A57)


def test_seeded_preset_off_returns_same():
    p = Preset(name="S", mosh_seed=5)
    assert seeded_preset(p, 3, "off") is p


def test_seeded_preset_increment():
    p = Preset(name="S", mosh_seed=5, grain_seed=10)
    q = seeded_preset(p, 1, "increment")
    assert q.mosh_seed == 6 and q.grain_seed == 11
    assert q.dissolve_seed == (53596 + 1) % 1000000
    r = seeded_preset(p, 2, "increment")
    assert r.mosh_seed == 7
    assert p.mosh_seed == 5  # original untouched


def test_seeded_preset_randomize_in_range():
    p = Preset(name="S")
    q = seeded_preset(p, 0, "randomize")
    for f in SEED_FIELDS:
        assert 0 <= getattr(q, f) <= 999999, f


def test_meta_carries_seeds_block():
    p = Preset(name="S", mosh_seed=42, grain_seed=7)
    m = p.meta()
    assert m["seeds"]["mosh"] == 42
    assert m["seeds"]["grain"] == 7
    assert m["texture"]["grain_seed"] == 7
    assert m["glitch"]["mosh_seed"] == 42
    assert "seed" in m["drift"] and "seed" in m["paste"]


def test_mosh_dice_wide_and_logged(window, qt_app):
    window.btn_mosh_dice.click()
    v = window.spn_mosh_seed.value()
    assert 0 <= v <= 999999
    assert str(v) in window.lbl_status.text()


def test_dissolve_dice(window, qt_app):
    window.btn_dissolve_dice.click()
    v = window.spn_dissolve_seed.value()
    assert 0 <= v <= 999999
    assert str(v) in window.lbl_status.text()
    assert window.current_params().dissolve_seed == v


def test_fx_seed_dice(window, qt_app):
    window.btn_grain_dice.click()
    assert 0 <= window.spn_grain_seed.value() <= 999999
    window.btn_dust_dice.click()
    assert 0 <= window.spn_dust_seed.value() <= 999999
    window.btn_slice_dice.click()
    assert 0 <= window.spn_slice_seed.value() <= 999999
    window.btn_pixelsort_dice.click()
    assert 0 <= window.spn_pixelsort_seed.value() <= 999999
    window.btn_wave_dice.click()
    assert 0 <= window.spn_wave_seed.value() <= 999999
    window.btn_drift_dice.click()
    assert window.current_params().drift_seed == window.spn_drift_seed.value()
    window.btn_paste_dice.click()
    assert window.current_params().paste_seed == window.spn_paste_seed.value()
    assert "seed" in window.lbl_status.text()


def test_palette_buttons_roll_and_log(window, qt_app):
    window.btn_pal_gen.click()
    v = window.spn_pal_seed.value()
    assert 0 <= v <= 999999
    assert str(v) in window.lbl_status.text()
    assert len(window.custom_colors) >= 2
    window.btn_pal_shuffle.click()
    assert "seed" in window.lbl_status.text()


def test_surprise_and_adjust_buttons_iterate(window, qt_app):
    from PIL import Image

    window.src = Image.new("RGB", (64, 64), (10, 200, 90))
    window.btn_random.click()
    v = window.spn_chaos_seed.value()
    assert 0 <= v <= 999999
    assert str(v) in window.lbl_status.text()


def test_chaos_seed_replays_surprise(window, qt_app):
    from PIL import Image

    window.src = Image.new("RGB", (64, 64), (10, 200, 90))
    window.spn_chaos_seed.setValue(777)
    window.randomize()
    first = (window.cmb_method.currentText(), window.sld_thr.value(),
             window.spn_pixel.value())
    window.randomize()
    assert (window.cmb_method.currentText(), window.sld_thr.value(),
            window.spn_pixel.value()) == first
    assert "777" in window.lbl_status.text()


def test_palette_seed_replays_generation(window, qt_app):
    window.spn_pal_seed.setValue(4242)
    window.gen_palette()
    first = list(window.custom_colors)
    window.gen_palette()
    assert list(window.custom_colors) == first
    assert "4242" in window.lbl_status.text()


def test_batch_increment_varies_per_file(tmp_path):
    from PIL import Image

    from app.batch import batch_process

    src = tmp_path / "in"
    dst = tmp_path / "out"
    src.mkdir()
    for name in ("a.png", "b.png"):
        Image.new("RGB", (32, 32), (120, 30, 200)).save(src / name)
    p = Preset(name="S", mosh=50.0, mosh_seed=10, mosh_mode="blocks")
    res = batch_process(src, dst, p, seed_mode="increment")
    assert [r["status"] for r in res] == ["ok", "ok"]
    a = (dst / "a.png").read_bytes()
    b = (dst / "b.png").read_bytes()
    assert a != b, "increment mode must vary the damage per file"
    res2 = batch_process(src, tmp_path / "out2", p, seed_mode="off",
                         skip_existing=False)
    assert [r["status"] for r in res2] == ["ok", "ok"]
    assert (tmp_path / "out2" / "a.png").read_bytes() == (
        tmp_path / "out2" / "b.png").read_bytes()
