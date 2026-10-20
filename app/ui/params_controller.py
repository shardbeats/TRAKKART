"""Params/preset controller: widgets <-> Preset dataclass.

Single source of truth for reading the panel (build_params) and applying
a preset back to the widgets (apply_preset). State and widgets stay on
MainWindow; this module holds the behavior. The window keeps the same
`current_params()` / `_apply_preset()` / `refresh_presets()` /
`save_current_preset()` / `share_preset_*()` API by delegation.
"""

from __future__ import annotations


# ------------------------------------------------------------------
# Widget readers (doc único CANVAS + anim único VIDEO)
# ------------------------------------------------------------------
def doc_size(win) -> int:
    from app.exporter import MAX_SIDE, MIN_SIDE

    try:
        return max(MIN_SIDE, min(MAX_SIDE, int(win.spn_docsize.value())))
    except Exception:  # noqa: BLE001
        return 3000


def anim_combo_int(cmb, default: int, lo: int, hi: int) -> int:
    """Lee un combo editable (lista sugerida + valor libre)."""
    try:
        return max(lo, min(hi, int(str(cmb.currentText()).strip())))
    except Exception:  # noqa: BLE001
        return int(default)


def set_anim_combo(cmb, value: int) -> None:
    """Fija un combo editable conservando valores custom fuera de la lista."""
    txt = str(int(value))
    try:
        if cmb.findText(txt) < 0:
            cmb.addItem(txt)
        cmb.blockSignals(True)
        cmb.setCurrentText(txt)
    finally:
        cmb.blockSignals(False)


def gif_anim_frames(win) -> int:
    try:
        return anim_combo_int(win.cmb_video_frames, 6, 2, 24)
    except Exception:  # noqa: BLE001
        return int(getattr(win, "_gif_frames", 6))


def gif_anim_mode(win) -> str:
    from app.gif import GIF_MODES

    try:
        m = win.cmb_video_mode.currentText()
        return m if m in GIF_MODES else "both"
    except Exception:  # noqa: BLE001
        return str(getattr(win, "_gif_mode", "both"))


def gif_anim_fps(win) -> int:
    try:
        return anim_combo_int(win.cmb_video_fps, 8, 2, 60)
    except Exception:  # noqa: BLE001
        return int(getattr(win, "_gif_fps", 8))


def gif_anim_size(win) -> int:
    # Sin Size en VIDEO: el anim sale al tamaño del documento canvas.
    return int(doc_size(win))


def gif_anim_pingpong(win) -> bool:
    try:
        return bool(win.chk_video_pingpong.isChecked())
    except Exception:  # noqa: BLE001
        return bool(getattr(win, "_gif_pingpong", False))


def valid_slice_bands(win) -> int:
    from app.render_params import normalize_slice_bands

    return normalize_slice_bands(int(win.spn_slice.value()))


def on_docsize_preset(win, text: str) -> None:
    if text == "Custom":
        return
    try:
        win.spn_docsize.blockSignals(True)
        win.spn_docsize.setValue(int(text))
    finally:
        win.spn_docsize.blockSignals(False)
    sync_docsize_combo(win, int(text))
    win._schedule_refresh()


def on_docsize_custom(win) -> None:
    try:
        sync_docsize_combo(win, int(win.spn_docsize.value()))
    except Exception:  # noqa: BLE001
        pass
    sync_docdims(win)
    win._schedule_refresh()


def sync_docsize_combo(win, size: int) -> None:
    from app.exporter import SIZE_PRESETS

    txt = str(size) if size in SIZE_PRESETS else "Custom"
    try:
        if win.cmb_docsize.currentText() != txt:
            win.cmb_docsize.blockSignals(True)
            win.cmb_docsize.setCurrentText(txt)
            win.cmb_docsize.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass


def sync_docdims(win) -> None:
    try:
        from app.canvas import canvas_size_for

        w, h = canvas_size_for(win.cmb_ratio.currentText(), doc_size(win))
        win.lbl_docdims.setText(f"{w}×{h} px")
        try:
            win.lbl_video_size.setText(f"{w}×{h} px (canvas)")
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------
# Preset build / apply
# ------------------------------------------------------------------
def current_adjust(win):
    from app.adjust import Adjust

    return Adjust(
        brightness=win.sld_bri.value() / 100.0,
        contrast=win.sld_con.value() / 100.0,
        saturation=win.sld_sat.value() / 100.0,
    )


