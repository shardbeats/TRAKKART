"""Custom palette UX: roles, usage, strip, dialog (fixtures en conftest)."""

import pytest

pytestmark = pytest.mark.slow


def test_rgb_hex_and_roles():
    from app.ui.palette_dialog import luminance_roles, rgb_to_hex

    assert rgb_to_hex((17, 34, 51)) == "#112233"
    assert luminance_roles([]) == []
    assert luminance_roles([(10, 10, 10)]) == ["single"]
    assert luminance_roles([(0, 0, 0), (255, 255, 255)]) == ["shadow", "light"]
    roles = luminance_roles([(255, 255, 255), (0, 0, 0), (128, 128, 128)])
    assert roles == ["light", "shadow", "mid 1"]


def test_palette_usage_half_half():
    from PIL import Image

    from app.ui.palette_dialog import palette_usage

    im = Image.new("RGB", (40, 20))
    px = im.load()
    for y in range(20):
        for x in range(40):
            px[x, y] = (0, 0, 0) if x < 20 else (255, 255, 255)
    usage = palette_usage(im, [(0, 0, 0), (255, 255, 255)])
    assert usage[0] == pytest.approx(50.0, abs=1.0)
    assert usage[1] == pytest.approx(50.0, abs=1.0)
    assert palette_usage(None, [(0, 0, 0)]) == [0.0]


def test_strip_shows_colors_and_hint(window):
    assert window.lbl_custom.text() == "4/16"  # preset SLIME precargado
    assert window.lbl_palette_hint.text() == ""
    window._set_custom_colors([(255, 0, 0)])
    assert window.lbl_custom.text() == "1/16"
    assert "ignored" in window.lbl_palette_hint.text()
    assert window.palette_strip.count() == 2  # 1 swatch + stretch
    window._set_custom_colors([(0, 0, 0), (255, 255, 255)])
    assert window.lbl_palette_hint.text() == ""
    assert window.lbl_custom.text() == "2/16"
    # click en el primer swatch lo quita
    sw = window.palette_strip.itemAt(0).widget()
    sw.click()
    assert window.custom_colors == [(255, 255, 255)]
    assert window.lbl_custom.text() == "1/16"


def test_dialog_sort_remove_move(qt_app):
    from app.ui.palette_dialog import CustomPaletteDialog
    from tests.conftest import close_dialog

    dlg = CustomPaletteDialog([(255, 255, 255), (0, 0, 0), (128, 0, 0)])
    dlg._sort()
    assert dlg.colors[0] == (0, 0, 0)
    assert dlg.colors[-1] == (255, 255, 255)
    dlg._move(0, 1)
    assert dlg.colors[0] != (0, 0, 0)
    dlg._remove(0)
    assert len(dlg.colors) == 2
    dlg.accept()
    assert dlg.result() == dlg.DialogCode.Accepted
    close_dialog(dlg)


