"""Export dialog — Photoshop/GIMP style: name, destination, outputs, collision.

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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
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
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setMinimumWidth(480)
        self._img = img
        self._meta = meta or {}
        self._vector_cells = vector_cells
        self._preset = preset  # kept for compat; preview lives in Video mode
        self._gif_count = max(1, int(gif_frames))
        self._ready = False  # __init__ signals paint nothing yet

        col = QVBoxLayout(self)
        # -- file name (dedicated section: base + reset + sanitized preview) --
        col.addWidget(QLabel("File name:"))
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
        # -- format (GIMP: extension rules; here the combo) --
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.cmb_format, self.spn_quality = build_format_quality(format, quality)
        self.cmb_format.setToolTip("PNG: lossless, ideal dither · JPG: small, artifacts · WebP: small, modern")
        self.cmb_format.currentTextChanged.connect(self._refresh_plan)
        fmt_row.addWidget(self.cmb_format)
        self.spn_quality.setToolTip("Quality for JPG/WebP (PNG ignores it)")
        self.spn_quality.valueChanged.connect(self._refresh_plan)
        fmt_row.addWidget(self.spn_quality)
        col.addLayout(fmt_row)
        # -- outputs --
        col.addWidget(QLabel("Include:"))
        self.chk_image = QCheckBox("Main image")
        self.chk_thumb = QCheckBox("Social thumb 1080p")
        self.chk_vector = QCheckBox("Vector SVG")
        self.chk_anim = QCheckBox("Animation GIF")
        self.chk_meta = QCheckBox("Metadata JSON")
        self.chk_black = QCheckBox("Black vector (print ink only)")
        self.chk_black.setToolTip("SVG with black ink on transparent (no paper rects)")
        self.chk_black.setChecked(bool(getattr(selection, "black_vector", False)))
        self.chk_lossless = QCheckBox("Lossless (force PNG)")
        self.chk_lossless.setToolTip("Ignores format combo: exports main + thumb as PNG")
        self.chk_lossless.setChecked(False)
        self.chk_lossless.stateChanged.connect(self._on_lossless)
        sel = selection or ExportSelection()
        self.chk_image.setChecked(sel.image)
        self.chk_thumb.setChecked(sel.thumb_1080p)
        self.chk_vector.setChecked(sel.vector)
        self.chk_vector.setToolTip("Vector for logos/merch (no post-fx)")
        self.chk_anim.setChecked(sel.anim)
        self.chk_anim.setToolTip("Animation for socials (Pillow only)")
        self.chk_meta.setChecked(sel.metadata)
        self.chk_black.setChecked(bool(getattr(sel, "black_vector", False)))
        from app.video_io import has_video as _has_video

        self._video_ok = bool(_has_video())
        self.chk_mp4 = QCheckBox("Animation MP4")
        self.chk_mp4.setChecked(False)
        if self._video_ok:
            self.chk_mp4.setToolTip("H.264 clip at canvas size (opt-in video extra present)")
        else:
            self.chk_mp4.setEnabled(False)
            self.chk_mp4.setToolTip("Settings → Extras → Install video")
        for chk in (self.chk_image, self.chk_thumb,
                    self.chk_vector, self.chk_anim, self.chk_meta,
                    self.chk_black, self.chk_mp4):
            chk.stateChanged.connect(self._refresh_plan)
            col.addWidget(chk)
        col.addWidget(self.chk_lossless)
        # -- animation: no duplicates (edited only in VIDEO); on/off here --
        self._gif_spec = normalize_gif_spec(gif_frames, gif_mode, gif_fps, gif_pingpong)
        self.lbl_gifspec = QLabel()
        self.lbl_gifspec.setWordWrap(True)
        self.lbl_gifspec.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_gifspec)
        self._sync_gifspec_label()
        # -- collision: always rename (never lose a file) --
        self.lbl_policy = QLabel("Existing files are kept: repeats save as name_2, name_3…")
        self.lbl_policy.setWordWrap(True)
        self.lbl_policy.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_policy)
        # -- plan (GIMP shows estimated size: here the list + ~weight) --
        col.addWidget(QLabel("Files to write:"))
        self.list_files = QListWidget()
        self.list_files.setMinimumHeight(110)
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
        col.addLayout(bar)

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

    def _refresh_plan(self) -> None:
        if not getattr(self, "_ready", False):
            return
        try:
            w, h = self._doc_wh()
            self.lbl_dims.setText(f"{w}×{h} (from CANVAS)")
            safe = sanitize_base(self.edit_base.text().strip() or "cover")
            self.lbl_basename.setText(f"Files start with: {safe}")
            opts = ExportOptions(
                base=self.edit_base.text().strip() or "cover",
                selection=self._current_selection(),
                overwrite="rename",
                size=self._current_size(),
                format=self.cmb_format.currentText(),
                quality=int(self.spn_quality.value()),
            )
            plan = plan_export(
                self._img, opts, meta=self._meta,
                has_vector=True, has_gif=True,
                extra={"vector_cells": self._vector_cells or (0, 0),
                       "gif_frames": int(self._gif_opts()["frames"]),
                       "gif_size": int(self._gif_opts()["size"])},
            )
        except ValueError:
            plan = []
        self.list_files.clear()
        total = 0
        for _, fname, est in plan:
            self.list_files.addItem(f"{fname}  ({_fmt_size(est)})")
            total += est
        n = len(plan)
        mp4_fname = ""
        if self.chk_mp4.isChecked() and self._video_ok:
            try:
                w, h = self._doc_wh()
                nf = int(self._gif_opts()["frames"])
                est = int(w * h * nf * 0.12)
                mp4_fname = mp4_name(sanitize_base(self.edit_base.text().strip() or "cover"))
                self.list_files.addItem(f"{mp4_fname}  ({_fmt_size(est)})")
                total += est
                n += 1
            except Exception:  # noqa: BLE001
                pass
        self.lbl_total.setText(f"{n} file(s) · {_fmt_size(total)} total (approx)")
        self.btn_export.setEnabled(n > 0)
        try:
            dest = Path(self.edit_dir.text())
            clashing = sum(1 for _, fname, _ in plan if (dest / fname).exists())
            if mp4_fname and (dest / mp4_fname).exists():
                clashing += 1
        except OSError:
            clashing = 0
        self.lbl_exists.setText(
            f"⚠ {clashing} already exist — you'll be asked" if clashing else "")

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Export folder", self.edit_dir.text())
        if d:
            self.edit_dir.setText(d)

    # -- animation: spec comes from VIDEO (shown here, not edited) --
    def _sync_gifspec_label(self) -> None:
        from app.gif import mode_label

        g = getattr(self, "_gif_spec", {})
        w, h = self._doc_wh()
        m = str(g.get("mode", "both"))
        self.lbl_gifspec.setText(
            f"Animation: {g.get('frames', 6)}f · {mode_label(m)} ({m}) · "
            f"{g.get('fps', 8)}fps"
            f"{' · ping-pong' if g.get('pingpong') else ''} "
            f"· {w}×{h}px (canvas). Edit it in VIDEO."
        )

    def _gif_opts(self) -> dict:
        g = dict(getattr(self, "_gif_spec", {}))
        g["size"] = self._current_size()  # canvas also rules the anim
        g["pingpong"] = bool(g.get("pingpong", False))
        g["mp4"] = bool(self.chk_mp4.isChecked() and self._video_ok)
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
        )
        return opts, Path(self.edit_dir.text()), self._gif_opts()

    # -- compat: (opts, out, frames, mode) for old code/tests --
    def legacy_options(self) -> tuple[ExportOptions, Path, int, str]:
        opts, out, g = self.options()
        return opts, out, int(g["frames"]), str(g["mode"])


__all__ = ["ExportDialog"]
