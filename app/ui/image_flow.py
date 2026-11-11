"""Image flow: open/load/drop/zoom/ops/undo/randomize/clipboard/crop editor.

Entry points for files (dialog, drag&drop, clipboard, URL) plus view ops.
State and widgets stay on MainWindow; this module holds the behavior.
Qt event entry points (`dragEnter/Leave/DropEvent`) stay as thin overrides
on the window and delegate here.
"""

from __future__ import annotations


# -- image ops + undo --
def op_image(win, fn, what: str) -> None:
    if win.src is None:
        return
    win.history.push(win.src)
    win.src = fn(win.src)
    win.refresh()
    win._status(f"{what} (Ctrl+Z to undo)")


def undo_image(win) -> None:
    prev = win.history.undo(win.src if win.src is not None else None)
    if prev is None:
        win._status("Nothing to undo")
        return
    win.src = prev
    win.refresh()
    win._status("Undone (Ctrl+Y to redo)")


def redo_image(win) -> None:
    nxt = win.history.redo(win.src if win.src is not None else None)
    if nxt is None:
        win._status("Nothing to redo")
        return
    win.src = nxt
    win.refresh()
    win._status("Redone")


def randomize(win) -> None:
    import random

    from app.dither import METHODS
    from app.palette_library import list_palettes
    from app.palettes import palette_names

    win.cmb_method.setCurrentText(random.choice(list(METHODS)))
    names = list_palettes() or palette_names()
    win._on_palette_preset_changed(random.choice(names))
    win.sld_thr.setValue(random.randint(80, 180))
    win.spn_pixel.setValue(random.randint(1, 4))
    win.refresh()
    win._status("Random applied (save the preset if you like it)")


# -- zoom / clipboard --
def zoom_step(win, factor: float) -> None:
    win.lbl_res.zoom_step(factor)


def zoom_fit(win) -> None:
    win._full_preview = False
    win.lbl_res.fit()


def zoom_full(win) -> None:
    win._full_preview = True
    win.lbl_res.actual_size()
    if win.src is not None:
        win.refresh()


def toggle_zoom(win) -> None:
    """Zoom badge click: Fit <-> real 100% (same flags as the View menu)."""
    if win.lbl_res.is_fit():
        zoom_full(win)
    else:
        zoom_fit(win)


def copy_result(win) -> None:
    if win.result is None:
        return
    from PySide6.QtGui import QGuiApplication

    from app.ui.qt_image import pil_to_pixmap

    QGuiApplication.clipboard().setPixmap(pil_to_pixmap(win.result, max_side=1920))
    win._status("Result copied to clipboard")


def paste_image(win) -> None:
    from PySide6.QtGui import QGuiApplication

    from app.ui.qt_image import qimage_to_pil

    cb = QGuiApplication.clipboard()
    qimg = cb.image()
    if qimg.isNull():
        win._status("No image in the clipboard")
        return
    try:
        load_pil(win, qimage_to_pil(qimg))
    except ValueError:
        win._status("No image in the clipboard")


# -- drag & drop --
def set_drag_hover(win, on: bool) -> None:
    lbl = win.lbl_res
    lbl.setProperty("dragHover", "true" if on else "false")
    st = lbl.style()
    st.unpolish(lbl)
    st.polish(lbl)
    lbl.update()


def drag_enter(win, event) -> None:
    if event.mimeData().hasUrls():
        event.acceptProposedAction()
        set_drag_hover(win, True)


def drag_leave(win, event) -> None:
    set_drag_hover(win, False)


def drop(win, event) -> None:
    from app.dnd import classify_drop
    from app.safety import MAX_BYTES as _MAX_URL_BYTES

    set_drag_hover(win, False)
    mime = event.mimeData()
    if mime.hasImage():
        # Browsers sometimes drag the raw pixels
        load_qimage(win, mime.imageData())
        return
    handled = False
    for url in mime.urls():
        kind = classify_drop(url.toString())
        if kind == "http":
            load_url(win, url.toString(), max_bytes=_MAX_URL_BYTES)
            handled = True
            break
        if kind == "data":
            load_data_url(win, url.toString())
            handled = True
            break
        if kind == "blob":
            win._status("That link (blob:) only lives in the browser: save the image or copy it (Ctrl+C)")
            handled = True
            break
        if kind == "local":
            from pathlib import Path

            p = Path(url.toLocalFile())
            if not (p.is_absolute() and p.exists()):
                continue  # ghost path: never a folder nor a file
            if p.is_dir():
                win._on_drop_folder(p)
                handled = True
                break
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                load_path(win, p)
                handled = True
                break
    if not handled:
        win._status("Nothing to import: drop images, an image URL or a folder")


# -- loaders --
def load_qimage(win, qimg) -> None:
    from app.ui.qt_image import qimage_to_pil

    try:
        load_pil(win, qimage_to_pil(qimg))
    except ValueError:
        win._status("Nothing to drop: no image")


