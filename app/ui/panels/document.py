"""Document sections: image, preset, method, pixel, color, canvas.

Split out of app/ui/panels.py (mechanical move, no logic change).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from app.ui.panels.widgets import hlab, tight, labeled_slider


def build_image_section(win, g: QVBoxLayout) -> None:
    from app.ops import flip_h, flip_v, invert, rotate_left, rotate_right

    win.btn_open = QPushButton("Open image...")
    win.btn_open.clicked.connect(win.open_image_dialog)
    g.addWidget(win.btn_open)
    ops_row = QHBoxLayout()
    for label, tip, fn in [
        ("⟲", "Rotate left", lambda: win._op_image(rotate_left, "rotate left")),
        ("⟳", "Rotate right", lambda: win._op_image(rotate_right, "rotate right")),
        ("⇋", "Flip H", lambda: win._op_image(flip_h, "flip H")),
        ("⇅", "Flip V", lambda: win._op_image(flip_v, "flip V")),
        ("◐", "Invert", lambda: win._op_image(invert, "invert")),
    ]:
        b = QPushButton(label)
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
    win.btn_random.setToolTip("Random (Ctrl+R)")
    win.btn_random.clicked.connect(win.randomize)
    ops2.addWidget(win.btn_random)
    g.addLayout(ops2)


def build_preset_section(win, g: QVBoxLayout) -> None:
    row = QHBoxLayout()
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
    g.addWidget(QLabel("Method:"))
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
    g.addWidget(QLabel("Pixel size:"))
    win.spn_pixel = QSpinBox()
    win.spn_pixel.setRange(1, 8)
    win.spn_pixel.setValue(2)
    win.spn_pixel.setFixedWidth(56)
    win.spn_pixel.valueChanged.connect(lambda _: win._schedule_refresh())
    g.addWidget(win.spn_pixel)
    win.sld_thr, _ = labeled_slider(win, g, "Threshold:", 1, 254, 128)


def build_color_section(win, g: QVBoxLayout) -> None:
    win.sld_bri, _ = labeled_slider(win, g, "Brightness:", 50, 200, 100, div=100.0)
    win.sld_con, _ = labeled_slider(win, g, "Contrast:", 50, 200, 100, div=100.0)
    win.sld_sat, _ = labeled_slider(win, g, "Saturation:", 0, 200, 100, div=100.0)
    win.sld_mid, _ = labeled_slider(win, g, "Midtones:", 0, 200, 100, "Mids gamma 0.0-2.0", div=100.0)
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

    _ca.randomize_adjusts(win)


def _apply_sp404_canvas(win) -> None:
    """One click to the SP-404MKII OLED canvas (Custom 128x64).

    Document-only: setting the spins fires the normal W/H path (flips
    Ratio to Custom + refresh). The OLED preview is an independent
    view toggle (btn_sp404_preview / View menu) and is NOT changed here.
    """
    from app.sp404 import SP_H, SP_W

    try:
        win.spn_canvas_w.setValue(int(SP_W))
        win.spn_canvas_h.setValue(int(SP_H))
    except Exception:  # noqa: BLE001
        pass


def _on_sp404_preview_toggled(win, on: bool) -> None:
    """IMAGE-panel toggle -> same flag as View > SP-404 OLED preview."""
    try:
        if win.act_sp404.isChecked() != bool(on):
            win.act_sp404.setChecked(bool(on))
    except Exception:  # noqa: BLE001
        pass
    try:
        win.toggle_sp404_preview()
    except Exception:  # noqa: BLE001
        win._sp404_preview = bool(on)


def build_canvas_section(win, g: QVBoxLayout, ratios, crop_modes) -> None:
    """Canvas editor-style: ratio fills W/H; editing W/H jumps to Custom."""
    from app.canvas import MAX_DIM, MIN_DIM, MODE_TIPS, canvas_ratios

    g.addWidget(QLabel("Ratio / Mode:"))
    row = QHBoxLayout()
    win.cmb_ratio = QComboBox()
    tight(win.cmb_ratio, 10)
    win.cmb_ratio.addItems(canvas_ratios())
    win.cmb_ratio.setToolTip("Preset aspect, or Custom for free W×H")
    # activated = user gesture only: applies the preset without fighting sync.
    win.cmb_ratio.activated.connect(lambda _: win._on_ratio_preset())
    win.cmb_ratio.currentTextChanged.connect(lambda _: win._schedule_refresh())
    win.cmb_ratio.currentTextChanged.connect(lambda _: win._sync_docdims())
    row.addWidget(win.cmb_ratio, 1)
    win.cmb_crop = QComboBox()
    tight(win.cmb_crop, 10)
    win.cmb_crop.addItems(list(crop_modes))
    win.cmb_crop.setToolTip("; ".join(f"{m}: {MODE_TIPS.get(m, '')}" for m in crop_modes))
    win.cmb_crop.currentTextChanged.connect(lambda _: win._schedule_refresh())
    win.cmb_crop.currentTextChanged.connect(lambda _: win._sync_docdims())
    row.addWidget(win.cmb_crop, 1)
    g.addLayout(row)
    hlab(g, "Canvas Size (W × H):")
    doc_row = QHBoxLayout()
    win.spn_canvas_w = QSpinBox()
    win.spn_canvas_w.setRange(MIN_DIM, MAX_DIM)
    win.spn_canvas_w.setValue(3000)
    win.spn_canvas_w.setSuffix(" px")
    win.spn_canvas_w.setMinimumWidth(85)
    win.spn_canvas_w.setToolTip("Canvas width: typing it flips Ratio to Custom (free)")
    win.spn_canvas_w.valueChanged.connect(lambda _: win._on_canvas_wh_changed())
    doc_row.addWidget(win.spn_canvas_w, 1)
    doc_row.addWidget(QLabel("×"))
    win.spn_canvas_h = QSpinBox()
    win.spn_canvas_h.setRange(MIN_DIM, MAX_DIM)
    win.spn_canvas_h.setValue(3000)
    win.spn_canvas_h.setSuffix(" px")
    win.spn_canvas_h.setMinimumWidth(85)
    win.spn_canvas_h.setToolTip("Canvas height: typing it flips Ratio to Custom (free)")
    win.spn_canvas_h.valueChanged.connect(lambda _: win._on_canvas_wh_changed())
    doc_row.addWidget(win.spn_canvas_h, 1)
    win.lbl_docdims = QLabel()
    win.lbl_docdims.setMinimumWidth(110)
    from PySide6.QtCore import Qt as _Qt2

    win.lbl_docdims.setAlignment(_Qt2.AlignRight | _Qt2.AlignVCenter)
    doc_row.addWidget(win.lbl_docdims)
    g.addLayout(doc_row)
    win.btn_sp404_canvas = QPushButton("SP-404 128×64")
    win.btn_sp404_canvas.setToolTip("Custom canvas at the Roland SP-404MKII OLED size (128×64): document only, preview unchanged")
    win.btn_sp404_canvas.clicked.connect(lambda: _apply_sp404_canvas(win))
    g.addWidget(win.btn_sp404_canvas)
    win.btn_sp404_preview = QPushButton("SP-404 OLED Preview: OFF")
    win.btn_sp404_preview.setCheckable(True)
    win.btn_sp404_preview.setChecked(False)
    win.btn_sp404_preview.setToolTip("Display-only 128x64 1-bit preview for the Roland SP-404MKII (same as View menu, stills only)")
    win.btn_sp404_preview.toggled.connect(lambda on: _on_sp404_preview_toggled(win, on))
    g.addWidget(win.btn_sp404_preview)
    hlab(g, "Crop (visual editor):")
    crop_row = QHBoxLayout()
    win.btn_crop = QPushButton("Adjust crop...")
    win.btn_crop.setToolTip("Visual crop: drag to move, wheel to zoom")
    win.btn_crop.clicked.connect(win.open_crop_editor)
    crop_row.addWidget(win.btn_crop, 1)
    from PySide6.QtCore import Qt as _Qt

    win.lbl_crop = QLabel()
    win.lbl_crop.setMinimumWidth(110)
    win.lbl_crop.setAlignment(_Qt.AlignRight | _Qt.AlignVCenter)
    crop_row.addWidget(win.lbl_crop)
    g.addLayout(crop_row)
