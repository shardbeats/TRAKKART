"""Document sections: image, preset, method, pixel, color, canvas.

Split out of app/ui/panels.py (mechanical move, no logic change).
"""

from __future__ import annotations

from contextlib import suppress

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from app.ui.panels.widgets import hlab, labeled_slider, roll_seed, seed_row, tight


def build_image_section(win, g: QVBoxLayout) -> None:
    from app.ops import flip_h, flip_v, invert, rotate_left, rotate_right

    win.btn_open = QPushButton("Open image...")
    win.btn_open.clicked.connect(win.open_image_dialog)
    g.addWidget(win.btn_open)
    ops_row = QHBoxLayout()
    for label, tip, fn in [
        ("Rot L", "Rotate left", lambda: win._op_image(rotate_left, "rotate left")),
        ("Rot R", "Rotate right", lambda: win._op_image(rotate_right, "rotate right")),
        ("Flip H", "Flip H", lambda: win._op_image(flip_h, "flip H")),
        ("Flip V", "Flip V", lambda: win._op_image(flip_v, "flip V")),
        ("Invert", "Invert colors", lambda: win._op_image(invert, "invert")),
    ]:
        b = QPushButton(label)
        b.setObjectName("opBtn")
        b.setToolTip(tip)
        b.clicked.connect(fn)
        ops_row.addWidget(b)
    g.addLayout(ops_row)
    ops2 = QHBoxLayout()
    win.btn_undo = QPushButton("Undo")
    win.btn_undo.setToolTip("Ctrl+Z")
    win.btn_undo.clicked.connect(win.undo_image)
    ops2.addWidget(win.btn_undo)
    win.btn_random = QPushButton("Surprise me")
    win.btn_random.setToolTip("Random (Ctrl+R): fresh chaos seed + new method/palette/threshold/pixel")
    win.btn_random.clicked.connect(win.surprise_me)
    ops2.addWidget(win.btn_random)
    g.addLayout(ops2)
    seed_row(g, win, "spn_chaos_seed", "btn_chaos_dice", "Chaos seed:", 0,
             "Seed for Surprise me + 🎲 Adjust (same seed = same result, replays)",
             "Fresh random chaos seed",
             lambda: roll_seed(win, "spn_chaos_seed", "Chaos"))


def build_preset_section(win, g: QVBoxLayout) -> None:
    row = QHBoxLayout()
    row.addWidget(QLabel("Preset:"))
    win.cmb_preset = QComboBox()
    win.cmb_preset.currentTextChanged.connect(win._on_preset_changed)
    row.addWidget(win.cmb_preset, 1)
    win.btn_preset_save = QPushButton("Save")
    win.btn_preset_save.setMinimumWidth(84)
    win.btn_preset_save.setToolTip("Save current method/palette/pixel/threshold as preset")
    win.btn_preset_save.clicked.connect(win.save_current_preset)
    row.addWidget(win.btn_preset_save)
    g.addLayout(row)