def load_url(win, url: str, max_bytes: int = 40_000_000, timeout: int = 15) -> None:
    """Download a dropped image from the browser (explicit user action)."""
    from PySide6.QtWidgets import QMessageBox

    from app.safety import TooBigError
    from app.services.image_io import download_image

    win._status("Downloading image...")
    try:
        img, nbytes = download_image(url, max_bytes=max_bytes, timeout=timeout)
        load_pil(win, img)
        win._status(f"Loaded from web ({nbytes // 1024}KB)")
    except TooBigError as e:
        QMessageBox.warning(win, "TRAKKART", f"Image too large:\n{e}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not download:\n{e}")


def load_data_url(win, url: str) -> None:
    """Decode a dropped data:image/... base64 blob from the browser (no network)."""
    from PySide6.QtWidgets import QMessageBox

    from app.safety import TooBigError
    from app.services.image_io import decode_data_url

    try:
        img, nbytes = decode_data_url(url)
        load_pil(win, img)
        win._status(f"Loaded from browser ({nbytes // 1024}KB)")
    except TooBigError as e:
        QMessageBox.warning(win, "TRAKKART", f"Image too large:\n{e}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not read what was dropped:\n{e}")


def open_image_dialog(win) -> None:
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog

    path, _ = QFileDialog.getOpenFileName(
        win, "Open image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
    )
    if path:
        load_path(win, Path(path))


def load_path(win, path) -> None:
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from app.safety import TooBigError
    from app.services.image_io import load_path as _load

    try:
        load_pil(win, _load(path))
        win.src_name = Path(path).stem  # default export base (editor-style)
        win._status(f"Loaded: {Path(path).name}")
        try:
            from app.recent import remember_recent
            from app.ui import session_flow as _sess

            remember_recent(Path(path), getattr(win, "_prefs_path", None))
            _sess.remember_image(win, Path(path))
        except Exception:  # noqa: BLE001
            pass
    except TooBigError as e:
        QMessageBox.warning(win, "TRAKKART", f"Image too large:\n{e}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not open:\n{e}")


def load_pil(win, img) -> None:
    from datetime import datetime

    from PySide6.QtWidgets import QMessageBox

    from app.safety import TooBigError, check_image

    try:
        check_image(img)
    except TooBigError as e:
        QMessageBox.warning(win, "TRAKKART", f"Image too large:\n{e}")
        return
    # Pasted/dropped/downloaded pixels get their own base (load_path
    # overwrites with the file stem right after for real files).
    win.src_name = datetime.now().strftime("pasted_%Y%m%d_%H%M%S")
    win.history.clear()
    win.history.push(img)
    win.src = img
    win._full_preview = False
    win.lbl_res.fit()
    win.refresh()


# -- visual crop --
def sync_crop_label(win) -> None:
    win.lbl_crop.setText(f"{win.crop_fx:.0f}, {win.crop_fy:.0f} · {win.crop_zoom:.1f}x")


def open_crop_editor(win) -> None:
    """Visual crop editor (frame + grid + drag + zoom). Applies on Done."""
    from PySide6.QtWidgets import QMessageBox

    if win.src is None:
        QMessageBox.information(win, "TRAKKART", "Open an image first.")
        return
    from app.canvas import ratio_value
    from app.ui.crop_editor import CropEditorDialog
    from app.ui import params_controller as _par

    w, h = _par.doc_dims(win)
    dlg = CropEditorDialog(
        win.src.copy(),
        ratio=ratio_value(win.cmb_ratio.currentText()),
        mode=win.cmb_crop.currentText(),
        fx=float(win.crop_fx), fy=float(win.crop_fy),
        zoom=float(win.crop_zoom),
        canvas_w=w, canvas_h=h,
        parent=win,
        show_safe=bool(getattr(win, "_show_safe", True)),
    )
    if dlg.exec() != dlg.DialogCode.Accepted:
        dlg.deleteLater()  # no hoard hidden dialogs (they linger in topLevelWidgets)
        win._status("Crop unchanged")
        return
    if dlg.turns:
        win.history.push(win.src)
        win.src = dlg.image
    from app.canvas import ratio_label

    if win.cmb_ratio.findText(ratio_label(dlg.ratio)) >= 0:
        win.cmb_ratio.setCurrentText(ratio_label(dlg.ratio))
    if win.cmb_crop.findText(dlg.mode) >= 0:
        win.cmb_crop.setCurrentText(dlg.mode)
    for spn, v in ((win.spn_canvas_w, dlg.doc_w), (win.spn_canvas_h, dlg.doc_h)):
        try:
            spn.blockSignals(True)
            spn.setValue(int(v))
        finally:
            spn.blockSignals(False)
    win.crop_fx, win.crop_fy, win.crop_zoom = dlg.fx, dlg.fy, dlg.zoom
    _status_msg = (f"Crop set: {ratio_label(dlg.ratio)} {dlg.doc_w}x{dlg.doc_h} {dlg.mode} "
                   f"({dlg.fx:.0f}, {dlg.fy:.0f} · {dlg.zoom:.1f}x)")
    dlg.deleteLater()  # no hoard hidden dialogs (they linger in topLevelWidgets)
    sync_crop_label(win)
    _par.sync_docdims(win)
    win.refresh()
    win._status(_status_msg)
