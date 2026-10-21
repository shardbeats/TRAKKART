"""Animation section: video preview + Signal Drift.

Split out of app/ui/panels.py (mechanical move, no logic change).
Timeline layers and clip import were cut in the v1.4 trim: animation
runs from the still image only (GIF modes + drift + phase).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from app.ui.panels.widgets import hlab, tight, labeled_slider


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
    win.cmb_video_mode.setToolTip("March needs an ordered method · others move on any method")
    win.cmb_video_mode.currentTextChanged.connect(lambda _: win._schedule_refresh())
    win.cmb_video_mode.currentTextChanged.connect(lambda _: win._sync_anim_ui())
    row.addWidget(win.cmb_video_mode, 1)
    g.addLayout(row)
    win.lbl_mode_desc = QLabel("")
    win.lbl_mode_desc.setWordWrap(True)
    win.lbl_mode_desc.setObjectName("subtitleLabel")
    g.addWidget(win.lbl_mode_desc)
    win.sld_motion, _ = labeled_slider(win, g, "Motion:", 0, 300, 100, "Animation intensity: 0 = freeze · 100 = classic · up to 300", div=100.0)
    win.lbl_compat = QLabel("")
    win.lbl_compat.setWordWrap(True)
    win.lbl_compat.setObjectName("subtitleLabel")
    g.addWidget(win.lbl_compat)
    win.btn_use_ordered = QPushButton("Try bayer8")
    win.btn_use_ordered.setToolTip("Switch to an ordered method so March becomes visible")
    win.btn_use_ordered.clicked.connect(win._use_ordered_method)
    g.addWidget(win.btn_use_ordered)
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
    win.cmb_video_frames.currentTextChanged.connect(lambda _: win._sync_duration_ui())
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
    dur_row = QHBoxLayout()
    dur_row.addWidget(QLabel("Length:"))
    win.lbl_duration = QLabel("= 0.3s loop")
    win.lbl_duration.setWordWrap(True)
    win.lbl_duration.setObjectName("subtitleLabel")
    win.lbl_duration.setToolTip("Loop length = frames ÷ fps (read-only)")
    dur_row.addWidget(win.lbl_duration, 1)
    g.addLayout(dur_row)
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
    win._sync_duration_ui()
