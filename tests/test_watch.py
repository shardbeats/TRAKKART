"""Watch folder (R11): state, settle, debounce, fixed preset, no modals."""

import os
import time

from PIL import Image


def _img(path, w=48, h=48):
    im = Image.new("RGB", (w, h), (200, 60, 40))
    im.save(path)
    return path


def _old(path, secs=10):
    t = time.time() - secs
    os.utime(path, (t, t))
    return path


class _StubWorker:
    """Synchronous BatchWorker stand-in (no threads in tests)."""

    made = []

    class _Sig:
        def __init__(self):
            self.fns = []

        def connect(self, fn):
            self.fns.append(fn)

    def __init__(self, src, dst, preset, **kw):
        _StubWorker.made.append((src, dst, preset))
        self.finished = _StubWorker._Sig()
        self.error = _StubWorker._Sig()

    def start(self):
        from app.batch import batch_process

        src, dst, preset = _StubWorker.made[-1]
        try:
            results = batch_process(src, dst, preset, skip_existing=True, jobs=1)
        except Exception as e:  # noqa: BLE001
            for fn in self.error.fns:
                fn(str(e))
            return
        for fn in self.finished.fns:
            fn(results)

    def isRunning(self):  # noqa: N802
        return False

    def blockSignals(self, _b):  # noqa: N802,ARG002
        return False


def _stub_worker(monkeypatch):
    import app.ui.main_window as _mw

    _StubWorker.made = []
    monkeypatch.setattr(_mw, "BatchWorker", _StubWorker)


def test_watch_start_stop_state(window, qt_app, monkeypatch, tmp_path):
    from app.ui import watch_flow as wf

    _stub_worker(monkeypatch)
    src = tmp_path / "in"
    src.mkdir()
    _old(_img(src / "a.png"))
    out = tmp_path / "out"
    assert wf.watch_start(window, src, out, "SLIME_FS") is True
    assert wf.is_watching(window) is True
    assert window._watch_preset == "SLIME_FS"
    assert window.act_watch.isChecked() is True
    # Initial cycle ran synchronously through the stub.
    assert (out / "a.png").exists()
    assert "Watch:" in window.lbl_status.text()
    wf.watch_stop(window)
    assert wf.is_watching(window) is False
    assert window.act_watch.isChecked() is False
    assert window.lbl_status.text() == "Watch stopped"


def test_watch_start_rejects_bad_input(window, qt_app, tmp_path):
    from app.ui import watch_flow as wf

    assert wf.watch_start(window, tmp_path / "nope", tmp_path / "o", "SLIME_FS") is False
    assert wf.is_watching(window) is False
    assert "not a folder" in window.lbl_status.text()
    assert wf.watch_start(window, tmp_path, tmp_path / "o", "NOPE") is False
    assert "bad preset" in window.lbl_status.text()


def test_watch_settle_defers_fresh_files(window, qt_app, monkeypatch, tmp_path):
    from app.ui import watch_flow as wf

    _stub_worker(monkeypatch)
    src = tmp_path / "in"
    src.mkdir()
    _img(src / "fresh.png")  # mtime now -> unsettled
    out = tmp_path / "out"
    assert wf._watch_settled(src) is False
    assert wf.watch_start(window, src, out, "SLIME_FS") is True
    assert _StubWorker.made == []  # no worker while unsettled
    assert "settle" in window.lbl_status.text()
    assert window._watch_timer.isActive() is True  # re-armed
    assert wf._watch_settled(tmp_path / "empty-missing") is True


def test_watch_busy_coalesces_and_pending_recycles(window, qt_app, monkeypatch, tmp_path):
    from app.ui import watch_flow as wf

    _stub_worker(monkeypatch)
    src = tmp_path / "in"
    src.mkdir()
    _old(_img(src / "a.png"))
    out = tmp_path / "out"
    assert wf.watch_start(window, src, out, "SLIME_FS") is True
    assert len(_StubWorker.made) == 1  # initial cycle
    window._watch_busy = True
    wf._on_watch_timeout(window)
    assert window._watch_pending is True
    assert len(_StubWorker.made) == 1  # no second worker while busy
    window._watch_busy = False
    wf._on_watch_finished(window, [])
    assert window._watch_pending is False
    assert len(_StubWorker.made) == 2  # pending recycled into a new cycle


def test_watch_cycle_stops_when_preset_gone(window, qt_app, monkeypatch, tmp_path):
    from app.ui import watch_flow as wf

    _stub_worker(monkeypatch)
    src = tmp_path / "in"
    src.mkdir()
    _old(_img(src / "a.png"))
    assert wf.watch_start(window, src, tmp_path / "o", "SLIME_FS") is True
    window._watch_preset = "NOPE-GONE"
    wf._watch_cycle(window)
    assert wf.is_watching(window) is False
    assert "preset gone" in window.lbl_status.text()


def test_watch_error_keeps_watching(window, qt_app, tmp_path):
    from app.ui import watch_flow as wf

    window._watch_src = tmp_path
    wf._on_watch_error(window, "boom")
    assert "still watching" in window.lbl_status.text()


def test_toggle_watch_dialog_paths(window, qt_app, monkeypatch, tmp_path):
    from app.ui import main_window as _mw
    from app.ui import watch_flow as wf

    src = tmp_path / "in"
    src.mkdir()
    _old(_img(src / "a.png"))
    out = tmp_path / "out"

    class _Dlg:
        DialogCode = type("C", (), {"Accepted": 1, "Rejected": 0})

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def paths(self):
            return src, out

        def deleteLater(self):
            pass

    monkeypatch.setattr(_mw, "WatchDialog", _Dlg)
    monkeypatch.setattr(_mw, "BatchWorker", _StubWorker)
    _StubWorker.made = []
    window.cmb_preset.setCurrentText("SLIME_FS")
    wf.toggle_watch(window)  # opens dialog -> starts
    assert wf.is_watching(window) is True
    wf.toggle_watch(window)  # watching -> stops
    assert wf.is_watching(window) is False


def test_watch_dialog_validates(window, qt_app, tmp_path):
    from PySide6.QtWidgets import QDialog

    from app.ui.batch_dialog import WatchDialog

    dlg = WatchDialog(in_dir=str(tmp_path / "nope"), out_dir=str(tmp_path / "o"),
                      preset_name="SLIME_FS", parent=window)
    try:
        dlg._on_start()
        assert dlg.result() != QDialog.DialogCode.Accepted
        assert "existing" in dlg.lbl_hint.text()
        dlg.edit_in.setText(str(tmp_path))
        dlg._on_start()
        assert dlg.result() == QDialog.DialogCode.Accepted
        assert dlg.paths()[0] == tmp_path
    finally:
        dlg.deleteLater()
