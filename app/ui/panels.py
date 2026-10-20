"""UI panel builders — extraído del _setup_ui monolítico (~350 líneas).

Cada función construye una sección QGroupBox y devuelve los widgets
que MainWindow necesita conservar como atributos. MainWindow orquesta,
no construye widgets a mano.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def make_group(host: QVBoxLayout, title: str) -> QVBoxLayout:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    lay.setSpacing(4)
    host.addWidget(box)
    return lay


def hlab(parent, text: str) -> QLabel:
    """Section header that wraps instead of forcing panel width."""
    lab = QLabel(text)
    lab.setWordWrap(True)
    parent.addWidget(lab)
    return lab


def tight(cmb, chars: int = 12):
    """Cap combo min-width so long items don't blow the panel (tooltips stay full)."""
    try:
        cmb.setSizeAdjustPolicy(cmb.AdjustToMinimumContentsLengthWithIcon)
        cmb.setMinimumContentsLength(max(4, int(chars)))
    except Exception:  # noqa: BLE001
        pass
    return cmb


def labeled_slider(win, parent, label, lo, hi, val, tooltip="", div=None):
    """Fila [label | slider | valor]. Doble-click resetea (ValueSlider)."""
    row = QHBoxLayout()
    lab = QLabel(label)
    lab.setMinimumWidth(120)
    row.addWidget(lab)
    sld, val_lbl = mini_slider(win, lo, hi, val, tooltip, div)
    row.addWidget(sld, 1)
    row.addWidget(val_lbl)
    parent.addLayout(row)
    return sld, val_lbl


def mini_slider(win, lo, hi, val, tooltip="", div=None):
    from app.ui.widgets import ValueSlider

    sld = ValueSlider(Qt.Horizontal)
    sld.setRange(lo, hi)
    sld.setValue(val)
    sld.setDefault(val)
    if tooltip:
        sld.setToolTip(tooltip)
    val_lbl = QLabel()
    val_lbl.setObjectName("valueLabel")
    val_lbl.setMinimumWidth(40)
    val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def _show(v, _lbl=val_lbl, _div=div):
        _lbl.setText(f"{(v / _div if _div else v):g}")

    sld.valueChanged.connect(_show)
    sld.valueChanged.connect(lambda _: win._schedule_refresh())
    _show(val)
    return sld, val_lbl


def spin_row(parent, label: str, lo: int, hi: int, val: int, tooltip: str = "") -> QSpinBox:
    spn = QSpinBox()
    spn.setRange(lo, hi)
    spn.setValue(val)
    if tooltip:
        spn.setToolTip(tooltip)
    spn.setFixedWidth(56)
    row = QHBoxLayout()
    row.addWidget(QLabel(label))
    row.addWidget(spn, 1)
    parent.addLayout(row)
    return spn


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
    row.addWidget(win.cmb_method, 1)
    win.btn_method_next = QPushButton("▶")
    win.btn_method_next.setFixedWidth(36)
    win.btn_method_next.setToolTip("Next method (Alt+Right)")
    win.btn_method_next.clicked.connect(lambda: win.step_method(1))
    row.addWidget(win.btn_method_next)
    g.addLayout(row)
    try:
        from PySide6.QtGui import QShortcut, QKeySequence

        win._sc_method_prev = QShortcut(QKeySequence("Alt+Left"), win)
        win._sc_method_prev.activated.connect(lambda: win.step_method(-1))
        win._sc_method_next = QShortcut(QKeySequence("Alt+Right"), win)
        win._sc_method_next.activated.connect(lambda: win.step_method(1))
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


def build_canvas_section(win, g: QVBoxLayout, ratios, crop_modes) -> None:
    """Canvas Photoshop-style: el ratio rellena W/H; editar W/H salta a Custom."""
    from app.canvas import MAX_DIM, MIN_DIM, MODE_TIPS, canvas_ratios

    g.addWidget(QLabel("Ratio / Mode:"))
    row = QHBoxLayout()
    win.cmb_ratio = QComboBox()
    tight(win.cmb_ratio, 10)
    win.cmb_ratio.addItems(canvas_ratios())
    win.cmb_ratio.setToolTip("Preset aspect, or Custom for free W×H")
    # activated = solo gesto del usuario: aplica el preset sin pelear con sync.
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


