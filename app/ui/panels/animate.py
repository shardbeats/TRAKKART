"""Animation sections: timeline layers, video preview.

Split out of app/ui/panels.py (mechanical move, no logic change).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from app.ui.panels.widgets import hlab, tight, labeled_slider


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
