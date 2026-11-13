"""Params/preset controller: widgets <-> Preset dataclass.

Single source of truth for reading the panel (build_params) and applying
a preset back to the widgets (apply_preset). State and widgets stay on
MainWindow; this module holds the behavior. The window keeps the same
`current_params()` / `_apply_preset()` / `refresh_presets()` /
`save_current_preset()` / `share_preset_*()` API by delegation.
"""

from __future__ import annotations


# ------------------------------------------------------------------
# Widget readers (single doc CANVAS + single anim VIDEO) + bindings table.
# Adding a control = 1 row in BINDINGS (before: touch build and apply by hand).
# Each row: (field, get(win) -> value, set(win, value)).
# ------------------------------------------------------------------


from app.ui.params_binding import (  # noqa: F401 (set_anim_combo re-exported for MainWindow)
    _slider,
    _spin,
    _combo,
    _anim_combo,
    _dspin,
    _brand_get,
    _brand_set,
    _duo_mid_get,
    _duo_mid_set,
    _border_color_get,
    _border_color_set,
    _scan_get,
    _scan_set,
    _glow_radius_get,
    _glow_radius_set,
    anim_combo_int,
    set_anim_combo,
)


# Render-param normalizations applied by build (UI accepts
# intermediates that the engine rounds to the nearest valid one).
def _norms():
    from app.render_params import (
        normalize_grille,
        normalize_halftone,
        normalize_palette_depth,
        normalize_posterize,
        normalize_scanlines,
        normalize_slice_bands,
    )

    return {
        "scanlines": normalize_scanlines,
        "posterize": normalize_posterize,
        "halftone": normalize_halftone,
        "grille": normalize_grille,
        "palette_depth": normalize_palette_depth,
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


def _morph_loop_get(win):
    try:
        return bool(win.chk_morph_loop.isChecked())
    except Exception:  # noqa: BLE001
        return True


def _morph_loop_set(win, v):
    try:
        w = win.chk_morph_loop
    except Exception:  # noqa: BLE001
        return
    try:
        w.blockSignals(True)
        w.setChecked(bool(v))
    finally:
        w.blockSignals(False)


def _shade_get(win):
    try:
        return bool(win.chk_dissolve_shade.isChecked())
    except Exception:  # noqa: BLE001
        return False


def _shade_set(win, v):
    try:
        w = win.chk_dissolve_shade
    except Exception:  # noqa: BLE001
        return
    try:
        w.blockSignals(True)
        w.setChecked(bool(v))
    finally:
        w.blockSignals(False)


def doc_dims(win) -> tuple[int, int]:
    """Document W/H (editor-style: spins rule)."""
    from app.canvas import MAX_DIM, MIN_DIM

    try:
        w = max(MIN_DIM, min(MAX_DIM, int(win.spn_canvas_w.value())))
        h = max(MIN_DIM, min(MAX_DIM, int(win.spn_canvas_h.value())))
        return w, h
    except Exception:  # noqa: BLE001
        return (3000, 3000)


def read_motif(win) -> dict | None:
    """Reads the MOTIF panel config. None if widgets are missing (tests)."""
    try:
        from app.motif import normalize_config

        bands = []
        for i in range(4):
            shape = getattr(win, f"cmb_motif_{i}").currentText()
            size = int(getattr(win, f"spn_motif_{i}").value())
            bands.append({"shape": str(shape), "size": size})
        return normalize_config({"bands": bands})
    except Exception:  # noqa: BLE001
        return None


def write_motif(win, cfg: dict | None) -> None:
    """Applies config to the panel (None = default). No signal loops."""
    try:
        from app.motif import default_config, normalize_config

        norm = normalize_config(cfg) if cfg else default_config()
        for i, band in enumerate(norm["bands"]):
            cmb = getattr(win, f"cmb_motif_{i}")
            spn = getattr(win, f"spn_motif_{i}")
            try:
                cmb.blockSignals(True)
                if cmb.findText(band["shape"]) >= 0:
                    cmb.setCurrentText(band["shape"])
            finally:
                cmb.blockSignals(False)
            try:
                spn.blockSignals(True)
                spn.setValue(int(band["size"]))
            finally:
                spn.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass


def read_ascii(win) -> dict | None:
    """Reads the ASCII panel config. None if widgets are missing (tests)."""
    try:
        from app.ascii import CHARSET_PRESETS, normalize_config
        preset = win.cmb_ascii_preset.currentText()
        custom = win.txt_ascii_custom.text().strip()
        return normalize_config({
            "charset": custom or CHARSET_PRESETS.get(preset, ""),
            "columns": int(win.spn_ascii_cols.value()),
            "gamma": float(win.sld_ascii_gamma.value()) / 100.0,
            "color": win.cmb_ascii_color.currentText(),
            "ink": win.txt_ascii_ink.text().strip(),
            "bg": win.txt_ascii_bg.text().strip(),
            "invert": bool(win.chk_ascii_invert.isChecked()),
            "dither": float(win.sld_ascii_dither.value()),
        })
    except Exception:  # noqa: BLE001
        return None


def write_ascii(win, cfg: dict | None) -> None:
    """Applies config to the ASCII panel (None = defaults). No signal loops."""
    try:
        from app.ascii import ASCII_DEFAULTS, CHARSET_PRESETS, normalize_config
        norm = normalize_config(cfg) if cfg else dict(ASCII_DEFAULTS)
        for w, v in ((win.cmb_ascii_preset, None),):
            pass
        # preset combo: match charset or fall back to Classic + custom text
        matched = next((k for k, v in CHARSET_PRESETS.items() if v == norm["charset"]), None)
        try:
            win.cmb_ascii_preset.blockSignals(True)
            win.cmb_ascii_preset.setCurrentText(matched or "Classic")
        finally:
            win.cmb_ascii_preset.blockSignals(False)
        try:
            win.txt_ascii_custom.blockSignals(True)
            win.txt_ascii_custom.setText("" if matched else norm["charset"])
        finally:
            win.txt_ascii_custom.blockSignals(False)
        try:
            win.spn_ascii_cols.blockSignals(True)
            win.spn_ascii_cols.setValue(int(norm["columns"]))
        finally:
            win.spn_ascii_cols.blockSignals(False)
        try:
            win.sld_ascii_gamma.blockSignals(True)
            win.sld_ascii_gamma.setValue(int(float(norm["gamma"]) * 100))
        finally:
            win.sld_ascii_gamma.blockSignals(False)
        try:
            win.cmb_ascii_color.blockSignals(True)
            if win.cmb_ascii_color.findText(norm["color"]) >= 0:
                win.cmb_ascii_color.setCurrentText(norm["color"])
        finally:
            win.cmb_ascii_color.blockSignals(False)
        for attr, val in (("txt_ascii_ink", norm["ink"]), ("txt_ascii_bg", norm["bg"])):
            try:
                w = getattr(win, attr)
                w.blockSignals(True)
                w.setText(str(val))
            finally:
                w.blockSignals(False)
        try:
            win.chk_ascii_invert.blockSignals(True)
            win.chk_ascii_invert.setChecked(bool(norm["invert"]))
        finally:
            win.chk_ascii_invert.blockSignals(False)
        try:
            win.sld_ascii_dither.blockSignals(True)
            win.sld_ascii_dither.setValue(int(float(norm["dither"])))
        finally:
            win.sld_ascii_dither.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass


def doc_size(win) -> int:
    """Long side (compat: prefs, batch legacy, GIF)."""
    w, h = doc_dims(win)
    return max(w, h)


def gif_anim_frames(win) -> int:
    try:
        return anim_combo_int(win.cmb_video_frames, 6, 2, 256)
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
    # No Size in VIDEO: anim renders at document canvas size.
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
    """User picked a ratio: fills W/H at current scale (classic editors)."""
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
    """Editing W/H jumps to Custom only (classic editors). No loops: activated never re-flips."""
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
    ("midtones",) + _slider("sld_mid", 100.0),
    ("highlights",) + _slider("sld_high"),
    ("palette_depth",) + _spin("spn_pal_depth"),
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
    ("grain_seed",) + _spin("spn_grain_seed"),
    ("vignette",) + _slider("sld_vig"),
    ("scanlines", _scan_get, _scan_set),
    ("replace_color", _brand_get, _brand_set),
    ("gif_frames",) + _anim_combo("cmb_video_frames", 2, 256, 6),
    ("gif_mode", _video_mode_get, _video_mode_set),
    ("gif_fps",) + _anim_combo("cmb_video_fps", 2, 60, 8),
    ("gif_pingpong", _pingpong_get, _pingpong_set),
    ("motion_amount",) + _slider("sld_motion", 100.0),
    ("duotone_mid", _duo_mid_get, _duo_mid_set),
    ("posterize",) + _spin("spn_poster"),
    ("split_tone",) + _slider("sld_split"),
    ("fade",) + _slider("sld_fade"),
    ("halftone",) + _spin("spn_halftone"),
    ("halftone_shape",) + _combo("cmb_halftone"),
    ("dust",) + _slider("sld_dust"),
    ("dust_seed",) + _spin("spn_dust_seed"),
    ("border",) + _spin("spn_border"),
    ("border_color", _border_color_get, _border_color_set),
    ("letterbox",) + _spin("spn_letterbox"),
    ("glitch_chroma",) + _slider("sld_chroma"),
    ("glitch_slice_bands",) + _spin("spn_slice"),
    ("glitch_slice_seed",) + _spin("spn_slice_seed"),
    ("pixelsort",) + _spin("spn_pixelsort"),
    ("pixelsort_seed",) + _spin("spn_pixelsort_seed"),
    ("wave",) + _spin("spn_wave"),
    ("wave_seed",) + _spin("spn_wave_seed"),
    ("mosh",) + _slider("sld_mosh"),
    ("mosh_mode",) + _combo("cmb_mosh_mode"),
    ("mosh_seed",) + _spin("spn_mosh_seed"),
    ("mosh_size",) + _slider("sld_mosh_size"),
    ("grille",) + _spin("spn_grille"),
    ("jpeg",) + _slider("sld_jpeg"),
    ("post_blur",) + _slider("sld_postblur", 10.0),
    ("post_sharpen",) + _spin("spn_postsharp"),
    ("drift_pattern",) + _combo("cmb_drift"),
    ("drift_amount",) + _slider("sld_drift"),
    ("drift_speed",) + _slider("sld_drift_speed", 100.0),
    ("drift_position",) + _slider("sld_drift_position"),
    ("drift_seed",) + _spin("spn_drift_seed"),
    ("dissolve_amount",) + _slider("sld_dissolve_amount", 100.0),
    ("dissolve_seed",) + _spin("spn_dissolve_seed"),
    ("dissolve_wind_x",) + _slider("sld_dissolve_wind_x"),
    ("dissolve_wind_y",) + _slider("sld_dissolve_wind_y"),
    ("dissolve_mode",) + _combo("cmb_dissolve_mode"),
    ("dissolve_stagger",) + _combo("cmb_dissolve_stagger"),
    ("dissolve_ease",) + _combo("cmb_dissolve_ease"),
    ("dissolve_dotsize",) + _slider("sld_dissolve_dotsize", 1.0),
    ("dissolve_travel",) + _slider("sld_dissolve_travel", 100.0),
    ("dissolve_path",) + _combo("cmb_dissolve_path"),
    ("dissolve_match",) + _combo("cmb_dissolve_match"),
    ("dissolve_dot_shape",) + _combo("cmb_dissolve_dot_shape"),
    ("dissolve_tint",) + _slider("sld_dissolve_tint", 100.0),
    ("dissolve_trail",) + _slider("sld_dissolve_trail", 1.0),
    ("dissolve_shade", _shade_get, _shade_set),
    ("dissolve_speed",) + _slider("sld_dissolve_speed", 100.0),
    ("dissolve_hold",) + _slider("sld_dissolve_hold", 10.0),
    ("dissolve_length",) + _dspin("spn_duration"),
    ("dissolve_loop", _morph_loop_get, _morph_loop_set),
    ("paste_mode",) + _combo("cmb_paste"),
    ("paste_opacity",) + _slider("sld_paste_op"),
    ("paste_blend",) + _combo("cmb_paste_blend"),
    ("paste_seed",) + _spin("spn_paste_seed"),
    ("pal_seed",) + _spin("spn_pal_seed"),
    ("chaos_seed",) + _spin("spn_chaos_seed"),
)


