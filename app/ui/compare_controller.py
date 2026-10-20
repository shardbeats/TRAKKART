"""Hold-to-compare controller: single canvas, ORIGINAL while held.

The state (`_comparing`) and the widgets (`lbl_res`, `src`, `result`,
video flags) stay on MainWindow; this module only holds the behavior so
`main_window.py` doesn't grow into a monolith. Callers keep the same
`window._compare_pressed()` / `window._paint_compare_*()` API.
"""

from __future__ import annotations


def pressed(win) -> None:
    if win.src is None:
        return
    win._comparing = True
    paint_orig(win)


def released(win) -> None:
    if not win._comparing:
        return
    win._comparing = False
    paint_result(win)


def paint_orig(win) -> None:
    if win.src is None:
        return
    from app.ui.qt_image import pil_to_pixmap

    zoomed = int(520 * win.zoom)
    win.lbl_res.setPixmap(pil_to_pixmap(win.src, max_side=zoomed))
    win.lbl_res_title.setText(f"ORIGINAL (hold) · {win.src.width}x{win.src.height}")


def paint_result(win) -> None:
    if win._video_on and win._video_frames:
        win._comparing = False
        win._show_video_frame(force=True)
        return
    if win.result is not None:
        from app.ui.qt_image import pil_to_pixmap

        zoomed = int(520 * win.zoom)
        win.lbl_res.setPixmap(pil_to_pixmap(win.result, max_side=zoomed))
        kind = "VIDEO" if win._video_on else "DITHER"
        win.lbl_res_title.setText(f"{kind} · {win.result.width}x{win.result.height}")
