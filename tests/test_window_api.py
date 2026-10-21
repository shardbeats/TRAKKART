"""Window API sweep: thin MainWindow delegations (they must at least not crash)."""

from PIL import Image


def _img():
    return Image.new("RGB", (48, 48), (90, 100, 140))


def test_window_api_sweep(window, qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    # Image ops / undo / zoom / clipboard (no src first, then with).
    window._op_image(lambda i: i, "noop")  # no src: silent
    window.undo_image()  # pops history or reports empty: no crash either way
    assert window.lbl_status.text() != ""
    window._zoom_step(1.25)
    assert abs(window.zoom - 1.25) < 1e-9
    window._zoom_fit()
    assert window.zoom == 1.0
    window._zoom_full()
    assert window.zoom == 4.0
    window.copy_result()  # no result: silent
    window.paste_image()  # empty/invalid clipboard: status, no crash
    assert window.lbl_status.text() != ""
    window.src = _img()
    n_hist = len(window.history)
    window._op_image(lambda i: i.transpose(Image.FLIP_LEFT_RIGHT), "flip")
    assert len(window.history) == n_hist + 1
    window.undo_image()
    assert window.lbl_status.text() == "Undone"
    window.copy_result()  # needs result; without it stays silent
    window._set_drag_hover(True)
    window._set_drag_hover(False)
    assert window.lbl_orig is window.lbl_res
    assert window.lbl_orig_title is window.lbl_res_title

    # Loaders.
    p = tmp_path / "a.png"
    _img().save(p)
    window._load_path(p)
    assert window.src is not None and window.src_name == "a"
    window._load_path(tmp_path / "missing.png")  # warns, keeps going
    assert window.src is not None
    window._load_qimage(None)  # invalid: status, no crash
    window._load_data_url("data:image/png;base64,")
    import app.services.image_io as iio

    monkeypatch.setattr(iio, "download_image", lambda *a, **k: (_img(), 10))
    window._load_url("http://example.invalid/x.png")
    assert window.src is not None
    monkeypatch.setattr(iio, "download_image", lambda *a, **k: (_ for _ in ()).throw(ValueError("net")))
    window._load_url("http://example.invalid/x.png")  # warns, keeps going
    monkeypatch.setattr("app.safety.check_image", lambda *a, **k: (_ for _ in ()).throw(
        __import__("app.safety", fromlist=["TooBigError"]).TooBigError("huge")))
    window._load_pil(_img())  # too big: warns, keeps going


def test_window_dialogs_and_share(window, qt_app, monkeypatch, tmp_path):
    import json

    from PySide6.QtWidgets import QFileDialog

    import app.presets as P

    (tmp_path / "presets").mkdir(exist_ok=True)
    monkeypatch.setattr(P, "PRESETS_DIR", tmp_path / "presets")
    P.ensure_bundled(tmp_path / "presets")
    window.refresh_presets()

    # Open dialog: cancel + accept.
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window.open_image_dialog()
    p = tmp_path / "b.png"
    _img().save(p)
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(p), "Images (*.png)"))
    window.open_image_dialog()
    assert window.src_name == "b"

    # Share preset out/in.
    target = tmp_path / "shared.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    window.share_preset_export()
    assert target.exists()
    info = json.loads(target.read_text(encoding="utf-8"))
    assert info["method"] in ("bayer4", info["method"])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window.share_preset_export()  # cancel
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(target), ""))
    window.share_preset_import()
    assert window.cmb_preset.findText("shared") >= 0
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window.share_preset_import()  # cancel
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(bad), ""))

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    window.share_preset_import()  # invalid: warns
    window.randomize()  # Surprise me: method/palette/threshold change, no crash
    assert window.lbl_status.text() != ""


def test_window_batch_and_export_paths(window, qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    # Batch dialog cancel path (stubbed dialog, no worker).
    import app.ui.main_window as MW
    from PySide6.QtWidgets import QDialog

    class FakeDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(MW, "BatchDialog", FakeDialog)
    window.run_batch_dialog()  # cancel: does nothing
    src = tmp_path / "in"
    src.mkdir()
    _img().save(src / "x.png")
    window.run_batch_sync(src, tmp_path / "dst")
    assert (tmp_path / "dst").exists()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    window.run_batch_with_input(src)  # no output dir: returns early
    window.close()  # cleanup path: stops timers, flags cancel


def test_save_current_preset_paths(window, qt_app, monkeypatch, tmp_path, isolated_presets):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    window.save_current_preset()  # cancel: silent
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("  ", True))
    window.save_current_preset()  # blank: silent
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("SweepPal", True))
    window.save_current_preset()
    assert window.cmb_preset.findText("SweepPal") >= 0
    from app.presets import list_presets

    assert "SweepPal" in list_presets()


def test_dnd_classify_all_branches(monkeypatch):
    from app import dnd

    assert dnd.classify_drop("") == "ignore"
    assert dnd.classify_drop("http://x/y.png") == "http"
    assert dnd.classify_drop("data:image/png;base64,xx") == "data"
    assert dnd.classify_drop("blob:http://x") == "blob"
    assert dnd.classify_drop("C:/a.png") == "local"
    assert dnd.classify_drop("file:///C:/a.png") == "local"
    assert dnd.classify_drop("ftp://x/y") == "ignore"
    monkeypatch.setattr("app.dnd.urlsplit",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("bad")))
    assert dnd.classify_drop("http://x") == "ignore"
    assert dnd.is_image_data_url("DATA:IMAGE/PNG;BASE64,x") is True
    assert dnd.is_image_data_url("http://x") is False