def build_pre_section(win, g: QVBoxLayout) -> None:
    win.sld_blur, _ = labeled_slider(win, g, "Blur:", 0, 50, 0, "Blur 0.0-5.0 (heavy: slower preview)", div=10.0)
    win.spn_sharp = spin_row(g, "Sharpen:", 0, 3, 0, "Sharpen 0-3")
    win.spn_sharp.valueChanged.connect(lambda _: win._schedule_refresh())
    win.sld_hue, _ = labeled_slider(win, g, "Hue:", -180, 180, 0, "Hue -180..180")
    win.spn_denoise = spin_row(g, "Denoise:", 0, 5, 0, "Denoise 0-5 (heavy: slower preview)")
    win.spn_denoise.valueChanged.connect(lambda _: win._schedule_refresh())
    win.sld_smooth, _ = labeled_slider(win, g, "Smooth:", 0, 50, 0, "Smooth 0.0-5.0", div=10.0)
    for sp in (win.spn_sharp, win.spn_denoise):
        sp.valueChanged.connect(lambda _: win._schedule_refresh())


def build_motif_section(win, g: QVBoxLayout) -> None:
    """Motif: 4 luminance bands -> shape + size.

    Kept simple on purpose. The `motif` method reads this config;
    every other method ignores it.
    """
    from app.motif import BAND_NAMES, SHAPES

    hlab(g, "Bands → shape/size (method `motif`):")
    for i, band in enumerate(BAND_NAMES):
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{band}:"))
        cmb = QComboBox()
        tight(cmb, 8)
        cmb.addItems(list(SHAPES))
        cmb.setCurrentText(["dot", "line", "cross", "square"][i])
        cmb.setToolTip(f"Shape for {band} band")
        cmb.currentTextChanged.connect(lambda _: win._schedule_refresh())
        row.addWidget(cmb, 1)
        setattr(win, f"cmb_motif_{i}", cmb)
        spn = QSpinBox()
        spn.setRange(1, 4)
        spn.setValue(2)
        spn.setFixedWidth(56)
        spn.setToolTip(f"Size 1-4 for {band}")
        spn.valueChanged.connect(lambda _: win._schedule_refresh())
        row.addWidget(spn)
        setattr(win, f"spn_motif_{i}", spn)
        g.addLayout(row)


def build_fx_stack_section(win, g: QVBoxLayout) -> None:
    """FX STACK reordenable (v1.2): orden + on/off. Los params viven en los
    sliders existentes (una sola fuente); aquí solo se ordena y conmuta."""
    from PySide6.QtWidgets import QListWidget

    hlab(g, "FX stack (order matters):")
    win.fx_list = QListWidget()
    win.fx_list.setMinimumHeight(150)
    win.fx_list.setMaximumHeight(220)
    win.fx_list.setToolTip("Uncheck to bypass · select + ▲/▼ to reorder · params in sliders below")
    win.fx_list.itemChanged.connect(lambda _item: win._on_fx_toggled())
    win.fx_list.itemSelectionChanged.connect(lambda: None)
    g.addWidget(win.fx_list)
    row = QHBoxLayout()
    win.btn_fx_up = QPushButton("▲")
    win.btn_fx_up.setFixedWidth(40)
    win.btn_fx_up.setToolTip("Move selected FX up")
    win.btn_fx_up.clicked.connect(win._on_fx_move_up)
    row.addWidget(win.btn_fx_up)
    win.btn_fx_down = QPushButton("▼")
    win.btn_fx_down.setFixedWidth(40)
    win.btn_fx_down.setToolTip("Move selected FX down")
    win.btn_fx_down.clicked.connect(win._on_fx_move_down)
    row.addWidget(win.btn_fx_down)
    row.addWidget(QLabel("Add:"))
    win.cmb_fx_add = QComboBox()
    tight(win.cmb_fx_add, 14)
    win.cmb_fx_add.setToolTip("Re-enable a bypassed FX")
    win.cmb_fx_add.currentTextChanged.connect(win._on_fx_add)
    row.addWidget(win.cmb_fx_add, 1)
    g.addLayout(row)
    win.sld_jpeg, _ = labeled_slider(win, g, "JPEG:", 0, 100, 0, "JPEG glitch 0=off")
    win.sld_postblur, _ = labeled_slider(win, g, "Post blur:", 0, 50, 0, "Post-dither blur 0.0-5.0", div=10.0)
    win.spn_postsharp = spin_row(g, "Post sharp:", 0, 3, 0, "Post-dither sharpen 0-3")
    win.spn_postsharp.valueChanged.connect(lambda _: win._schedule_refresh())
    hlab(g, "Paste-Up:")
    paste_row = QHBoxLayout()
    win.cmb_paste = QComboBox()
    win.cmb_paste.addItems(["off", "paper", "riso", "fiber"])
    tight(win.cmb_paste, 8)
    win.cmb_paste.setToolTip("Procedural paper overlay (post-dither stack FX)")
    win.cmb_paste.currentTextChanged.connect(lambda _: win._schedule_refresh())
    paste_row.addWidget(win.cmb_paste, 1)
    win.cmb_paste_blend = QComboBox()
    win.cmb_paste_blend.addItems(["overlay", "multiply", "screen"])
    tight(win.cmb_paste_blend, 10)
    win.cmb_paste_blend.setToolTip("Paste-Up blend mode")
    win.cmb_paste_blend.currentTextChanged.connect(lambda _: win._schedule_refresh())
    paste_row.addWidget(win.cmb_paste_blend, 1)
    g.addLayout(paste_row)
    win.sld_paste_op, _ = labeled_slider(win, g, "Paste:", 0, 100, 0, "Paste-Up opacity 0=off")
    win.fx_stack_data: list = []


