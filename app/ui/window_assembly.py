"""Window assembly: frame, panel groups, action bar, preview canvas.

Pure construction: creates widgets on `win`, wires signals to `win.*`
methods (which delegate to controllers). No render/export logic here.
The window keeps `_setup_ui()` / `_setup_control_panel()` /
`_setup_action_bar()` / `_setup_previews()` by delegation.
"""

from __future__ import annotations


def setup_ui(win) -> None:
    from pathlib import Path

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    from app import __version__

    win.setWindowTitle(f"TRAKKART {__version__}")
    win.resize(1280, 780)
    win.setMinimumSize(1060, 640)
    from app.paths import bundle_path

    icon = bundle_path("icon.png")
    if icon.is_file():
        from PySide6.QtGui import QIcon

        win.setWindowIcon(QIcon(str(icon)))
    try:
        import sys

        from PySide6.QtWidgets import QApplication

        if getattr(sys, "frozen", False):
            # PyInstaller onefile: theme.qss ships at the bundle root (--add-data).
            qss_path = bundle_path("theme.qss")
        else:
            qss_path = Path(__file__).with_name("theme.qss")
        qss = qss_path.read_text(encoding="utf-8") if qss_path.exists() else ""
        if qss:
            try:
                app = QApplication.instance()
                if app is not None:
                    app.setStyleSheet(qss)
            except Exception:
                pass
            win.setStyleSheet(qss)
    except Exception:
        pass
    central = QWidget()
    win.setCentralWidget(central)
    col = QVBoxLayout(central)
    col.setContentsMargins(8, 8, 8, 8)
    col.setSpacing(4)

    header = QHBoxLayout()
    title = QLabel("TRAKKART")
    title.setObjectName("titleLabel")
    header.addWidget(title)
    header.addStretch()
    col.addLayout(header)

    root = QHBoxLayout()
    root.setSpacing(8)
    col.addLayout(root, 1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setMinimumWidth(360)
    scroll.setMaximumWidth(460)
    panel_host = QWidget()
    panel = QVBoxLayout(panel_host)
    panel.setContentsMargins(2, 2, 6, 2)
    scroll.setWidget(panel_host)
    left_col = QVBoxLayout()
    left_col.setSpacing(4)
    left_col.setContentsMargins(0, 0, 0, 0)
    left_col.addWidget(scroll, 1)
    root.addLayout(left_col, 0)
    win._action_bar = QVBoxLayout()
    win._action_bar.setSpacing(4)
    left_col.addLayout(win._action_bar)

    setup_control_panel(win, panel)
    setup_action_bar(win)
    setup_previews(win, root)

    win.statusBar().showMessage("TRAKKART ready")
    ver = QLabel(f"v{__version__}")
    ver.setObjectName("subtitleLabel")
    win.statusBar().addPermanentWidget(ver)
    win._sync_crop_label()


def setup_control_panel(win, panel) -> None:
    """7 accordion pages in the SAME scroll (test_layout: 1 QScrollArea).

    IMAGE = open/ops + canvas/crop · DITHER = preset/method/pixel/motif ·
    COLOR = adjusts + duotone/brand + palette library · FX = pre/grade/
    texture/glitch params next to the stack that orders them · DATAMOSH =
    flavor + amount + size + seed + Signal Drift (still position + anim speed) ·
    MORPH = particle dissolve params + morph image chain (A = canvas) ·
    MOTION = video preview (mode/frames/fps/length). Widget attribute names
    are unchanged, so controllers, presets and tests keep working.
    """
    from app.ui import panels as P
    from app.canvas import CROP_MODES, ratio_names
    from app.dither import METHODS

    add_page, win._accordion_pages = P.make_accordion(panel)

    image = add_page("IMAGE")
    P.build_image_section(win, image)
    P.build_canvas_section(win, image, ratio_names(), CROP_MODES)

    dither = add_page("DITHER")
    P.build_preset_section(win, dither)
    P.build_method_section(win, dither, METHODS)
    P.build_pixel_section(win, dither)
    P.build_motif_section(win, dither)

    color = add_page("COLOR")
    P.build_color_section(win, color)
    P.build_tint_section(win, color)
    P.build_custom_palette_section(win, color)

    fx = add_page("FX")
    P.build_pre_section(win, fx)
    P.build_grade_section(win, fx)
    P.build_texture_section(win, fx)
    P.build_glitch_section(win, fx)
    P.build_fx_stack_section(win, fx)

    mosh = add_page("DATAMOSH")
    P.build_mosh_section(win, mosh)
    P.build_drift_section(win, mosh)

    morph = add_page("MORPH")
    P.build_morph_section(win, morph)

    motion = add_page("MOTION")
    P.build_video_section(win, motion)
    win._sync_motif_visibility()
    panel.addStretch()


def setup_action_bar(win) -> None:
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
    )

    from app.ui.dialog_fields import build_jobs_spin

    win.btn_export = QPushButton("Export…")
    win.btn_export.setToolTip("Export with options (Ctrl+Shift+S) · Quick export (Ctrl+S)")
    win.btn_export.setObjectName("exportBtn")
    win.btn_export.clicked.connect(lambda: win.export(False))
    win._action_bar.addWidget(win.btn_export)

    batch_row = QHBoxLayout()
    win.btn_batch = QPushButton("Batch folder...")
    win.btn_batch.setToolTip("Process every image in a folder with the current preset")
    win.btn_batch.clicked.connect(win.run_batch_dialog)
    batch_row.addWidget(win.btn_batch, 1)
    win.btn_cancel = QPushButton("X")
    win.btn_cancel.setToolTip("Cancel batch")
    win.btn_cancel.clicked.connect(win.cancel_batch)
    win.btn_cancel.hide()
    batch_row.addWidget(win.btn_cancel)
    from PySide6.QtWidgets import QCheckBox

    win.chk_batch_drop = QCheckBox("Drop=Batch")
    win.chk_batch_drop.setToolTip("OFF = dropping only loads images. ON = dropping a folder asks for confirmation and processes it.")
    win.chk_batch_drop.setChecked(False)
    batch_row.addWidget(win.chk_batch_drop)
    batch_row.addWidget(QLabel("Jobs:"))
    win.spn_jobs = build_jobs_spin(1)
    win.spn_jobs.setFixedWidth(56)
    batch_row.addWidget(win.spn_jobs)
    win._action_bar.addLayout(batch_row)

    win.progress = QProgressBar()
    win.progress.setRange(0, 100)
    win.progress.setValue(0)
    win.progress.hide()
    win._action_bar.addWidget(win.progress)
    win.lbl_status = QLabel("Open an image to start.")
    win.lbl_status.setWordWrap(True)
    win._action_bar.addWidget(win.lbl_status)


