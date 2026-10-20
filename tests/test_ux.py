"""v1.5 Iteration UX: viewport modes, heavy fast-path, tutorial, themes."""


def test_viewport_intervals():
    from app.viewport import MODES, mode_label, normalize_mode, resolve_interval

    assert set(MODES) == {"full", "live", "still"}
    assert normalize_mode("FULL") == "full"
    assert normalize_mode("nope") == "live"
    assert resolve_interval("full") == 0
    assert resolve_interval("still") is None
    assert resolve_interval("live", fast=True) == 120
    assert resolve_interval("live", fast=False) == 350
    assert mode_label("still") == "Still"


def test_heavy_preset_detection():
    from types import SimpleNamespace

    from app.viewport import is_heavy_preset

    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=0.0)) is False
    assert is_heavy_preset(SimpleNamespace(pre_blur=2.0, pre_denoise=0, pre_smooth=0.0)) is True
    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=3, pre_smooth=0.0)) is True
    assert is_heavy_preset(SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=1.0)) is True
    assert is_heavy_preset(None) is False


def test_tutorial_steps_and_samples(tmp_path):
    from app.tutorial import STEPS, ensure_samples, first_run_needed, mark_seen

    assert len(STEPS) == 5
    assert all(title and body for title, body in STEPS)
    assert first_run_needed(tmp_path) is True
    paths = ensure_samples(tmp_path)
    assert len(paths) == 3 and all(p.exists() for p in paths)
    assert first_run_needed(tmp_path) is True  # samples != seen
    mark_seen(tmp_path)
    assert first_run_needed(tmp_path) is False
    # Idempotent: second run keeps the same files.
    assert ensure_samples(tmp_path) == paths


def test_themes_all_load_with_same_selectors():
    from app.ui.theme import load_stylesheet, theme_label, theme_names

    base = load_stylesheet("dark")
    assert set(theme_names()) == {"dark", "light", "green", "pink"}
    assert theme_label("green") == "Handheld green"
    for name in theme_names():
        css = load_stylesheet(name)
        assert css
        for sel in ("QGroupBox", "QPushButton#exportBtn", "QSlider::groove:horizontal",
                    "QMenuBar", "QStatusBar", "QLabel#previewFrame"):
            assert sel in css, (name, sel)
    assert load_stylesheet("nope") == base  # unknown falls back to dark


def test_window_viewport_and_theme_switch(window, qt_app):
    from PySide6.QtWidgets import QApplication

    assert window.viewport_mode == "live"
    assert window.lbl_viewport.text() == "Viewport: Live"
    window.set_viewport_mode("still")
    assert window.viewport_mode == "still"
    assert window.lbl_viewport.text() == "Viewport: Still"
    window.set_viewport_mode("full")
    assert window._act_viewport_full.isChecked()
    window.set_theme("green")
    assert window.app_theme == "green"
    assert window._act_theme_green.isChecked()
    assert "8BC34A" in (QApplication.instance().styleSheet() or "")
    window.set_theme("dark")
    assert window.app_theme == "dark"


def test_still_mode_skips_auto_refresh(window, qt_app):
    from PySide6.QtWidgets import QApplication

    window.set_viewport_mode("still")
    window._preview_timer.stop()  # isolate: init arms it once via preset apply
    window._schedule_refresh()  # must not re-arm the timer
    assert not window._preview_timer.isActive()
    assert "Still mode" in window.lbl_status.text()
    # Theme applies app-wide; the window inherits it.
    window.set_theme("green")
    assert window.app_theme == "green"
    assert "8BC34A" in (QApplication.instance().styleSheet() or "")
