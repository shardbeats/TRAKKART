"""Hold-to-compare controller: single canvas, ORIGINAL while held.

The state (`_comparing`) and the widgets (`lbl_res`, `src`, `result`,
video flags) stay on MainWindow; this module only holds the behavior so
`main_window.py` doesn't grow into a monolith. Callers keep the same
`window._compare_pressed()` / `window._paint_compare_*()` API.

R13 adds wipe compare (drag divider: ORIGINAL left, result right) and
R12 draws safe-area guides on still result views (not on video frames).
"""

from __future__ import annotations


def _guides_on(win) -> bool:
    return bool(getattr(win, "_show_safe", True))


def guided_pixmap(win, pixmap, w: int, h: int):
    """Display pixmap with 9:16 chrome bands when enabled (copy, no doc touch)."""
    if not _guides_on(win):
        return pixmap
    try:
        from app.ui.safeareas import is_916, paint_guides

        if is_916(w, h):
            return paint_guides(pixmap)
    except Exception:  # noqa: BLE001
        pass
    return pixmap


def pressed(win) -> None:
    if win.src is None:
        return
    win._comparing = True
    paint_orig(win)


def released(win) -> None:
    if not win._comparing:
        return
    win._comparing = False
    redisplay(win)


def paint_orig(win) -> None:
    if win.src is None:
        return
    from app.ui.preview_canvas import PREVIEW_MAX_SIDE
    from app.ui.qt_image import pil_to_pixmap

    win.lbl_res.set_wipe_mode(False)
    win.lbl_res.setPixmap(pil_to_pixmap(win.src, max_side=PREVIEW_MAX_SIDE))
    win.lbl_res_title.setText(f"ORIGINAL (hold) · {win.src.width}x{win.src.height}")


def paint_result(win) -> None:
    if win._video_on and win._video_frames:
        win._comparing = False
        win._show_video_frame(force=True)
        return
    if win.result is not None:
        from app.ui.preview_canvas import PREVIEW_MAX_SIDE
        from app.ui.qt_image import pil_to_pixmap

        win.lbl_res.set_wipe_mode(False)
        if bool(getattr(win, "_sp404_preview", False)):
            from app.sp404 import SP_H, SP_W, sp404_frame

            oled = sp404_frame(win.result)
            pix = pil_to_pixmap(oled.convert("RGB"), max_side=PREVIEW_MAX_SIDE)
            win.lbl_res.setPixmap(guided_pixmap(win, pix, SP_W, SP_H))
            win.lbl_res_title.setText(f"SP-404 · {SP_W}x{SP_H} 1-bit (preview)")
            return
        pix = pil_to_pixmap(win.result, max_side=PREVIEW_MAX_SIDE)
        win.lbl_res.setPixmap(guided_pixmap(win, pix, win.result.width, win.result.height))
        kind = "VIDEO" if win._video_on else "DITHER"
        win.lbl_res_title.setText(f"{kind} · {win.result.width}x{win.result.height}")


def wipe_pos(win) -> int:
    """Wipe slider 0-100 (% ORIGINAL shown; 0 = off = full result)."""
    try:
        return max(0, min(100, int(win.sld_wipe.value())))
    except Exception:  # noqa: BLE001
        return 0


def _aligned_orig(win):
    """Source through the live canvas framing (same WxH as the result).

    Cached per (src object, framing params): a wipe drag used to rerun
    to_canvas over the full source on every tick (~75-311ms). The cache
    lives on the window and is replaced when any key component changes.
    """
    from app.canvas import to_canvas
    from app.ui import params_controller as _par

    ratio = _par.ratio_value_of(win)
    try:
        mode = str(win.cmb_crop.currentText())
    except Exception:  # noqa: BLE001
        mode = "cover"
    try:
        w, h = _par.doc_dims(win)
    except Exception:  # noqa: BLE001
        w, h = (0, 0)
    fx = float(getattr(win, "crop_fx", 50.0) or 50.0)
    fy = float(getattr(win, "crop_fy", 50.0) or 50.0)
    zoom = float(getattr(win, "crop_zoom", 1.0) or 1.0)
    key = (ratio, mode, int(w or 0), int(h or 0),
           round(fx, 3), round(fy, 3), round(zoom, 4))
    cache = getattr(win, "_aligned_orig_cache", None)
    if cache is not None and cache[0] is win.src and cache[1] == key:
        return cache[2]
    img = to_canvas(
        win.src.convert("RGB"), ratio=ratio, mode=mode,
        fx=fx, fy=fy, zoom=zoom,
        canvas_w=int(w or 0), canvas_h=int(h or 0))
    win._aligned_orig_cache = (win.src, key, img)
    return img