def sync_docdims(win) -> None:
    try:
        from app.canvas import output_budget_note, output_megapixels
        from app.ui.widgets import set_warning

        w, h = doc_dims(win)
        label = win.cmb_ratio.currentText()
        note = output_budget_note(w, h)
        text = f"{w}×{h} · {label}"
        tip = f"{w}×{h} px · {label}"
        if note:
            text = f"{w}×{h} · {label} · ⚠ {output_megapixels(w, h):g} MP"
            tip = f"{w}×{h} px · {label}\n{note}"
        win.lbl_docdims.setText(text)
        win.lbl_docdims.setToolTip(tip)
        set_warning(win.lbl_docdims, bool(note))
        try:
            win.lbl_video_size.setText(f"{w}×{h}")
            win.lbl_video_size.setToolTip(f"{w}×{h} px (canvas)")
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------
# Preset build / apply
# ------------------------------------------------------------------
def sync_anim_ui(win) -> None:
    """Mode description + ED-march compat hint. No render, just labels."""
    from app.dither import ED_METHODS
    from app.gif import GIF_MODES, mode_desc, mode_label

    try:
        mode = win.cmb_video_mode.currentText()
        if mode not in GIF_MODES:
            mode = "both"
        method = win.cmb_method.currentText()
    except Exception:  # noqa: BLE001
        return
    try:
        win.lbl_mode_desc.setText(f"{mode_label(mode)} — {mode_desc(mode)}")
    except Exception:  # noqa: BLE001
        pass
    frozen = mode in ("phase", "both") and method in set(ED_METHODS) | {"hilbert"}
    try:
        win.lbl_compat.setText(
            f"March is frozen on {method} (error-diffusion ignores the matrix). "
            "Hue still cycles; wobble/shimmer still move."
            if frozen else "")
        win.btn_use_ordered.setVisible(bool(frozen))
    except Exception:  # noqa: BLE001
        pass
    if mode == "morph":
        try:
            chain = morph_images(win)
            if not chain:
                win.lbl_compat.setText("Morph needs images (MORPH page, Add...) — meanwhile showing dissolve.")
            elif len(chain) == 1:
                win.lbl_compat.setText("Morph A->B ready — play or scrub the video bar frame by frame.")
            else:
                win.lbl_compat.setText(f"Morph chain A + {len(chain)} ready — play or scrub frame by frame.")
            try:
                n = int(win.cmb_video_frames.currentText())
            except (TypeError, ValueError):
                n = 6
            try:
                fps = max(1, int(win.cmb_video_fps.currentText()))
            except (TypeError, ValueError):
                fps = 8
            segs = max(1, len(chain)) if chain else 1
            import math as _math

            try:
                loop_c = bool(win.chk_morph_loop.isChecked())
            except Exception:  # noqa: BLE001
                loop_c = True
            legs_c = segs + (1 if (loop_c and chain) else 0)
            floor = legs_c * max(8, int(_math.ceil(0.8 * fps)))
            if chain and n < floor:
                win.lbl_compat.setText(win.lbl_compat.text() + f" ({n // legs_c}f / {n / legs_c / fps:.1f}s per form — raise Hold or Frames for slower morphs)")
        except Exception:  # noqa: BLE001
            pass
    update_morph_short_hint(win)


