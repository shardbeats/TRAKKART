"""UI presets: apply/save/roundtrip (fixtures in conftest)."""

import pytest

pytestmark = pytest.mark.slow


def test_preset_apply_updates_controls(window, isolated_presets):
    window.cmb_preset.setCurrentText("SLIME_FS")
    window.cmb_preset.setCurrentText("CRT_HARD")
    assert window.spn_pixel.value() == 4
    assert window.sld_thr.value() == 160
    assert window._palette_base == "BW"
    assert window.custom_colors == [(0, 0, 0), (255, 255, 255)]


def test_preset_invalid_name_ignored(window, isolated_presets):
    window._apply_preset("NOPE_XYZ")  # must not crash, keeps state


def test_save_preset(window, isolated_presets, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("MyStyle", True))
    window.save_current_preset()
    assert (isolated_presets / "MyStyle.json").exists()
    assert "MyStyle" in [window.cmb_preset.itemText(i) for i in range(window.cmb_preset.count())]


def test_save_preset_cancel(window, isolated_presets, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from app.presets import BUNDLED

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    window.save_current_preset()  # cancel: creates nothing
    assert len(list(isolated_presets.glob("*.json"))) == len(BUNDLED)


def test_adjust_roundtrip_ui(window, isolated_presets, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from app.presets import load_preset

    window.sld_bri.setValue(140)
    window.sld_sat.setValue(50)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("WithAdjust", True))
    window.save_current_preset()
    back = load_preset("WithAdjust", isolated_presets)
    assert back.brightness == 1.4
    assert back.saturation == 0.5
    window.sld_bri.setValue(100)
    window._apply_preset("WithAdjust")
    assert window.sld_bri.value() == 140


def test_pack_share_roundtrip_ui(window, isolated_presets, tmp_path, monkeypatch):
    import json

    from PySide6.QtWidgets import QFileDialog

    import app.paths as _paths
    from app.presets import Preset, load_preset, save_preset

    pal = tmp_path / "pal"
    pal.mkdir()
    (pal / "Custom9.json").write_text(json.dumps(
        {"name": "Custom9", "colors": [[10, 20, 30], [200, 210, 220]]}),
        encoding="utf-8")
    save_preset(Preset(name="PackMe", method="bayer8", palette="BW"), isolated_presets)
    out_zip = tmp_path / "looks.zip"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(out_zip), ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(out_zip), ""))
    monkeypatch.setattr(_paths, "get_presets_dir", lambda: isolated_presets)
    monkeypatch.setattr(_paths, "get_palettes_dir", lambda: pal)
    window.share_pack_export()
    assert out_zip.is_file()

    dst_p, dst_a = tmp_path / "dp", tmp_path / "da"
    monkeypatch.setattr(_paths, "get_presets_dir", lambda: dst_p)
    monkeypatch.setattr(_paths, "get_palettes_dir", lambda: dst_a)
    window.share_pack_import()
    assert load_preset("PackMe", dst_p).method == "bayer8"
    assert (dst_a / "Custom9.json").is_file()


def test_serpentine_ui_roundtrip(window, isolated_presets, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from app.presets import load_preset

    window.cmb_method.setCurrentText("floyd")
    assert window.chk_serpentine.isEnabled()
    window.chk_serpentine.setChecked(True)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Serp", True))
    window.save_current_preset()
    assert load_preset("Serp", isolated_presets).serpentine is True
    window.chk_serpentine.setChecked(False)
    window._apply_preset("Serp")
    assert window.chk_serpentine.isChecked()
    window.cmb_method.setCurrentText("bayer8")
    assert not window.chk_serpentine.isEnabled()
