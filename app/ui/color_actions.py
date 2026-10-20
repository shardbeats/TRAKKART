"""Color/palette actions: brand, duotone, border, custom strip, library.

State and widgets stay on MainWindow; this module holds the behavior.
The window keeps the same `pick_*/set_*` / palette API by delegation.
"""

from __future__ import annotations


def pick_brand_color(win) -> None:
    from PySide6.QtWidgets import QColorDialog

    color = QColorDialog.getColor()
    if not color.isValid():
        return
    set_brand_color(win, color.name().upper())


def set_brand_color(win, hex_color: str) -> None:
    from app.fx import parse_hex

    if hex_color and parse_hex(hex_color) is None:
        win._status("Invalid brand color (use #RRGGBB)")
        return
    win.brand_color = hex_color or ""
    win.lbl_brand.setText(win.brand_color if win.brand_color else "(no brand)")
    win.refresh()


def pick_duotone_color(win, which: str) -> None:
    from PySide6.QtWidgets import QColorDialog

    color = QColorDialog.getColor()
    if not color.isValid():
        return
    set_duotone_color(win, which, color.name().upper())


def set_duotone_color(win, which: str, hex_color: str) -> None:
    from app.fx import parse_hex

    if hex_color and parse_hex(hex_color) is None:
        win._status("Invalid duotone color (use #RRGGBB)")
        return
    hex_color = (hex_color or "").upper()
    if which == "light":
        win.duotone_light = hex_color
    else:
        win.duotone_dark = hex_color
    sync_duo_label(win)
    win.refresh()


def clear_duotone(win) -> None:
    win.duotone_dark = ""
    win.duotone_light = ""
    sync_duo_label(win)
    win.refresh()


def sync_duo_label(win) -> None:
    if win.duotone_dark or win.duotone_light:
        win.lbl_duo.setText(f"{win.duotone_dark or '—'} → {win.duotone_light or '—'}")
    else:
        win.lbl_duo.setText("(off)")


def pick_border_color(win) -> None:
    from PySide6.QtWidgets import QColorDialog

    color = QColorDialog.getColor()
    if not color.isValid():
        return
    set_border_color(win, color.name().upper())


def set_border_color(win, hex_color: str) -> None:
    from app.fx import parse_hex

    if not hex_color or parse_hex(hex_color) is None:
        win._status("Invalid border color (use #RRGGBB)")
        return
    win.border_color = hex_color.upper()
    win.lbl_border.setText(win.border_color)
    win.refresh()


def add_custom_color(win) -> None:
    from PySide6.QtWidgets import QColorDialog

    color = QColorDialog.getColor()
    if not color.isValid():
        return
    rgb = (color.red(), color.green(), color.blue())
    if rgb not in win.custom_colors and len(win.custom_colors) < 16:
        set_custom_colors(win, [*win.custom_colors, rgb])
    win.refresh()


def gen_palette(win) -> None:
    """🎲 Sorpresa: genera una paleta armoniosa (ramp/harmony en Oklch)."""
    from app.palette_gen import generate_palette

    n = max(2, len(win.custom_colors) or 4)
    style = win.cmb_palgen.currentText().lower() if hasattr(win, "cmb_palgen") else "ramp"
    set_custom_colors(win, generate_palette(n, style=style))
    win.refresh()
    win._status(f"Generated {style} palette: {len(win.custom_colors)} colors (editable)")


def edit_custom_palette(win) -> None:
    """Full editor: swatches, hex, roles, usage, reorder, sort."""
    from app.ui.palette_dialog import CustomPaletteDialog

    dlg = CustomPaletteDialog(
        win.custom_colors, preview=palette_preview_small(win), parent=win
    )
    if dlg.exec() != dlg.DialogCode.Accepted:
        return
    set_custom_colors(win, [tuple(c) for c in dlg.colors])
    win.refresh()
    win._status(f"Custom palette: {len(win.custom_colors)} colors")


def remove_custom_color(win, i: int) -> None:
    if 0 <= i < len(win.custom_colors):
        set_custom_colors(win, [c for j, c in enumerate(win.custom_colors) if j != i])
        win.refresh()