def update_morph_short_hint(win) -> None:
    """MORPH-page warning when a leg is too short to show the transition.

    Uses the exact plan budget (transition frames per leg, same divmod
    the engine renders): 2 or fewer per leg means joints only, i.e. a
    hard cut with no pour and no mid-flight color; 3-4 is a flash.
    Points at Frames on purpose: holds add stills, they never buy
    transition frames.
    """
    try:
        label = win.lbl_morph_short
    except Exception:  # noqa: BLE001
        return
    try:
        from app.gif import leg_transitions

        extras = morph_chain_data(win)
        if not extras:
            label.setText("")
            return
        try:
            loop = bool(win.chk_morph_loop.isChecked())
        except Exception:  # noqa: BLE001
            loop = True
        legs = len(extras) + (1 if loop else 0)
        try:
            n_req = int(win._anim_combo_int(win.cmb_video_frames, 6, 2, 256))
        except Exception:  # noqa: BLE001
            n_req = 6
        try:
            fps = max(1, int(win._anim_combo_int(win.cmb_video_fps, 8, 2, 60)))
        except Exception:  # noqa: BLE001
            fps = 8
        per_leg = leg_transitions(n_req, legs)
        worst = min(per_leg)
        secs = worst / max(1, fps)
        if worst <= 2:
            label.setText(
                f"⚠ {worst}f per leg (~{secs:.1f}s): hard cut, no transition or color "
                f"(total transition {sum(per_leg)}f over {legs} legs) — raise Frames")
        elif worst <= 4:
            label.setText(
                f"⚠ {worst}f per leg (~{secs:.1f}s): transition too short, color barely "
                f"shows (total transition {sum(per_leg)}f) — raise Frames")
        else:
            label.setText("")
    except Exception:  # noqa: BLE001
        pass


