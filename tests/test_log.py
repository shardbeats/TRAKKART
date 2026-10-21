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