def build_timeline_section(win, g: QVBoxLayout) -> None:
    """TIMELINE (v1.4): clip import + animation layers + Signal Drift."""
    from PySide6.QtWidgets import QListWidget

    hlab(g, "Clip (optional video source):")
    clip_row = QHBoxLayout()
    win.btn_clip_open = QPushButton("Open clip...")
    win.btn_clip_open.setToolTip("Import MP4/GIF/WebP clip (opt-in video extra)")
    win.btn_clip_open.clicked.connect(win.open_clip)
    clip_row.addWidget(win.btn_clip_open)
    win.btn_clip_browse = QPushButton("Browse...")
    win.btn_clip_browse.setToolTip("Pick the poster frame / clear the clip")
    win.btn_clip_browse.clicked.connect(win.browse_clip)
    clip_row.addWidget(win.btn_clip_browse)
    clip_row.addStretch()
    g.addLayout(clip_row)
    win.lbl_clip = QLabel("still image")
    win.lbl_clip.setObjectName("subtitleLabel")
    g.addWidget(win.lbl_clip)
    hlab(g, "Layers (prop frm→to ease [start-end]):")
    win.anim_list = QListWidget()
    win.anim_list.setMinimumHeight(90)
    win.anim_list.setMaximumHeight(150)
    win.anim_list.setToolTip("Later layers win. Animated controls lock in their panels.")
    win.anim_list.itemSelectionChanged.connect(win._on_anim_selected)
    g.addWidget(win.anim_list)
    lr = QHBoxLayout()
    win.btn_anim_add = QPushButton("+ layer")
    win.btn_anim_add.clicked.connect(win._on_anim_add)
    lr.addWidget(win.btn_anim_add)
    win.btn_anim_remove = QPushButton("− layer")
    win.btn_anim_remove.clicked.connect(win._on_anim_remove)
    lr.addWidget(win.btn_anim_remove)
    g.addLayout(lr)
    erow = QHBoxLayout()
    win.cmb_anim_prop = QComboBox()
    tight(win.cmb_anim_prop, 14)
    win.cmb_anim_prop.addItems(["threshold", "pixel_size", "pre_hue", "grain",
                                "glow_intensity", "glitch_chroma", "wave", "jpeg",
                                "fade", "split_tone"])
    win.cmb_anim_prop.setToolTip("Animated property")
    win.cmb_anim_prop.currentTextChanged.connect(lambda _: win._on_anim_edited())
    erow.addWidget(win.cmb_anim_prop, 1)
    win.cmb_anim_ease = QComboBox()
    win.cmb_anim_ease.addItems(["linear", "in", "out"])
    tight(win.cmb_anim_ease, 8)
    win.cmb_anim_ease.setToolTip("Easing from→to")
    win.cmb_anim_ease.currentTextChanged.connect(lambda _: win._on_anim_edited())
    erow.addWidget(win.cmb_anim_ease, 1)
    g.addLayout(erow)
    frow = QHBoxLayout()
    from PySide6.QtWidgets import QDoubleSpinBox
    frow.addWidget(QLabel("From:"))
    win.spn_anim_from = QDoubleSpinBox()
    win.spn_anim_from.setRange(-300.0, 300.0)
    win.spn_anim_from.setValue(128.0)
    win.spn_anim_from.valueChanged.connect(lambda _: win._on_anim_edited())
    frow.addWidget(win.spn_anim_from, 1)
    frow.addWidget(QLabel("To:"))
    win.spn_anim_to = QDoubleSpinBox()
    win.spn_anim_to.setRange(-300.0, 300.0)
    win.spn_anim_to.setValue(200.0)
    win.spn_anim_to.valueChanged.connect(lambda _: win._on_anim_edited())
    frow.addWidget(win.spn_anim_to, 1)
    g.addLayout(frow)
    srow = QHBoxLayout()
    srow.addWidget(QLabel("Start:"))
    win.spn_anim_start = QSpinBox()
    win.spn_anim_start.setRange(0, 23)
    win.spn_anim_start.setValue(0)
    win.spn_anim_start.valueChanged.connect(lambda _: win._on_anim_edited())
    srow.addWidget(win.spn_anim_start, 1)
    srow.addWidget(QLabel("End:"))
    win.spn_anim_end = QSpinBox()
    win.spn_anim_end.setRange(0, 23)
    win.spn_anim_end.setValue(23)
    win.spn_anim_end.valueChanged.connect(lambda _: win._on_anim_edited())
    srow.addWidget(win.spn_anim_end, 1)
    g.addLayout(srow)
    hlab(g, "Signal Drift (animated pre-dither noise):")
    drow = QHBoxLayout()
    win.cmb_drift = QComboBox()
    win.cmb_drift.addItems(["off", "hum_bar", "roll", "crawl", "snow",
                            "weave", "flicker", "moire", "sweep", "jitter"])
    tight(win.cmb_drift, 10)
    win.cmb_drift.setToolTip("Retro-screen noise, marches with phase")
    win.cmb_drift.currentTextChanged.connect(lambda _: win._schedule_refresh())
    drow.addWidget(win.cmb_drift, 1)
    g.addLayout(drow)
    win.sld_drift, _ = labeled_slider(win, g, "Drift:", 0, 100, 0, "Signal Drift amount 0=off")
    win.anim_layers_data: list = []