def palette_preview_small(win):
    """Canvas actual reducido (160px) para el % de uso. None sin imagen."""
    if win.src is None:
        return None
    try:
        from PIL import Image

        from app.canvas import to_canvas

        canvas = to_canvas(
            win.src, ratio=win.cmb_ratio.currentText(), mode=win.cmb_crop.currentText(),
            fx=float(win.crop_fx), fy=float(win.crop_fy), zoom=float(win.crop_zoom),
        )
        m = max(canvas.size)
        if m > 160:
            f = 160.0 / m
            canvas = canvas.resize(
                (max(1, round(canvas.width * f)), max(1, round(canvas.height * f))),
                Image.BICUBIC,
            )
        return canvas
    except Exception:  # noqa: BLE001
        return None


def clear_custom_colors(win) -> None:
    set_custom_colors(win, [])
    win.refresh()


def set_custom_colors(win, colors: list, dirty: bool = True) -> None:
    """Único punto de escritura: actualiza tira + estado dirty."""
    from app.palette_library import CUSTOM_SENTINEL

    win.custom_colors = [tuple(c) for c in colors]
    if dirty:
        win._palette_dirty = True
        if win.cmb_pal_preset.findText(CUSTOM_SENTINEL) < 0:
            win.cmb_pal_preset.addItem(CUSTOM_SENTINEL)
        win.cmb_pal_preset.blockSignals(True)
        win.cmb_pal_preset.setCurrentText(CUSTOM_SENTINEL)
        win.cmb_pal_preset.blockSignals(False)
    sync_custom_label(win)


def sync_custom_label(win) -> None:
    from app.ui.palette_dialog import ColorSwatch, luminance_roles, rgb_to_hex

    n = len(win.custom_colors)
    win.lbl_custom.setText(f"{n}/16")
    lay = win.palette_strip
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    roles = luminance_roles(win.custom_colors)
    for i, rgb in enumerate(win.custom_colors):
        sw = ColorSwatch(rgb, i, size=26)
        sw.setToolTip(f"{rgb_to_hex(rgb)} · {roles[i]} — click to remove")
        sw.picked.connect(win._remove_custom_color)
        lay.addWidget(sw)
    lay.addStretch()
    if n == 1:
        win.lbl_palette_hint.setText("1 color is ignored: custom needs 2–16 colors.")
    else:
        win.lbl_palette_hint.setText("")


def refresh_palette_list(win) -> None:
    """Combo de la biblioteca (built-ins + usuario)."""
    from app.palette_library import CUSTOM_SENTINEL, list_palettes

    win.cmb_pal_preset.blockSignals(True)
    win.cmb_pal_preset.clear()
    win.cmb_pal_preset.addItems(list_palettes())
    if win._palette_dirty and win.cmb_pal_preset.findText(CUSTOM_SENTINEL) < 0:
        win.cmb_pal_preset.addItem(CUSTOM_SENTINEL)
    cur = CUSTOM_SENTINEL if win._palette_dirty else win._palette_base
    if win.cmb_pal_preset.findText(cur) >= 0:
        win.cmb_pal_preset.setCurrentText(cur)
    win.cmb_pal_preset.blockSignals(False)


def on_palette_preset_changed(win, name: str) -> None:
    """Elegir paleta = cargarla como copia editable en la tira."""
    from app.palette_library import CUSTOM_SENTINEL, palette_colors

    if not name or name == CUSTOM_SENTINEL:
        return
    try:
        colors = palette_colors(name)
    except ValueError:
        return
    win._palette_base = name
    set_custom_colors(win, colors, dirty=False)
    win.refresh()
    win._status(f"Palette loaded: {name} (editable)")


def save_palette_preset(win) -> None:
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    from app.palette_library import save_palette

    name, ok = QInputDialog.getText(win, "Save palette", "Name:")
    if not ok or not name.strip():
        return
    try:
        save_palette(name.strip(), [list(c) for c in win.custom_colors])
        win._palette_base = name.strip()
        win._palette_dirty = False
        refresh_palette_list(win)
        win.cmb_pal_preset.setCurrentText(name.strip())
        win._status(f"Palette saved: {name.strip()}")
    except ValueError as e:
        QMessageBox.warning(win, "TRAKKART", f"Could not save:\n{e}")
