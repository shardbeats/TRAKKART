"""Params/preset controller: widgets <-> Preset dataclass.

Single source of truth for reading the panel (build_params) and applying
a preset back to the widgets (apply_preset). State and widgets stay on
MainWindow; this module holds the behavior. The window keeps the same
`current_params()` / `_apply_preset()` / `refresh_presets()` /
`save_current_preset()` / `share_preset_*()` API by delegation.
"""

from __future__ import annotations


# ------------------------------------------------------------------
# Widget readers (doc único CANVAS + anim único VIDEO) + tabla de bindings.
# Añadir un control = 1 fila en BINDINGS (antes: tocar build y apply a mano).
# Cada fila: (campo, get(win) -> valor, set(win, valor)).
# ------------------------------------------------------------------


def _block(w):
    w.blockSignals(True)


def _unblock(w):
    w.blockSignals(False)


def _slider(attr: str, div: float = 1.0):
    def get(win):
        return getattr(win, attr).value() / div

    def set(win, v):
        w = getattr(win, attr)
        try:
            _block(w)
            w.setValue(int(round(float(v) * div)))
        finally:
            _unblock(w)

    return get, set


def _spin(attr: str):
    def get(win):
        return int(getattr(win, attr).value())

    def set(win, v):
        w = getattr(win, attr)
        try:
            _block(w)
            w.setValue(int(v))
        finally:
            _unblock(w)

    return get, set


def _combo(attr: str):
    def get(win):
        return getattr(win, attr).currentText()

    def set(win, v):
        w = getattr(win, attr)
        if w.findText(str(v)) < 0:
            return
        try:
            _block(w)
            w.setCurrentText(str(v))
        finally:
            _unblock(w)

    return get, set


def _anim_combo(attr: str, lo: int, hi: int, default: int):
    def get(win):
        return anim_combo_int(getattr(win, attr), default, lo, hi)

    def set(win, v):
        set_anim_combo(getattr(win, attr), max(lo, min(hi, int(v))))

    return get, set


def _brand_get(win):
    return win.brand_color


def _brand_set(win, v):
    win.set_brand_color(v or "")


def _duo_mid_get(win):
    return float(win.sld_duo_mid.value())


def _duo_mid_set(win, v):
    win.sld_duo_mid.setValue(int(float(v)))


def _border_color_get(win):
    return win.border_color


def _border_color_set(win, v):
    win.set_border_color(str(v or "#000000"))


def _scan_get(win):
    return int(win.spn_scan.value())


def _scan_set(win, v):
    win.spn_scan.setValue(int(v))


def _glow_radius_get(win):
    # Radio 0 si el glow está apagado (el spin conserva su último valor).
    if win.sld_glow.value() <= 0:
        return 0.0
    return float(win.spn_glowrad.value())


def _glow_radius_set(win, v):
    win.spn_glowrad.setValue(int(float(v)))


# Normalizaciones de render_params que el build aplica (la UI admite
# intermedios que el motor redondea al válido más cercano).
def _norms():
    from app.render_params import (
        normalize_grille,
        normalize_halftone,
        normalize_posterize,
        normalize_scanlines,
        normalize_slice_bands,
    )

    return {
        "scanlines": normalize_scanlines,
        "posterize": normalize_posterize,
        "halftone": normalize_halftone,
        "grille": normalize_grille,
        "glitch_slice_bands": lambda v: normalize_slice_bands(int(v)),
    }


def _video_mode_get(win):
    return gif_anim_mode(win)


def _video_mode_set(win, v):
    w = win.cmb_video_mode
    try:
        w.blockSignals(True)
        if w.findText(str(v)) >= 0:
            w.setCurrentText(str(v))
    finally:
        w.blockSignals(False)


def _pingpong_get(win):
    return bool(win.chk_video_pingpong.isChecked())


def _pingpong_set(win, v):
    w = win.chk_video_pingpong
    try:
        w.blockSignals(True)
        w.setChecked(bool(v))
    finally:
        w.blockSignals(False)