def build_effects_section(win, g: QVBoxLayout) -> None:
    """Compat: redirige a los tres grupos (GRADE/TEXTURE/GLITCH)."""
    build_grade_section(win, g)
    build_texture_section(win, g)
    build_glitch_section(win, g)
    build_fx_stack_section(win, g)


def build_grade_section(win, g: QVBoxLayout) -> None:
    g.addWidget(QLabel("Grade:"))
    duo_row = QHBoxLayout()
    duo_row.addWidget(QLabel("Duo:"))
    win.btn_duo_dark = QPushButton("Dark...")
    win.btn_duo_dark.setToolTip("Duotone shadow color (empty = off)")
    win.btn_duo_dark.clicked.connect(lambda: win.pick_duotone_color("dark"))
    duo_row.addWidget(win.btn_duo_dark)
    win.btn_duo_light = QPushButton("Light...")
    win.btn_duo_light.setToolTip("Duotone highlight color (empty = off)")
    win.btn_duo_light.clicked.connect(lambda: win.pick_duotone_color("light"))
    duo_row.addWidget(win.btn_duo_light)
    win.lbl_duo = QLabel("(off)")
    win.lbl_duo.setMinimumWidth(110)
    duo_row.addWidget(win.lbl_duo, 1)
    win.duotone_dark = ""
    win.duotone_light = ""
    g.addLayout(duo_row)
    win.sld_duo_mid, _ = labeled_slider(win, g, "Duo mid:", 0, 100, 50, "Gradient midpoint")
    win.spn_poster = spin_row(g, "Posterize:", 0, 8, 0, "Tones 2-8, 0=off")
    win.spn_poster.valueChanged.connect(lambda _: win._schedule_refresh())
    win.sld_split, _ = labeled_slider(win, g, "Split tone:", 0, 100, 0, "Cool shadows / warm highlights")
    win.sld_fade, _ = labeled_slider(win, g, "Fade:", 0, 100, 0, "Lift blacks (matte film)")
    win.sld_glow, _ = labeled_slider(win, g, "Glow:", 0, 100, 0, "Glow intensity")
    glow_row = QHBoxLayout()
    _glow_lab = QLabel("Glow rad/thr:")
    _glow_lab.setToolTip("Glow radius / threshold")
    glow_row.addWidget(_glow_lab)
    win.spn_glowrad = QSpinBox()
    win.spn_glowrad.setRange(0, 50)
    win.spn_glowrad.setValue(8)
    win.spn_glowrad.setFixedWidth(56)
    win.spn_glowrad.setToolTip("Blur radius 0-50")
    win.spn_glowrad.valueChanged.connect(lambda _: win._schedule_refresh())
    glow_row.addWidget(win.spn_glowrad)
    win.spn_glowthr = QSpinBox()
    win.spn_glowthr.setRange(0, 255)
    win.spn_glowthr.setValue(0)
    win.spn_glowthr.setFixedWidth(56)
    win.spn_glowthr.setToolTip("0 = everything glows; high = only brights")
    win.spn_glowthr.valueChanged.connect(lambda _: win._schedule_refresh())
    glow_row.addWidget(win.spn_glowthr)
    g.addLayout(glow_row)
    g.addWidget(QLabel("Brand:"))
    brand_row = QHBoxLayout()
    win.btn_brand = QPushButton("Brand...")
    win.btn_brand.setToolTip("Brand color: replaces dither white")
    win.btn_brand.clicked.connect(win.pick_brand_color)
    brand_row.addWidget(win.btn_brand)
    win.lbl_brand = QLabel("(no brand)")
    brand_row.addWidget(win.lbl_brand, 1)
    win.brand_color = ""
    g.addLayout(brand_row)