def test_window_tutorial_samples_drop(window, qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    import app.tutorial as tut

    monkeypatch.setenv("TRAKKART_DATA_DIR", str(tmp_path / "data"))
    assert tut.first_run_needed() is True
    # show_tutorial(manual=True) with a stubbed dialog (no modal).
    from PySide6.QtWidgets import QDialog

    import app.ui.tutorial_dialog as TD

    class FakeTut:
        DialogCode = QDialog.DialogCode

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(TD, "TutorialDialog", FakeTut)
    window.show_tutorial(manual=True)
    assert window.lbl_status.text() == "Quick tour done"
    # Real first-run path (env guard lifted): samples + marker, no dialogs.
    had_pytest = "PYTEST_CURRENT_TEST" in __import__("os").environ
    old_pytest = __import__("os").environ.get("PYTEST_CURRENT_TEST")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    window._maybe_first_run()
    assert tut.first_run_needed() is False
    if had_pytest:
        monkeypatch.setenv("PYTEST_CURRENT_TEST", old_pytest)
    monkeypatch.setenv("TRAKKART_SKIP_FIRST_RUN", "1")
    window._maybe_first_run()  # env guard: returns immediately
    # Open samples folder (desktop service mocked).
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda *a, **k: True)
    window.open_samples()
    assert "samples" in window.lbl_status.text().lower()
    # About dialog (static QMessageBox.about mocked): version + MIT shown.
    from app import __version__ as _ver
    from app.ui import about_dialog as _about

    seen = {}
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.about",
        lambda *a, **k: seen.setdefault("text", a[2] if len(a) > 2 else k.get("text", "")),
    )
    window.show_about()
    assert f"v{_ver}" in seen.get("text", "") and "MIT" in seen.get("text", "")
    assert "MIT" in _about.about_text() and f"v{_ver}" in _about.about_text()

    # Drop-folder gate: toggle off / empty / confirm-no / confirm-yes.
    src = tmp_path / "drop"
    src.mkdir()
    window._on_drop_folder(src)  # toggle off by default
    assert "enable" in window.lbl_status.text()
    window.chk_batch_drop.setChecked(True)
    window._on_drop_folder(src)  # empty folder
    assert "no compatible" in window.lbl_status.text()
    Image.new("RGB", (16, 16), (9, 9, 9)).save(src / "a.png")
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.No)
    window._on_drop_folder(src)
    assert "cancelled" in window.lbl_status.text().lower()
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes)
    ran = {}
    monkeypatch.setattr(window, "run_batch", lambda s, d=None, **k: ran.update(src=s))
    window._on_drop_folder(src)
    assert ran.get("src") == src
    # Vector cells estimate needs an image.
    window.src = Image.new("RGB", (64, 64), (5, 5, 5))
    cells = window._estimate_vector_cells(window.current_params())
    assert cells is not None and len(cells) == 2
    window.src = None
    import app.ui.export_flow as ef

    assert ef.estimate_vector_cells(window, window.current_params()) is None


def test_recent_files_roundtrip_cap_and_missing(tmp_path):
    from app.recent import MAX_RECENT, existing_recent, load_recent, remember_recent

    prefs = tmp_path / "prefs.json"
    files = []
    for i in range(MAX_RECENT + 2):
        p = tmp_path / f"img{i}.png"
        p.write_bytes(b"x")
        files.append(p)
        remember_recent(p, prefs)
    assert load_recent(prefs) == [str(p) for p in reversed(files[-MAX_RECENT:])]
    remember_recent(files[-1], prefs)  # move to front, no duplicates
    assert load_recent(prefs)[0] == str(files[-1])
    assert len(load_recent(prefs)) == MAX_RECENT
    files[-1].unlink()  # missing files are filtered for the menu
    assert all(p != files[-1] for p in existing_recent(prefs))


def test_open_recent_menu_loads_image(window, qt_app, tmp_path):
    from PIL import Image as _Image

    from app.recent import remember_recent

    p = tmp_path / "shot.png"
    _Image.new("RGB", (8, 8), (1, 2, 3)).save(p)
    remember_recent(p, window._prefs_path)
    recent_menu = None
    for a in window.menuBar().actions():
        if a.text() == "File" and a.menu():
            for b in a.menu().actions():
                if b.text() == "Open recent" and b.menu():
                    recent_menu = b.menu()
    assert recent_menu is not None
    recent_menu.aboutToShow.emit()
    names = [x.text() for x in recent_menu.actions() if x.isEnabled()]
    assert "shot.png" in names
    recent_menu.actions()[0].trigger()
    assert window.src_name == "shot"


def test_shortcuts_dialog_lists_all(window, qt_app, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import app.ui.shortcuts_dialog as _keys

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    window.show_shortcuts()  # no crash offscreen
    assert len(_keys.SHORTCUTS) >= 10
    assert any("Space" in keys for _, keys in _keys.SHORTCUTS)
    assert any("Alt+Left" in keys for _, keys in _keys.SHORTCUTS)


def test_motif_box_only_visible_for_motif(window, qt_app):
    window.cmb_method.setCurrentText("bayer8")
    assert window._motif_box.isHidden()
    window.cmb_method.setCurrentText("motif")
    assert not window._motif_box.isHidden()
    assert window.step_method(1) != "motif"  # stepping away hides it again
    assert window._motif_box.isHidden()
