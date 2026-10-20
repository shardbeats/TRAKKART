"""Palette library: JSON bundle, dirty tracking, BW fast path (fixtures en conftest)."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def test_bundled_palettes_created_once(tmp_path: Path):
    from app.palette_library import ensure_bundled_palettes, list_palettes

    created = ensure_bundled_palettes(tmp_path)
    assert set(created) == {"BW", "SLIME", "VAPOR", "EMBER"}
    assert list_palettes(tmp_path) == ["BW", "EMBER", "SLIME", "VAPOR"]
    assert ensure_bundled_palettes(tmp_path) == []  # nunca sobrescribe


def test_user_palette_overrides_builtin(tmp_path: Path):
    from app.palette_library import palette_colors, save_palette

    save_palette("SLIME", [(1, 2, 3), (4, 5, 6)], tmp_path)
    assert palette_colors("SLIME", tmp_path) == [(1, 2, 3), (4, 5, 6)]
    assert palette_colors("VAPOR", tmp_path)[0] == (12, 10, 28)  # builtin intacto


def test_save_palette_validates(tmp_path: Path):
    import pytest as _pt

    from app.palette_library import save_palette

    with _pt.raises(ValueError):
        save_palette("one", [(1, 2, 3)], tmp_path)
    with _pt.raises(ValueError):
        save_palette("   ", [(1, 2, 3), (4, 5, 6)], tmp_path)
    with _pt.raises(ValueError):
        save_palette("bad", [["x"]], tmp_path)


def test_is_bw_equivalence():
    from app.palette_library import is_bw

    assert is_bw([(0, 0, 0), (255, 255, 255)]) is True
    assert is_bw([(255, 255, 255), (0, 0, 0)]) is True  # orden da igual
    assert is_bw([(0, 0, 0), (255, 255, 254)]) is False
    assert is_bw([]) is False
    assert is_bw(None) is False


def test_resolve_palette_bw_fast_path():
    from app.pipeline import resolve_palette

    pal, label = resolve_palette("SLIME", [(0, 0, 0), (255, 255, 255)])
    assert pal is None and label == "BW"
    pal, label = resolve_palette("SLIME", [(1, 2, 3), (4, 5, 6)])
    assert pal == [(1, 2, 3), (4, 5, 6)] and label == "custom"


def test_combo_loads_editable_copy(window, qt_app, monkeypatch, tmp_path: Path):
    import app.palette_library as PL

    monkeypatch.setattr(PL, "PALETTES_DIR", tmp_path / "pal")
    PL.ensure_bundled_palettes(tmp_path / "pal")
    window.refresh_palette_list()
    assert "SLIME" in [window.cmb_pal_preset.itemText(i) for i in range(window.cmb_pal_preset.count())]
    window._on_palette_preset_changed("VAPOR")
    assert window.custom_colors[0] == (12, 10, 28)
    assert window._palette_dirty is False
    assert "Custom" not in window.cmb_pal_preset.currentText()
    # tocar un swatch marca dirty
    window._set_custom_colors([*window.custom_colors[:3], (1, 1, 1)])
    assert window._palette_dirty is True
    assert window.cmb_pal_preset.currentText() == "(Custom)"


def test_save_palette_flow(window, qt_app, monkeypatch, tmp_path: Path):
    from PySide6.QtWidgets import QInputDialog

    import app.palette_library as PL

    monkeypatch.setattr(PL, "PALETTES_DIR", tmp_path / "pal2")
    window._set_custom_colors([(10, 20, 30), (40, 50, 60)], dirty=False)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Mine", True))
    window.save_palette_preset()
    assert (tmp_path / "pal2" / "Mine.json").exists()
    assert window.cmb_pal_preset.currentText() == "Mine"
    assert window._palette_dirty is False
    # base no-builtin: current_params usa SLIME pero conserva el custom
    assert window._palette_base == "Mine"
    assert window.current_params().palette == "SLIME"
    assert window.current_params().custom_palette == [[10, 20, 30], [40, 50, 60]]


def test_bw_loads_two_cells(window, qt_app, monkeypatch, tmp_path: Path):
    import app.palette_library as PL

    monkeypatch.setattr(PL, "PALETTES_DIR", tmp_path / "pal3")
    window._on_palette_preset_changed("BW")
    assert window.custom_colors == [(0, 0, 0), (255, 255, 255)]