def build_texture_section(win, g: QVBoxLayout) -> None:
    hlab(g, "Texture / decay:")
    win.sld_grain, _ = labeled_slider(win, g, "Grain:", 0, 50, 0, "Grain 0-50")
    win.sld_vig, _ = labeled_slider(win, g, "Vignette:", 0, 100, 0, "Vignette 0-100")
    half_row = QHBoxLayout()
    half_row.addWidget(QLabel("Halftone:"))
    win.spn_halftone = QSpinBox()
    win.spn_halftone.setRange(0, 12)
    win.spn_halftone.setValue(0)
    win.spn_halftone.setFixedWidth(56)
    win.spn_halftone.setToolTip("Dot cell 3-12px, 0=off")
    win.spn_halftone.valueChanged.connect(lambda _: win._schedule_refresh())
    half_row.addWidget(win.spn_halftone)
    win.cmb_halftone = QComboBox()
    win.cmb_halftone.addItems(["dots", "lines"])
    tight(win.cmb_halftone, 8)
    win.cmb_halftone.setToolTip("Dot screen vs line screen")
    win.cmb_halftone.currentTextChanged.connect(lambda _: win._schedule_refresh())
    half_row.addWidget(win.cmb_halftone, 1)
    g.addLayout(half_row)
    win.sld_dust, _ = labeled_slider(win, g, "Dust:", 0, 100, 0, "Dust & scratches")
    hlab(g, "Scanlines / Frame:")
    fx_row = QHBoxLayout()
    win.spn_scan = QSpinBox()
    win.spn_scan.setRange(0, 8)
    win.spn_scan.setValue(0)
    win.spn_scan.setFixedWidth(56)
    win.spn_scan.setToolTip("Scanlines: 0=off, every N rows (only 0,2,3,4,6,8 are valid)")
    win.spn_scan.valueChanged.connect(lambda _: win._schedule_refresh())
    fx_row.addWidget(win.spn_scan)
    win.spn_border = QSpinBox()
    win.spn_border.setRange(0, 64)
    win.spn_border.setValue(0)
    win.spn_border.setFixedWidth(56)
    win.spn_border.setToolTip("Solid border 0-64px, 0=off")
    win.spn_border.valueChanged.connect(lambda _: win._schedule_refresh())
    fx_row.addWidget(win.spn_border)
    win.btn_border_color = QPushButton("Border...")
    win.btn_border_color.setToolTip("Border color")
    win.btn_border_color.clicked.connect(win.pick_border_color)
    fx_row.addWidget(win.btn_border_color)
    win.lbl_border = QLabel("#000000")
    fx_row.addWidget(win.lbl_border, 1)
    win.border_color = "#000000"
    g.addLayout(fx_row)
    win.spn_letterbox = spin_row(g, "Letterbox:", 0, 25, 0, "Cinema bars % each side, 0=off")
    win.spn_letterbox.valueChanged.connect(lambda _: win._schedule_refresh())