def current_adjust(win):
    from app.adjust import Adjust

    return Adjust(
        brightness=win.sld_bri.value() / 100.0,
        contrast=win.sld_con.value() / 100.0,
        saturation=win.sld_sat.value() / 100.0,
        midtones=getattr(win, "sld_mid", win.sld_bri).value() / 100.0
        if hasattr(win, "sld_mid") else 1.0,
        highlights=float(getattr(win, "sld_high", None).value())
        if hasattr(win, "sld_high") else 0.0,
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
    """Preset from widgets. Single source (the UI is the editor)."""
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
    from app.fx_stack import normalize_stack

    return Preset(
        name=win.cmb_preset.currentText(),
        palette=base,
        focus_x=float(win.crop_fx),
        focus_y=float(win.crop_fy),
        crop_zoom=float(win.crop_zoom),
        custom_palette=[list(c) for c in win.custom_colors] or None,
        vector_export=bool(win._vector_export),
        vector_cell=int(win._vector_cell),
        vector_black=bool(getattr(win, "_vector_black", False)),
        gif_export=bool(win._gif_export),
        gif_size=int(gif_anim_size(win)),
        export_size=int(doc_size(win)),
        export_format=str(win._export_format),
        export_quality=int(win._export_quality),
        duotone_dark=win.duotone_dark,
        duotone_light=win.duotone_light,
        glitch_slice_max=24,
        fx_stack=normalize_stack(getattr(win, "fx_stack_data", None)),
        motif=read_motif(win),
        ascii=read_ascii(win),
        **kwargs,
    )


def apply_preset(win, name: str) -> None:
    from app.palette_library import palette_colors
    from app.presets import load_preset

    try:
        p = load_preset(name)
    except Exception:
        return
    # Auto -> concrete: old/hand-made presets without W/H inherit ratio+export_size.
    from app.canvas import doc_dimensions

    cw, ch = doc_dimensions(p.ratio, p.export_size,
                            int(getattr(p, "canvas_w", 0) or 0),
                            int(getattr(p, "canvas_h", 0) or 0))
    p.canvas_w, p.canvas_h = int(cw), int(ch)
    for field, _get, set in BINDINGS:
        set(win, getattr(p, field))
    # Crop vars (no direct widget).
    win.crop_fx = float(p.focus_x)
    win.crop_fy = float(p.focus_y)
    win.crop_zoom = float(p.crop_zoom)
    win._sync_crop_label()
    # The palette in use is the custom strip: from the preset, or the built-in base.
    # SOURCE has no swatches: keeps the current strip as editable.
    win._palette_base = p.palette
    if p.palette == "SOURCE":
        win._palette_dirty = False
    else:
        base_colors = palette_colors(p.palette)
        win._set_custom_colors(
            [tuple(c) for c in (p.custom_palette or [])] or base_colors,
            dirty=False,
        )
        win._palette_dirty = False
    win.refresh_palette_list()
    # FX stack (v1.2): None = legacy -> default; sync list + ADD.
    from app.ui import fx_stack_controller as _fx

    _fx.set_stack(win, getattr(p, "fx_stack", None))
    # Motif (v1.3): panel config; None = default.
    write_motif(win, getattr(p, "motif", None))
    write_ascii(win, getattr(p, "ascii", None))
    # Outputs: the preset is the recipe; dialogs apply it per operation.
    win._vector_export = bool(p.vector_export)
    win._vector_cell = int(p.vector_cell)
    win._vector_black = bool(getattr(p, "vector_black", False))
    win._gif_export = bool(p.gif_export)
    win._gif_frames = int(p.gif_frames)
    win._gif_mode = str(p.gif_mode)
    win._gif_fps = int(getattr(p, "gif_fps", 8))
    win._gif_size = int(getattr(p, "gif_size", 1200))
    win._gif_pingpong = bool(getattr(p, "gif_pingpong", False))
    win._export_size = int(p.export_size)
    win._export_format = str(p.export_format)
    win._export_quality = int(p.export_quality)
    # Single doc: CANVAS W/H (setters block signals: no flips).
    sync_docdims(win)
    # Grade + remaining labels.
    win.duotone_dark = str(p.duotone_dark or "")
    win.duotone_light = str(p.duotone_light or "")
    win._sync_duo_label()
    win.border_color = str(p.border_color or "#000000")
    win.lbl_border.setText(win.border_color)
    sync_anim_ui(win)
    win._sync_duration_ui()
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

    from app.presets import Preset, preset_from_metadata, save_preset

    path, _ = QFileDialog.getOpenFileName(win, "Import preset", "", "JSON (*.json)")
    if not path:
        return
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("params"), dict):
            p = preset_from_metadata(raw, Path(path).stem.replace("_metadata", ""))
        else:
            p = Preset.from_dict(raw)
        save_preset(p)
        win.refresh_presets()
        win._apply_preset(p.name)
        win._status(f"Preset imported: {p.name}")
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Invalid preset:\n{e}")


