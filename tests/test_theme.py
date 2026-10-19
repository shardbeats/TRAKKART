"""TRAKK family theme tests."""

from app.ui.theme import THEME_FILE, accent, load_stylesheet


def test_stylesheet_loads_with_family_tokens():
    css = load_stylesheet()
    assert css
    for token in ("#151617", "#F5A623", "#E5E5E5", "#45474A", "Segoe UI", "#exportBtn"):
        assert token in css, token
    assert THEME_FILE.exists()
    assert accent() == "#F5A623"


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
