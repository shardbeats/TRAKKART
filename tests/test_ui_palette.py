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
