"""Presets tests: roundtrip, bundled, validation, delete."""

from pathlib import Path

import pytest

from app.presets import (
    BUNDLED,
    Preset,
    delete_preset,
    ensure_bundled,
    list_presets,
    load_preset,
    save_preset,
)


@pytest.fixture
def pdir(tmp_path: Path) -> Path:
    d = tmp_path / "presets"
    d.mkdir()
    return d


def test_roundtrip(pdir: Path):
    p = Preset(name="My Test", method="floyd", palette="VAPOR", pixel_size=3, threshold=100)
    path = save_preset(p, pdir)
    assert path.exists()
    back = load_preset("My Test", pdir)
    assert back.to_dict() == p.to_dict()


def test_ensure_bundled_no_overwrite(pdir: Path):
    created = ensure_bundled(pdir)
    assert set(created) == set(BUNDLED.keys())
    # edit one and re-ensure: never overwrites
    custom = pdir / "SLIME_FS.json"
    custom.write_text('{"custom": true}', encoding="utf-8")
    assert ensure_bundled(pdir) == []
    assert custom.read_text(encoding="utf-8") == '{"custom": true}'


def test_delete(pdir: Path):
    save_preset(Preset(name="DeleteMe", method="bayer4"), pdir)
    assert "DeleteMe" in list_presets(pdir)
    assert delete_preset("DeleteMe", pdir) is True
    assert delete_preset("DeleteMe", pdir) is False


def test_validation_rejects():
    with pytest.raises(ValueError):
        Preset(name="x", method="nope").validate()
    with pytest.raises(ValueError):
        Preset(name="x", palette="NOPE").validate()
    with pytest.raises(ValueError):
        Preset(name="x", pixel_size=99).validate()
    with pytest.raises(ValueError):
        Preset(name="x", threshold=999).validate()
    with pytest.raises(ValueError):
        save_preset(Preset(name="   "), Path("/tmp"))
    with pytest.raises(FileNotFoundError):
        load_preset("nope-xyz", Path("/tmp/nope_trakkart_123"))


def test_bundled_all_valid():
    for name, params in BUNDLED.items():
        Preset(name=name, **params).validate()


def test_bundled_dissolve_presets():
    from app.presets import load_preset

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        from app.presets import ensure_bundled

        ensure_bundled(Path(d))
        ash = load_preset("ASH_WIND", Path(d))
        dust = load_preset("DUST_RANDOM", Path(d))
        assert (ash.dissolve_mode, ash.dissolve_amount) == ("wind", 1.0)
        assert dust.dissolve_mode == "random"
        ash.validate()
        dust.validate()


def test_roundtrip_extended_fields(pdir: Path):
    p = Preset(name="Full", method="bayer8", palette="EMBER", pixel_size=3, threshold=150,
               brightness=1.2, contrast=0.9, saturation=1.3,
               ratio="9:16", crop_mode="contain", focus_x=20, focus_y=80)
    back = load_preset(save_preset(p, pdir).stem, pdir)
    assert back.to_dict() == p.to_dict()
    assert back.meta()["ratio"] == "9:16"


def test_custom_canvas_validates_and_roundtrips(pdir: Path):
    p = Preset(name="Wide", ratio="custom", canvas_w=1920, canvas_h=800)
    p.validate()
    back = load_preset(save_preset(p, pdir).stem, pdir)
    assert (back.canvas_w, back.canvas_h) == (1920, 800)
    assert back.meta()["canvas"] == {"w": 1920, "h": 800}
    assert back.meta()["ratio"] == "custom"
    with pytest.raises(ValueError):
        Preset(name="x", ratio="custom").validate()  # custom requires concrete W/H
    with pytest.raises(ValueError):
        Preset(name="x", ratio="custom", canvas_w=1920, canvas_h=10).validate()


def test_old_json_without_canvas_migrates(pdir: Path):
    import json

    (pdir / "Legacy.json").write_text(
        json.dumps({"name": "Legacy", "method": "floyd", "ratio": "9:16",
                    "export_size": 3000}), encoding="utf-8")
    back = load_preset("Legacy", pdir)
    assert (back.canvas_w, back.canvas_h) == (1688, 3000)
    assert back.meta()["ratio"] == "9:16"


def test_old_format_loads_with_defaults(pdir: Path):
    import json

    (pdir / "Oldie.json").write_text(json.dumps({"name": "Oldie", "method": "floyd"}), encoding="utf-8")
    back = load_preset("Oldie", pdir)
    assert (back.palette, back.brightness, back.ratio) == ("SLIME", 1.0, "1:1")
    # v0.12 presets with title still load (field ignored, no crash)
    (pdir / "Withtitle.json").write_text(
        json.dumps({"name": "Withtitle", "method": "floyd", "title": "X", "title_position": "top"}),
        encoding="utf-8",
    )
    back2 = load_preset("Withtitle", pdir)
    assert back2.method == "floyd" and not hasattr(back2, "title")


def test_list_presets_missing_dir(tmp_path: Path):
    assert list_presets(tmp_path / "nodir") == []


def test_roundtrip_crop_zoom(pdir: Path):
    p = Preset(name="Zoomy", method="floyd", crop_zoom=2.5,
               ratio="9:16", focus_x=20, focus_y=80)
    back = load_preset(save_preset(p, pdir).stem, pdir)
    assert back.to_dict() == p.to_dict()
    assert back.meta()["zoom"] == 2.5