def import_metadata(win, path=None) -> bool:
    """Load an export _metadata.json: apply values + sibling image if present.

    Returns True when a preset was applied. Used by File > Import metadata
    and by drag&drop of *_metadata.json.
    """
    import json
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from app.presets import preset_from_metadata, save_preset

    if path is None:
        picked, _ = QFileDialog.getOpenFileName(
            win, "Import metadata", "", "Metadata JSON (*_metadata.json *.json)")
        if not picked:
            return False
        path = picked
    try:
        meta_path = Path(str(path))
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
        base = meta_path.stem
        if base.endswith("_metadata"):
            base = base[: -len("_metadata")]
        p = preset_from_metadata(raw, base)
        save_preset(p)
        win.refresh_presets()
        win._apply_preset(p.name)
        # Sibling still: <base>.png/.jpg/.webp next to the metadata.
        loaded_image = False
        try:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                cand = meta_path.parent / f"{base}{ext}"
                if cand.is_file():
                    win._load_path(cand)
                    loaded_image = True
                    break
        except Exception:  # noqa: BLE001
            pass
        win._status(f"Metadata imported: {p.name}"
                    + ("" if loaded_image else " (values only, image not found)"))
        return True
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Invalid metadata:\n{e}")
        return False


def morph_images(win) -> list:
    """Chain extras B.. as PIL images (playlist first, legacy single second)."""
    chain = morph_chain_data(win)
    imgs = [e["img"] for e in chain if e.get("img") is not None]
    if not imgs:
        single = getattr(win, "morph_src", None)
        if single is not None:
            imgs = [single]
    return imgs


