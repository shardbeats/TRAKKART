"""QThread life-cycle guard (v2.1).

Qt aborts the whole process with `QThread: Destroyed while thread is
still running` (fast-fail 0xC0000409, no traceback, nothing in
trakkart.log) when the last reference to a live QThread is released.
v2.0 hit that in three places:

- `preview_controller.on_done/on_error` cleared `_preview_worker`
  while the render was still emitting;
- `project_flow.new_project` cleared it on a running thread;
- `MainWindow.closeEvent` blocked signals but never waited, so the
  wrapper died with the interpreter while the thread was alive.

Rule: a worker is either *retired* (idle -> deleteLater) or *held*
until its `finished` signal fires. Never dropped alive.
"""

from __future__ import annotations

#: Running workers whose owning window is already gone (close/teardown).
#: Kept referenced on purpose so Qt never destructs a live QThread.
_ORPHANS: list = []


def is_running(worker) -> bool:
    """Safe `isRunning()` (None/fakes never raise)."""
    try:
        return bool(worker is not None and worker.isRunning())
    except Exception:  # noqa: BLE001
        return False


def retire(worker) -> None:
    """Release a worker: delete when idle, hold until finished when live."""
    if worker is None:
        return
    if is_running(worker):
        if worker in _ORPHANS:
            return
        _ORPHANS.append(worker)
        try:
            worker.finished.connect(lambda w=worker: drop(w))
        except Exception:  # noqa: BLE001
            pass
        return
    _delete(worker)


def drop(worker) -> None:
    """Forget a retired worker and let Qt own its deletion."""
    if worker is None:
        return
    try:
        if worker in _ORPHANS:
            _ORPHANS.remove(worker)
    except Exception:  # noqa: BLE001
        pass
    _delete(worker)


def stop(worker, timeout_ms: int = 5000) -> bool:
    """Shut a worker down at window close: block signals, wait, orphan.

    Returns True when the thread is no longer running. A render that
    ignores the timeout is orphaned (kept referenced) instead of being
    destroyed mid-run — that destruction is the hard crash.
    """
    if worker is None:
        return True
    try:
        worker.blockSignals(True)
    except Exception:  # noqa: BLE001
        pass
    try:
        worker.requestInterruption()
    except Exception:  # noqa: BLE001
        pass
    if not is_running(worker):
        return True
    try:
        if worker.wait(int(timeout_ms)):
            return True
    except Exception:  # noqa: BLE001
        pass
    retire(worker)
    return False


def pending_count() -> int:
    """How many running workers are currently held alive (tests/diagnostics)."""
    return len(_ORPHANS)


def _delete(worker) -> None:
    try:
        deleter = getattr(worker, "deleteLater", None)
        if callable(deleter):
            deleter()
    except Exception:  # noqa: BLE001
        pass


__all__ = ["is_running", "retire", "drop", "stop", "pending_count"]
