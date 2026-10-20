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


def build_method_section(win, g: QVBoxLayout, methods, palettes) -> None:
    g.addWidget(QLabel("Method:"))
    win.cmb_method = QComboBox()
    win.cmb_method.addItems(list(methods))
    win.cmb_method.currentTextChanged.connect(lambda _: win._schedule_refresh())
    g.addWidget(win.cmb_method)
    g.addWidget(QLabel("Palette:"))
    win.cmb_palette = QComboBox()
    win.cmb_palette.addItems(palettes)
    win.cmb_palette.currentTextChanged.connect(lambda _: win._schedule_refresh())
    g.addWidget(win.cmb_palette)


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


def build_canvas_section(win, g: QVBoxLayout, ratios, crop_modes) -> None:
    g.addWidget(QLabel("Ratio / Mode:"))
    row = QHBoxLayout()
    win.cmb_ratio = QComboBox()
    win.cmb_ratio.addItems(ratios)
    win.cmb_ratio.currentTextChanged.connect(lambda _: win._schedule_refresh())
    row.addWidget(win.cmb_ratio, 1)
    win.cmb_crop = QComboBox()
    win.cmb_crop.addItems(list(crop_modes))
    win.cmb_crop.currentTextChanged.connect(lambda _: win._schedule_refresh())
    row.addWidget(win.cmb_crop, 1)
    g.addLayout(row)
    g.addWidget(QLabel("Crop (visual editor):"))
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
    win.sld_blur, _ = labeled_slider(win, g, "Blur:", 0, 50, 0, "Blur 0.0-5.0", div=10.0)
    win.spn_sharp = spin_row(g, "Sharpen:", 0, 3, 0, "Sharpen 0-3")
    win.spn_sharp.valueChanged.connect(lambda _: win._schedule_refresh())
    win.sld_hue, _ = labeled_slider(win, g, "Hue:", -180, 180, 0, "Hue -180..180")
    win.spn_denoise = spin_row(g, "Denoise:", 0, 5, 0, "Denoise 0-5")
    win.spn_denoise.valueChanged.connect(lambda _: win._schedule_refresh())
    win.sld_smooth, _ = labeled_slider(win, g, "Smooth:", 0, 50, 0, "Smooth 0.0-5.0", div=10.0)
    for sp in (win.spn_sharp, win.spn_denoise):
        sp.valueChanged.connect(lambda _: win._schedule_refresh())


def build_effects_section(win, g: QVBoxLayout) -> None:
    win.sld_glow, _ = labeled_slider(win, g, "Glow:", 0, 100, 0, "Glow intensity (fixed radius 8)")
    win.sld_grain, _ = labeled_slider(win, g, "Grain:", 0, 50, 0, "Grain 0-50")
    win.sld_vig, _ = labeled_slider(win, g, "Vignette:", 0, 100, 0, "Vignette 0-100")
    g.addWidget(QLabel("Scanlines / Brand:"))
    fx_row = QHBoxLayout()
    win.spn_scan = QSpinBox()
    win.spn_scan.setRange(0, 8)
    win.spn_scan.setValue(0)
    win.spn_scan.setFixedWidth(56)
    win.spn_scan.setToolTip("Scanlines: 0=off, every N rows (only 0,2,3,4,6,8 are valid)")
    win.spn_scan.valueChanged.connect(lambda _: win._schedule_refresh())
    fx_row.addWidget(win.spn_scan)
    win.btn_brand = QPushButton("Brand...")
    win.btn_brand.setToolTip("Brand color: replaces dither white")
    win.btn_brand.clicked.connect(win.pick_brand_color)
    fx_row.addWidget(win.btn_brand)
    win.lbl_brand = QLabel("(no brand)")
    fx_row.addWidget(win.lbl_brand, 1)
    win.brand_color = ""
    g.addLayout(fx_row)
    g.addWidget(QLabel("Glitch / Scanlines:"))
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
    g.addLayout(glitch_row)


def build_custom_palette_section(win, g: QVBoxLayout) -> None:
    g.addWidget(QLabel("Empty = use combo:"))
    row = QHBoxLayout()
    win.btn_custom_add = QPushButton("+ color")
    win.btn_custom_add.setToolTip("Quick-add one color")
    win.btn_custom_add.clicked.connect(win.add_custom_color)
    row.addWidget(win.btn_custom_add)
    win.btn_palette_edit = QPushButton("Edit...")
    win.btn_palette_edit.setToolTip("Editor: see, edit, reorder and sort colors")
    win.btn_palette_edit.clicked.connect(win.edit_custom_palette)
    row.addWidget(win.btn_palette_edit)
    win.btn_custom_clear = QPushButton("Clear")
    win.btn_custom_clear.clicked.connect(win.clear_custom_colors)
    row.addWidget(win.btn_custom_clear)
    win.lbl_custom = QLabel("0 colors")
    row.addWidget(win.lbl_custom, 1)
    win.custom_colors: list[tuple[int, int, int]] = []
    g.addLayout(row)
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


def build_output_section(win, g: QVBoxLayout, gif_modes) -> None:
    g.addWidget(QLabel("Bundle + Vector + GIF:"))
    vec_row = QHBoxLayout()
    win.chk_vector = QCheckBox("Include SVG")
    win.chk_vector.setToolTip("Vector for logos/merch (no post-fx)")
    win.chk_vector.stateChanged.connect(lambda _: win._schedule_refresh())
    vec_row.addWidget(win.chk_vector)
    win.spn_vcell = QSpinBox()
    win.spn_vcell.setRange(4, 16)
    win.spn_vcell.setValue(8)
    win.spn_vcell.setFixedWidth(56)
    win.spn_vcell.setToolTip("SVG cell 4-16 (higher = smaller file)")
    win.spn_vcell.valueChanged.connect(lambda _: win._schedule_refresh())
    vec_row.addWidget(win.spn_vcell)
    win.lbl_vec = QLabel("")
    vec_row.addWidget(win.lbl_vec, 1)
    g.addLayout(vec_row)
    gif_row = QHBoxLayout()
    win.chk_gif = QCheckBox("Include GIF")
    win.chk_gif.setToolTip("Animation for socials (Pillow only)")
    win.chk_gif.stateChanged.connect(lambda _: win._schedule_refresh())
    gif_row.addWidget(win.chk_gif)
    win.spn_gframes = QSpinBox()
    win.spn_gframes.setRange(2, 8)
    win.spn_gframes.setValue(6)
    win.spn_gframes.setFixedWidth(56)
    win.spn_gframes.setToolTip("Frames 2-8")
    win.spn_gframes.valueChanged.connect(lambda _: win._schedule_refresh())
    gif_row.addWidget(win.spn_gframes)
    win.cmb_gifmode = QComboBox()
    win.cmb_gifmode.addItems(list(gif_modes))
    win.cmb_gifmode.setCurrentText("both")
    win.cmb_gifmode.setToolTip("Animation: phase / hue / both")
    win.cmb_gifmode.currentTextChanged.connect(lambda _: win._schedule_refresh())
    gif_row.addWidget(win.cmb_gifmode, 1)
    g.addLayout(gif_row)


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
    "build_custom_palette_section",
    "build_output_section",
]