def morph_chain_data(win) -> list:
    """Full chain entries [{img, name, fx, fy, zoom, repeat}] for cover-fit morph."""
    items = list(getattr(win, "morph_list", []) or [])
    out = []
    for entry in items:
        if not isinstance(entry, dict) or entry.get("img") is None:
            continue
        try:
            fx = max(0.0, min(100.0, float(entry.get("fx", 50.0))))
            fy = max(0.0, min(100.0, float(entry.get("fy", 50.0))))
            zm = max(1.0, min(4.0, float(entry.get("zoom", 1.0))))
            entry["fx"], entry["fy"], entry["zoom"] = fx, fy, zm
        except (TypeError, ValueError):
            entry["fx"], entry["fy"], entry["zoom"] = 50.0, 50.0, 1.0
        try:
            rp = max(1, min(8, int(entry.get("repeat", 1) or 1)))
        except (TypeError, ValueError):
            rp = 1
        entry["repeat"] = rp
        out.append({"img": entry["img"], "name": str(entry.get("name", "?")),
                    "fx": fx, "fy": fy, "zoom": zm, "repeat": rp})
    return out


def on_morph_selected(win) -> None:
    """Show which chain image the crop button will edit."""
    try:
        items = list(getattr(win, "morph_list", []) or [])
        row = int(win.morph_list_widget.currentRow())
    except Exception:  # noqa: BLE001
        return
    try:
        rep_spin = getattr(win, "spn_morph_repeat", None)
        if rep_spin is not None:
            entry = items[row] if 0 <= row < len(items) else None
            try:
                rv = max(1, min(8, int((entry or {}).get("repeat", 1) or 1)))
            except (TypeError, ValueError):
                rv = 1
            rep_spin.blockSignals(True)
            try:
                rep_spin.setValue(rv)
            finally:
                rep_spin.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass
    if not 0 <= row < len(items):
        try:
            win.lbl_morph_crop.setText("Crop: select a chain image")
        except Exception:  # noqa: BLE001
            pass
        return
    entry = items[row]
    if not isinstance(entry, dict):
        return
    try:
        fx = float(entry.get("fx", 50.0))
        fy = float(entry.get("fy", 50.0))
        zm = float(entry.get("zoom", 1.0))
        win.lbl_morph_crop.setText(
            f"Crop {row + 2}: {entry.get('name', '?')} "
            f"({fx:.0f}, {fy:.0f} · {zm:.1f}x) — Adjust crop...")
    except Exception:  # noqa: BLE001
        pass


