"""Settings: default output + export defaults + general behavior."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_prefs_new_fields_roundtrip(tmp_path):
    from app.export_prefs import load_prefs, save_prefs

    p = tmp_path / "p.json"
    prefs = load_prefs(p)
    assert prefs.jobs == 1 and prefs.drop_batch is False and prefs.viewport == "live"
    prefs.jobs = 4
    prefs.drop_batch = True
    prefs.viewport = "still"
    prefs.out_dir = str(tmp_path / "out")
    save_prefs(prefs, p)
    back = load_prefs(p)
    assert (back.jobs, back.drop_batch, back.viewport) == (4, True, "still")
    assert back.out_dir.endswith("out")


def test_prefs_normalizes_bad_values(tmp_path):
    import json

    from app.export_prefs import load_prefs

    p = tmp_path / "p.json"
    p.write_text(json.dumps({"jobs": 99, "viewport": "nope", "format": "bmp"}), encoding="utf-8")
    back = load_prefs(p)
    assert back.jobs == 8
    assert back.viewport == "live"
    assert back.format == "png"


def test_prefs_normalizes_all_numeric_and_enums(tmp_path):
    import json

    from app.export_prefs import load_prefs

    p = tmp_path / "p.json"
    p.write_text(json.dumps({
        "gif_frames": "abc", "gif_fps": 999, "gif_size": -5,
        "quality": 0, "size": 10**9, "gif_mode": "nope",
        "base": "   ", "overwrite": "overwrite",
        "recent_files": [" a ", "", None, 42],
    }), encoding="utf-8")
    back = load_prefs(p)
    assert (back.gif_frames, back.gif_fps, back.gif_size) == (6, 60, 64)
    assert (back.quality, back.size) == (1, 8000)  # clamped, not defaulted
    assert back.gif_mode == "both"
    assert back.base == "trakkart_cover"
    assert back.overwrite == "rename"
    assert back.recent_files == [" a ", "None", "42"]  # blanks dropped, rest kept verbatim


def test_resolve_out_dir_fallbacks(tmp_path):
    from app.export_prefs import is_writable_dir, resolve_out_dir

    assert is_writable_dir(tmp_path) is True
    assert is_writable_dir("") is False
    assert is_writable_dir(None) is False
    # missing nested path under a writable parent counts as creatable
    assert is_writable_dir(tmp_path / "new" / "sub") is True
    # unwritable preferred -> falls back to a real dir, never raises
    target = resolve_out_dir(tmp_path / "chosen", fallback=tmp_path / "fb")
    assert target == tmp_path / "chosen" and target.is_dir()
    target2 = resolve_out_dir(None, fallback=tmp_path / "fb2")
    assert target2.is_dir()


def test_dialog_fields_normalize_and_summary():
    from app.ui.dialog_fields import gif_summary, normalize_gif_spec

    assert normalize_gif_spec(99, "nope", 0, True) == {
        "frames": 64, "mode": "both", "fps": 2, "pingpong": True}
    assert normalize_gif_spec("abc", "hue", None, False)["frames"] == 6
    spec = normalize_gif_spec(6, "phase", 8, True)
    assert gif_summary(spec, "canvas px") == "6f · phase · 8fps · 0.8s · ping-pong · canvas px"
    assert gif_summary(spec) == "6f · phase · 8fps · 0.8s · ping-pong"


def test_dialog_fields_widgets(qt_app):
    from app.ui.dialog_fields import build_folder_row, build_format_quality, build_jobs_spin

    cmb, spn = build_format_quality("bmp", 999)
    assert cmb.currentText() == "png" and spn.value() == 100
    jobs = build_jobs_spin(99)
    assert jobs.value() == 8
    _row, edit, btn = build_folder_row("Input folder:", "", None)
    assert edit.isReadOnly() and btn.text() == "Browse..."
    _row2, edit2, _b2 = build_folder_row("Output folder:", "", None, editable=True)
    assert not edit2.isReadOnly()


def test_settings_dialog_values(qt_app):
    from app.export_prefs import ExportPrefs
    from app.ui.settings_dialog import SettingsDialog

    prefs = ExportPrefs(out_dir="", format="jpg", quality=80, size=2000,
                        image=True, thumb_1080p=False, vector=True,
                        jobs=3, drop_batch=True, viewport="full")
    dlg = SettingsDialog(prefs, data_dir="/tmp", recent_count=2)
    try:
        v = dlg.values()
        assert v["format"] == "jpg" and v["quality"] == 80 and v["size"] == 2000
        assert v["jobs"] == 3 and v["drop_batch"] is True and v["viewport"] == "full"
        assert v["thumb_1080p"] is False and v["vector"] is True
        assert v["clear_recents"] is False
        dlg.btn_clear_recent.click()
        assert dlg.values()["clear_recents"] is True
    finally:
        from tests.conftest import close_dialog

        close_dialog(dlg)


def test_open_settings_applies_and_saves(window, qt_app, tmp_path, monkeypatch):
    from app.export_prefs import load_prefs
    from app.ui import settings_dialog as _sd

    out = tmp_path / "custom_out"
    captured = {}

    class FakeDlg:
        DialogCode = type("C", (), {"Accepted": 1, "Rejected": 0})

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def deleteLater(self):
            pass

        def values(self):
            return {"out_dir": str(out), "format": "webp", "quality": 77,
                    "size": 1500, "image": True, "thumb_1080p": True,
                    "vector": False, "anim": False, "metadata": True,
                    "jobs": 5, "drop_batch": True, "viewport": "still",
                    "clear_recents": True}

    monkeypatch.setattr(_sd, "SettingsDialog", FakeDlg)
    # recent to clear
    from app.recent import remember_recent

    remember_recent(tmp_path / "f.png", window._prefs_path)
    window.open_settings()
    assert window.out_dir == out and out.is_dir()
    assert window.spn_jobs.value() == 5
    assert window.chk_batch_drop.isChecked() is True
    assert window.viewport_mode == "still"
    back = load_prefs(window._prefs_path)
    assert (back.format, back.quality, back.size) == ("webp", 77, 1500)
    assert (back.jobs, back.drop_batch, back.viewport) == (5, True, "still")
    assert back.recent_files == []
    assert "Settings saved" in window.lbl_status.text()
    captured["ok"] = True


def test_open_settings_cancel_keeps_state(window, qt_app, monkeypatch):
    from app.ui import settings_dialog as _sd

    before_out = str(window.out_dir)
    before_jobs = window.spn_jobs.value()

    class CancelDlg:
        DialogCode = type("C", (), {"Accepted": 1, "Rejected": 0})

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 0

        def deleteLater(self):
            pass

    monkeypatch.setattr(_sd, "SettingsDialog", CancelDlg)
    window.open_settings()
    assert str(window.out_dir) == before_out
    assert window.spn_jobs.value() == before_jobs
    assert "cancelled" in window.lbl_status.text().lower()
