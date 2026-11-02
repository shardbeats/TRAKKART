"""Watch flow (R11): folder watched -> auto-batch with a fixed preset.

QFileSystemWatcher + 2s debounce; only new/changed files process
(batch skip-existing = free idempotency). New files get a 3s settle
delay so half-copied images are never baked. Preset is fixed by NAME
at start (reloaded every cycle, so edits to it apply). Stateless:
no history spam, session-only (no prefs), jobs=1 sequential.

State on MainWindow (`_watch_*`); no modals anywhere on this path
(status bar only: a modal per drop would punish the feature).
"""

from __future__ import annotations

import time
from pathlib import Path

SETTLE_S = 3.0
DEBOUNCE_MS = 2000
REARM_MS = 3000


def _worker_cls():
    # Resolvable via MW for test stubs (same seam as batch_flow).
    from app.ui import main_window as _mw

    return _mw.BatchWorker


def _dialog_cls():
    from app.ui import main_window as _mw

    return getattr(_mw, "WatchDialog", None) or __import__(
        "app.ui.batch_dialog", fromlist=["WatchDialog"]).WatchDialog


def is_watching(win) -> bool:
    return getattr(win, "_watch_src", None) is not None


def toggle_watch(win) -> None:
    """File menu entry: stop when watching, else open the Watch dialog."""
    if is_watching(win):
        watch_stop(win)
        return
    Dialog = _dialog_cls()
    try:
        preset_name = str(win.cmb_preset.currentText())
    except Exception:  # noqa: BLE001
        preset_name = "SLIME_FS"
    try:
        in_init = str(win.out_dir)
    except Exception:  # noqa: BLE001
        in_init = ""
    try:
        out_init = str(win.out_dir)
    except Exception:  # noqa: BLE001
        out_init = ""
    dlg = Dialog(in_dir=in_init, out_dir=out_init,
                 preset_name=preset_name, parent=win)
    if dlg.exec() != dlg.DialogCode.Accepted:
        dlg.deleteLater()
        return
    src, dst = dlg.paths()
    dlg.deleteLater()
    watch_start(win, src, dst, preset_name)


def watch_start(win, src, dst, preset_name: str) -> bool:
    """Validate + arm the watcher; runs an initial cycle. Returns watching."""
    from app.presets import load_preset

    src_p, dst_p = Path(src), Path(dst)
    if not src_p.is_dir():
        win._status(f"Watch: input is not a folder: {src_p}")
        return False
    try:
        dst_p.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        win._status(f"Watch: cannot create output {dst_p}: {e}")
        return False
    try:
        load_preset(str(preset_name)).validate()
    except Exception as e:  # noqa: BLE001
        win._status(f"Watch: bad preset {preset_name}: {e}")
        return False
    watch_stop(win, quiet=True)
    from PySide6.QtCore import QFileSystemWatcher, QTimer

    win._watch_src = src_p
    win._watch_dst = dst_p
    win._watch_preset = str(preset_name)
    win._watch_cancel = [False]
    win._watch_busy = False
    win._watch_pending = False
    win._watch_worker = None
    watcher = QFileSystemWatcher([str(src_p)], win)
    watcher.directoryChanged.connect(lambda _: _on_watch_dir_changed(win))
    win._watcher = watcher
    timer = QTimer(win)
    timer.setSingleShot(True)
    timer.setInterval(DEBOUNCE_MS)
    timer.timeout.connect(lambda: _on_watch_timeout(win))
    win._watch_timer = timer
    try:
        win.act_watch.setChecked(True)
    except Exception:  # noqa: BLE001
        pass
    win._status(f"Watching {src_p} → {dst_p} ({preset_name})")
    _watch_cycle(win)
    return True


def watch_stop(win, msg: str = "Watch stopped", quiet: bool = False) -> None:
    """Disarm everything (a running cycle finishes but reports nowhere)."""
    try:
        win._watch_cancel[0] = True
    except Exception:  # noqa: BLE001
        pass
    for attr in ("_watcher", "_watch_timer"):
        try:
            obj = getattr(win, attr, None)
            if obj is not None:
                try:
                    obj.deleteLater()
                except Exception:  # noqa: BLE001
                    pass
            setattr(win, attr, None)
        except Exception:  # noqa: BLE001
            pass
    try:
        if getattr(win, "_watch_worker", None) is not None:
            win._watch_worker.blockSignals(True)
    except Exception:  # noqa: BLE001
        pass
    win._watch_worker = None
    win._watch_src = None
    win._watch_dst = None
    win._watch_preset = ""
    win._watch_busy = False
    win._watch_pending = False
    try:
        win.act_watch.setChecked(False)
    except Exception:  # noqa: BLE001
        pass
    if not quiet:
        try:
            win._status(msg)
        except Exception:  # noqa: BLE001
            pass


def _on_watch_dir_changed(win) -> None:
    if not is_watching(win):
        return
    try:
        win._watch_timer.start(DEBOUNCE_MS)  # restart: coalesce bursts
    except Exception:  # noqa: BLE001
        pass


def _on_watch_timeout(win) -> None:
    if not is_watching(win):
        return
    if bool(getattr(win, "_watch_busy", False)):
        win._watch_pending = True
        return
    _watch_cycle(win)


def _watch_settled(src: Path) -> bool:
    """True when no image file was touched in the last SETTLE_S seconds."""
    from app.batch import EXTS

    try:
        now = time.time()
        for f in Path(src).iterdir():
            if f.is_file() and f.suffix.lower() in EXTS:
                if now - f.stat().st_mtime < SETTLE_S:
                    return False
    except OSError:
        return True
    return True


def _watch_cycle(win) -> None:
    """One batch run on the worker thread (preset reloaded by name)."""
    if not is_watching(win):
        return
    from app.presets import load_preset

    try:
        preset = load_preset(str(win._watch_preset))
        preset.validate()
    except Exception as e:  # noqa: BLE001
        watch_stop(win, msg=f"Watch stopped: preset gone ({e})")
        return
    if not _watch_settled(win._watch_src):
        win._status("Watch: waiting for files to settle…")
        try:
            win._watch_timer.start(REARM_MS)
        except Exception:  # noqa: BLE001
            pass
        return
    BatchWorker = _worker_cls()
    win._watch_busy = True
    worker = BatchWorker(win._watch_src, win._watch_dst, preset,
                         store=None, jobs=1, cancel=win._watch_cancel)
    worker.finished.connect(lambda results: _on_watch_finished(win, results))
    worker.error.connect(lambda msg: _on_watch_error(win, msg))
    win._watch_worker = worker
    worker.start()


def _on_watch_finished(win, results: list) -> None:
    win._watch_busy = False
    win._watch_worker = None
    if not is_watching(win):
        return
    ok = sum(1 for r in results if r.get("status") == "ok")
    sk = sum(1 for r in results if r.get("status") == "skipped")
    er = sum(1 for r in results if r.get("status") == "error")
    try:
        win._status(f"Watch: {ok} ok, {sk} skipped, {er} errors → {win._watch_dst}")
    except Exception:  # noqa: BLE001
        pass
    if bool(getattr(win, "_watch_pending", False)):
        win._watch_pending = False
        _watch_cycle(win)


def _on_watch_error(win, msg: str) -> None:
    win._watch_busy = False
    win._watch_worker = None
    if not is_watching(win):
        return
    try:
        win._status(f"Watch error: {msg} (still watching)")
    except Exception:  # noqa: BLE001
        pass


__all__ = [
    "DEBOUNCE_MS",
    "REARM_MS",
    "SETTLE_S",
    "is_watching",
    "toggle_watch",
    "watch_start",
    "watch_stop",
]