def doc_dims(win) -> tuple[int, int]:
    """W/H del documento (Photoshop-style: los spins mandan)."""
    from app.canvas import MAX_DIM, MIN_DIM

    try:
        w = max(MIN_DIM, min(MAX_DIM, int(win.spn_canvas_w.value())))
        h = max(MIN_DIM, min(MAX_DIM, int(win.spn_canvas_h.value())))
        return w, h
    except Exception:  # noqa: BLE001
        return (3000, 3000)


def doc_size(win) -> int:
    """Lado largo (compat: prefs, batch legacy, GIF)."""
    w, h = doc_dims(win)
    return max(w, h)


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


def on_ratio_preset(win) -> None:
    """El usuario eligió un ratio: rellena W/H a la escala actual (Photoshop)."""
    from app.canvas import canvas_size_for, ratio_value

    try:
        ratio = ratio_value(win.cmb_ratio.currentText())
    except Exception:  # noqa: BLE001
        return
    if ratio == "custom":
        sync_docdims(win)
        win._schedule_refresh()
        return
    long_side = max(doc_dims(win))
    try:
        w, h = canvas_size_for(ratio, long_side)
    except KeyError:
        return
    for spn, v in ((win.spn_canvas_w, w), (win.spn_canvas_h, h)):
        try:
            spn.blockSignals(True)
            spn.setValue(int(v))
        finally:
            spn.blockSignals(False)
    sync_docdims(win)
    win._schedule_refresh()


def on_canvas_wh_changed(win) -> None:
    """Editar W/H salta solo a Custom (Photoshop). Sin bucles: activated no re-flippea."""
    from app.canvas import CUSTOM_LABEL

    try:
        if win.cmb_ratio.currentText() != CUSTOM_LABEL:
            win.cmb_ratio.blockSignals(True)
            win.cmb_ratio.setCurrentText(CUSTOM_LABEL)
            win.cmb_ratio.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass
    sync_docdims(win)
    win._schedule_refresh()


def ratio_value_of(win) -> str:
    from app.canvas import ratio_value

    try:
        return ratio_value(win.cmb_ratio.currentText())
    except Exception:  # noqa: BLE001
        return "1:1"


def set_ratio_label(win, value: str) -> None:
    from app.canvas import ratio_label

    try:
        win.cmb_ratio.blockSignals(True)
        win.cmb_ratio.setCurrentText(ratio_label(value))
    finally:
        win.cmb_ratio.blockSignals(False)


BINDINGS: tuple = (
    ("method",) + _combo("cmb_method"),
    ("pixel_size",) + _spin("spn_pixel"),
    ("threshold",) + _slider("sld_thr"),
    ("brightness",) + _slider("sld_bri", 100.0),
    ("contrast",) + _slider("sld_con", 100.0),
    ("saturation",) + _slider("sld_sat", 100.0),
    ("ratio", ratio_value_of, set_ratio_label),
    ("canvas_w",) + _spin("spn_canvas_w"),
    ("canvas_h",) + _spin("spn_canvas_h"),
    ("crop_mode",) + _combo("cmb_crop"),
    ("pre_blur",) + _slider("sld_blur", 10.0),
    ("pre_sharpen",) + _spin("spn_sharp"),
    ("pre_hue",) + _slider("sld_hue"),
    ("pre_denoise",) + _spin("spn_denoise"),
    ("pre_smooth",) + _slider("sld_smooth", 10.0),
    ("glow_radius", _glow_radius_get, _glow_radius_set),
    ("glow_intensity",) + _slider("sld_glow"),
    ("glow_threshold",) + _spin("spn_glowthr"),
    ("grain",) + _slider("sld_grain"),
    ("vignette",) + _slider("sld_vig"),
    ("scanlines", _scan_get, _scan_set),
    ("replace_color", _brand_get, _brand_set),
    ("gif_frames",) + _anim_combo("cmb_video_frames", 2, 24, 6),
    ("gif_mode", _video_mode_get, _video_mode_set),
    ("gif_fps",) + _anim_combo("cmb_video_fps", 2, 60, 8),
    ("gif_pingpong", _pingpong_get, _pingpong_set),
    ("duotone_mid", _duo_mid_get, _duo_mid_set),
    ("posterize",) + _spin("spn_poster"),
    ("split_tone",) + _slider("sld_split"),
    ("fade",) + _slider("sld_fade"),
    ("halftone",) + _spin("spn_halftone"),
    ("halftone_shape",) + _combo("cmb_halftone"),
    ("dust",) + _slider("sld_dust"),
    ("border",) + _spin("spn_border"),
    ("border_color", _border_color_get, _border_color_set),
    ("letterbox",) + _spin("spn_letterbox"),
    ("glitch_chroma",) + _slider("sld_chroma"),
    ("glitch_slice_bands",) + _spin("spn_slice"),
    ("pixelsort",) + _spin("spn_pixelsort"),
    ("wave",) + _spin("spn_wave"),
    ("mosh",) + _slider("sld_mosh"),
    ("grille",) + _spin("spn_grille"),
)