def setup_previews(win, root) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSizePolicy,
        QSlider,
        QVBoxLayout,
        QWidget,
    )

    previews = QHBoxLayout()
    previews.setSpacing(8)
    res_col = QVBoxLayout()
    title_row = QHBoxLayout()
    win.lbl_res_title = QLabel("COVER")
    win.lbl_res_title.setObjectName("previewTitle")
    win.lbl_res_title.setAlignment(Qt.AlignCenter)
    title_row.addWidget(win.lbl_res_title, 1)
    # Hold-to-compare: hold (or Space) = ORIGINAL.
    win.btn_compare = QPushButton("Hold to compare")
    win.btn_compare.setToolTip("Hold to see ORIGINAL (or hold Space). Release to go back.")
    win.btn_compare.setMinimumWidth(140)
    win.btn_compare.pressed.connect(win._compare_pressed)
    win.btn_compare.released.connect(win._compare_released)
    title_row.addWidget(win.btn_compare)
    res_col.addLayout(title_row)
    # Video toolbar: scrub + counter (visible only in Video mode).
    win._video_bar = QHBoxLayout()
    win.sld_video = QSlider(Qt.Horizontal)
    win.sld_video.setRange(0, 0)
    win.sld_video.setValue(0)
    win.sld_video.valueChanged.connect(win._on_video_scrub)
    win._video_bar.addWidget(win.sld_video, 1)
    win.lbl_video_pos = QLabel("0/0")
    win.lbl_video_pos.setMinimumWidth(52)
    win.lbl_video_pos.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    win._video_bar.addWidget(win.lbl_video_pos)
    win._video_bar_widget = QWidget()
    win._video_bar_widget.setLayout(win._video_bar)
    win._video_bar_widget.setVisible(False)
    res_col.addWidget(win._video_bar_widget)
    win.lbl_res = QLabel("NO IMAGE\n\nDrop a file onto the window · Ctrl+O to open\nHelp → Quick tour for the 5-step tour")
    win.lbl_res.setObjectName("previewFrame")
    win.lbl_res.setAlignment(Qt.AlignCenter)
    win.lbl_res.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    win.lbl_res.setMinimumSize(200, 200)
    res_col.addWidget(win.lbl_res, 1)
    # Wipe compare: drag divider (ORIGINAL left, result right). 0 = off.
    wipe_row = QHBoxLayout()
    wipe_row.addWidget(QLabel("Wipe:"))
    win.sld_wipe = QSlider(Qt.Horizontal)
    win.sld_wipe.setRange(0, 100)
    win.sld_wipe.setValue(0)
    win.sld_wipe.setToolTip("Wipe compare: drag to reveal ORIGINAL on the left (0 = off)")
    win.sld_wipe.valueChanged.connect(win._on_wipe_changed)
    wipe_row.addWidget(win.sld_wipe, 1)
    res_col.addLayout(wipe_row)
    previews.addLayout(res_col, 1)
    root.addLayout(previews, 1)