def build_method_section(win, g: QVBoxLayout, methods) -> None:
    hlab(g, "Method:")
    row = QHBoxLayout()
    win.btn_method_prev = QPushButton("◀")
    win.btn_method_prev.setFixedWidth(36)
    win.btn_method_prev.setToolTip("Previous method (Alt+Left)")
    win.btn_method_prev.clicked.connect(lambda: win.step_method(-1))
    row.addWidget(win.btn_method_prev)
    win.cmb_method = QComboBox()
    win.cmb_method.addItems(list(methods))
    tight(win.cmb_method)
    win.cmb_method.currentTextChanged.connect(lambda _: win._schedule_refresh())
    win.cmb_method.currentTextChanged.connect(lambda _: win._sync_anim_ui())
    win.cmb_method.currentTextChanged.connect(lambda _: win._sync_motif_visibility())
    row.addWidget(win.cmb_method, 1)
    win.btn_method_next = QPushButton("▶")
    win.btn_method_next.setFixedWidth(36)
    win.btn_method_next.setToolTip("Next method (Alt+Right)")
    win.btn_method_next.clicked.connect(lambda: win.step_method(1))
    row.addWidget(win.btn_method_next)
    g.addLayout(row)
    win.chk_serpentine = QCheckBox("Serpentine")
    win.chk_serpentine.setToolTip("Error-diffusion only: alternate scan direction per row (less directional streaks)")
    win.chk_serpentine.toggled.connect(lambda _: win._schedule_refresh())
    g.addWidget(win.chk_serpentine)
    prow = QHBoxLayout()
    prow.addWidget(QLabel("Rosette:"))
    win.cmb_rosette = QComboBox()
    win.cmb_rosette.addItems(["standard", "alt", "single"])
    tight(win.cmb_rosette)
    win.cmb_rosette.setToolTip("CMYK only: screen-offset assignment (standard rosette / swapped / aligned)")
    win.cmb_rosette.currentTextChanged.connect(lambda _: win._schedule_refresh())
    prow.addWidget(win.cmb_rosette, 1)
    prow.addWidget(QLabel("LPI:"))
    win.spn_lpi = QSpinBox()
    win.spn_lpi.setRange(0, 200)
    win.spn_lpi.setValue(0)
    win.spn_lpi.setSpecialValueText("off")
    win.spn_lpi.setToolTip("CMYK only: print ruling in lines/inch at the export DPI (0 = off, legacy 8px cell)")
    win.spn_lpi.valueChanged.connect(lambda _: win._schedule_refresh())
    prow.addWidget(win.spn_lpi)
    g.addLayout(prow)

    def _sync_serp(_=None):
        from app.ui import params_controller as _par

        _par.sync_method_widgets(win)
    win.cmb_method.currentTextChanged.connect(_sync_serp)
    _sync_serp()
    try:
        from PySide6.QtGui import QKeySequence, QShortcut

        from app import shortcuts as _keys

        win._sc_method_prev = QShortcut(QKeySequence(_keys.effective_for(win, "edit_method_prev")), win)
        win._sc_method_prev.activated.connect(lambda: win.step_method(-1))
        win._sc_method_next = QShortcut(QKeySequence(_keys.effective_for(win, "edit_method_next")), win)
        win._sc_method_next.activated.connect(lambda: win.step_method(1))
        registry = getattr(win, "_shortcut_actions", None)
        if registry is None:
            registry = win._shortcut_actions = {}
        registry.setdefault("edit_method_prev", []).append(win._sc_method_prev)
        registry.setdefault("edit_method_next", []).append(win._sc_method_next)
    except Exception:  # noqa: BLE001
        pass


def build_pixel_section(win, g: QVBoxLayout) -> None:
    hlab(g, "Pixel & threshold:")
    row = QHBoxLayout()
    row.addWidget(QLabel("Pixel size:"))
    win.spn_pixel = QSpinBox()
    win.spn_pixel.setRange(1, 8)
    win.spn_pixel.setValue(2)
    win.spn_pixel.setFixedWidth(56)
    win.spn_pixel.setToolTip("Dither cell in pixels (1 = finest)")
    win.spn_pixel.valueChanged.connect(lambda _: win._schedule_refresh())
    row.addWidget(win.spn_pixel)
    row.addStretch()
    g.addLayout(row)
    win.sld_thr, _ = labeled_slider(win, g, "Threshold:", 1, 254, 128)


