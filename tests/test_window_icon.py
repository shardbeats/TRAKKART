"""Window icon pins (nov-2026): title-bar corner must not fall back to W11 default."""

from __future__ import annotations


def test_find_app_icon_resolves_in_dev():
    from app.paths import find_app_icon

    icon = find_app_icon("icon.png")
    assert icon is not None and icon.is_file()


def test_find_app_icon_missing_returns_none(tmp_path, monkeypatch):
    import app.paths as P

    monkeypatch.setattr(P, "bundle_path", lambda *a: tmp_path / "nope.png")
    assert P.find_app_icon("nope.png") is None


def test_main_window_has_icon(window):
    assert not window.windowIcon().isNull()


def test_qapp_global_icon_follows_window(window, qt_app):
    from PySide6.QtGui import QIcon

    from app.paths import find_app_icon

    icon = find_app_icon("icon.png")
    assert icon is not None
    qt_app.setWindowIcon(QIcon(str(icon)))
    assert not qt_app.windowIcon().isNull()
