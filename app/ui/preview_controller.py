"""Still-preview controller: sync render or background worker.

State (`result`, `_preview_worker/_token/_pending`, `_comparing`) and the
`lbl_res` widgets stay on MainWindow; this module holds the behavior.
API on the window (`_show_preview`, `_start_preview_async`,
`_on_preview_done/_error`) is preserved by delegation.
"""

from __future__ import annotations


def preview_max_side(win) -> int:
    """Adaptive proxy long side: 640 floor, viewport-sized, 1600 cap.

    A fixed 640px proxy looked soft on a big window. The canvas reports its
    real area; HiDPI multiplies by the device ratio so Fit stays crisp.
    """
    from app.services.render_service import PREVIEW_LONG_SIDE

    try:
        canvas = win.lbl_res
        dpr = float(canvas.devicePixelRatioF())
        side = int(max(canvas.width(), canvas.height()) * max(1.0, dpr))
    except Exception:  # noqa: BLE001
        side = PREVIEW_LONG_SIDE
    return max(PREVIEW_LONG_SIDE, min(1600, side))


def _full_dims(preset, src) -> tuple[int, int]:
    """Dimensions of the full (non-proxy) render, without rendering it."""
    from app.canvas import crop_box_for, resolve_frame

    w, h = src.size
    cw = int(getattr(preset, "canvas_w", 0) or 0)
    ch = int(getattr(preset, "canvas_h", 0) or 0)
    mode = str(getattr(preset, "crop_mode", "cover") or "cover")
    if mode == "cover":
        _x, _y, bw, bh = crop_box_for(
            w, h, preset.ratio, float(preset.focus_x), float(preset.focus_y),
            float(preset.crop_zoom), cw, ch)
        return int(bw), int(bh)
    long_side = max(w, h)
    want, _, _ = resolve_frame(preset.ratio, long_side, cw, ch)
    if mode == "contain":
        if w / h > want:  # natural padded canvas before the doc cap
            return w, max(1, round(w / want))
        return max(1, round(h * want)), h
    # stretch / blur preserve the source long side
    if want >= 1:
        return long_side, max(1, round(long_side / want))
    return max(1, round(long_side * want)), long_side


def document_target(win, preset) -> tuple[int, int] | None:
    """Doc WxH when the full render has at least that detail; else None.

    None still means a full render (1:1 of the source) — never the proxy.
    """
    try:
        from app.canvas import doc_dimensions

        dw, dh = doc_dimensions(
            preset.ratio, int(getattr(preset, "export_size", 3000) or 3000),
            int(getattr(preset, "canvas_w", 0) or 0),
            int(getattr(preset, "canvas_h", 0) or 0))
        fw, fh = _full_dims(preset, win.src)
    except Exception:  # noqa: BLE001
        return None
    if fw >= dw and fh >= dh:
        return (int(dw), int(dh))
    return None


def render_still(win) -> None:
    """One still render: proxy, Full viewport, or 100% full/doc preview.

    Sync when cheap, background thread when heavy. The worker gets the same
    adaptive proxy size, so sync and async previews agree.
    """
    import time

    if getattr(win, "src", None) is None:
        return
    from app.services.render_service import should_render_async
    from app.viewport import is_heavy_preset, normalize_mode

    preset = win.current_params()
    full_preview = bool(getattr(win, "_full_preview", False))
    full = normalize_mode(getattr(win, "viewport_mode", "live")) == "full"
    side = preview_max_side(win)
    win._last_preview_side = side
    large = max(win.src.size) > side
    heavy = should_render_async(win.src) or (large and is_heavy_preset(preset))
    target = document_target(win, preset) if full_preview else None
    if heavy:
        start_async(win, full=full_preview, target=target, max_side=side)
        return
    t0 = time.perf_counter()
    from app import gpu as _gpu

    if full_preview:
        win.result, backend = _gpu.render_full_or_cpu(win.src, preset)
        if target is not None and win.result.size != target:
            from PIL import Image

            win.result = win.result.resize(target, Image.NEAREST)
        label = f"100% · {'doc' if target else 'full'} · {backend}"
    elif full:
        win.result, backend = _gpu.render_full_or_cpu(win.src, preset)
        label = f"full-res · {backend}"
    else:
        win.result, backend = _gpu.render_proxy_or_cpu(win.src, preset,
                                                       max_side=side)
        label = f"{side}px · {backend}"
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


def start_async(win, *, full: bool = False,
                target: tuple[int, int] | None = None,
                max_side: int | None = None) -> None:
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
        win.src.copy(), win._render_kwargs(), win._preview_token,
        full=full, target=target,
        max_side=int(max_side or preview_max_side(win)),
    )
    win._preview_worker.finished_ok.connect(win._on_preview_done)
    win._preview_worker.finished_err.connect(win._on_preview_error)
    win._status("Rendering full preview in the background..." if full
                else "Rendering heavy preview in the background...")
    try:
        from PySide6.QtCore import Qt

        win.setCursor(Qt.WaitCursor)
    except Exception:  # noqa: BLE001
        pass
    win._preview_worker.start()


def on_done(win, qimg, pil_img, token: int) -> None:
    if token != win._preview_token:
        return  # stale: another render is already on its way
    if getattr(win, "src", None) is None:
        win.result = None
        win._preview_worker = None
        win._preview_pending = False
        try:
            _restore_cursor(win)
        except Exception:  # noqa: BLE001
            pass
        return
    win.result = pil_img
    from app.ui import compare_controller as _cc

    _cc.redisplay(win)
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
        render_still(win)
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
        render_still(win)
        return
    _restore_cursor(win)
    win._report_error("Preview error", msg)
