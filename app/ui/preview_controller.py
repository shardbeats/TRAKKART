"""Still-preview controller: sync render or background worker.

State (`result`, `_preview_worker/_token/_pending`, `_comparing`) and the
`lbl_res` widgets stay on MainWindow; this module holds the behavior.
API on the window (`_show_preview`, `_start_preview_async`,
`_on_preview_done/_error`) is preserved by delegation.
"""

from __future__ import annotations


def render_still(win) -> None:
    """One still render: sync when cheap, background thread when heavy."""
    from app.services.render_service import render_full, should_render_async

    if should_render_async(win.src):
        start_async(win)  # no numba and big: do not freeze
        return
    win.result = render_full(win.src, win.current_params())
    show(win, win.src, win.result)


def show(win, orig, res) -> None:
    from app.ui.qt_image import pil_to_pixmap

    zoomed = int(520 * win.zoom)
    if win._comparing:
        win.lbl_res.setPixmap(pil_to_pixmap(orig, max_side=zoomed))
        win.lbl_res_title.setText(f"ORIGINAL (hold) · {orig.width}x{orig.height}")
        return
    win.lbl_res.setPixmap(pil_to_pixmap(res, max_side=zoomed))
    win.lbl_res_title.setText(f"DITHER · {res.width}x{res.height}")


def start_async(win) -> None:
    from app.ui.preview_worker import PreviewWorker

    # Guard real: si ya hay un worker vivo, encolar. Si ya hay uno encolado,
    # no spawnear otro. No depender solo de isRunning(), que no es visible
    # de inmediato tras start() y abre ventana de carrera.
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
        win.lbl_res.setPixmap(QPixmap.fromImage(qimg))
        win.lbl_res_title.setText(f"DITHER · {pil_img.width}x{pil_img.height}")
    win._status("Preview ready")
    w = win._preview_worker
    if w is not None:
        try:
            w.wait(5000)
        except Exception:  # noqa: BLE001
            pass
        if w.isRunning():
            # Todavía vivo de verdad (o fake busy en tests): reencolar sin
            # spawnear ni loopear. El próximo on_done/on_error lo drena.
            win._preview_pending = True
            return
    win._preview_worker = None
    if win._preview_pending:
        win._preview_pending = False
        start_async(win)


def on_error(win, msg: str, token: int) -> None:
    if token != win._preview_token:
        return
    w = win._preview_worker
    if w is not None:
        try:
            w.wait(5000)
        except Exception:  # noqa: BLE001
            pass
        if w.isRunning():
            # Worker aún vivo (o fake busy en tests): reencolar sin spawnear
            # y sin loopear. No se toca el slot.
            win._preview_pending = True
            return
    win._preview_worker = None
    if win._preview_pending:
        win._preview_pending = False
        start_async(win)
        return
    win._status(f"Preview error: {msg}")