def build_color_section(win, g: QVBoxLayout) -> None:
    hlab(g, "Adjust:")
    win.sld_bri, _ = labeled_slider(win, g, "Brightness:", 50, 200, 100, div=100.0, unit="×")
    win.sld_con, _ = labeled_slider(win, g, "Contrast:", 50, 200, 100, div=100.0, unit="×")
    win.sld_sat, _ = labeled_slider(win, g, "Saturation:", 0, 200, 100, div=100.0, unit="×")
    win.sld_mid, _ = labeled_slider(win, g, "Midtones:", 0, 200, 100, "Mids gamma 0.0-2.0", div=100.0, unit="×")
    win.sld_high, _ = labeled_slider(win, g, "Highlights:", -100, 100, 0, "Lift/cut brights")
    for sld in (win.sld_bri, win.sld_con, win.sld_sat, win.sld_mid, win.sld_high):
        try:
            sld.setProperty("fast", True)  # core adjusts: 120ms fast path in Live
        except Exception:  # noqa: BLE001
            pass
    lock_row = QHBoxLayout()
    lock_row.addWidget(QLabel("Lock:"))
    win._adjust_locks = getattr(win, "_adjust_locks", {})
    for key, label in (("brightness", "B"), ("contrast", "C"), ("saturation", "S"),
                       ("midtones", "M"), ("highlights", "H")):
        btn = QPushButton("🔓")
        btn.setFixedWidth(36)
        btn.setCheckable(True)
        locked = bool(win._adjust_locks.get(key, False))
        btn.setChecked(locked)
        if locked:
            btn.setText("🔒")
        btn.setToolTip(f"Lock {label} ({key}) against randomize")
        btn.toggled.connect(lambda on, _k=key, _b=btn: _on_adjust_lock(win, _k, on, _b))
        setattr(win, f"btn_lock_{key}", btn)
        lock_row.addWidget(btn)
    win.btn_adjust_dice = QPushButton("🎲 Adjust")
    win.btn_adjust_dice.setToolTip("Randomize unlocked brightness/contrast/saturation/mids/highlights")
    win.btn_adjust_dice.clicked.connect(lambda: _on_adjust_dice(win))
    lock_row.addWidget(win.btn_adjust_dice, 1)
    g.addLayout(lock_row)


def _on_adjust_lock(win, key: str, on: bool, btn) -> None:
    win._adjust_locks[key] = bool(on)
    btn.setText("🔒" if on else "🔓")
    win._status(f"{key} {'locked' if on else 'unlocked'}")


def _on_adjust_dice(win) -> None:
    from app.ui import color_actions as _ca

    roll_seed(win, "spn_chaos_seed", "Chaos")  # fresh seed so every click iterates
    _ca.randomize_adjusts(win)


def _apply_sp404_canvas(win) -> None:
    """One click to the SP-404MKII OLED canvas (Custom 128x64).

    Document-only: setting the spins fires the normal W/H path (flips
    Ratio to Custom + refresh). The OLED preview is an independent
    view toggle (btn_sp404_preview / View menu) and is NOT changed here.
    A linked W×H would fight the pair (128 then 64), so SP-404 unlinks
    first — it is inherently non-square.
    """
    from app.sp404 import SP_H, SP_W

    for spn in (win.spn_canvas_w, win.spn_canvas_h):
        with suppress(Exception):
            spn.blockSignals(True)
    with suppress(Exception):
        win.spn_canvas_w.setValue(int(SP_W))
    with suppress(Exception):
        win.spn_canvas_h.setValue(int(SP_H))
    for spn in (win.spn_canvas_w, win.spn_canvas_h):
        with suppress(Exception):
            spn.blockSignals(False)
    with suppress(Exception):
        win.btn_canvas_link.setChecked(False)
    with suppress(Exception):
        win._on_canvas_wh_changed()


def _on_sp404_preview_toggled(win, on: bool) -> None:
    """IMAGE-panel toggle -> same flag as View > SP-404 OLED preview."""
    with suppress(Exception):
        if win.act_sp404.isChecked() != bool(on):
            win.act_sp404.setChecked(bool(on))
    try:
        win.toggle_sp404_preview()
    except Exception:  # noqa: BLE001
        win._sp404_preview = bool(on)


