"""UI a11y pins (§12 Fase A-C): foco, teclado, buddies, contraste, estados."""

from __future__ import annotations

from PySide6.QtCore import Qt


def test_zoom_badge_is_keyboard_operable(window):
    badge = window.lbl_zoom
    assert badge.focusPolicy() == Qt.StrongFocus
    assert badge.accessibleName()
    fired = []
    badge.onClick(lambda: fired.append(1))
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent

    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
    badge.keyPressEvent(ev)
    assert fired == [1]


def test_value_slider_home_resets(window):
    from app.ui.widgets import ValueSlider

    sld = ValueSlider(Qt.Horizontal)
    sld.setRange(0, 100)
    sld.setValue(80)
    sld.setDefault(20)
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent

    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Home, Qt.NoModifier)
    sld.keyPressEvent(ev)
    assert sld.value() == 20
    assert sld.focusPolicy() == Qt.StrongFocus


def test_slider_labels_have_buddies_and_names(window):
    from app.ui.panels.widgets import labeled_slider, seed_row, spin_row
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    host = QWidget()
    lay = QVBoxLayout(host)
    sld, _val = labeled_slider(window, lay, "Grano", 0, 100, 10, "grain tip")
    assert sld.accessibleName() == "Grano"
    assert sld.accessibleDescription() == "grain tip"
    spn = spin_row(lay, "Semilla", 0, 10, 1, "seed tip")
    assert spn.accessibleName() == "Semilla"
    spn2, dice = seed_row(lay, window, "_t_spn", "_t_dice", "Motivo", 5, "tip", "roll tip")
    try:
        assert spn2.accessibleName() == "Motivo"
        assert dice.text() == "Roll"
        assert dice.accessibleName()
    finally:
        host.deleteLater()


def test_disabled_contrast_is_readable():
    from pathlib import Path

    qss = Path("app/ui/theme.qss").read_text(encoding="utf-8")
    assert "#383B40" not in qss
    assert "#6B6E73" in qss


def test_focus_ring_covers_interactives():
    from pathlib import Path

    qss = Path("app/ui/theme.qss").read_text(encoding="utf-8")
    for sel in ("QPushButton:focus", "QCheckBox:focus", "QSlider:focus", "QListWidget:focus"):
        assert sel in qss, sel


def test_empty_state_cta_and_retry(window):
    assert window.btn_empty_open is not None
    assert window.btn_empty_open.accessibleName()
    assert window.btn_preview_retry is not None
    window._report_error("Preview error", "[E0007] boom")
    assert "boom" in window.lbl_status.text().lower() or "preview" in window.lbl_status.text().lower()
    assert window.lbl_res.accessibleDescription()


def test_reduced_motion_envlengthens_timers(monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("TRAKKART_REDUCED_MOTION", "1")
    from pathlib import Path as _P

    from app.ui.main_window import MainWindow

    w = MainWindow(out_dir=_P(str(tmp_path)) / "o", db_path=_P(str(tmp_path)) / "h.db",
                   prefs_path=_P(str(tmp_path)) / "p.json")
    try:
        assert w._preview_timer.interval() >= 700
        assert w._video_timer.interval() >= 500
        assert w.lbl_res._resize_timer.interval() >= 500
    finally:
        w.store.close()
        w.close()
    os.environ.pop("TRAKKART_REDUCED_MOTION", None)


def test_export_dialog_adapts_to_short_screens(window, tmp_path):
    from app.ui.export_dialog import ExportDialog

    dlg = ExportDialog(window.src, {"ratio": "1:1"}, base="d", out_dir=str(tmp_path))
    try:
        assert dlg.minimumWidth() == 480
        assert dlg.list_files.minimumHeight() >= 140
        assert dlg.list_files.maximumHeight() <= 220
        assert dlg.list_files.accessibleName()
    finally:
        dlg.close()
        dlg.deleteLater()
