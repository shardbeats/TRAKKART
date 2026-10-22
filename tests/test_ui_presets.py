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

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    window.save_current_preset()  # cancel: creates nothing
    assert len(list(isolated_presets.glob("*.json"))) == 4


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