def build_params(win):
    """Preset from widgets. Única fuente (la UI es el editor)."""
    from app.palettes import palette_names
    from app.presets import Preset
    from app.render_params import (
        normalize_grille,
        normalize_halftone,
        normalize_posterize,
        normalize_scanlines,
    )

    base = win._palette_base if win._palette_base in palette_names() else "SLIME"
    return Preset(
        name=win.cmb_preset.currentText(),
        method=win.cmb_method.currentText(),
        palette=base,
        pixel_size=int(win.spn_pixel.value()),
        threshold=int(win.sld_thr.value()),
        brightness=win.sld_bri.value() / 100.0,
        contrast=win.sld_con.value() / 100.0,
        saturation=win.sld_sat.value() / 100.0,
        ratio=win.cmb_ratio.currentText(),
        crop_mode=win.cmb_crop.currentText(),
        focus_x=float(win.crop_fx),
        focus_y=float(win.crop_fy),
        crop_zoom=float(win.crop_zoom),
        pre_blur=win.sld_blur.value() / 10.0,
        pre_sharpen=int(win.spn_sharp.value()),
        pre_hue=float(win.sld_hue.value()),
        pre_denoise=int(win.spn_denoise.value()),
        pre_smooth=win.sld_smooth.value() / 10.0,
        glow_radius=float(win.spn_glowrad.value()) if win.sld_glow.value() > 0 else 0.0,
        glow_intensity=float(win.sld_glow.value()),
        glow_threshold=int(win.spn_glowthr.value()),
        grain=float(win.sld_grain.value()),
        vignette=float(win.sld_vig.value()),
        scanlines=normalize_scanlines(int(win.spn_scan.value())),
        replace_color=win.brand_color,
        custom_palette=[list(c) for c in win.custom_colors] or None,
        vector_export=bool(win._vector_export),
        vector_cell=int(win._vector_cell),
        gif_export=bool(win._gif_export),
        gif_frames=int(gif_anim_frames(win)),
        gif_mode=str(gif_anim_mode(win)),
        gif_fps=int(gif_anim_fps(win)),
        gif_size=int(gif_anim_size(win)),
        gif_pingpong=bool(gif_anim_pingpong(win)),
        export_size=int(doc_size(win)),
        export_format=str(win._export_format),
        export_quality=int(win._export_quality),
        duotone_dark=win.duotone_dark,
        duotone_light=win.duotone_light,
        duotone_mid=float(win.sld_duo_mid.value()),
        posterize=normalize_posterize(int(win.spn_poster.value())),
        split_tone=float(win.sld_split.value()),
        fade=float(win.sld_fade.value()),
        halftone=normalize_halftone(int(win.spn_halftone.value())),
        halftone_shape=win.cmb_halftone.currentText(),
        dust=float(win.sld_dust.value()),
        border=int(win.spn_border.value()),
        border_color=win.border_color,
        letterbox=int(win.spn_letterbox.value()),
        glitch_chroma=int(win.sld_chroma.value()),
        glitch_slice_bands=valid_slice_bands(win),
        glitch_slice_max=24,
        pixelsort=int(win.spn_pixelsort.value()),
        wave=int(win.spn_wave.value()),
        mosh=float(win.sld_mosh.value()),
        grille=normalize_grille(int(win.spn_grille.value())),
    )