def build_canvas_section(win, g: QVBoxLayout, ratios, crop_modes) -> None:
    """Canvas editor-style: ratio fills W/H; editing W/H jumps to Custom."""
    from app.canvas import MAX_DIM, MIN_DIM, MODE_TIPS, canvas_ratios
    from app.ui.icons import chain_icon

    hlab(g, "Ratio & crop:")
    row = QHBoxLayout()
    row.addWidget(QLabel("Ratio:"))
    win.cmb_ratio = QComboBox()
    tight(win.cmb_ratio, 5)
    win.cmb_ratio.addItems(canvas_ratios())
    win.cmb_ratio.setToolTip("Preset aspect, or Custom for free W×H")
    # activated = user gesture only: applies the preset without fighting sync.
    win.cmb_ratio.activated.connect(lambda _: win._on_ratio_preset())
    win.cmb_ratio.currentTextChanged.connect(lambda _: win._schedule_refresh())
    win.cmb_ratio.currentTextChanged.connect(lambda _: win._sync_docdims())
    row.addWidget(win.cmb_ratio, 1)
    row.addWidget(QLabel("Crop:"))
    win.cmb_crop = QComboBox()
    tight(win.cmb_crop, 7)
    win.cmb_crop.addItems(list(crop_modes))
    win.cmb_crop.setToolTip("; ".join(f"{m}: {MODE_TIPS.get(m, '')}" for m in crop_modes))
    win.cmb_crop.currentTextChanged.connect(lambda _: win._schedule_refresh())
    win.cmb_crop.currentTextChanged.connect(lambda _: win._sync_docdims())
    row.addWidget(win.cmb_crop, 1)
    g.addLayout(row)
    hlab(g, "Canvas size (W × H):")
    doc_row = QHBoxLayout()
    win.spn_canvas_w = QSpinBox()
    win.spn_canvas_w.setRange(MIN_DIM, MAX_DIM)
    win.spn_canvas_w.setValue(3000)
    win.spn_canvas_w.setSuffix(" px")
    win.spn_canvas_w.setMinimumWidth(85)
    win.spn_canvas_w.setToolTip("Canvas width: typing it flips Ratio to Custom (free)")
    win.spn_canvas_w.valueChanged.connect(lambda _: win._on_canvas_wh_changed("w"))
    doc_row.addWidget(win.spn_canvas_w, 1)
    doc_row.addWidget(QLabel("×"))
    win.spn_canvas_h = QSpinBox()
    win.spn_canvas_h.setRange(MIN_DIM, MAX_DIM)
    win.spn_canvas_h.setValue(3000)
    win.spn_canvas_h.setSuffix(" px")
    win.spn_canvas_h.setMinimumWidth(85)
    win.spn_canvas_h.setToolTip("Canvas height: typing it flips Ratio to Custom (free)")
    win.spn_canvas_h.valueChanged.connect(lambda _: win._on_canvas_wh_changed("h"))
    doc_row.addWidget(win.spn_canvas_h, 1)
    win.btn_canvas_link = QPushButton()
    win.btn_canvas_link.setIcon(chain_icon())
    win.btn_canvas_link.setCheckable(True)
    win.btn_canvas_link.setChecked(False)
    win.btn_canvas_link.setFixedWidth(34)
    win.btn_canvas_link.setToolTip("Link W×H (Photoshop-style): editing one scales the other, keeps the aspect — square in, square out (3000 → 3000×3000)")
    win.btn_canvas_link.toggled.connect(win._on_canvas_link)
    doc_row.addWidget(win.btn_canvas_link)
    win.lbl_docdims = QLabel()
    win.lbl_docdims.setMinimumWidth(110)
    win.lbl_docdims.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    doc_row.addWidget(win.lbl_docdims)
    g.addLayout(doc_row)
    sp_row = QHBoxLayout()
    win.btn_sp404_canvas = QPushButton("SP-404 128×64")
    win.btn_sp404_canvas.setToolTip("Custom canvas at the Roland SP-404MKII OLED size (128×64): document only, preview unchanged")
    win.btn_sp404_canvas.clicked.connect(lambda: _apply_sp404_canvas(win))
    sp_row.addWidget(win.btn_sp404_canvas, 1)
    win.btn_sp404_preview = QPushButton("OLED preview: OFF")
    win.btn_sp404_preview.setCheckable(True)
    win.btn_sp404_preview.setChecked(False)
    win.btn_sp404_preview.setToolTip("Display-only 128x64 1-bit preview for the Roland SP-404MKII (same as View menu, stills only)")
    win.btn_sp404_preview.toggled.connect(lambda on: _on_sp404_preview_toggled(win, on))
    sp_row.addWidget(win.btn_sp404_preview, 1)
    g.addLayout(sp_row)
    hlab(g, "Crop (visual editor):")
    crop_row = QHBoxLayout()
    win.btn_crop = QPushButton("Adjust crop...")
    win.btn_crop.setToolTip("Visual crop: drag to move, wheel to zoom")
    win.btn_crop.clicked.connect(win.open_crop_editor)
    crop_row.addWidget(win.btn_crop, 1)
    win.lbl_crop = QLabel()
    win.lbl_crop.setMinimumWidth(110)
    win.lbl_crop.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    crop_row.addWidget(win.lbl_crop)
    g.addLayout(crop_row)
