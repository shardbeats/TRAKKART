"""File logging + crash hook (stdlib only, rotating, offscreen-safe)."""

import logging
import sys


def test_setup_logging_writes_file(tmp_path, monkeypatch):
    import app.log as _log

    monkeypatch.setattr(_log, "_INITIALIZED", False)
    path = _log.setup_logging(tmp_path)
    assert path == tmp_path / "trakkart.log"
    logging.getLogger("trakkart").info("hello-log")
    for h in logging.getLogger("trakkart").handlers:
        try:
            h.flush()
        except Exception:  # noqa: BLE001
            pass
    assert "hello-log" in path.read_text(encoding="utf-8")
    n = len(logging.getLogger("trakkart").handlers)
    _log.setup_logging(tmp_path)  # idempotent: no duplicate handler
    assert len(logging.getLogger("trakkart").handlers) == n


def test_crash_hook_logs_and_shows_dialog(tmp_path, monkeypatch, qt_app):
    import app.log as _log

    monkeypatch.setattr(_log, "_INITIALIZED", False)
    log_file = _log.setup_logging(tmp_path)
    import main as _main

    seen = {}
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.critical",
        lambda *a, **k: seen.setdefault("text", str(a[2]) if len(a) > 2 else ""))
    hook = _main.install_crash_hook(log_file)
    try:
        raise ValueError("boom-test")
    except ValueError:
        hook(*sys.exc_info())
    for h in logging.getLogger("trakkart").handlers:
        try:
            h.flush()
        except Exception:  # noqa: BLE001
            pass
    assert "boom-test" in log_file.read_text(encoding="utf-8")
    assert "boom-test" in seen.get("text", "") and str(tmp_path) in seen.get("text", "")


def test_report_error_block_and_remember(tmp_path, monkeypatch):
    import app.log as _log

    monkeypatch.setattr(_log, "_INITIALIZED", False)
    monkeypatch.setattr(_log, "_REPORT_SEQ", 0)
    monkeypatch.setattr(_log, "LAST_REPORT", None)
    log_file = _log.setup_logging(tmp_path)
    try:
        1 / 0
    except ZeroDivisionError as e:
        rid = _log.report_error("video preview", e, {"mode": "morph", "frames": 8})
    assert rid == "E0001"
    text = _log.last_report_text()
    assert "E0001" in text
    assert "video preview" in text and "morph" in text
    assert "ZeroDivisionError" in text and "Traceback" in text
    for h in logging.getLogger("trakkart").handlers:
        try:
            h.flush()
        except Exception:  # noqa: BLE001
            pass
    assert "E0001" in log_file.read_text(encoding="utf-8")
    rid2 = _log.report_error("still", ValueError("x"))
    assert rid2 == "E0002"


def test_friendly_messages():
    from app.log import friendly_message

    assert "internal bug" in friendly_message(
        ValueError("The truth value of an array with more than one "
                   "element is ambiguous. Use a.any() or a.all()"))
    assert "Out of memory" in friendly_message(MemoryError("nope"))
    assert "Out of memory" in friendly_message(
        Exception("GIF needs ~9GB transient (budget 1200MP)"))
    assert "too large" in friendly_message(Exception("TooBig 9000px"))
    assert "backend missing" in friendly_message(
        Exception("VideoBackendMissing: imageio"))
    assert "not found" in friendly_message(FileNotFoundError("x.json"))
    assert "corrupt" in friendly_message(Exception("cannot identify image file"))
    assert friendly_message(ValueError("weird xyz")) == "weird xyz"
    assert friendly_message("") == "Unknown error"


def test_split_report_tag():
    from app.log import split_report_tag

    assert split_report_tag("[E0012] boom") == ("E0012", "boom")
    assert split_report_tag("plain") == (None, "plain")
    assert split_report_tag("") == (None, "")


def test_worker_report_error_logs_in_thread(tmp_path, monkeypatch):
    import app.log as _log
    from app.ui.preview_worker import VideoWorker

    monkeypatch.setattr(_log, "_INITIALIZED", False)
    monkeypatch.setattr(_log, "LAST_REPORT", None)
    _log.setup_logging(tmp_path)
    from PIL import Image

    w = VideoWorker(Image.new("RGB", (8, 8)), None, 64, 4, "morph", False, 1)
    w._report_error(ValueError("truth value of an array is ambiguous"))
    text = _log.last_report_text()
    assert "video preview" in text and "morph" in text
    assert "ValueError" in text and "traceback:" in text