def sync_docdims(win) -> None:
    try:
        w, h = doc_dims(win)
        label = win.cmb_ratio.currentText()
        win.lbl_docdims.setText(f"{w}×{h} px · {label}")
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


def _kinds() -> dict:
    from app.presets import FIELDS

    return {f.name: f.kind for f in FIELDS}


def _coerce_kind(kind: str, value):
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "str":
        return str(value)
    if kind == "bool":
        return bool(value)
    return value


def build_params(win):
    """Preset from widgets. Única fuente (la UI es el editor)."""
    from app.palettes import palette_names
    from app.presets import Preset

    kinds = _kinds()
    norms = _norms()
    kwargs: dict = {}
    for field, get, _set in BINDINGS:
        v = get(win)
        if field in norms:
            v = norms[field](v)
        kwargs[field] = _coerce_kind(kinds[field], v)
    base = win._palette_base if win._palette_base in palette_names() else "SLIME"
    return Preset(
        name=win.cmb_preset.currentText(),
        palette=base,
        focus_x=float(win.crop_fx),
        focus_y=float(win.crop_fy),
        crop_zoom=float(win.crop_zoom),
        custom_palette=[list(c) for c in win.custom_colors] or None,
        vector_export=bool(win._vector_export),
        vector_cell=int(win._vector_cell),
        gif_export=bool(win._gif_export),
        gif_size=int(gif_anim_size(win)),
        export_size=int(doc_size(win)),
        export_format=str(win._export_format),
        export_quality=int(win._export_quality),
        duotone_dark=win.duotone_dark,
        duotone_light=win.duotone_light,
        glitch_slice_max=24,
        **kwargs,
    )


def apply_preset(win, name: str) -> None:
    from app.palette_library import palette_colors
    from app.presets import load_preset

    try:
        p = load_preset(name)
    except Exception:
        return
    # Auto -> concreto: presets viejos/a mano sin W/H heredan ratio+export_size.
    from app.canvas import doc_dimensions

    cw, ch = doc_dimensions(p.ratio, p.export_size,
                            int(getattr(p, "canvas_w", 0) or 0),
                            int(getattr(p, "canvas_h", 0) or 0))
    p.canvas_w, p.canvas_h = int(cw), int(ch)
    for field, _get, set in BINDINGS:
        set(win, getattr(p, field))
    # Crop vars (sin widget directo).
    win.crop_fx = float(p.focus_x)
    win.crop_fy = float(p.focus_y)
    win.crop_zoom = float(p.crop_zoom)
    win._sync_crop_label()
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
    # Doc único: W/H del CANVAS (los setters bloquean señales: sin flips).
    sync_docdims(win)
    # Grado + resto de etiquetas.
    win.duotone_dark = str(p.duotone_dark or "")
    win.duotone_light = str(p.duotone_light or "")
    win._sync_duo_label()
    win.border_color = str(p.border_color or "#000000")
    win.lbl_border.setText(win.border_color)
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