def apply_preset(win, name: str) -> None:
    from app.palette_library import palette_colors
    from app.presets import load_preset

    try:
        p = load_preset(name)
    except Exception:
        return
    win.cmb_method.setCurrentText(p.method)
    win.spn_pixel.setValue(int(p.pixel_size))
    win.sld_thr.setValue(int(p.threshold))
    win.sld_bri.setValue(int(float(p.brightness) * 100))
    win.sld_con.setValue(int(float(p.contrast) * 100))
    win.sld_sat.setValue(int(float(p.saturation) * 100))
    if win.cmb_ratio.findText(p.ratio) >= 0:
        win.cmb_ratio.setCurrentText(p.ratio)
    if win.cmb_crop.findText(p.crop_mode) >= 0:
        win.cmb_crop.setCurrentText(p.crop_mode)
    win.crop_fx = float(p.focus_x)
    win.crop_fy = float(p.focus_y)
    win.crop_zoom = float(p.crop_zoom)
    win._sync_crop_label()
    win.sld_blur.setValue(int(round(float(p.pre_blur) * 10)))
    win.spn_sharp.setValue(int(p.pre_sharpen))
    win.sld_hue.setValue(int(float(p.pre_hue)))
    win.spn_denoise.setValue(int(p.pre_denoise))
    win.sld_smooth.setValue(int(round(float(p.pre_smooth) * 10)))
    win.sld_glow.setValue(int(float(p.glow_intensity)))
    win.spn_glowrad.setValue(int(float(p.glow_radius)))
    win.spn_glowthr.setValue(int(p.glow_threshold))
    win.sld_grain.setValue(int(float(p.grain)))
    win.sld_vig.setValue(int(float(p.vignette)))
    win.spn_scan.setValue(int(p.scanlines))
    win.set_brand_color(p.replace_color)
    # La paleta en uso es la tira custom: del preset, o la built-in base.
    win._palette_base = p.palette
    base_colors = palette_colors(p.palette)
    win._set_custom_colors(
        [tuple(c) for c in (p.custom_palette or [])] or base_colors,
        dirty=False,
    )
    win._palette_dirty = False
    win.refresh_palette_list()
    # Salidas: el preset es la receta; los diálogos las aplican por operación.
    win._vector_export = bool(p.vector_export)
    win._vector_cell = int(p.vector_cell)
    win._gif_export = bool(p.gif_export)
    win._gif_frames = int(p.gif_frames)
    win._gif_mode = str(p.gif_mode)
    win._gif_fps = int(getattr(p, "gif_fps", 8))
    win._gif_size = int(getattr(p, "gif_size", 1200))
    win._gif_pingpong = bool(getattr(p, "gif_pingpong", False))
    win._export_size = int(p.export_size)
    win._export_format = str(p.export_format)
    win._export_quality = int(p.export_quality)
    # Doc único: tamaño documento en CANVAS.
    try:
        win.spn_docsize.blockSignals(True)
        win.spn_docsize.setValue(int(p.export_size))
    finally:
        win.spn_docsize.blockSignals(False)
    sync_docsize_combo(win, int(p.export_size))
    sync_docdims(win)
    # Anim único: VIDEO es el editor (widgets), vars como respaldo.
    try:
        win.cmb_video_mode.blockSignals(True)
        if win.cmb_video_mode.findText(str(p.gif_mode)) >= 0:
            win.cmb_video_mode.setCurrentText(str(p.gif_mode))
    finally:
        win.cmb_video_mode.blockSignals(False)
    set_anim_combo(win.cmb_video_frames, max(2, min(24, int(p.gif_frames))))
    set_anim_combo(win.cmb_video_fps, max(2, min(60, int(getattr(p, "gif_fps", 8)))))
    try:
        win.chk_video_pingpong.blockSignals(True)
        win.chk_video_pingpong.setChecked(bool(getattr(p, "gif_pingpong", False)))
    finally:
        win.chk_video_pingpong.blockSignals(False)
    # Grade pack.
    win.duotone_dark = str(p.duotone_dark or "")
    win.duotone_light = str(p.duotone_light or "")
    win.sld_duo_mid.setValue(int(float(p.duotone_mid)))
    win._sync_duo_label()
    win.spn_poster.setValue(int(p.posterize))
    win.sld_split.setValue(int(float(p.split_tone)))
    win.sld_fade.setValue(int(float(p.fade)))
    win._sync_duo_label()
    # Texture pack.
    win.spn_halftone.setValue(int(p.halftone))
    if win.cmb_halftone.findText(p.halftone_shape) >= 0:
        win.cmb_halftone.setCurrentText(p.halftone_shape)
    win.sld_dust.setValue(int(float(p.dust)))
    win.spn_border.setValue(int(p.border))
    win.border_color = str(p.border_color or "#000000")
    win.lbl_border.setText(win.border_color)
    win.spn_letterbox.setValue(int(p.letterbox))
    win.sld_chroma.setValue(int(p.glitch_chroma))
    win.spn_slice.setValue(int(p.glitch_slice_bands))
    # Glitch extra pack.
    win.spn_pixelsort.setValue(int(p.pixelsort))
    win.spn_wave.setValue(int(p.wave))
    win.sld_mosh.setValue(int(float(p.mosh)))
    win.spn_grille.setValue(int(p.grille))
    if win.cmb_preset.findText(name) < 0:
        win.refresh_presets()
    win.cmb_preset.setCurrentText(name)
    win.refresh()


def refresh_presets(win) -> None:
    from app.presets import list_presets

    win.cmb_preset.blockSignals(True)
    win.cmb_preset.clear()
    win.cmb_preset.addItems(list_presets())
    win.cmb_preset.blockSignals(False)


def on_preset_changed(win, name: str) -> None:
    if name:
        win._apply_preset(name)


def save_current_preset(win) -> None:
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    from app.presets import save_preset

    name, ok = QInputDialog.getText(win, "Save preset", "Name:")
    if not ok or not name.strip():
        return
    try:
        p = win.current_params()
        p.name = name.strip()
        save_preset(p)
        win.refresh_presets()
        win.cmb_preset.setCurrentText(name.strip())
        win._status(f"Preset saved: {name.strip()}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not save:\n{e}")


def share_export(win) -> None:
    import json
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog, QMessageBox

    path, _ = QFileDialog.getSaveFileName(win, "Export preset", "my_preset.json", "JSON (*.json)")
    if not path:
        return
    try:
        p = win.current_params()
        p.name = Path(path).stem
        Path(path).write_text(json.dumps(p.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        win._status(f"Preset exported: {Path(path).name}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not export:\n{e}")


def share_import(win) -> None:
    import json
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from app.presets import Preset, save_preset

    path, _ = QFileDialog.getOpenFileName(win, "Import preset", "", "JSON (*.json)")
    if not path:
        return
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        p = Preset.from_dict(raw)
        save_preset(p)
        win.refresh_presets()
        win._apply_preset(p.name)
        win._status(f"Preset imported: {p.name}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Invalid preset:\n{e}")
