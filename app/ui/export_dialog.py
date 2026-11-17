"""Export dialog — classic editor style: name, destination, outputs, collision.

The engine (`export_bundle`/`export_with_options`) never asks;
this dialog asks everything and previews what will be written.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.exporter import (
    MAX_SIDE,
    MIN_SIDE,
    ExportOptions,
    ExportSelection,
    mp4_name,
    plan_export,
    sanitize_base,
)
from app.ui.panels.widgets import hlab


def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"~{n / (1024 * 1024):.1f}MB"
    if n >= 1024:
        return f"~{n // 1024}KB"
    return f"~{n}B"


class ExportDialog(QDialog):
    """What, where and under which name. `options()` only valid after Accept."""

    def __init__(
        self,
        img: Image.Image,
        meta: dict | None,
        base: str = "trakkart_cover",
        out_dir: str | Path = ".",
        selection: ExportSelection | None = None,
        gif_frames: int = 6,
        gif_mode: str = "both",
        gif_fps: int = 8,
        gif_pingpong: bool = False,
        vector_cells: tuple[int, int] | None = None,
        preset=None,
        size: int = 3000,
        format: str = "png",
        quality: int = 90,
        mp4_size: str = "1080p",
        mp4: bool = False,
        webp: bool = False,
        apng: bool = False,
        tiff: bool = False,
        social: bool = False,
        dpi: int = 300,
        sep: bool = False,
        sep_trap: bool = False,
        sp404: bool = False,
        clip_info: dict | None = None,
        clip_fps: int | None = None,
        clip_track: str = "",
        still_enabled: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setMinimumWidth(480)
        self.resize(560, 820)
        self._img = img
        self._meta = meta or {}
        self._vector_cells = vector_cells
        self._preset = preset  # kept for compat; preview lives in Video mode
        self._gif_count = max(1, int(gif_frames))
        self._ready = False  # __init__ signals paint nothing yet
        self._track_dur_cache: dict = {}  # audio probe memo (plan-only)
        self._still_enabled = bool(still_enabled) and img is not None
        self._clip_info = dict(clip_info) if clip_info else None

        col = QVBoxLayout(self)
        # Content scrolls on short screens; the action bar stays pinned.
        from PySide6.QtWidgets import QFrame, QScrollArea, QWidget

        outer = col
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self._scroll = scroll
        # -- file name (dedicated section: base + reset + sanitized preview) --
        hlab(col, "File name:")
        name_row = QHBoxLayout()
        self._init_base = base
        self.edit_base = QLineEdit(base)
        self.edit_base.setPlaceholderText("trakkart_cover")
        self.edit_base.setToolTip("Base for every file: unsafe characters become _")
        self.edit_base.textChanged.connect(self._refresh_plan)
        name_row.addWidget(self.edit_base, 1)
        self.btn_name_reset = QPushButton("Reset")
        self.btn_name_reset.setToolTip("Restore the initial name")
        self.btn_name_reset.clicked.connect(lambda: self.edit_base.setText(self._init_base))
        name_row.addWidget(self.btn_name_reset)
        col.addLayout(name_row)
        self.lbl_basename = QLabel()
        self.lbl_basename.setWordWrap(True)
        self.lbl_basename.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_basename)
        # -- destination --
        from app.ui.dialog_fields import (build_folder_row, build_format_quality,
                                          normalize_gif_spec)

        dest_row, self.edit_dir, self.btn_browse = build_folder_row(
            "Folder:", str(out_dir), self, on_browse=self._browse)
        col.addLayout(dest_row)
        # -- single document: size comes from CANVAS, shown here only --
        self._doc_size = max(MIN_SIDE, min(MAX_SIDE, int(size)))
        doc_row = QHBoxLayout()
        doc_row.addWidget(QLabel("Document:"))
        self.lbl_dims = QLabel()
        self.lbl_dims.setMinimumWidth(130)
        self.lbl_dims.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_dims.setToolTip("Main image renders at the CANVAS document size")
        doc_row.addWidget(self.lbl_dims, 1)
        col.addLayout(doc_row)
        # -- format (extension rules like classic editors; here the combo) --
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.cmb_format, self.spn_quality = build_format_quality(format, quality)
        self.cmb_format.setToolTip("PNG: lossless, ideal dither · JPG: small, artifacts · WebP: small, modern")
        self.cmb_format.currentTextChanged.connect(self._refresh_plan)
        fmt_row.addWidget(self.cmb_format, 1)
        fmt_row.addWidget(QLabel("Quality:"))
        self.spn_quality.setToolTip("Quality for JPG/WebP (PNG ignores it)")
        self.spn_quality.valueChanged.connect(self._refresh_plan)
        fmt_row.addWidget(self.spn_quality)
        col.addLayout(fmt_row)
        self.chk_lossless = QCheckBox("Lossless (force PNG)")
        self.chk_lossless.setToolTip("Ignores format combo: exports main + thumb as PNG")
        self.chk_lossless.setChecked(False)
        self.chk_lossless.stateChanged.connect(self._on_lossless)
        # -- resolution tags (print; distributors ignore DPI, RISO does not) --
        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("DPI:"))
        self.spn_dpi = QSpinBox()
        self.spn_dpi.setRange(72, 600)
        self.spn_dpi.setValue(max(72, min(600, int(dpi or 300))))
        self.spn_dpi.setFixedWidth(80)
        self.spn_dpi.setToolTip("Resolution tags on JPG/PNG/TIFF + separations + metadata")
        self.spn_dpi.valueChanged.connect(self._refresh_plan)
        dpi_row.addWidget(self.spn_dpi)
        dpi_row.addWidget(QLabel("(tags only: pixels never change)"))
        dpi_row.addStretch()
        col.addLayout(dpi_row)
        self.chk_image = QCheckBox("Main image")
        self.chk_thumb = QCheckBox("Social thumb (1080p)")
        self.chk_vector = QCheckBox("Vector SVG")
        self.chk_anim = QCheckBox("Animated GIF")
        self.chk_meta = QCheckBox("Metadata JSON")
        self.chk_black = QCheckBox("Black vector (print ink only)")
        self.chk_black.setToolTip("SVG with black ink on transparent (no paper rects)")
        self.chk_black.setChecked(bool(getattr(selection, "black_vector", False)))
        sel = selection or ExportSelection()
        self.chk_image.setChecked(sel.image)
        self.chk_thumb.setChecked(sel.thumb_1080p)
        self.chk_vector.setChecked(sel.vector)
        self.chk_vector.setToolTip("Vector for logos/merch (no post-fx)")
        self.chk_anim.setChecked(sel.anim)
        self.chk_anim.setToolTip("Animation for socials (Pillow only)")
        self.chk_webp = QCheckBox("Animated WebP")
        self.chk_webp.setChecked(bool(webp))
        self.chk_webp.setToolTip("Same frames as the GIF, ~1/3 the weight, full color (Pillow only)")
        self.chk_apng = QCheckBox("Animated PNG (APNG)")
        self.chk_apng.setChecked(bool(apng))
        self.chk_apng.setToolTip("Same frames as the GIF, full color like WebP (Pillow only; first frame doubles as the still)")
        self.chk_tiff = QCheckBox("Print TIFF (LZW)")
        self.chk_tiff.setChecked(bool(tiff))
        self.chk_tiff.setToolTip("Full-doc lossless TIFF with DPI tags for stores/print")
        self.chk_social = QCheckBox("Social pack (16:9 + 9:16 + 1:1)")
        self.chk_social.setChecked(bool(social))
        self.chk_social.setToolTip("One click, same render: 1280×720 + 1080×1920 + 1080×1080, center-anchored (grids crop to center)")
        self.chk_sep = QCheckBox("Ink separations (print)")
        self.chk_sep.setChecked(bool(sep))
        self.chk_sep.setToolTip("One PNG per palette ink + registration marks (RISO/screen print)")
        self.chk_trap = QCheckBox("RISO trap (1px ink expand)")
        self.chk_trap.setChecked(bool(sep_trap))
        self.chk_trap.setToolTip("Expand every ink area by 1px so small misregistrations don't show white hairlines")
        self.chk_sp404 = QCheckBox("SP-404MKII BMP (128×64 1-bit)")
        self.chk_sp404.setChecked(bool(sp404))
        self.chk_sp404.setToolTip("Roland SP-404MKII still: one 128×64 1-bit BMP of the current image (rename it to startup_N/screen_saver_N yourself)")
        self.chk_meta.setChecked(sel.metadata)
        from app.video_io import has_video as _has_video

        self._video_ok = bool(_has_video())
        self.chk_mp4 = QCheckBox("MP4 video")
        self.chk_mp4.setChecked(bool(mp4))
        if self._video_ok:
            self.chk_mp4.setToolTip("H.264 clip at MP4 size below (video backend present)")
        else:
            self.chk_mp4.setEnabled(False)
            self.chk_mp4.setToolTip("Settings → Extras → Install video")
        for chk in (self.chk_image, self.chk_thumb,
                    self.chk_vector, self.chk_anim, self.chk_webp, self.chk_apng, self.chk_tiff, self.chk_social, self.chk_sep, self.chk_trap, self.chk_meta,
                    self.chk_black, self.chk_mp4, self.chk_sp404):
            chk.stateChanged.connect(self._refresh_plan)
        if not self._still_enabled:
            # Clip-only export (no still open): still outputs stay off.
            for chk in (self.chk_image, self.chk_thumb,
                        self.chk_vector, self.chk_anim, self.chk_webp, self.chk_apng, self.chk_tiff, self.chk_social, self.chk_sep, self.chk_trap, self.chk_meta,
                        self.chk_black, self.chk_mp4, self.chk_sp404, self.chk_lossless):
                try:
                    chk.setChecked(False)
                    chk.setEnabled(False)
                except Exception:  # noqa: BLE001
                    pass
            self.cmb_format.setEnabled(False)
            self.spn_quality.setEnabled(False)
            self.spn_dpi.setEnabled(False)
        # -- grouped outputs, top to bottom: stills -> motion -> print --
        hlab(col, "Stills:")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)
        stills = (self.chk_image, self.chk_thumb, self.chk_vector,
                  self.chk_black, self.chk_social, self.chk_tiff,
                  self.chk_meta, self.chk_lossless)
        for i, chk in enumerate(stills):
            grid.addWidget(chk, i // 2, i % 2)
        col.addLayout(grid)
        hlab(col, "Motion:")
        for chk in (self.chk_anim, self.chk_webp, self.chk_apng, self.chk_mp4):
            col.addWidget(chk)
        from PySide6.QtWidgets import QComboBox as _Cmb

        from app.gif import MP4_SIZES

        mp4_row = QHBoxLayout()
        mp4_row.addWidget(QLabel("MP4 size:"))
        self.cmb_mp4_size = _Cmb()
        self.cmb_mp4_size.addItems(list(MP4_SIZES))
        cur_mp4 = str(mp4_size) if str(mp4_size) in MP4_SIZES else "1080p"
        self.cmb_mp4_size.setCurrentText(cur_mp4)
        self.cmb_mp4_size.setToolTip("MP4 resolution (main image always stays at canvas size). 1080p is social-ready; Canvas is full-doc and heavy.")
        self.cmb_mp4_size.currentTextChanged.connect(self._refresh_plan)
        mp4_row.addWidget(self.cmb_mp4_size, 1)
        col.addLayout(mp4_row)
        # -- animation: no duplicates (edited only in VIDEO); on/off here --
        self._gif_spec = normalize_gif_spec(gif_frames, gif_mode, gif_fps, gif_pingpong)
        self.lbl_gifspec = QLabel()
        self.lbl_gifspec.setWordWrap(True)
        self.lbl_gifspec.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_gifspec)
        self._sync_gifspec_label()
        hlab(col, "Print & device:")
        print_grid = QGridLayout()
        print_grid.setHorizontalSpacing(12)
        print_grid.setVerticalSpacing(2)
        print_grid.addWidget(self.chk_sep, 0, 0)
        print_grid.addWidget(self.chk_trap, 0, 1)
        print_grid.addWidget(self.chk_sp404, 1, 0, 1, 2)
        col.addLayout(print_grid)
        # -- clip (session footage): rendered here, not in the MOTION panel --
        if self._clip_info is not None:
            hlab(col, "Clip (session footage):")
            self.lbl_clipinfo = QLabel()
            self.lbl_clipinfo.setWordWrap(True)
            self.lbl_clipinfo.setObjectName("subtitleLabel")
            col.addWidget(self.lbl_clipinfo)
            try:
                ci = self._clip_info
                self.lbl_clipinfo.setText(
                    f"{ci.get('name', 'clip')} · {ci.get('span', ci.get('frames', 0))}f "
                    f"@{ci.get('fps', 24)}fps (trim {ci.get('start', 0)}-{ci.get('end', 0)}"
                    f" = {ci.get('duration', 0.0):.1f}s, dithered)")
                if ci.get("truncated"):
                    self.lbl_clipinfo.setText(self.lbl_clipinfo.text() + " · capped at 120f")
            except Exception:  # noqa: BLE001
                pass
            self.chk_clip_gif = QCheckBox("Clip GIF (trimmed range, dithered)")
            self.chk_clip_mp4 = QCheckBox("Clip MP4 (libx264, dithered)")
            self.chk_clip_zip = QCheckBox("Clip frame ZIP (PNG sequence)")
            for chk in (self.chk_clip_gif, self.chk_clip_mp4, self.chk_clip_zip):
                chk.setChecked(False)
                chk.stateChanged.connect(self._refresh_plan)
                col.addWidget(chk)
            self.chk_clip_full = QCheckBox("Full length MP4 (streaming, from in-point)")
            self.chk_clip_full.setChecked(False)
            self.chk_clip_full.setToolTip(
                "MP4 renders the whole clip from Start at (s), streamed in 120f windows "
                "(preview + GIF/ZIP stay on the trim range). Capped at 3600f.")
            self.chk_clip_full.stateChanged.connect(self._refresh_plan)
            self.chk_clip_full.setEnabled(False)  # needs MP4 on (toggled below)
            self.chk_clip_mp4.stateChanged.connect(
                lambda _s: self.chk_clip_full.setEnabled(
                    bool(self.chk_clip_mp4.isChecked()) and self._video_ok))
            col.addWidget(self.chk_clip_full)
            if not self._video_ok:
                self.chk_clip_mp4.setEnabled(False)
                self.chk_clip_mp4.setToolTip("Settings → Extras → Install video")
                self.chk_clip_full.setEnabled(False)
                self.chk_clip_full.setToolTip("Settings → Extras → Install video")
            clip_fps_row = QHBoxLayout()
            clip_fps_row.addWidget(QLabel("Clip FPS:"))
            self.spn_clip_fps = QSpinBox()
            self.spn_clip_fps.setRange(2, 60)
            try:
                default_fps = int(clip_fps if clip_fps is not None
                                  else self._clip_info.get("fps", 24))
            except (TypeError, ValueError):
                default_fps = 24
            self.spn_clip_fps.setValue(max(2, min(60, default_fps)))
            self.spn_clip_fps.setToolTip("Clip export fps (preview Length = frames / fps)")
            self.spn_clip_fps.valueChanged.connect(self._refresh_plan)
            clip_fps_row.addWidget(self.spn_clip_fps)
            col.addLayout(clip_fps_row)
            clip_q_row = QHBoxLayout()
            clip_q_row.addWidget(QLabel("Clip size:"))
            from PySide6.QtWidgets import QComboBox as _QC

            self.cmb_clip_res = _QC()
            self.cmb_clip_res.addItems(["Proxy 720p (light)", "Source ≤1920 (heavy)"])
            self.cmb_clip_res.setToolTip(
                "MP4 pixels: Proxy reuses the 720p session frames (fast); "
                "Source re-decodes the trim/full range at native size (≤1920, heavy). "
                "GIF/ZIP stay proxy.")
            self.cmb_clip_res.currentIndexChanged.connect(lambda _i: self._refresh_plan())
            clip_q_row.addWidget(self.cmb_clip_res, 1)
            clip_q_row.addWidget(QLabel("Quality:"))
            self.cmb_clip_q = _QC()
            self.cmb_clip_q.addItems(["Balanced (q8)", "Compact (q5, smaller)", "High (q10, larger)"])
            self.cmb_clip_q.setToolTip("MP4 quality: imageio q (higher = bigger/sharper grain).")
            self.cmb_clip_q.currentIndexChanged.connect(lambda _i: self._refresh_plan())
            col.addLayout(clip_q_row)
            track_row = QHBoxLayout()
            track_row.addWidget(QLabel("Track:"))
            self.edit_track = QLineEdit(str(clip_track or ""))
            self.edit_track.setPlaceholderText("Soundtrack (optional, MP4 only)")
            self.edit_track.setToolTip("Audio file muxed at MP4 export (-c:v copy -c:a aac, cut at clip end); empty = silent MP4")
            self.edit_track.textChanged.connect(lambda _t: self._refresh_plan())
            track_row.addWidget(self.edit_track, 1)
            self.btn_track = QPushButton("Browse...")
            self.btn_track.setToolTip("Pick the soundtrack (offline file, never analyzed)")
            self.btn_track.clicked.connect(self._browse_track)
            track_row.addWidget(self.btn_track)
            self.btn_track_clear = QPushButton("X")
            self.btn_track_clear.setFixedWidth(32)
            self.btn_track_clear.setToolTip("Clear the soundtrack (back to silent MP4)")
            self.btn_track_clear.clicked.connect(lambda: self.edit_track.setText(""))
            track_row.addWidget(self.btn_track_clear)
            col.addLayout(track_row)
        else:
            self.chk_clip_gif = self.chk_clip_mp4 = self.chk_clip_zip = None
            self.chk_clip_full = None
            self.cmb_clip_res = self.cmb_clip_q = None
        # -- distributor readiness (honest hints, nothing blocked) --
        self.lbl_distro = QLabel()
        self.lbl_distro.setWordWrap(True)
        self.lbl_distro.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_distro)
        # -- collision: always rename (never lose a file) --
        self.lbl_policy = QLabel("Existing files are kept: repeats save as name_2, name_3…")
        self.lbl_policy.setWordWrap(True)
        self.lbl_policy.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_policy)
        # -- plan (classic editors show estimated size: here the list + ~weight) --
        hlab(col, "Files to write:")
        self.list_files = QListWidget()
        self.list_files.setMinimumHeight(110)
        self.list_files.setMaximumHeight(180)
        col.addWidget(self.list_files, 1)
        self.lbl_total = QLabel()
        col.addWidget(self.lbl_total)
        self.lbl_exists = QLabel()
        self.lbl_exists.setWordWrap(True)
        self.lbl_exists.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_exists)
        # -- buttons --
        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bar.addWidget(self.btn_cancel)
        self.btn_export = QPushButton("Export")
        self.btn_export.setObjectName("exportBtn")
        self.btn_export.setDefault(True)
        self.btn_export.clicked.connect(self._on_export)
        bar.addWidget(self.btn_export)
        outer.addLayout(bar)

        self._ready = True
        self._refresh_plan()

    def _on_lossless(self) -> None:
        on = self.chk_lossless.isChecked()
        self.cmb_format.setEnabled(not on)
        self.spn_quality.setEnabled(not on)
        self._refresh_plan()

    # -- live plan --
    def _current_selection(self) -> ExportSelection:
        return ExportSelection(
            image=self.chk_image.isChecked(),
            thumb_1080p=self.chk_thumb.isChecked(),
            vector=self.chk_vector.isChecked(),
            anim=self.chk_anim.isChecked(),
            metadata=self.chk_meta.isChecked(),
            black_vector=self.chk_black.isChecked(),
        )

    def _current_size(self) -> int:
        return int(getattr(self, "_doc_size", 3000))

    def _doc_wh(self) -> tuple[int, int]:
        from app.exporter import _main_dims

        try:
            return _main_dims(self._meta, self._current_size())
        except Exception:  # noqa: BLE001
            s = self._current_size()
            return (s, s)

    def _clip_wh(self) -> tuple[int, int]:
        """Proxy dims for clip weight estimates (0, 0 when unknown)."""
        try:
            w, h = (self._clip_info or {}).get("size", [0, 0])
            return max(0, int(w)), max(0, int(h))
        except (TypeError, ValueError):
            return (0, 0)

    def _clip_res(self) -> str:
        """Clip MP4 pixels: "source" only when the combo says so."""
        try:
            if (self.cmb_clip_res is not None
                    and self.cmb_clip_res.currentIndex() == 1):
                return "source"
        except Exception:  # noqa: BLE001
            pass
        return "proxy"

    def _clip_q(self) -> int:
        """Clip MP4 quality q (5/8/10, default Balanced)."""
        try:
            idx = int(self.cmb_clip_q.currentIndex())
        except Exception:  # noqa: BLE001
            return 8
        return {0: 8, 1: 5, 2: 10}.get(idx, 8)

    def _clip_est_wh(self) -> tuple[int, int]:
        """Estimate dims for the selected res (source probe, proxy fallback)."""
        if self._clip_res() == "source":
            try:
                from app.clip import CLIP_SOURCE_SIDE, _proxy_dims, source_dims

                path = str((self._clip_info or {}).get("path", "") or "")
                nat = source_dims(path) if path else None
                if nat:
                    return _proxy_dims(int(nat[0]), int(nat[1]), CLIP_SOURCE_SIDE)
            except Exception:  # noqa: BLE001
                pass
        return self._clip_wh()

    def _clip_noise(self) -> float:
        """Peak animated noise (grain/dust) for the clip estimate.

        Preset flats, envelope-aware on grain (peak over the curve).
        Rough by design; the estimator documents ±2x.
        """
        base = 0.0
        try:
            p = getattr(self, "_preset", None)
            base = max(float(getattr(p, "grain", 0.0) or 0.0),
                       float(getattr(p, "dust", 0.0) or 0.0))
        except (TypeError, ValueError):
            base = 0.0
        try:
            win = self.parent()
            env = dict(getattr(win, "_envelopes", {}) or {})
            if env:
                from app.envelopes import envelope_peak

                base = max(base, float(envelope_peak(env, "grain", base)))
        except Exception:  # noqa: BLE001
            pass
        return max(0.0, min(100.0, base))

    def _clip_short_mp4_est(self) -> int:
        """Weight estimate for the trim-range clip MP4 (0 when unknown)."""
        try:
            from app.gif import estimate_clip_mp4

            n = max(0, int((self._clip_info or {}).get("span", 0)))
            w, h = self._clip_est_wh()
            if n <= 0 or w <= 0 or h <= 0:
                return 0
            return int(estimate_clip_mp4(w, h, n, self._clip_noise(), self._clip_q()))
        except Exception:  # noqa: BLE001
            return 0

    def _clip_track_warn(self, full_video_len: float | None = None) -> str:
        """Track-vs-clip note for the plan ("" = nothing to say).

        Missing track file -> silent MP4 (mux rule); known durations go
        through `track_fit_note`. Probes are memoized per path so typing
        in the track field never re-spawns ffmpeg.
        """
        try:
            track = str(self.edit_track.text()).strip()
        except Exception:  # noqa: BLE001
            return ""
        if not track:
            return ""
        from pathlib import Path as _P

        if not _P(track).is_file():
            return "Track not found → silent MP4."
        try:
            if track not in self._track_dur_cache:
                from app.clip import audio_duration

                try:
                    self._track_dur_cache[track] = audio_duration(track)
                except Exception:  # noqa: BLE001
                    self._track_dur_cache[track] = None
            track_s = self._track_dur_cache.get(track)
        except Exception:  # noqa: BLE001
            track_s = None
        if track_s is None:
            return "Track length unknown."
        try:
            if full_video_len is not None and full_video_len > 0:
                video_len = float(full_video_len)
            else:
                video_len = float((self._clip_info or {}).get("duration", 0.0) or 0.0)
        except (TypeError, ValueError):
            return ""
        try:
            from app.clip import track_fit_note

            note = track_fit_note(track_s, video_len)
        except Exception:  # noqa: BLE001
            return ""
        return f"Track: {note}" if note else ""

    def _refresh_plan(self) -> None:
        if not getattr(self, "_ready", False):
            return
        # R8: particle GIF plan once (256f cap, chain unknown -> 1 segment):
        # transitions + forms feed the hold-collapse-aware anim estimate
        # below AND the WebP line (same capped list).
        go_d = self._gif_opts()
        gif_trans = None
        gif_forms = None
        try:
            mode_d = str(go_d.get("mode", "both"))
            if mode_d in ("dissolve", "morph") and getattr(self, "_preset", None) is not None:
                from app.gif import MAX_TOTAL_FRAMES, plan_dissolve as _plan_d

                p_d = getattr(self, "_preset", None)
                hold_d = float(getattr(p_d, "dissolve_hold", 0.0) or 0.0)
                plan_d = _plan_d(int(go_d["frames"]),
                                 1, max(2, min(60, int(go_d.get("fps", 8)))),
                                 hold_d, None, cap=MAX_TOTAL_FRAMES)
                gif_trans, gif_forms = int(plan_d["n_trans"]), 2
        except Exception:  # noqa: BLE001
            gif_trans, gif_forms = None, None
        try:
            from app.canvas import output_budget_note, output_megapixels
            from app.ui.widgets import set_warning

            w, h = self._doc_wh()
            note = output_budget_note(w, h)
            if not self._still_enabled:
                self.lbl_dims.setText("— (clip only, no stills)")
                self.lbl_dims.setToolTip("Open a still to enable the document outputs")
                set_warning(self.lbl_dims, False)
            else:
                self.lbl_dims.setText(f"{w}×{h} (from CANVAS)")
                self.lbl_dims.setToolTip("Main image renders at the CANVAS document size")
            if note and self._still_enabled:
                self.lbl_dims.setText(
                    f"{w}×{h} (from CANVAS) · ⚠ {output_megapixels(w, h):g} MP")
                self.lbl_dims.setToolTip(
                    "Main image renders at the CANVAS document size\n" + note)
            set_warning(self.lbl_dims, bool(note))
            safe = sanitize_base(self.edit_base.text().strip() or "cover")
            self.lbl_basename.setText(f"Files start with: {safe}")
            opts = ExportOptions(
                base=self.edit_base.text().strip() or "cover",
                selection=self._current_selection(),
                overwrite="rename",
                size=self._current_size(),
                format=self.cmb_format.currentText(),
                quality=int(self.spn_quality.value()),
                dpi=int(self.spn_dpi.value()),
            )
            if not self._still_enabled or self._img is None:
                plan = []  # clip-only: no still files planned
            else:
                plan = plan_export(
                    self._img, opts, meta=self._meta,
                    has_vector=True, has_gif=True,
                    extra={"vector_cells": self._vector_cells or (0, 0),
                           "gif_frames": int(go_d["frames"]),
                           "gif_size": int(go_d["size"]),
                           "gif_trans": gif_trans, "gif_forms": gif_forms},
                )
        except ValueError:
            plan = []
        self.list_files.clear()
        total = 0
        for _, fname, est in plan:
            self.list_files.addItem(f"{fname}  ({_fmt_size(est)})")
            total += est
        n = len(plan)
        webp_fname = ""
        apng_fname = ""
        mp4_fname = ""
        mp4_hint = ""
        if self.chk_mp4.isChecked() and self._video_ok:
            try:
                dw, dh = self._doc_wh()
                go = self._gif_opts()
                nf = int(go["frames"])
                fps_m = max(2, min(60, int(go.get("fps", 8))))
                mode_m = str(go.get("mode", "both"))
                total_m = nf
                n_trans_m = min(64, max(2, nf))
                if mode_m in ("dissolve", "morph") and getattr(self, "_preset", None) is not None:
                    try:
                        from app.gif import MAX_MP4_FRAMES, plan_dissolve

                        p = getattr(self, "_preset", None)
                        hold_m = float(getattr(p, "dissolve_hold", 0.0) or 0.0)
                        # Chain length unknown here (session-only); 1 segment
                        # is the conservative estimate for the plan line.
                        # Hold-manda: derived total, no Length target.
                        plan_m = plan_dissolve(nf, 1, fps_m, hold_m,
                                               None, cap=MAX_MP4_FRAMES)
                        total_m = int(plan_m["total"])
                        n_trans_m = int(plan_m["n_trans"])
                    except Exception:  # noqa: BLE001
                        total_m = nf
                from app.gif import estimate_mp4, mp4_dims

                mw, mh = mp4_dims(dw, dh, str(go.get("mp4_size", "1080p")))
                est = estimate_mp4(mw, mh, n_trans_m, max(0, total_m - n_trans_m))
                mp4_fname = mp4_name(sanitize_base(self.edit_base.text().strip() or "cover"))
                self.list_files.addItem(f"{mp4_fname}  ({_fmt_size(est)} · {mw}×{mh})")
                total += est
                n += 1
                if est > 400 * 1024 * 1024:
                    mp4_hint = (f"⚠ MP4 ~{_fmt_size(est)} — heavy: pick 720p, "
                                "30fps, less Hold or fewer frames.")
                elif est > 100 * 1024 * 1024:
                    mp4_hint = (f"MP4 ~{_fmt_size(est)} — consider 720p / "
                                "30fps / less Hold.")
                # R2 Canvas check (size half lives here: mp4_size is dialog-local).
                actual_m = total_m / max(1, fps_m)
                if abs(dw / max(1, dh) - 9 / 16) < 0.01 and (
                        str(go.get("mp4_size", "1080p")) == "Canvas"
                        or actual_m < 3.0 or actual_m > 8.0):
                    note = "· Canvas: 9:16 wants 720p/1080p and 3–8s."
                    mp4_hint = f"{mp4_hint} {note}" if mp4_hint else note
            except Exception:  # noqa: BLE001
                pass
        if self.chk_webp.isChecked():
            try:
                from app.gif import estimate_webp
                from app.exporter import webp_name

                dw, dh = self._doc_wh()
                if gif_trans is None:
                    go = self._gif_opts()
                    n_trans_w, forms_w = int(go["frames"]), 0
                else:
                    n_trans_w, forms_w = gif_trans, gif_forms
                est_w = estimate_webp(n_trans_w, dw, dh, forms_w)
                webp_fname = webp_name(sanitize_base(self.edit_base.text().strip() or "cover"))
                self.list_files.addItem(f"{webp_fname}  ({_fmt_size(est_w)} · {dw}×{dh})")
                total += est_w
                n += 1
            except Exception:  # noqa: BLE001
                pass
        if self.chk_apng.isChecked():
            try:
                from app.gif import estimate_apng
                from app.exporter import apng_name

                dw, dh = self._doc_wh()
                if gif_trans is None:
                    go = self._gif_opts()
                    n_trans_a, forms_a = int(go["frames"]), 0
                else:
                    n_trans_a, forms_a = gif_trans, gif_forms
                est_a = estimate_apng(n_trans_a, dw, dh, forms_a)
                apng_fname = apng_name(sanitize_base(self.edit_base.text().strip() or "cover"))
                self.list_files.addItem(f"{apng_fname}  ({_fmt_size(est_a)} · {dw}×{dh})")
                total += est_a
                n += 1
            except Exception:  # noqa: BLE001
                pass
        if self.chk_tiff.isChecked():
            try:
                from app.exporter import estimate_tiff, tiff_name

                dw, dh = self._doc_wh()
                est_t = estimate_tiff(dw, dh)
                tiff_fname = tiff_name(sanitize_base(self.edit_base.text().strip() or "cover"))
                self.list_files.addItem(f"{tiff_fname}  ({_fmt_size(est_t)} · {dw}×{dh} LZW)")
                total += est_t
                n += 1
            except Exception:  # noqa: BLE001
                pass
        if self.chk_social.isChecked():
            try:
                from app.social import estimate_pack, pack_names

                fmt_eff = "png" if self.chk_lossless.isChecked() else self.cmb_format.currentText()
                base_eff = sanitize_base(self.edit_base.text().strip() or "cover")
                est_p = estimate_pack(fmt_eff, int(self.spn_quality.value()))
                for stem, fname in pack_names(base_eff, fmt_eff).items():
                    self.list_files.addItem(f"{fname}  ({stem})")
                self.list_files.addItem(f"3 social files  ({_fmt_size(est_p)} total)")
                total += est_p
                n += 3
            except Exception:  # noqa: BLE001
                pass
        if self.chk_sep.isChecked():
            # R9: plate hexes need the render (SOURCE extracts); the plan
            # shows the count line, the post-accept alert lists exact files.
            try:
                from app.separations import estimate_sep, plate_count

                dw, dh = self._doc_wh()
                n_plates = plate_count(getattr(self, "_preset", None))
                est_s = estimate_sep(dw, dh, n_plates)
                safe = sanitize_base(self.edit_base.text().strip() or "cover")
                trap = " · trap" if self.chk_trap.isChecked() else ""
                self.list_files.addItem(f"{safe}_sep_*.png  ({n_plates} plates{trap} · {_fmt_size(est_s)})")
                total += est_s
                n += 1
            except Exception:  # noqa: BLE001
                pass
        if self.chk_sp404.isChecked():
            # One 128x64 1-bit BMP of the current still (~1KB); the user
            # renames/organizes it (startup_N / screen_saver_N) by hand.
            safe = sanitize_base(self.edit_base.text().strip() or "cover")
            self.list_files.addItem(f"{safe}_sp404.bmp (128×64 1-bit · ~1KB)")
            total += 2048
            n += 1
        clip_names = []
        clip_mp4_warn = ""
        clip_track_warn = ""
        if getattr(self, "_clip_info", None) is not None:
            try:
                from app.ui.clip_controller import clip_names as _clip_names

                safe = sanitize_base(self.edit_base.text().strip() or "cover")
                try:
                    full_mp4 = bool(
                        self.chk_clip_full is not None
                        and self.chk_clip_full.isChecked()
                        and self.chk_clip_full.isEnabled())
                except Exception:  # noqa: BLE001
                    full_mp4 = False
                full_note = ""
                full_est = 0
                full_video_len = None
                if full_mp4:
                    try:
                        from app.clip import clip_full_length
                        from app.gif import estimate_clip_mp4

                        ci = self._clip_info
                        plan = clip_full_length(str(ci.get("path", "")),
                                                float(ci.get("start_s", 0.0) or 0.0))
                        total_f = plan["total_frames"]
                        try:
                            fps_f = max(2, min(60, int(self.spn_clip_fps.value())))
                        except Exception:  # noqa: BLE001
                            fps_f = 24
                        if total_f:
                            full_video_len = total_f / max(1, fps_f)
                        noise = self._clip_noise()
                        cw, ch_ = self._clip_est_wh()
                        full_est = (estimate_clip_mp4(cw, ch_, total_f or 0, noise,
                                                      self._clip_q())
                                    if total_f else 0)
                        res_tag = "source" if self._clip_res() == "source" else "720p"
                        q_tag = f"q{self._clip_q()}"
                        full_note = (f"full {total_f}f"
                                     if total_f is not None else "full length")
                        full_note += f", {res_tag}, {q_tag}"
                        if full_est:
                            full_note += f", {_fmt_size(full_est)}"
                        if plan.get("capped"):
                            full_note += ", capped 3600f"
                    except Exception:  # noqa: BLE001
                        full_note = "full length"
                for kind, want in (("gif", self.chk_clip_gif.isChecked()),
                                   ("mp4", self.chk_clip_mp4.isChecked()
                                    and self._video_ok),
                                   ("zip", self.chk_clip_zip.isChecked())):
                    if want:
                        fname = _clip_names(safe)[kind]
                        clip_names.append(fname)
                        if kind == "mp4":
                            if full_mp4:
                                self.list_files.addItem(
                                    f"{fname}  ({full_note}, streaming, rendered at export)")
                                total += full_est
                            else:
                                short_est = self._clip_short_mp4_est()
                                if short_est:
                                    res_tag = ("source" if self._clip_res() == "source"
                                               else "720p")
                                    self.list_files.addItem(
                                        f"{fname}  (trim {self._clip_info.get('span', 0)}f"
                                        f", {res_tag}, q{self._clip_q()}"
                                        f", {_fmt_size(short_est)}, rendered at export)")
                                    total += short_est
                                else:
                                    self.list_files.addItem(f"{fname}  (clip, rendered at export)")
                        else:
                            self.list_files.addItem(f"{fname}  (clip, rendered at export)")
                        n += 1
                        if kind == "mp4":
                            est = full_est if full_mp4 else short_est
                            for thresh, word in ((400 * 1024 * 1024, "heavy"),
                                                 (100 * 1024 * 1024, "consider 720p / lower grain")):
                                if est and est > thresh:
                                    clip_mp4_warn = f"Clip MP4 ~{_fmt_size(est)} — {word}."
                                    break
            except Exception:  # noqa: BLE001
                clip_names = []
                clip_mp4_warn = ""
                clip_track_warn = ""
            if (self.chk_clip_mp4 is not None and self._clip_info is not None
                    and self.chk_clip_mp4.isChecked()):
                clip_track_warn = self._clip_track_warn(full_video_len)
        self.lbl_total.setText(
            f"{n} {'file' if n == 1 else 'files'} · {_fmt_size(total)} total (approx)")
        self.btn_export.setEnabled(n > 0)
        try:
            dest = Path(self.edit_dir.text())
            clashing = sum(1 for _, fname, _ in plan if (dest / fname).exists())
            if mp4_fname and (dest / mp4_fname).exists():
                clashing += 1
            if webp_fname and (dest / webp_fname).exists():
                clashing += 1
            if apng_fname and (dest / apng_fname).exists():
                clashing += 1
            if self.chk_tiff.isChecked():
                try:
                    from app.exporter import tiff_name as _tiff_name

                    if (dest / _tiff_name(sanitize_base(self.edit_base.text().strip() or "cover"))).exists():
                        clashing += 1
                except OSError:
                    pass
            if self.chk_social.isChecked():
                try:
                    from app.social import pack_names as _pack_names

                    fmt_c = "png" if self.chk_lossless.isChecked() else self.cmb_format.currentText()
                    base_c = sanitize_base(self.edit_base.text().strip() or "cover")
                    clashing += sum(1 for f in _pack_names(base_c, fmt_c).values()
                                    if (dest / f).exists())
                except OSError:
                    pass
            if self.chk_sep.isChecked():
                try:
                    safe = sanitize_base(self.edit_base.text().strip() or "cover")
                    clashing += sum(1 for _ in dest.glob(f"{safe}_sep_*.png"))
                except OSError:
                    pass
            for fname in clip_names:
                try:
                    if (dest / fname).exists():
                        clashing += 1
                except OSError:
                    pass
        except OSError:
            clashing = 0
        notes = []
        if clashing:
            notes.append(f"⚠ {clashing} already exist — you'll be asked")
        if clip_mp4_warn:
            notes.append(clip_mp4_warn)
        if clip_track_warn:
            notes.append(clip_track_warn)
        if mp4_hint:
            notes.append(mp4_hint)
        self.lbl_exists.setText("\n".join(notes))
        self._sync_distro_label()

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Export folder", self.edit_dir.text())
        if d:
            self.edit_dir.setText(d)

    def _browse_track(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Soundtrack (MP4 only, optional)",
            "", "Audio (*.mp3 *.wav *.ogg *.m4a *.flac *.aac)")
        if path:
            self.edit_track.setText(path)

    def clip_options(self) -> dict | None:
        """Clip export choice (None when no clip or nothing checked).

        {gif, mp4, zip, fps, track}: consumed by export_flow, which owns
        the render + naming (dialog base, first-free per file).
        """
        if getattr(self, "_clip_info", None) is None:
            return None
        try:
            gif = bool(self.chk_clip_gif.isChecked())
            mp4 = bool(self.chk_clip_mp4.isChecked() and self._video_ok)
            zip_ = bool(self.chk_clip_zip.isChecked())
            full = bool(mp4 and self.chk_clip_full.isChecked()
                        and self.chk_clip_full.isEnabled())
            fps = max(2, min(60, int(self.spn_clip_fps.value())))
            track = str(self.edit_track.text()).strip()
        except Exception:  # noqa: BLE001
            return None
        if not (gif or mp4 or zip_):
            return None
        try:
            res = self._clip_res()
            q = self._clip_q()
        except Exception:  # noqa: BLE001
            res, q = "proxy", 8
        return {"gif": gif, "mp4": mp4, "zip": zip_, "fps": fps,
                "track": track, "full": full, "res": res, "quality": q}

    def _sync_distro_label(self) -> None:
        """Distributor readiness hints (never blocks; honest, not nagging)."""
        try:
            from app.distro import distro_summary, validate_session
            from app.ui.widgets import set_warning

            dw, dh = self._doc_wh()
            fmt = "png" if self.chk_lossless.isChecked() else self.cmb_format.currentText()
            try:
                sw, sh = self._img.size
            except Exception:  # noqa: BLE001
                sw, sh = 0, 0
            checks = validate_session(dw, dh, fmt, sw, sh, int(self.spn_quality.value()))
            ok, summary = distro_summary(checks)
            bad = [c.hint for c in checks if not c.ok and c.hint]
            self.lbl_distro.setText("Distro 3000: ✓ ready" if ok
                                    else "Distro 3000: " + " · ".join(bad[:2]))
            set_warning(self.lbl_distro, not ok)
            self.lbl_distro.setToolTip(summary)
        except Exception:  # noqa: BLE001
            pass

    # -- animation: spec comes from VIDEO (shown here, not edited) --
    def _sync_gifspec_label(self) -> None:
        from app.gif import mode_label

        g = getattr(self, "_gif_spec", {})
        w, h = self._doc_wh()
        m = str(g.get("mode", "both"))
        extra = ""
        if m in ("dissolve", "morph") and getattr(self, "_preset", None) is not None:
            try:
                hold = float(getattr(self._preset, "dissolve_hold", 0.0) or 0.0)
                if hold > 0:
                    extra = f" · Hold {hold:.1f}s/form (GIF capped 256f, MP4 full)"
            except (TypeError, ValueError):
                extra = ""
        self.lbl_gifspec.setText(
            f"Animation: {g.get('frames', 6)}f · {mode_label(m)} ({m}) · "
            f"{g.get('fps', 8)}fps"
            f"{' · ping-pong' if g.get('pingpong') else ''} "
            f"· {w}×{h}px (canvas){extra}. Edit it in MOTION."
        )

    def _gif_opts(self) -> dict:
        g = dict(getattr(self, "_gif_spec", {}))
        g["size"] = self._current_size()  # canvas rules the still + GIF
        g["pingpong"] = bool(g.get("pingpong", False))
        g["mp4"] = bool(self.chk_mp4.isChecked() and self._video_ok)
        g["webp"] = bool(self.chk_webp.isChecked())
        g["apng"] = bool(self.chk_apng.isChecked())
        g["tiff"] = bool(self.chk_tiff.isChecked())
        g["social"] = bool(self.chk_social.isChecked())
        g["sep"] = bool(self.chk_sep.isChecked())
        g["sep_trap"] = bool(self.chk_trap.isChecked())
        g["sp404"] = bool(self.chk_sp404.isChecked())
        try:
            g["mp4_size"] = str(self.cmb_mp4_size.currentText())
        except Exception:  # noqa: BLE001
            g["mp4_size"] = "1080p"
        return g

    def _on_export(self) -> None:
        if not self.edit_base.text().strip():
            self.edit_base.setText("cover")
        self.accept()

    # -- result --
    def options(self) -> tuple[ExportOptions, Path, dict]:
        """(options, destination, gif_opts). Only valid after Accept.

        gif_opts = {frames, mode, fps, size, pingpong}. Old callers
        unpacking (opts, out, frames, mode) still work
        via GifOpts (tuple + dict at once).
        """
        fmt = "png" if self.chk_lossless.isChecked() else self.cmb_format.currentText()
        opts = ExportOptions(
            base=self.edit_base.text().strip() or "cover",
            selection=self._current_selection(),
            overwrite="rename",
            size=self._current_size(),
            format=fmt,
            quality=int(self.spn_quality.value()),
            dpi=int(self.spn_dpi.value()),
        )
        return opts, Path(self.edit_dir.text()), self._gif_opts()

    # -- compat: (opts, out, frames, mode) for old code/tests --
    def legacy_options(self) -> tuple[ExportOptions, Path, int, str]:
        opts, out, g = self.options()
        return opts, out, int(g["frames"]), str(g["mode"])


__all__ = ["ExportDialog"]
