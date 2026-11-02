"""Animation section: video preview (mode/frames/fps/length/proxy/play).

Split out of app/ui/panels.py (mechanical move, no logic change).
Dissolve params + morph chain live in the MORPH page (panels/morph.py).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from app.ui.panels.widgets import tight, labeled_slider


def build_video_section(win, g: QVBoxLayout) -> None:
    """Single place to animate: Mode/Frames/FPS/Ping-pong + preview resolution.

    Preview = light proxy (Draft/HD/Full); export ALWAYS renders the full
    document, whatever the preview uses."""
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
    win.cmb_video_mode.currentTextChanged.connect(lambda _: win._on_video_mode_changed())
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
    win.cmb_video_frames.setToolTip("Suggested: 4/6/8/12/24/32/48/64 (editable, 2-64)")
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
    from PySide6.QtWidgets import QDoubleSpinBox as _DSpin

    win.spn_duration = _DSpin()
    win.spn_duration.setRange(0.0, 99.9)
    win.spn_duration.setSingleStep(0.5)
    win.spn_duration.setDecimals(1)
    win.spn_duration.setValue(5.0)
    win.spn_duration.setSuffix("s")
    win.spn_duration.setFixedWidth(72)
    win.spn_duration.setReadOnly(True)
    win.spn_duration.setButtonSymbols(_DSpin.NoButtons)
    win.spn_duration.setToolTip("Derived total = transitions + holds. Hold adds time; Frames add transitions; FPS retimes.")
    dur_row.addWidget(win.spn_duration)
    win.lbl_duration = QLabel("= 0.3s loop")
    win.lbl_duration.setWordWrap(True)
    win.lbl_duration.setObjectName("subtitleLabel")
    win.lbl_duration.setToolTip("Total = transitions + holds. Hold mandates: every tick adds still frames.")
    dur_row.addWidget(win.lbl_duration, 1)
    g.addLayout(dur_row)
    from PySide6.QtWidgets import QPushButton as _Btn
    from PySide6.QtWidgets import QSpinBox as _Spn

    bpm_row = QHBoxLayout()
    bpm_row.addWidget(QLabel("♫ BPM:"))
    win.spn_bpm = _Spn()
    win.spn_bpm.setRange(40, 250)
    win.spn_bpm.setValue(120)
    win.spn_bpm.setFixedWidth(58)
    win.spn_bpm.setToolTip("Beat grid: BPM of the theme (4/4 time)")
    bpm_row.addWidget(win.spn_bpm)
    bpm_row.addWidget(QLabel("Bars:"))
    win.spn_bars = _Spn()
    win.spn_bars.setRange(1, 16)
    win.spn_bars.setValue(2)
    win.spn_bars.setFixedWidth(48)
    win.spn_bars.setToolTip("Bars of the loop: target Length = bars×240/BPM")
    bpm_row.addWidget(win.spn_bars)
    win.btn_bpm_apply = _Btn("Set Hold")
    win.btn_bpm_apply.setToolTip("Solve Hold so the clip lands on the beat grid (dissolve/morph only)")
    win.btn_bpm_apply.clicked.connect(win._on_bpm_apply)
    bpm_row.addWidget(win.btn_bpm_apply, 1)
    g.addLayout(bpm_row)
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
    win.chk_video_pingpong.stateChanged.connect(lambda _: win._sync_duration_ui())
    play_row.addWidget(win.chk_video_pingpong, 1)
    g.addLayout(play_row)
    win._sync_duration_ui()