def build_glitch_section(win, g: QVBoxLayout) -> None:
    g.addWidget(QLabel("Glitch:"))
    win.sld_chroma, _ = labeled_slider(win, g, "Chroma:", 0, 20, 0, "Chromatic aberration 0-20px")
    glitch_row = QHBoxLayout()
    glitch_row.addWidget(QLabel("Slices:"))
    win.spn_slice = QSpinBox()
    win.spn_slice.setRange(0, 16)
    win.spn_slice.setValue(0)
    win.spn_slice.setFixedWidth(56)
    win.spn_slice.setToolTip("Slice bands 0=off (valid: 0,2,3,4,6,8,12,16)")
    win.spn_slice.valueChanged.connect(lambda _: win._schedule_refresh())
    glitch_row.addWidget(win.spn_slice)
    win.spn_pixelsort = QSpinBox()
    win.spn_pixelsort.setRange(0, 255)
    win.spn_pixelsort.setValue(0)
    win.spn_pixelsort.setFixedWidth(56)
    win.spn_pixelsort.setToolTip("Pixel sort threshold 0=off")
    win.spn_pixelsort.valueChanged.connect(lambda _: win._schedule_refresh())
    glitch_row.addWidget(QLabel("Sort:"))
    glitch_row.addWidget(win.spn_pixelsort)
    g.addLayout(glitch_row)
    fx2_row = QHBoxLayout()
    fx2_row.addWidget(QLabel("Wave:"))
    win.spn_wave = QSpinBox()
    win.spn_wave.setRange(0, 30)
    win.spn_wave.setValue(0)
    win.spn_wave.setFixedWidth(56)
    win.spn_wave.setToolTip("Sine displacement 0-30px, 0=off")
    win.spn_wave.valueChanged.connect(lambda _: win._schedule_refresh())
    fx2_row.addWidget(win.spn_wave)
    fx2_row.addWidget(QLabel("Mosh:"))
    win.sld_mosh, _mosh_lbl = mini_slider(win, 0, 100, 0, "Datamosh blocks")
    win.sld_mosh.setToolTip("Datamosh blocks")
    fx2_row.addWidget(win.sld_mosh, 1)
    fx2_row.addWidget(_mosh_lbl)
    fx2_row.addWidget(QLabel("Grille:"))
    win.spn_grille = QSpinBox()
    win.spn_grille.setRange(0, 3)
    win.spn_grille.setValue(0)
    win.spn_grille.setFixedWidth(56)
    win.spn_grille.setToolTip("RGB grille every N px: 0=off, 2 or 3")
    win.spn_grille.valueChanged.connect(lambda _: win._schedule_refresh())
    fx2_row.addWidget(win.spn_grille)
    g.addLayout(fx2_row)


