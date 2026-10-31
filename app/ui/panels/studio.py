"""Studio sections: motif, FX stack, custom palette.

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
    QWidget,
)
from app.ui.panels.widgets import hlab, tight, labeled_slider, spin_row


def build_motif_section(win, g: QVBoxLayout) -> None:
    """Motif: 4 luminance bands -> shape + size.

    Kept simple on purpose. The `motif` method reads this config;
    every other method ignores it.
    """
    from app.motif import BAND_NAMES, SHAPES

    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setSpacing(4)
    lay.setContentsMargins(0, 0, 0, 0)
    hlab(lay, "Bands → shape/size (method `motif`):")
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
        lay.addLayout(row)
    g.addWidget(box)
    win._motif_box = box


def build_fx_stack_section(win, g: QVBoxLayout) -> None:
    """Reorderable FX STACK (v1.2): order + on/off. Params live in the
    existing sliders (single source); here only order and toggle."""
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


def build_mosh_section(win, g: QVBoxLayout) -> None:
    """DATAMOSH page: flavor + amount + feature size + seed variation.

    Params live here; order lives in the FX STACK (v1.2 rule). Amount 0
    disables every flavor (off-safe). The dice re-rolls the seed.
    """
    from app.mosh import MOSH_MODES

    mode_row = QHBoxLayout()
    mode_row.addWidget(QLabel("Mode:"))
    win.cmb_mosh_mode = QComboBox()
    tight(win.cmb_mosh_mode, 10)
    win.cmb_mosh_mode.addItems(list(MOSH_MODES))
    win.cmb_mosh_mode.setToolTip("Datamosh flavor: blocks/smear/ghost/rows/chroma/crush/speckle")
    win.cmb_mosh_mode.currentTextChanged.connect(lambda _: win._schedule_refresh())
    mode_row.addWidget(win.cmb_mosh_mode, 1)
    g.addLayout(mode_row)
    win.sld_mosh, _ = labeled_slider(win, g, "Amount:", 0, 100, 0, "Datamosh amount 0=off")
    win.sld_mosh_size, _ = labeled_slider(
        win, g, "Size:", 10, 200, 100, "Feature scale % (100 = classic)")
    seed_row = QHBoxLayout()
    seed_row.addWidget(QLabel("Variation:"))
    win.spn_mosh_seed = QSpinBox()
    win.spn_mosh_seed.setRange(0, 99)
    win.spn_mosh_seed.setValue(0)
    win.spn_mosh_seed.setFixedWidth(56)
    win.spn_mosh_seed.setToolTip("Seed variation 0-99: re-rolls the damage")
    win.spn_mosh_seed.valueChanged.connect(lambda _: win._schedule_refresh())
    seed_row.addWidget(win.spn_mosh_seed)
    win.btn_mosh_dice = QPushButton("🎲")
    win.btn_mosh_dice.setFixedWidth(36)
    win.btn_mosh_dice.setToolTip("Re-roll the damage pattern")
    win.btn_mosh_dice.clicked.connect(lambda: _roll_mosh_seed(win))
    seed_row.addWidget(win.btn_mosh_dice)
    seed_row.addStretch()
    g.addLayout(seed_row)


def build_drift_section(win, g: QVBoxLayout) -> None:
    """Signal Drift in DATAMOSH: same Preset fields as MOTION had.

    Single source (Preset drift_*): pattern/amount/speed shared with
    animation, position freezes the still (50 = mid-traverse, visible).
    Animation ignores position and sweeps 0->1 with speed.
    """
    hlab(g, "Signal Drift (pre-dither noise):")
    drow = QHBoxLayout()
    win.cmb_drift = QComboBox()
    win.cmb_drift.addItems(["off", "hum_bar", "roll", "crawl", "snow",
                            "weave", "flicker", "moire", "sweep", "jitter"])
    tight(win.cmb_drift, 10)
    win.cmb_drift.setToolTip("Retro-screen noise, full traverse per clip (loop-perfect)")
    win.cmb_drift.currentTextChanged.connect(lambda _: win._schedule_refresh())
    drow.addWidget(win.cmb_drift, 1)
    g.addLayout(drow)
    win.sld_drift, _ = labeled_slider(win, g, "Drift:", 0, 100, 0, "Signal Drift amount 0=off")
    win.sld_drift_speed, _ = labeled_slider(win, g, "Speed:", 25, 400, 100,
                                            "Drift traversals per clip 0.25-4.0x (1 = full sweep)",
                                            div=100.0)
    win.sld_drift_position, _ = labeled_slider(win, g, "Position:", 0, 100, 50,
                                               "Still freeze 0-100 (50 = mid-traverse, visible)")


def _roll_mosh_seed(win) -> None:
    import random

    win.spn_mosh_seed.setValue(random.randint(0, 99))
    win._status("Mosh variation re-rolled")


def build_custom_palette_section(win, g: QVBoxLayout) -> None:
    # Library: a loaded named palette = editable starting point.
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
    # Swatch strip: each color visible, click removes it.
    strip_host = QWidget()
    win.palette_strip = QHBoxLayout(strip_host)
    win.palette_strip.setContentsMargins(0, 2, 0, 2)
    win.palette_strip.setSpacing(4)
    g.addWidget(strip_host)
    win.lbl_palette_hint = QLabel("")
    win.lbl_palette_hint.setWordWrap(True)
    win.lbl_palette_hint.setObjectName("subtitleLabel")
    g.addWidget(win.lbl_palette_hint)