def paint_wipe(win, pos: int | None = None) -> None:
    """Side-by-side wipe at display size (ORIGINAL left, result right)."""
    if win.src is None or win.result is None:
        return
    if bool(getattr(win, "_video_on", False)):
        return
    if pos is None:
        pos = wipe_pos(win)
    pos = max(0, min(100, int(pos)))
    if pos <= 0:
        paint_result(win)
        return
    from app.ui.preview_canvas import PREVIEW_MAX_SIDE
    from app.ui.qt_image import pil_to_pixmap

    res = win.result.convert("RGB")
    if pos >= 100:
        # Framed original (same geometry as 99%), never the raw uncropped
        # source: the old jump showed a different aspect at the last tick.
        base = _aligned_orig(win).convert("RGB")
        win.lbl_res.set_wipe_mode(True)
        pix = guided_pixmap(win, pil_to_pixmap(base, max_side=PREVIEW_MAX_SIDE),
                            res.width, res.height)
        win.lbl_res.setPixmap(pix)
        win.lbl_res_title.setText(f"WIPE 100% · {res.width}x{res.height}")
        return
    import numpy as np

    win.lbl_res.set_wipe_mode(True)
    scale = min(1.0, PREVIEW_MAX_SIDE / max(res.width, res.height))
    dw, dh = max(1, int(res.width * scale)), max(1, int(res.height * scale))
    try:
        base = _aligned_orig(win).convert("RGB").resize((dw, dh))
    except Exception:  # noqa: BLE001
        return
    right = res.resize((dw, dh)) if (dw, dh) != res.size else res
    left = np.asarray(base, dtype=np.uint8)
    arr = np.asarray(right, dtype=np.uint8)
    x = max(1, min(dw - 1, int(dw * pos / 100)))
    comp = arr.copy()
    comp[:, :x] = left[:, :x]
    comp[:, max(0, x - 1):x + 1] = (245, 166, 35)  # amber divider
    from PIL import Image

    pix = pil_to_pixmap(Image.fromarray(comp), max_side=PREVIEW_MAX_SIDE)
    win.lbl_res.setPixmap(guided_pixmap(win, pix, res.width, res.height))
    win.lbl_res_title.setText(f"WIPE {pos}% · {res.width}x{res.height}")


def wipe(win) -> None:
    """Wipe slider moved (hold-to-compare wins while held)."""
    if bool(getattr(win, "_comparing", False)):
        return
    paint_wipe(win)


def redisplay(win) -> None:
    """Current still view: video frame | ORIGINAL (hold) | wipe | result."""
    if bool(getattr(win, "_video_on", False)) and getattr(win, "_video_frames", None):
        win._comparing = False
        win._show_video_frame(force=True)
        return
    if win.src is None:
        return
    if bool(getattr(win, "_comparing", False)):
        paint_orig(win)
        return
    if win.result is not None and wipe_pos(win) > 0:
        paint_wipe(win)
        return
    paint_result(win)


def toggle_sp404_preview(win) -> None:
    """View menu checkbox: 128x64 1-bit OLED preview (display-only)."""
    try:
        on = bool(win.act_sp404.isChecked())
    except Exception:  # noqa: BLE001
        on = not bool(getattr(win, "_sp404_preview", False))
        try:
            win.act_sp404.setChecked(on)
        except Exception:  # noqa: BLE001
            pass
    win._sp404_preview = on
    try:
        btn = getattr(win, "btn_sp404_preview", None)
        if btn is not None:
            if btn.isChecked() != bool(on):
                btn.blockSignals(True)
                btn.setChecked(bool(on))
                btn.blockSignals(False)
            btn.setText(f"SP-404 OLED Preview: {'ON' if on else 'OFF'}")
    except Exception:  # noqa: BLE001
        pass
    if win.src is None or win.result is None or bool(getattr(win, "_video_on", False)):
        try:
            win._schedule_refresh()
        except Exception:  # noqa: BLE001
            pass
        return
    redisplay(win)


def toggle_safe_areas(win) -> None:
    """View menu checkbox: chrome guides on/off (display-only re-display)."""
    try:
        on = bool(win.act_safe.isChecked())
    except Exception:  # noqa: BLE001
        on = not bool(getattr(win, "_show_safe", True))
        try:
            win.act_safe.setChecked(on)
        except Exception:  # noqa: BLE001
            pass
    win._show_safe = on
    if win.src is None or win.result is None or bool(getattr(win, "_video_on", False)):
        try:
            win._schedule_refresh()
        except Exception:  # noqa: BLE001
            pass
        return
    redisplay(win)