def open_morph_crop(win) -> bool:
    """Visual crop of the selected chain image (frame locked to A).

    Same CropEditorDialog as IMAGE, with ratio/mode/W/H locked: only
    fx/fy/zoom (and optional rotation) come back into the entry.
    """
    from PySide6.QtWidgets import QMessageBox

    try:
        items = list(getattr(win, "morph_list", []) or [])
        row = int(win.morph_list_widget.currentRow())
    except Exception:  # noqa: BLE001
        return False
    if not 0 <= row < len(items) or not isinstance(items[row], dict):
        try:
            QMessageBox.information(win, "TRAKKART", "Select a chain image first.")
        except Exception:  # noqa: BLE001
            pass
        return False
    entry = items[row]
    try:
        from app.canvas import CUSTOM_RATIO
        from app.ui.crop_editor import CropEditorDialog

        if getattr(win, "src", None) is not None:
            from app.ui import params_controller as _par

            aw, ah = _par.doc_dims(win)
        else:
            aw, ah = 1200, 1200
        dlg = CropEditorDialog(
            entry["img"].copy(),
            ratio=CUSTOM_RATIO, mode="cover",
            fx=float(entry.get("fx", 50.0)), fy=float(entry.get("fy", 50.0)),
            zoom=float(entry.get("zoom", 1.0)),
            canvas_w=int(aw), canvas_h=int(ah),
            fixed_frame=True, parent=win,
            show_safe=bool(getattr(win, "_show_safe", True)),
        )
        ok = dlg.exec() == dlg.DialogCode.Accepted
        if ok:
            entry["fx"] = max(0.0, min(100.0, float(dlg.fx)))
            entry["fy"] = max(0.0, min(100.0, float(dlg.fy)))
            entry["zoom"] = max(1.0, min(4.0, float(dlg.zoom)))
            if int(getattr(dlg, "turns", 0) or 0):
                entry["img"] = dlg.image.copy()
            win.morph_list = items
            on_morph_selected(win)
            win._schedule_refresh()
            win._status(f"Crop set for {entry.get('name', '?')}: "
                        f"({entry['fx']:.0f}, {entry['fy']:.0f} · {entry['zoom']:.1f}x)")
        dlg.deleteLater()
        return bool(ok)
    except Exception as e:  # noqa: BLE001
        try:
            QMessageBox.warning(win, "TRAKKART", f"Could not crop:\n{e}")
        except Exception:  # noqa: BLE001
            pass
        return False


def _sync_morph_list_ui(win) -> None:
    """Refresh playlist widget + compat single-image aliases + hints."""
    from app.disintegrate import MAX_MORPH_IMAGES

    items = list(getattr(win, "morph_list", []) or [])
    try:
        lst = win.morph_list_widget
        lst.blockSignals(True)
        lst.clear()
        for i, entry in enumerate(items):
            name = str((entry or {}).get("name", f"img{i + 2}"))
            try:
                rep = max(1, min(8, int((entry or {}).get("repeat", 1) or 1)))
            except (TypeError, ValueError):
                rep = 1
            lst.addItem(f"{i + 2}: {name}" + (f" ×{rep}" if rep > 1 else ""))
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            win.morph_list_widget.blockSignals(False)
        except Exception:  # noqa: BLE001
            pass
    on_morph_selected(win)
    # Legacy single-image alias: first extra = B (old preview/export paths).
    try:
        if items:
            win.morph_src = items[0]["img"].copy()
            win.morph_path = str(items[0].get("name", ""))
        else:
            win.morph_src = None
            win.morph_path = ""
    except Exception:  # noqa: BLE001
        pass
    try:
        if items:
            win.lbl_morph.setText(f"Chain: A + {len(items)} ({MAX_MORPH_IMAGES - 1 - len(items)} slots free)")
        else:
            win.lbl_morph.setText("B: (none — morph falls back to dissolve)")
    except Exception:  # noqa: BLE001
        pass
    try:
        win._sync_anim_ui()
    except Exception:  # noqa: BLE001
        pass
    update_morph_short_hint(win)