def build_video_section(win, g: QVBoxLayout) -> None:
    """Único sitio para animar: Mode/Frames/FPS/Ping-pong + resolución de preview.

    Preview = proxy ligero (Draft/HD/Full); el export SIEMPRE sale al
    documento completo, elija lo que elija el preview."""
    from app.gif import GIF_MODES

    win.chk_video = QCheckBox("Video mode (animated preview)")
    win.chk_video.setToolTip("OFF = still dither · ON = full video preview on canvas")
    win.chk_video.setChecked(False)
    win.chk_video.stateChanged.connect(win._on_video_toggle)
    g.addWidget(win.chk_video)
    row = QHBoxLayout()
    row.addWidget(QLabel("Mode:"))
    from PySide6.QtWidgets import QComboBox

    win.cmb_video_mode = QComboBox()
    win.cmb_video_mode.addItems(list(GIF_MODES))
    tight(win.cmb_video_mode, 8)
    win.cmb_video_mode.setCurrentText("mix")
    win.cmb_video_mode.setToolTip("phase=march · hue=cycle · both · glitch=CRT · mix=all")
    win.cmb_video_mode.currentTextChanged.connect(lambda _: win._schedule_refresh())
    row.addWidget(win.cmb_video_mode, 1)
    g.addLayout(row)
    row2 = QHBoxLayout()
    row2.addWidget(QLabel("Frames:"))
    from PySide6.QtWidgets import QComboBox as _Cmb

    from app.gif import GIF_FRAMES_SUGGESTED, GIF_FPS_SUGGESTED

    win.cmb_video_frames = _Cmb()
    tight(win.cmb_video_frames, 6)
    win.cmb_video_frames.setEditable(True)
    win.cmb_video_frames.addItems([str(n) for n in GIF_FRAMES_SUGGESTED])
    win.cmb_video_frames.setCurrentText("6")
    win.cmb_video_frames.setToolTip("Suggested: 4/6/8/12/24 (editable, 2-24)")
    win.cmb_video_frames.setFixedWidth(72)
    win.cmb_video_frames.currentTextChanged.connect(lambda _: win._schedule_refresh())
    row2.addWidget(win.cmb_video_frames)
    row2.addWidget(QLabel("FPS:"))
    win.cmb_video_fps = _Cmb()
    tight(win.cmb_video_fps, 6)
    win.cmb_video_fps.setEditable(True)
    win.cmb_video_fps.addItems([str(n) for n in GIF_FPS_SUGGESTED])
    win.cmb_video_fps.setCurrentText("24")
    win.cmb_video_fps.setToolTip("Suggested: 12/24/30/48/60 (editable, 2-60; GIF stores ~50fps max)")
    win.cmb_video_fps.setFixedWidth(72)
    win.cmb_video_fps.currentTextChanged.connect(win._on_video_fps_changed)
    row2.addWidget(win.cmb_video_fps)
    g.addLayout(row2)
    row3 = QHBoxLayout()
    row3.addWidget(QLabel("Size:"))
    win.lbl_video_size = QLabel("canvas")
    win.lbl_video_size.setToolTip("Animation renders at the CANVAS document size")
    row3.addWidget(win.lbl_video_size, 1)
    row3.addWidget(QLabel("Preview:"))
    win.cmb_video_proxy = QComboBox()
    win.cmb_video_proxy.addItems(["Draft 720p", "HD 1080p", "Full (doc)"])
    win.cmb_video_proxy.setCurrentText("Draft 720p")
    tight(win.cmb_video_proxy, 12)
    win.cmb_video_proxy.setToolTip(
        "Preview resolution only, like video proxies: lighter = instant. "
        "Export always renders at full document size.")
    win.cmb_video_proxy.setMinimumWidth(110)
    win.cmb_video_proxy.currentTextChanged.connect(win._on_video_proxy_changed)
    row3.addWidget(win.cmb_video_proxy)
    g.addLayout(row3)
    play_row = QHBoxLayout()
    win.btn_video_play = QPushButton("⏸ Pause")
    win.btn_video_play.setToolTip("Play / pause video preview")
    win.btn_video_play.clicked.connect(win._on_video_playpause)
    play_row.addWidget(win.btn_video_play)
    from PySide6.QtWidgets import QCheckBox as _Chk

    win.chk_video_pingpong = _Chk("Ping-pong")
    win.chk_video_pingpong.setChecked(False)
    win.chk_video_pingpong.setToolTip("Forward-backward loop (no jump cut)")
    win.chk_video_pingpong.stateChanged.connect(lambda _: win._schedule_refresh())
    play_row.addWidget(win.chk_video_pingpong, 1)
    g.addLayout(play_row)


