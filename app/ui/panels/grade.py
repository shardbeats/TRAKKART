"""Look sections: pre-process, grade, texture, glitch (+ compat).

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
from app.ui.panels.studio import build_fx_stack_section
from app.ui.panels.widgets import hlab, tight, labeled_slider, spin_row


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


def build_effects_section(win, g: QVBoxLayout) -> None:
    """Compat: redirige a los tres grupos (GRADE/TEXTURE/GLITCH)."""
    build_tint_section(win, g)
    build_grade_section(win, g)
    build_texture_section(win, g)
    build_glitch_section(win, g)
    build_fx_stack_section(win, g)


def build_tint_section(win, g: QVBoxLayout) -> None:
    """Duotone + brand: viven en la página COLOR (extraído de grade)."""
    g.addWidget(QLabel("Duotone:"))
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


def build_grade_section(win, g: QVBoxLayout) -> None:
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
    g.addLayout(fx2_row)
    fx3_row = QHBoxLayout()
    fx3_row.addWidget(QLabel("Grille:"))
    win.spn_grille = QSpinBox()
    win.spn_grille.setRange(0, 3)
    win.spn_grille.setValue(0)
    win.spn_grille.setFixedWidth(56)
    win.spn_grille.setToolTip("RGB grille every N px: 0=off, 2 or 3")
    win.spn_grille.valueChanged.connect(lambda _: win._schedule_refresh())
    fx3_row.addWidget(win.spn_grille)
    fx3_row.addStretch()
    g.addLayout(fx3_row)
