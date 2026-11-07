"""Still-preview controller: sync render or background worker.

State (`result`, `_preview_worker/_token/_pending`, `_comparing`) and the
`lbl_res` widgets stay on MainWindow; this module holds the behavior.
API on the window (`_show_preview`, `_start_preview_async`,
`_on_preview_done/_error`) is preserved by delegation.
"""

from __future__ import annotations


def render_still(win) -> None:
    """One still render: Full = full-res; otherwise a fast 640px proxy.

    Sync when cheap, background thread when heavy (serial diffusion or a
    large image without numba). The worker renders the same 640px proxy,
    so sync and async previews agree.
    """
    import time

    from app.services.render_service import (
        PREVIEW_LONG_SIDE,
        render_full,
        should_render_async,
    )
    from app.viewport import is_heavy_preset, normalize_mode

    preset = win.current_params()
    full = normalize_mode(getattr(win, "viewport_mode", "live")) == "full"
    large = max(win.src.size) > PREVIEW_LONG_SIDE
    if should_render_async(win.src) or (large and is_heavy_preset(preset)):
        start_async(win)  # heavy large canvas: never freeze the sliders
        return
    t0 = time.perf_counter()
    if full:
        win.result = render_full(win.src, preset)
        label = "full-res"
    else:
        from app import gpu as _gpu

        win.result, backend = _gpu.render_proxy_or_cpu(win.src, preset)
        label = f"{PREVIEW_LONG_SIDE}px · {backend}"
    ms = (time.perf_counter() - t0) * 1000.0
    show(win, win.src, win.result)
    win._status(f"Preview ready · {label} · {ms:.0f}ms")


def _restore_cursor(win) -> None:
    try:
        win.unsetCursor()
    except Exception:  # noqa: BLE001
        pass


def show(win, orig, res) -> None:
    """Still result display (single router: hold-compare, wipe, safe guides)."""
    from app.ui import compare_controller as _cc

    _cc.redisplay(win)


def start_async(win) -> None:
    from app.ui.preview_worker import PreviewWorker

    # Real guard: if a worker is alive, queue. If one is already queued,
    # don't spawn another. Don't rely on isRunning() alone: it isn't
    # visible right after start() and that opens a race window.
    if win._preview_worker is not None and win._preview_worker.isRunning():
        win._preview_pending = True
        win._status("Rendering heavy preview in the background...")
        return
    if win._preview_pending:
        return
    win._preview_token += 1
    win._preview_worker = PreviewWorker(
        win.src.copy(), win._render_kwargs(), win._preview_token
    )
    win._preview_worker.finished_ok.connect(win._on_preview_done)
    win._preview_worker.finished_err.connect(win._on_preview_error)
    win._status("Rendering heavy preview in the background...")
    try:
        from PySide6.QtCore import Qt

        win.setCursor(Qt.WaitCursor)
    except Exception:  # noqa: BLE001
        pass
    win._preview_worker.start()


def on_done(win, qimg, pil_img, token: int) -> None:
    from PySide6.QtGui import QPixmap

    if token != win._preview_token:
        return  # stale: another render is already on its way
    win.result = pil_img
    if win._comparing and win.src is not None:
        from app.ui.qt_image import pil_to_pixmap

        zoomed = int(520 * win.zoom)
        win.lbl_res.setPixmap(pil_to_pixmap(win.src, max_side=zoomed))
        win.lbl_res_title.setText(f"ORIGINAL (hold) · {win.src.width}x{win.src.height}")
    else:
        from app.ui import compare_controller as _cc

        if _cc.wipe_pos(win) > 0 and win.src is not None:
            _cc.paint_wipe(win)
        else:
            win.lbl_res.setPixmap(_cc.guided_pixmap(
                win, QPixmap.fromImage(qimg), pil_img.width, pil_img.height))
            win.lbl_res_title.setText(f"DITHER · {pil_img.width}x{pil_img.height}")
    win._status("Preview ready")
    w = win._preview_worker
    win._preview_worker = None
    if w is not None:
        try:
            alive = bool(w.isRunning())
        except Exception:  # noqa: BLE001
            alive = False
        try:
            deleter = getattr(w, "deleteLater", None)
            if callable(deleter):
                deleter()
        except Exception:  # noqa: BLE001
            pass
        if alive:
            # Still truly alive (or fake-busy in tests): re-queue without
            # spawning or looping. The next on_done/on_error drains it.
            # No wait() here: blocking the GUI slot up to 5s freezes the UI.
            win._preview_pending = True
            return
    if win._preview_pending:
        win._preview_pending = False
        start_async(win)
        return
    _restore_cursor(win)


def on_error(win, msg: str, token: int) -> None:
    if token != win._preview_token:
        return
    w = win._preview_worker
    win._preview_worker = None
    if w is not None:
        try:
            alive = bool(w.isRunning())
        except Exception:  # noqa: BLE001
            alive = False
        try:
            deleter = getattr(w, "deleteLater", None)
            if callable(deleter):
                deleter()
        except Exception:  # noqa: BLE001
            pass
        if alive:
            # Worker still alive (or fake-busy in tests): re-queue without
            # spawning or looping. Slot untouched. No wait() in GUI slot.
            win._preview_pending = True
            return
    if win._preview_pending:
        win._preview_pending = False
        start_async(win)
        return
    _restore_cursor(win)
    win._report_error("Preview error", msg)