def build_custom_palette_section(win, g: QVBoxLayout) -> None:
    # Biblioteca: una paleta con nombre cargada = punto de partida editable.
    lib_row = QHBoxLayout()
    lib_row.addWidget(QLabel("Palette:"))
    win.cmb_pal_preset = QComboBox()
    tight(win.cmb_pal_preset, 14)
    win.cmb_pal_preset.setToolTip("Load a named palette as editable swatches")
    win.cmb_pal_preset.currentTextChanged.connect(win._on_palette_preset_changed)
    lib_row.addWidget(win.cmb_pal_preset, 1)
    win.btn_palette_save = QPushButton("Save...")
    win.btn_palette_save.setToolTip("Save current swatches as a named palette")
    win.btn_palette_save.clicked.connect(win.save_palette_preset)
    lib_row.addWidget(win.btn_palette_save)
    g.addLayout(lib_row)
    row = QHBoxLayout()
    win.btn_custom_add = QPushButton("+ color")
    win.btn_custom_add.setToolTip("Quick-add one color")
    win.btn_custom_add.clicked.connect(win.add_custom_color)
    row.addWidget(win.btn_custom_add)
    win.btn_pal_gen = QPushButton("🎲")
    win.btn_pal_gen.setToolTip("Surprise palette: generate harmonious colors")
    win.btn_pal_gen.clicked.connect(win.gen_palette)
    row.addWidget(win.btn_pal_gen)
    win.cmb_palgen = QComboBox()
    tight(win.cmb_palgen, 8)
    win.cmb_palgen.addItems(["Ramp", "Harmony"])
    win.cmb_palgen.setToolTip("Ramp: shading gradient (best for dither) · Harmony: analogous/complementary/triadic")
    row.addWidget(win.cmb_palgen)
    win.btn_palette_edit = QPushButton("Edit...")
    win.btn_palette_edit.setToolTip("Editor: see, edit, reorder and sort colors")
    win.btn_palette_edit.clicked.connect(win.edit_custom_palette)
    row.addWidget(win.btn_palette_edit)
    win.custom_colors: list[tuple[int, int, int]] = []
    g.addLayout(row)
    row2 = QHBoxLayout()
    win.btn_pal_extract = QPushButton("From image")
    win.btn_pal_extract.setToolTip("Auto-extract palette from current image (median-cut, offline)")
    win.btn_pal_extract.clicked.connect(win.extract_palette_from_image)
    row2.addWidget(win.btn_pal_extract)
    win.btn_custom_clear = QPushButton("Clear")
    win.btn_custom_clear.clicked.connect(win.clear_custom_colors)
    row2.addWidget(win.btn_custom_clear)
    win.lbl_custom = QLabel("0 colors")
    row2.addWidget(win.lbl_custom, 1)
    g.addLayout(row2)
    depth_row = QHBoxLayout()
    depth_row.addWidget(QLabel("Depth:"))
    win.spn_pal_depth = QSpinBox()
    win.spn_pal_depth.setRange(0, 16)
    win.spn_pal_depth.setValue(0)
    win.spn_pal_depth.setFixedWidth(56)
    win.spn_pal_depth.setToolTip("0 = full palette · 2-16 = limit shades")
    win.spn_pal_depth.valueChanged.connect(lambda _: win._schedule_refresh())
    depth_row.addWidget(win.spn_pal_depth)
    win.btn_pal_shuffle = QPushButton("🔀")
    win.btn_pal_shuffle.setFixedWidth(36)
    win.btn_pal_shuffle.setToolTip("Shuffle unlocked swatches (locked stay)")
    win.btn_pal_shuffle.clicked.connect(win.shuffle_palette)
    depth_row.addWidget(win.btn_pal_shuffle)
    depth_row.addStretch()
    g.addLayout(depth_row)
    io_row = QHBoxLayout()
    win.btn_pal_import = QPushButton("Import")
    win.btn_pal_import.setToolTip("Import palette .json / .gpl (offline)")
    win.btn_pal_import.clicked.connect(win.import_palette_file)
    io_row.addWidget(win.btn_pal_import)
    win.btn_pal_export = QPushButton("Export")
    win.btn_pal_export.setToolTip("Export current swatches .json / .gpl (offline share)")
    win.btn_pal_export.clicked.connect(win.export_palette_file)
    io_row.addWidget(win.btn_pal_export)
    io_row.addStretch()
    g.addLayout(io_row)
    # Tira de swatches: cada color visible, clic lo quita.
    strip_host = QWidget()
    win.palette_strip = QHBoxLayout(strip_host)
    win.palette_strip.setContentsMargins(0, 2, 0, 2)
    win.palette_strip.setSpacing(4)
    g.addWidget(strip_host)
    win.lbl_palette_hint = QLabel("")
    win.lbl_palette_hint.setWordWrap(True)
    win.lbl_palette_hint.setObjectName("subtitleLabel")
    g.addWidget(win.lbl_palette_hint)


__all__ = [
    "make_group",
    "labeled_slider",
    "mini_slider",
    "spin_row",
    "build_image_section",
    "build_preset_section",
    "build_method_section",
    "build_pixel_section",
    "build_color_section",
    "build_canvas_section",
    "build_pre_section",
    "build_effects_section",
    "build_motif_section",
    "build_fx_stack_section",
    "build_timeline_section",
    "build_grade_section",
    "build_texture_section",
    "build_glitch_section",
    "build_video_section",
    "build_custom_palette_section",
]
