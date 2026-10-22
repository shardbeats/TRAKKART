"""Static dark stylesheet tests (no theme switching)."""

from pathlib import Path

THEME_FILE = Path(__file__).resolve().parent.parent / "app" / "ui" / "theme.qss"


def test_stylesheet_loads_with_family_tokens():
    assert THEME_FILE.exists()
    css = THEME_FILE.read_text(encoding="utf-8")
    assert css
    for token in ("#151617", "#F5A623", "#E5E5E5", "#45474A", "Segoe UI", "#exportBtn"):
        assert token in css, token


def test_stylesheet_covers_selectors():
    css = THEME_FILE.read_text(encoding="utf-8")
    for sel in ("QGroupBox", "QPushButton#exportBtn", "QSlider::groove:horizontal",
                "QMenuBar", "QStatusBar", "QLabel#previewFrame"):
        assert sel in css, sel


def test_window_applies_stylesheet(tmp_path):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    w = MainWindow(out_dir=tmp_path / "o", db_path=tmp_path / "h.db")
    assert "151617" in w.styleSheet()
    assert w.statusBar() is not None
    w.close()
