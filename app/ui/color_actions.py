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
    """🎲 Surprise: generates a harmonious palette (ramp/harmony in Oklch).

    Uses the palette seed spin when the dice set it; manual "Generate"
    clicks keep the current spin value, so any result replays by seed.
    """
    from app.palette_gen import generate_palette

    n = max(2, len(win.custom_colors) or 4)
    style = win.cmb_palgen.currentText().lower() if hasattr(win, "cmb_palgen") else "ramp"
    try:
        seed = int(win.spn_pal_seed.value())
    except Exception:  # noqa: BLE001
        seed = 0
    set_custom_colors(win, generate_palette(n, style=style, seed=seed))
    win.refresh()
    win._status(f"Generated {style} palette: {len(win.custom_colors)} colors (seed {seed})")


def edit_custom_palette(win) -> None:
    """Full editor: swatches, hex, roles, usage, reorder, sort, locks, shuffle."""
    from app.ui.palette_dialog import CustomPaletteDialog

    dlg = CustomPaletteDialog(
        win.custom_colors, preview=palette_preview_small(win),
        locks=list(getattr(win, "_palette_locks", []) or []), parent=win,
    )
    if dlg.exec() != dlg.DialogCode.Accepted:
        return
    win._palette_locks = list(getattr(dlg, "locks", [False] * len(dlg.colors)))
    set_custom_colors(win, [tuple(c) for c in dlg.colors])
    # set_custom_colors resets locks when length changes: restore dialog ones.
    win._palette_locks = list(getattr(dlg, "locks", [False] * len(dlg.colors)))
    win.refresh()
    win._status(f"Custom palette: {len(win.custom_colors)} colors")


def remove_custom_color(win, i: int) -> None:
    if 0 <= i < len(win.custom_colors):
        set_custom_colors(win, [c for j, c in enumerate(win.custom_colors) if j != i])
        win.refresh()


