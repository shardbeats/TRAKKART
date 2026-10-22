"""Session restore + settings backup tests."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _shot(tmp_path, name="cover.png"):
    from PIL import Image as _Image

    p = tmp_path / name
    _Image.new("RGB", (32, 32), (10, 200, 90)).save(p)
    return p


def test_remember_image_persists(window, tmp_path):
    from app.export_prefs import load_prefs
    from app.ui import session_flow as _sf

    p = _shot(tmp_path)
    _sf.remember_image(window, p)
    assert load_prefs(window._prefs_path).last_image == str(p)


def test_restore_reopens_image_and_preset(window, tmp_path):
    from app.export_prefs import load_prefs, save_prefs
    from app.ui import session_flow as _sf

    p = _shot(tmp_path)
    prefs = load_prefs(window._prefs_path)
    prefs.restore_session = True
    prefs.last_image = str(p)
    prefs.last_preset = window.cmb_preset.currentText()
    save_prefs(prefs, window._prefs_path)
    window.src = None
    assert _sf.restore(window) is True
    assert window.src is not None
    assert window.src_name == "cover"
    assert "Session restored" in window.lbl_status.text()


def test_restore_disabled_or_missing(window, tmp_path):
    from app.export_prefs import load_prefs, save_prefs
    from app.ui import session_flow as _sf

    prefs = load_prefs(window._prefs_path)
    prefs.restore_session = False
    prefs.last_image = str(tmp_path / "ghost.png")
    save_prefs(prefs, window._prefs_path)
    before = window.src
    assert _sf.restore(window) is False
    assert window.src is before
    prefs.restore_session = True  # missing file also refuses
    save_prefs(prefs, window._prefs_path)
    assert _sf.restore(window) is False


def test_save_on_close_stores_preset_and_clears_stale(window):
    from app.export_prefs import load_prefs
    from app.ui import session_flow as _sf

    _sf.save_on_close(window)
    assert load_prefs(window._prefs_path).last_preset == window.cmb_preset.currentText()
    window.src = None
    _sf.save_on_close(window)
    assert load_prefs(window._prefs_path).last_image == ""


def test_load_path_records_session(window, tmp_path):
    from app.export_prefs import load_prefs

    p = _shot(tmp_path, "shot.png")
    window._load_path(p)
    assert load_prefs(window._prefs_path).last_image == str(p)
    assert window.src_name == "shot"


def test_backup_roundtrip_and_invalid(tmp_path, qt_app, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from app.export_prefs import apply_dialog_values, load_backup_file, load_prefs, save_prefs
    from app.ui.settings_dialog import SettingsDialog

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    src = tmp_path / "prefs.json"
    save_prefs(load_prefs(src), src)  # defaults file
    dlg = SettingsDialog(load_prefs(src), data_dir="/tmp", recent_count=0, prefs_path=src)
    try:
        dlg.cmb_format.setCurrentText("webp")
        dlg.spn_jobs.setValue(6)
        dlg.chk_session.setChecked(False)
        # drive the real slots with stubbed file dialogs
        backup = tmp_path / "backup.json"
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(backup), "")))
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
                            staticmethod(lambda *a, **k: (str(backup), "")))
        dlg._on_export_backup()
        assert backup.is_file()
        back = load_backup_file(backup)
        assert (back.format, back.jobs, back.restore_session) == ("webp", 6, False)
        # corrupt the dialog, then import the backup back in
        dlg.cmb_format.setCurrentText("png")
        dlg._on_import_backup()
        assert dlg.cmb_format.currentText() == "webp"
        assert dlg.values()["restore_session"] is False
        # invalid file warns instead of resetting
        bad = tmp_path / "bad.json"
        bad.write_text("{no json", encoding="utf-8")
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
                            staticmethod(lambda *a, **k: (str(bad), "")))
        import pytest

        with pytest.raises(Exception):
            load_backup_file(bad)
        dlg._on_import_backup()  # warning path, dialog keeps values
        assert dlg.cmb_format.currentText() == "webp"
    finally:
        from tests.conftest import close_dialog

        close_dialog(dlg)
    # pure helper: unknown keys ignored, clear_recents honored
    prefs = apply_dialog_values(load_prefs(src), {"jobs": 99, "nope": 1, "clear_recents": True})
    assert prefs.jobs == 99 and prefs.recent_files == []
