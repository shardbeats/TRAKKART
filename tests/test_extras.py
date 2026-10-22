"""Extras tests: detection (pure) + Settings group (Qt)."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_extras_detection_pure():
    from app import extras as _ex

    assert _ex.is_frozen() is False  # pytest never runs frozen
    accel_ok, accel_txt = _ex.accel_status()
    assert isinstance(accel_ok, bool) and accel_txt
    video_ok, video_txt = _ex.video_status()
    assert isinstance(video_ok, bool) and video_txt
    assert _ex.missing_packages("accel") == ("numba",)
    assert _ex.missing_packages("video") == ("imageio", "imageio-ffmpeg")
    assert _ex.pip_install_cmd(("numba",)) == [sys.executable, "-m", "pip", "install", "numba"]
    import pytest

    with pytest.raises(ValueError):
        _ex.missing_packages("nope")


def test_settings_extras_group_dev(qt_app, monkeypatch):
    import app.extras as _ex
    from app.export_prefs import ExportPrefs
    from app.ui.settings_dialog import SettingsDialog

    monkeypatch.setattr(_ex, "is_frozen", lambda: False)
    monkeypatch.setattr(_ex, "accel_status", lambda: (False, "numpy fallback"))
    monkeypatch.setattr(_ex, "video_status", lambda: (False, "MP4 desactivado"))
    dlg = SettingsDialog(ExportPrefs(), data_dir="/tmp", recent_count=0)
    try:
        assert "numpy fallback" in dlg.lbl_accel.text()
        assert "MP4 desactivado" in dlg.lbl_video.text()
        assert dlg.btn_accel.isEnabled() and dlg.btn_video.isEnabled()
        assert "Reinicia" in dlg.lbl_extra_note.text() or "reiniciar" in dlg.lbl_extra_note.text()
    finally:
        from tests.conftest import close_dialog

        close_dialog(dlg)


def test_settings_extras_group_frozen(qt_app, monkeypatch):
    import app.extras as _ex
    from app.export_prefs import ExportPrefs
    from app.ui.settings_dialog import SettingsDialog

    monkeypatch.setattr(_ex, "is_frozen", lambda: True)
    dlg = SettingsDialog(ExportPrefs(), data_dir="/tmp", recent_count=0)
    try:
        assert not dlg.btn_accel.isEnabled() and not dlg.btn_video.isEnabled()
        assert "TRAKKART-full.exe" in dlg.lbl_extra_note.text()
    finally:
        from tests.conftest import close_dialog

        close_dialog(dlg)