def palette_preview_small(win):
    """Small current canvas (160px) for usage %. None without image."""
    if win.src is None:
        return None
    try:
        from PIL import Image

        from app.canvas import ratio_value, to_canvas
        from app.ui import params_controller as _par

        w, h = _par.doc_dims(win)
        canvas = to_canvas(
            win.src, ratio=ratio_value(win.cmb_ratio.currentText()),
            mode=win.cmb_crop.currentText(),
            fx=float(win.crop_fx), fy=float(win.crop_fy), zoom=float(win.crop_zoom),
            canvas_w=w, canvas_h=h,
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
    """Single write point: updates strip + dirty state."""
    from app.palette_library import CUSTOM_SENTINEL

    win.custom_colors = [tuple(c) for c in colors]
    # Parallel locks: keep when same length, otherwise reset.
    locks = list(getattr(win, "_palette_locks", []) or [])
    if len(locks) != len(win.custom_colors):
        locks = [False] * len(win.custom_colors)
    win._palette_locks = locks
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
    """Library combo (built-ins + user + SOURCE + Custom)."""
    from app.palette_library import CUSTOM_SENTINEL, list_palettes

    win.cmb_pal_preset.blockSignals(True)
    win.cmb_pal_preset.clear()
    items = list_palettes()
    if "SOURCE" not in items:
        items = ["SOURCE", *items]
    win.cmb_pal_preset.addItems(items)
    if win._palette_dirty and win.cmb_pal_preset.findText(CUSTOM_SENTINEL) < 0:
        win.cmb_pal_preset.addItem(CUSTOM_SENTINEL)
    cur = CUSTOM_SENTINEL if win._palette_dirty else win._palette_base
    if win.cmb_pal_preset.findText(cur) >= 0:
        win.cmb_pal_preset.setCurrentText(cur)
    win.cmb_pal_preset.blockSignals(False)


def on_palette_preset_changed(win, name: str) -> None:
    """Choosing a palette = loading it as an editable copy into the strip.

    SOURCE is auto mode (extracts from image at render): loads no swatches,
    only sets the base and clears dirty.
    """
    from app.palette_library import CUSTOM_SENTINEL, palette_colors

    if not name or name == CUSTOM_SENTINEL:
        return
    if name == "SOURCE":
        win._palette_base = "SOURCE"
        win._palette_dirty = False
        win.refresh_palette_list()
        win.refresh()
        win._status("Palette: SOURCE (auto from image, Depth controls N)")
        return
    try:
        colors = palette_colors(name)
    except ValueError:
        return
    win._palette_base = name
    set_custom_colors(win, colors, dirty=False)
    win.refresh()
    win._status(f"Palette loaded: {name} (editable)")


def extract_from_image(win, n: int | None = None) -> None:
    """Auto-extract (median-cut offline) -> editable custom strip."""
    from app.palette_extract import extract_palette

    if win.src is None:
        win._status("Open an image first")
        return
    try:
        depth = int(win.spn_pal_depth.value()) if hasattr(win, "spn_pal_depth") else 0
    except Exception:  # noqa: BLE001
        depth = 0
    count = int(n or depth or 6)
    count = max(2, min(16, count))
    colors = extract_palette(win.src, n=count)
    set_custom_colors(win, [tuple(c) for c in colors], dirty=True)
    win.refresh()
    win._status(f"Extracted {len(colors)} colors from image (editable)")


def import_palette_file(win) -> None:
    """Import .json (TRAKKART/share) or .gpl (GIMP palette) offline."""
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from app.palette_library import parse_gpl, save_palette

    path, _ = QFileDialog.getOpenFileName(
        win, "Import palette", "", "Palettes (*.json *.gpl);;JSON (*.json);;GIMP (*.gpl)")
    if not path:
        return
    try:
        p = Path(path)
        if p.suffix.lower() == ".gpl":
            name, colors = parse_gpl(p.read_text(encoding="utf-8", errors="replace"))
            base = name or p.stem
        else:
            import json

            raw = json.loads(p.read_text(encoding="utf-8"))
            colors = raw.get("colors", raw) if isinstance(raw, dict) else raw
            base = (raw.get("name", p.stem) if isinstance(raw, dict) else p.stem)
        save_palette(base.strip(), [list(c) for c in colors])
        win._palette_base = base.strip()
        win._palette_dirty = False
        refresh_palette_list(win)
        win.cmb_pal_preset.setCurrentText(base.strip())
        on_palette_preset_changed(win, base.strip())
        win._status(f"Palette imported: {base.strip()}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not import:\n{e}")


def export_palette_file(win) -> None:
    """Exports the current strip to .json or .gpl (offline share)."""
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from app.palette_library import to_gpl

    if len(win.custom_colors) < 2:
        QMessageBox.warning(win, "TRAKKART", "Need 2-16 colors to export")
        return
    path, selected = QFileDialog.getSaveFileName(
        win, "Export palette", "my_palette.json",
        "JSON (*.json);;GIMP palette (*.gpl)")
    if not path:
        return
    try:
        p = Path(path)
        if p.suffix.lower() == ".gpl" or "GIMP" in (selected or ""):
            if p.suffix.lower() != ".gpl":
                p = p.with_suffix(".gpl")
            p.write_text(to_gpl(p.stem, win.custom_colors), encoding="utf-8")
        else:
            import json

            if p.suffix.lower() != ".json":
                p = p.with_suffix(".json")
            p.write_text(
                json.dumps({"name": p.stem, "colors": [list(c) for c in win.custom_colors]},
                           indent=2), encoding="utf-8")
        win._status(f"Palette exported: {p.name}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not export:\n{e}")


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


def shuffle_custom_colors(win) -> None:
    """🔀 Shuffle only unlocked swatches (locks stay in place).

    Deterministic on the palette seed spin: same seed + same strip =
    same order. The dice rolls a fresh seed first.
    """
    import random

    colors = list(win.custom_colors)
    locks = list(getattr(win, "_palette_locks", []) or [False] * len(colors))
    if len(locks) != len(colors):
        locks = [False] * len(colors)
    free_idx = [i for i, locked in enumerate(locks) if not locked]
    if len(free_idx) < 2:
        win._status("Nothing to shuffle (lock fewer swatches)")
        return
    try:
        seed = int(win.spn_pal_seed.value())
    except Exception:  # noqa: BLE001
        seed = 0
    pool = [colors[i] for i in free_idx]
    random.Random(seed).shuffle(pool)
    for i, c in zip(free_idx, pool):
        colors[i] = c
    set_custom_colors(win, colors, dirty=True)
    win._palette_locks = locks
    win.refresh()
    win._status(f"Shuffled {len(pool)} unlocked colors (seed {seed})")


def toggle_palette_lock(win, i: int) -> None:
    locks = list(getattr(win, "_palette_locks", []) or [False] * len(win.custom_colors))
    if 0 <= i < len(locks):
        locks[i] = not locks[i]
        win._palette_locks = locks
        sync_custom_label(win)


def randomize_adjusts(win) -> None:
    """🎲 Randomizes only unlocked adjusts (B/C/S/M/H).

    Draws from the chaos seed spin, so the result replays by seed.
    """
    import random

    locks = dict(getattr(win, "_adjust_locks", {}) or {})
    try:
        seed = int(win.spn_chaos_seed.value())
    except Exception:  # noqa: BLE001
        seed = 0
    rng = random.Random(seed)

    def _set(slider, value: int):
        try:
            slider.blockSignals(True)
            slider.setValue(int(value))
        finally:
            slider.blockSignals(False)

    if not locks.get("brightness", False) and hasattr(win, "sld_bri"):
        _set(win.sld_bri, rng.randint(80, 130))
    if not locks.get("contrast", False) and hasattr(win, "sld_con"):
        _set(win.sld_con, rng.randint(80, 130))
    if not locks.get("saturation", False) and hasattr(win, "sld_sat"):
        _set(win.sld_sat, rng.randint(60, 160))
    if not locks.get("midtones", False) and hasattr(win, "sld_mid"):
        _set(win.sld_mid, rng.randint(80, 130))
    if not locks.get("highlights", False) and hasattr(win, "sld_high"):
        _set(win.sld_high, rng.randint(-30, 30))
    win.refresh()
    locked = sorted(k for k, v in locks.items() if v)
    win._status(f"Adjusts randomized (seed {seed}, locked: {', '.join(locked) or 'none'})")
