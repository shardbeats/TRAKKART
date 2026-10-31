"""MORPH page: particle dissolve controls + morph playlist (up to 5 extra).

Split out of the MOTION video section (same mechanical-move rule as the
other panel modules): widget attribute names are unchanged so BINDINGS,
presets and tests keep working. A (src) always comes from the canvas;
the list holds B..F in play order (chain capped at 6 total, A + 5).
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


def build_morph_section(win, g: QVBoxLayout) -> None:
    """Dissolve params (still single source) + morph image playlist."""
    hlab(g, "Dissolve (particle disperse):")
    win.cmb_dissolve_mode = QComboBox()
    win.cmb_dissolve_mode.addItems(["wind", "random"])
    tight(win.cmb_dissolve_mode, 8)
    win.cmb_dissolve_mode.setToolTip("Particle drift: wind = directional + turbulence · random = all directions")
    win.cmb_dissolve_mode.currentTextChanged.connect(lambda _: win._schedule_refresh())
    mrow = QHBoxLayout()
    mrow.addWidget(QLabel("Drift:"))
    mrow.addWidget(win.cmb_dissolve_mode, 1)
    g.addLayout(mrow)
    win.sld_dissolve_amount, _ = labeled_slider(win, g, "Amount:", 0, 200, 100, "Disperse strength 0=still · 100=classic · up to 200", div=100.0)
    win.sld_dissolve_speed, _ = labeled_slider(win, g, "Speed:", 25, 400, 100, "Traversals per clip 0.25-4.0x (1 = full sweep)", div=100.0)
    win.sld_dissolve_wind_x, _ = labeled_slider(win, g, "Wind X:", -500, 500, 120, "Horizontal wind px at full disperse")
    win.sld_dissolve_wind_y, _ = labeled_slider(win, g, "Wind Y:", -500, 500, -40, "Vertical wind px at full disperse")
    seed_row = QHBoxLayout()
    seed_row.addWidget(QLabel("Seed:"))
    win.spn_dissolve_seed = QSpinBox()
    win.spn_dissolve_seed.setRange(0, 999999)
    win.spn_dissolve_seed.setValue(53596)
    win.spn_dissolve_seed.setFixedWidth(80)
    win.spn_dissolve_seed.setToolTip("Deterministic pattern seed (same seed = same particles)")
    win.spn_dissolve_seed.valueChanged.connect(lambda _: win._schedule_refresh())
    seed_row.addWidget(win.spn_dissolve_seed)
    seed_row.addStretch()
    g.addLayout(seed_row)
    win.sld_dissolve_hold, _ = labeled_slider(win, g, "Hold:", 0, 30, 10, "Still pause per end 0-3.0s (each form reads)", div=10.0)
    hlab(g, "Morph chain A->B->C... (A = canvas):")
    from PySide6.QtWidgets import QListWidget

    win.morph_list_widget = QListWidget()
    win.morph_list_widget.setMinimumHeight(90)
    win.morph_list_widget.setMaximumHeight(150)
    win.morph_list_widget.setToolTip("Play order after A. Add up to 5 (chain of 6 max).")
    win.morph_list_widget.itemSelectionChanged.connect(lambda: win._on_morph_selected())
    g.addWidget(win.morph_list_widget)
    brow = QHBoxLayout()
    win.btn_morph_pick = QPushButton("Add...")
    win.btn_morph_pick.setToolTip("Append an image to the chain (B, C, ... up to 5)")
    win.btn_morph_pick.clicked.connect(win._on_morph_pick)
    brow.addWidget(win.btn_morph_pick)
    win.btn_morph_remove = QPushButton("Remove")
    win.btn_morph_remove.setFixedWidth(70)
    win.btn_morph_remove.setToolTip("Remove the selected chain image")
    win.btn_morph_remove.clicked.connect(win._on_morph_remove)
    brow.addWidget(win.btn_morph_remove)
    win.btn_morph_up = QPushButton("▲")
    win.btn_morph_up.setFixedWidth(36)
    win.btn_morph_up.setToolTip("Move selected earlier in the chain")
    win.btn_morph_up.clicked.connect(win._on_morph_up)
    brow.addWidget(win.btn_morph_up)
    win.btn_morph_down = QPushButton("▼")
    win.btn_morph_down.setFixedWidth(36)
    win.btn_morph_down.setToolTip("Move selected later in the chain")
    win.btn_morph_down.clicked.connect(win._on_morph_down)
    brow.addWidget(win.btn_morph_down)
    win.btn_morph_clear = QPushButton("Clear")
    win.btn_morph_clear.setFixedWidth(56)
    win.btn_morph_clear.setToolTip("Forget the whole chain")
    win.btn_morph_clear.clicked.connect(win._on_morph_clear)
    brow.addWidget(win.btn_morph_clear)
    g.addLayout(brow)
    win.lbl_morph = QLabel("B: (none — morph falls back to dissolve)")
    win.lbl_morph.setWordWrap(True)
    win.lbl_morph.setObjectName("subtitleLabel")
    g.addWidget(win.lbl_morph)
    win.lbl_morph_crop = QLabel("Crop: select a chain image")
    win.lbl_morph_crop.setWordWrap(True)
    win.lbl_morph_crop.setObjectName("subtitleLabel")
    g.addWidget(win.lbl_morph_crop)
    win.sld_morph_fx, _ = labeled_slider(win, g, "Crop X:", 0, 100, 50, "Chain image focus X 0-100 (cover crop)")
    win.sld_morph_fy, _ = labeled_slider(win, g, "Crop Y:", 0, 100, 50, "Chain image focus Y 0-100 (cover crop)")
    win.sld_morph_zoom, _ = labeled_slider(win, g, "Crop zoom:", 100, 400, 100, "Chain image zoom 1.0-4.0x (cover crop)", div=100.0)
    try:
        win.sld_morph_fx.valueChanged.connect(lambda _v: win._on_morph_crop_changed())
        win.sld_morph_fy.valueChanged.connect(lambda _v: win._on_morph_crop_changed())
        win.sld_morph_zoom.valueChanged.connect(lambda _v: win._on_morph_crop_changed())
    except Exception:  # noqa: BLE001
        pass