def test_old_preset_defaults_crop_zoom(pdir: Path):
    import json

    (pdir / "Nozoom.json").write_text(json.dumps({"name": "Nozoom", "method": "floyd"}), encoding="utf-8")
    assert load_preset("Nozoom", pdir).crop_zoom == 1.0


def test_validation_rejects_crop_zoom():
    with pytest.raises(ValueError):
        Preset(name="x", crop_zoom=9).validate()
    with pytest.raises(ValueError):
        Preset(name="x", crop_zoom=0.5).validate()


def test_validation_rejects_extended():
    with pytest.raises(ValueError):
        Preset(name="x", brightness=9).validate()
    with pytest.raises(ValueError):
        Preset(name="x", ratio="99:99").validate()
    with pytest.raises(ValueError):
        Preset(name="x", crop_mode="weird").validate()
    with pytest.raises(ValueError):
        Preset(name="x", focus_x=999).validate()
    with pytest.raises(ValueError):
        Preset(name="x", pre_blur=99).validate()
    with pytest.raises(ValueError):
        Preset(name="x", pre_sharpen=9).validate()
    with pytest.raises(ValueError):
        Preset(name="x", glow_radius=99).validate()
    with pytest.raises(ValueError):
        Preset(name="x", grain=101).validate()
    with pytest.raises(ValueError):
        Preset(name="x", scanlines=5).validate()
    with pytest.raises(ValueError):
        Preset(name="x", pre_hue=999).validate()
    with pytest.raises(ValueError):
        Preset(name="x", scanlines=5).validate()
    with pytest.raises(ValueError):
        Preset(name="x", pre_denoise=9).validate()
    with pytest.raises(ValueError):
        Preset(name="x", pre_smooth=99).validate()
    with pytest.raises(ValueError):
        Preset(name="x", vector_cell=3).validate()
    with pytest.raises(ValueError):
        Preset(name="x", glitch_chroma=99).validate()
    with pytest.raises(ValueError):
        Preset(name="x", glitch_slice_bands=5).validate()
    with pytest.raises(ValueError):
        Preset(name="x", glitch_slice_max=999).validate()
    with pytest.raises(ValueError):
        Preset(name="x", gif_frames=99).validate()
    with pytest.raises(ValueError):
        Preset(name="x", gif_fps=61).validate()
    with pytest.raises(ValueError):
        Preset(name="x", gif_mode="nope").validate()
    Preset(name="x", gif_frames=64, gif_fps=60).validate()  # new caps
    with pytest.raises(ValueError):
        Preset(name="x", replace_color="red").validate()
    with pytest.raises(ValueError):
        Preset(name="x", custom_palette=[[0, 0, 0]]).validate()
    with pytest.raises(ValueError):
        Preset(name="x", export_size=10).validate()
    with pytest.raises(ValueError):
        Preset(name="x", export_format="bmp").validate()
    with pytest.raises(ValueError):
        Preset(name="x", export_quality=0).validate()


def test_export_fields_roundtrip(pdir: Path):
    p = Preset(name="x", export_size=1080, export_format="jpg", export_quality=80)
    p.validate()
    save_preset(p, pdir)
    back = load_preset("x", pdir)
    assert (back.export_size, back.export_format, back.export_quality) == (1080, "jpg", 80)
    assert back.meta()["export"] == {"size": 1080, "format": "jpg", "quality": 80}


def test_safe_name_fallback(pdir: Path):
    path = save_preset(Preset(name="!!!", method="bayer4"), pdir)
    assert path.name == "preset.json"


def test_preset_from_metadata_maps_nested_params():
    import pytest

    from app.presets import preset_from_metadata

    raw = {"params": {"method": "halftone", "palette": "custom",
                      "custom_palette": [[10, 18, 12], [200, 30, 40]],
                      "threshold": 254, "pixel_size": 1,
                      "adjust": {"brightness": 0.98},
                      "glitch": {"mosh": 36.0, "mosh_mode": "chroma", "mosh_seed": 62},
                      "gif": {"export": False, "frames": 64, "mode": "mix",
                              "fps": 12, "pingpong": True, "motion_amount": 0.84}}}
    p = preset_from_metadata(raw, "pasted_demo")
    assert (p.method, p.threshold, p.mosh, p.mosh_mode) == ("halftone", 254, 36.0, "chroma")
    assert (p.gif_frames, p.gif_mode, p.gif_fps) == (64, "mix", 12)
    assert p.gif_pingpong is True and p.motion_amount == 0.84
    assert len(p.custom_palette or []) == 2
    p.validate()
    with pytest.raises(ValueError):
        preset_from_metadata({"no": "params"})


def test_safe_stem_single_home():
    from app.exporter import sanitize_base
    from app.names import safe_stem
    from app.palette_library import _safe_name as lib_name
    from app.presets import _safe_name as preset_name

    assert safe_stem("A B!", "preset") == preset_name("A B!") == "A B"
    assert lib_name("!!!") == "palette" and preset_name("") == "preset"
    assert sanitize_base("Mi Beat v2.0 (final)") == "Mi_Beat_v2_0_final"
    assert sanitize_base("../../evil") == "evil"