def pick_morph_image(win) -> bool:
    """Append an image to the morph chain (B, C, ... up to 5 extras)."""
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog

    from app.disintegrate import MAX_MORPH_IMAGES
    from app.services.image_io import load_path as _load

    items = list(getattr(win, "morph_list", []) or [])
    if len(items) >= MAX_MORPH_IMAGES - 1:
        try:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(win, "TRAKKART",
                                    f"Chain is full ({MAX_MORPH_IMAGES} images max: A + {MAX_MORPH_IMAGES - 1}).")
        except Exception:  # noqa: BLE001
            pass
        return False
    path, _ = QFileDialog.getOpenFileName(
        win, f"Morph image ({chr(66 + len(items))})", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
    if not path:
        return False
    try:
        img = _load(Path(path))
    except Exception:  # noqa: BLE001
        try:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(win, "TRAKKART", f"Could not open:\n{path}")
        except Exception:  # noqa: BLE001
            pass
        return False
    items.append({"img": img.copy(), "name": str(Path(path).name),
                  "fx": 50.0, "fy": 50.0, "zoom": 1.0, "repeat": 1})
    win.morph_list = items
    _sync_morph_list_ui(win)
    try:
        win.morph_list_widget.setCurrentRow(len(items) - 1)
    except Exception:  # noqa: BLE001
        pass
    ensure_morph_budget(win)
    try:
        mode = str(win.cmb_video_mode.currentText())
    except Exception:  # noqa: BLE001
        mode = ""
    if mode == "morph" and not bool(getattr(win, "_video_on", False)):
        try:
            win.chk_video.setChecked(True)  # toggle re-renders video live
            win._status(f"Chain +1: {Path(path).name} — video preview on")
        except Exception:  # noqa: BLE001
            win._schedule_refresh()
    else:
        win._schedule_refresh()
    return True


def remove_morph_selected(win) -> None:
    """Remove the selected chain image."""
    items = list(getattr(win, "morph_list", []) or [])
    try:
        row = int(win.morph_list_widget.currentRow())
    except Exception:  # noqa: BLE001
        return
    if 0 <= row < len(items):
        items.pop(row)
        win.morph_list = items
        _sync_morph_list_ui(win)
        win._schedule_refresh()


def move_morph_selected(win, delta: int) -> None:
    """Reorder the selected chain image (-1 earlier, +1 later)."""
    items = list(getattr(win, "morph_list", []) or [])
    try:
        row = int(win.morph_list_widget.currentRow())
    except Exception:  # noqa: BLE001
        return
    nxt = row + int(delta)
    if 0 <= row < len(items) and 0 <= nxt < len(items):
        items[row], items[nxt] = items[nxt], items[row]
        win.morph_list = items
        _sync_morph_list_ui(win)
        try:
            win.morph_list_widget.setCurrentRow(nxt)
        except Exception:  # noqa: BLE001
            pass
        win._schedule_refresh()


def set_morph_repeat(win, value: int) -> None:
    """Store the per-leg repeat (1-8) on the selected chain entry."""
    items = list(getattr(win, "morph_list", []) or [])
    try:
        row = int(win.morph_list_widget.currentRow())
    except Exception:  # noqa: BLE001
        return
    if not 0 <= row < len(items) or not isinstance(items[row], dict):
        return
    try:
        items[row]["repeat"] = max(1, min(8, int(value)))
    except (TypeError, ValueError):
        items[row]["repeat"] = 1
    win.morph_list = items
    _sync_morph_list_ui(win)
    try:
        win.morph_list_widget.setCurrentRow(row)
    except Exception:  # noqa: BLE001
        pass
    win._schedule_refresh()


def clear_morph_image(win) -> None:
    """Forget the whole chain (morph falls back to dissolve)."""
    win.morph_list = []
    _sync_morph_list_ui(win)
    win._schedule_refresh()


def ensure_morph_budget(win) -> bool:
    """Grow total Frames so every chain segment keeps watchable time.

    Per-segment floor: 8 frames AND ~0.8s at current fps. Only grows
    (never shrinks below the floor), capped at 64. Returns True when
    Frames were bumped. Call on chain growth and on switch to morph mode.
    """
    try:
        from app.gif import GIF_MAX_FRAMES

        mode = str(win.cmb_video_mode.currentText())
    except Exception:  # noqa: BLE001
        return False
    if mode != "morph":
        return False
    chain = morph_chain_data(win)
    if not chain:
        return False
    try:
        segs = len(chain)
        try:
            loop = bool(win.chk_morph_loop.isChecked())
        except Exception:  # noqa: BLE001
            loop = True
        legs = segs + (1 if loop else 0)
        fps = max(1, int(win._anim_combo_int(win.cmb_video_fps, 8, 2, 60)))
        n = int(win._anim_combo_int(win.cmb_video_frames, 6, 2, 256))
    except Exception:  # noqa: BLE001
        return False
    import math

    floor = legs * max(8, int(math.ceil(0.8 * fps)))
    want = min(int(GIF_MAX_FRAMES), max(n, floor))
    if want <= n:
        return False
    try:
        win._set_anim_combo(win.cmb_video_frames, want)
        win._status(f"Chain x{segs}: frames {n}->{want} to keep transitions readable")
    except Exception:  # noqa: BLE001
        pass
    return True
