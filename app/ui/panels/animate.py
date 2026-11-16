"""Animation section: video preview (mode/frames/fps/length/proxy/play).

Split out of app/ui/panels.py (mechanical move, no logic change).
Dissolve params + morph chain live in the MORPH page (panels/morph.py).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)
from app.ui.panels.widgets import tight, labeled_slider


def build_video_section(win, g: QVBoxLayout) -> None:
    """Single place to animate: Mode/Frames/FPS/Ping-pong + preview resolution.

    One Motion line, two sources (XOR): "Animate still" renders the
    still through the recipe; "Clip footage" plays the imported clip.
    Only the selected source is visible and only it writes the canvas.
    Preview = light proxy (Draft/HD/Full); export ALWAYS renders the full
    document, whatever the preview uses."""
    from PySide6.QtWidgets import QRadioButton, QWidget
    src_row = QHBoxLayout()
    src_row.addWidget(QLabel("Source:"))
    win.rb_motion_still = QRadioButton("Animate still")
    win.rb_motion_still.setToolTip("Procedural motion from the still (recipe FX, march, dissolve, morph)")
    win.rb_motion_still.setChecked(True)
    win.rb_motion_still.toggled.connect(lambda on: on and win._on_motion_source("still"))
    src_row.addWidget(win.rb_motion_still)
    win.rb_motion_clip = QRadioButton("Clip footage")
    win.rb_motion_clip.setToolTip("Imported MP4/GIF/WebP, dithered with the live recipe")
    win.rb_motion_clip.toggled.connect(lambda on: on and win._on_motion_source("clip"))
    src_row.addWidget(win.rb_motion_clip, 1)
    g.addLayout(src_row)

    win._motion_still_box = QWidget()
    still = QVBoxLayout(win._motion_still_box)
    still.setContentsMargins(0, 0, 0, 0)
    _build_still_source(win, still)
    g.addWidget(win._motion_still_box)

    win._motion_clip_box = QWidget()
    clip_lay = QVBoxLayout(win._motion_clip_box)
    clip_lay.setContentsMargins(0, 0, 0, 0)
    build_clip_section(win, clip_lay)
    win._motion_clip_box.setVisible(False)
    g.addWidget(win._motion_clip_box)
    win._sync_duration_ui()


def _build_still_source(win, g: QVBoxLayout) -> None:
    from app.gif import GIF_MODES

    win.chk_video = QCheckBox("Animate (motion preview)")
    win.chk_video.setToolTip("OFF = still dither · ON = full motion preview on canvas")
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
    from PySide6.QtWidgets import QWidget as _DetailsBox

    win.btn_motion_details = QPushButton("Details ▸")
    win.btn_motion_details.setCheckable(True)
    win.btn_motion_details.setChecked(False)
    win.btn_motion_details.setToolTip("Timing + preview resolution (Frames/FPS/Length/proxy)")
    win.btn_motion_details.toggled.connect(win._on_motion_details)
    g.addWidget(win.btn_motion_details)
    win._motion_details_box = _DetailsBox()
    details = QVBoxLayout(win._motion_details_box)
    details.setContentsMargins(0, 0, 0, 0)
    row2 = QHBoxLayout()
    row2.addWidget(QLabel("Frames:"))
    from PySide6.QtWidgets import QComboBox as _Cmb

    from app.gif import GIF_FRAMES_SUGGESTED, GIF_FPS_SUGGESTED

    win.cmb_video_frames = _Cmb()
    tight(win.cmb_video_frames, 6)
    win.cmb_video_frames.setEditable(True)
    win.cmb_video_frames.addItems([str(n) for n in GIF_FRAMES_SUGGESTED])
    win.cmb_video_frames.setCurrentText("6")
    win.cmb_video_frames.setToolTip("Suggested: 4/6/8/12/24/32/48/64/96/128/256 (editable, 2-256; non-particle modes follow Length)")
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
    details.addLayout(row2)
    dur_row = QHBoxLayout()
    dur_row.addWidget(QLabel("Length:"))
    from PySide6.QtWidgets import QDoubleSpinBox as _DSpin

    win.spn_duration = _DSpin()
    win.spn_duration.setRange(0.5, 60.0)
    win.spn_duration.setSingleStep(0.5)
    win.spn_duration.setDecimals(2)
    win.spn_duration.setValue(5.0)
    win.spn_duration.setSuffix("s")
    win.spn_duration.setFixedWidth(128)  # fits 60.00s + step buttons (was 72 read-only)
    win.spn_duration.setToolTip("Sacred total: edit to retime the clip (particle: solves Hold · rest: n = Length x FPS). Hold/Frames/FPS re-derive it.")
    win.spn_duration.valueChanged.connect(lambda _: win._on_duration_changed())
    dur_row.addWidget(win.spn_duration)
    win.lbl_duration = QLabel("= 0.3s loop")
    win.lbl_duration.setWordWrap(True)
    win.lbl_duration.setObjectName("subtitleLabel")
    win.lbl_duration.setToolTip("Total = transitions + holds. Hold mandates: every tick adds still frames.")
    dur_row.addWidget(win.lbl_duration, 1)
    details.addLayout(dur_row)
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
    details.addLayout(row3)
    win._motion_details_box.setVisible(False)
    g.addWidget(win._motion_details_box)
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
    stale_row = QHBoxLayout()
    win.lbl_stale = QLabel("")
    win.lbl_stale.setWordWrap(True)
    win.lbl_stale.setObjectName("subtitleLabel")
    win.lbl_stale.setVisible(False)
    stale_row.addWidget(win.lbl_stale, 1)
    win.btn_rebuild = QPushButton("Rebuild")
    win.btn_rebuild.setToolTip("Re-render the preview from current canvas + preset (one click, no stale frames)")
    win.btn_rebuild.setVisible(False)
    win.btn_rebuild.clicked.connect(win._on_video_rebuild)
    stale_row.addWidget(win.btn_rebuild)
    g.addLayout(stale_row)


def build_clip_section(win, g: QVBoxLayout) -> None:
    """Clip import + timeline: session-only, ≤120f, 720p proxy.

    The canvas shows the clip dithered through the live preset recipe
    (no raw/proxy toggle: what you see is what the export renders).
    Export lives in the Export window (File → Export → Clip section);
    batch stays stills-only by design (no clip path there). Only the
    selected Motion source is visible (see the Source radios above).
    """
    open_row = QHBoxLayout()
    win.btn_clip_open = QPushButton("Open clip...")
    win.btn_clip_open.setToolTip("Import MP4/GIF/WebP (≤120f, 720p proxy, session-only)")
    win.btn_clip_open.clicked.connect(win.open_clip_dialog)
    open_row.addWidget(win.btn_clip_open, 1)
    win.btn_clip_close = QPushButton("Close")
    win.btn_clip_close.setToolTip("Drop the session clip (stills untouched)")
    win.btn_clip_close.clicked.connect(win.close_clip)
    win.btn_clip_close.setEnabled(False)
    open_row.addWidget(win.btn_clip_close)
    g.addLayout(open_row)
    start_row = QHBoxLayout()
    start_row.addWidget(QLabel("Start at (s):"))
    from PySide6.QtWidgets import QDoubleSpinBox
    win.spn_clip_start_s = QDoubleSpinBox()
    win.spn_clip_start_s.setRange(0.0, 36000.0)
    win.spn_clip_start_s.setDecimals(1)
    win.spn_clip_start_s.setSingleStep(1.0)
    win.spn_clip_start_s.setValue(0.0)
    win.spn_clip_start_s.setToolTip("In-point in seconds (fast -ss seek for MP4, frame skip for GIF/WebP); 0 = from the start")
    start_row.addWidget(win.spn_clip_start_s, 1)
    g.addLayout(start_row)
    win.lbl_clip_info = QLabel("No clip (session-only, ≤120f · 720p proxy)")
    win.lbl_clip_info.setWordWrap(True)
    win.lbl_clip_info.setObjectName("subtitleLabel")
    g.addWidget(win.lbl_clip_info)
    trim_row = QHBoxLayout()
    trim_row.addWidget(QLabel("Trim:"))
    win.spn_clip_start = QSpinBox()
    win.spn_clip_start.setRange(0, 0)
    win.spn_clip_start.setToolTip("First frame of the range (inclusive)")
    win.spn_clip_start.valueChanged.connect(lambda _: win._on_clip_range())
    trim_row.addWidget(win.spn_clip_start)
    trim_row.addWidget(QLabel("–"))
    win.spn_clip_end = QSpinBox()
    win.spn_clip_end.setRange(0, 0)
    win.spn_clip_end.setToolTip("Last frame of the range (inclusive)")
    win.spn_clip_end.valueChanged.connect(lambda _: win._on_clip_range())
    trim_row.addWidget(win.spn_clip_end)
    win.lbl_clip_pos = QLabel("–")
    win.lbl_clip_pos.setToolTip("Timeline position (frame / total)")
    trim_row.addWidget(win.lbl_clip_pos, 1)
    g.addLayout(trim_row)
    play_row = QHBoxLayout()
    win.btn_clip_play = QPushButton("▶ Play")
    win.btn_clip_play.setToolTip("Play / pause the trimmed range, dithered (no audio in-app)")
    win.btn_clip_play.setEnabled(False)
    win.btn_clip_play.clicked.connect(win._on_clip_playpause)
    play_row.addWidget(win.btn_clip_play)
    win.sld_clip = QSlider(Qt.Horizontal)
    win.sld_clip.setRange(0, 0)
    win.sld_clip.setEnabled(False)
    win.sld_clip.setToolTip("Scrub the trimmed range, dithered (visual only, no audio)")
    win.sld_clip.valueChanged.connect(lambda v: win._on_clip_scrub(v))
    play_row.addWidget(win.sld_clip, 1)
    g.addLayout(play_row)