def test_dialog_add_and_edit(qt_app, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog

    from app.ui.palette_dialog import CustomPaletteDialog
    from tests.conftest import close_dialog

    dlg = CustomPaletteDialog([(10, 20, 30)])
    monkeypatch.setattr(QColorDialog, "getColor", lambda *a, **k: QColor("#112233"))
    dlg._add()
    assert (17, 34, 51) in dlg.colors
    monkeypatch.setattr(QColorDialog, "getColor", lambda *a, **k: QColor())
    dlg._add()  # cancel: no cambia
    assert len(dlg.colors) == 2
    dlg._edit(0)
    assert (17, 34, 51) in dlg.colors  # inválido: no cambia (sigue el dupe check)
    close_dialog(dlg)


def test_edit_custom_palette_accepts(window, qt_app, monkeypatch):
    import app.ui.palette_dialog as PD

    window.custom_colors = [(200, 0, 0), (0, 200, 0)]

    class FakeDialog:
        DialogCode = PD.CustomPaletteDialog.DialogCode

        def __init__(self, *a, **k):
            self.colors = [(1, 2, 3), (4, 5, 6)]

        def exec(self):
            return FakeDialog.DialogCode.Accepted

    monkeypatch.setattr(PD, "CustomPaletteDialog", FakeDialog)
    window.edit_custom_palette()
    assert window.custom_colors == [(1, 2, 3), (4, 5, 6)]
    assert window.lbl_custom.text() == "2/16"


def test_preview_small_none_without_src(window):
    window.src = None
    assert window._palette_preview_small() is None
    from PIL import Image

    window.src = Image.new("RGB", (64, 64), (9, 9, 9))
    small = window._palette_preview_small()
    assert small is not None and max(small.size) <= 160


def _color(monkeypatch, hexcode):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog

    monkeypatch.setattr(QColorDialog, "getColor",
                        lambda *a, **k: QColor(hexcode) if hexcode else QColor())


def test_brand_duotone_border_picks(window, qt_app, monkeypatch):
    _color(monkeypatch, "#112233")
    window.pick_brand_color()
    assert window.brand_color == "#112233"
    assert window.lbl_brand.text() == "#112233"
    window.pick_duotone_color("dark")
    window.pick_duotone_color("light")
    assert (window.duotone_dark, window.duotone_light) == ("#112233", "#112233")
    assert "→" in window.lbl_duo.text()
    window.pick_border_color()
    assert window.border_color == "#112233"
    window.clear_duotone()
    assert (window.duotone_dark, window.duotone_light) == ("", "")
    assert window.lbl_duo.text() == "(off)"
    _color(monkeypatch, "")  # cancel: nothing changes
    window.pick_brand_color()
    assert window.brand_color == "#112233"
    window.set_brand_color("not-a-color")  # invalid: keeps old + status
    assert window.brand_color == "#112233"
    window.set_duotone_color("dark", "zzz")
    assert window.duotone_dark == ""
    window.set_border_color("")
    assert window.border_color == "#112233"


def test_add_gen_shuffle_lock_adjusts(window, qt_app, monkeypatch):
    _color(monkeypatch, "#123456")
    before = list(window.custom_colors)
    window.add_custom_color()
    assert (18, 52, 86) in window.custom_colors
    window.add_custom_color()  # duplicate: no double add
    assert window.custom_colors.count((18, 52, 86)) == 1
    window.gen_palette()
    assert 2 <= len(window.custom_colors) <= 16
    window._set_custom_colors([(10, 10, 10), (20, 20, 20), (250, 250, 250), (30, 30, 30)],
                              dirty=False)
    window._palette_locks = [True, False, False, False]
    n_before = list(window.custom_colors)
    window.shuffle_palette()
    assert window.custom_colors[0] == n_before[0]  # locked stays
    assert sorted(window.custom_colors) == sorted(n_before)
    from app.ui import color_actions as ca

    ca.toggle_palette_lock(window, 1)
    assert window._palette_locks[1] is True
    ca.toggle_palette_lock(window, 99)  # out of range: no crash
    window._adjust_locks = {"brightness": True}
    before_bri = window.sld_bri.value()
    ca.randomize_adjusts(window)
    assert window.sld_bri.value() == before_bri  # locked untouched
    assert window.lbl_status.text() != ""
    window._adjust_locks = {}
    ca.randomize_adjusts(window)  # unlocked: runs
    window._remove_custom_color(0)
    assert len(window.custom_colors) == 3
    window.clear_custom_colors()
    assert window.custom_colors == []
    window.shuffle_palette()  # <2 free: status, no crash
    assert len(before) >= 2  # sanity: fixture really had colors


def test_extract_import_export_save(window, qt_app, monkeypatch, tmp_path):
    import json

    from PIL import Image
    from PySide6.QtWidgets import QFileDialog

    window.src = None
    window.extract_palette_from_image()
    assert "first" in window.lbl_status.text()
    window.src = Image.new("RGB", (64, 32))
    px = window.src.load()
    for y in range(32):
        for x in range(64):
            px[x, y] = (255, 0, 0) if x < 32 else (0, 0, 255)
    window.spn_pal_depth.setValue(4)
    window.extract_palette_from_image()
    assert 2 <= len(window.custom_colors) <= 4
    assert window._palette_dirty is True

    # Import JSON + GPl into an isolated dir (never touches repo palettes/).
    import app.palette_library as lib

    real_save = lib.save_palette

    def _save_tmp(name, colors, palettes_dir=None):
        return real_save(name, colors, palettes_dir=tmp_path / "pal")

    monkeypatch.setattr(lib, "save_palette", _save_tmp)
    payload = tmp_path / "imp.json"
    payload.write_text(json.dumps({"name": "ImpT", "colors": [[1, 2, 3], [200, 10, 10]]}),
                       encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(payload), ""))
    window.import_palette_file()
    assert window._palette_base == "ImpT"
    gpl = tmp_path / "imp.gpl"
    gpl.write_text("GIMP Palette\nName: GimpT\nColumns: 4\n#\n255   0   0\t#FF0000\n  0   0 255\t#0000FF\n",
                   encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(gpl), ""))
    window.import_palette_file()
    assert window._palette_base == "GimpT"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window.import_palette_file()  # cancel: no crash
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(bad), ""))
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    window.import_palette_file()  # invalid: warns, keeps going

    # Export current strip to tmp (json + gpl).
    out_json = tmp_path / "my.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(out_json), "JSON (*.json)"))
    window.export_palette_file()
    assert out_json.with_suffix(".json").exists()
    out_gpl = tmp_path / "my.gpl"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(out_gpl), "GIMP palette (*.gpl)"))
    window.export_palette_file()
    assert out_gpl.exists()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window.export_palette_file()  # cancel: no crash

    # Save preset dialog paths.
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    window.save_palette_preset()  # cancel: no crash
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("TmpPal", True))
    window.save_palette_preset()
    assert window._palette_base == "TmpPal"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("x", True))
    window._set_custom_colors([(1, 2, 3)])  # 1 color: invalid
    window.save_palette_preset()  # warns, keeps going


def test_palette_list_and_preset_changed(window):
    window._on_palette_preset_changed("")  # empty: no-op
    window._on_palette_preset_changed("(Custom)")  # sentinel: no-op
    window._on_palette_preset_changed("SOURCE")
    assert window._palette_base == "SOURCE"
    assert window._palette_dirty is False
    window._on_palette_preset_changed("VAPOR")
    assert window._palette_base == "VAPOR"
    assert len(window.custom_colors) >= 2
    window._on_palette_preset_changed("no-such-palette")  # fallback: SLIME colors
    from app.palettes import PALETTES

    assert sorted(map(tuple, window.custom_colors)) == sorted(PALETTES["SLIME"])
    window.refresh_palette_list()
    assert window.cmb_pal_preset.count() >= 4
