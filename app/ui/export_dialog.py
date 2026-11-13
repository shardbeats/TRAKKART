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
        mp4_size: str = "1080p",
        mp4: bool = False,
        mp4_encoder: str = "libx264",
        webp: bool = False,
        sep: bool = False,
        sp404: bool = False,
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
        # -- format (extension rules like classic editors; here the combo) --
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
        self.chk_webp = QCheckBox("Animation WebP")
        self.chk_webp.setChecked(bool(webp))
        self.chk_webp.setToolTip("Same frames as the GIF, ~1/3 the weight, full color (Pillow only)")
        self.chk_sep = QCheckBox("Ink separations (print)")
        self.chk_sep.setChecked(bool(sep))
        self.chk_sep.setToolTip("One PNG per palette ink + registration marks (RISO/screen print)")
        self.chk_sp404 = QCheckBox("SP-404MKII BMP (128×64 1-bit)")
        self.chk_sp404.setChecked(bool(sp404))
        self.chk_sp404.setToolTip("Roland SP-404MKII still: one 128×64 1-bit BMP of the current image (rename it to startup_N/screen_saver_N yourself)")
        self.chk_meta.setChecked(sel.metadata)
        self.chk_black.setChecked(bool(getattr(sel, "black_vector", False)))
        from app.video_io import has_video as _has_video

        self._video_ok = bool(_has_video())
        self.chk_mp4 = QCheckBox("Animation MP4")
        self.chk_mp4.setChecked(bool(mp4))
        if self._video_ok:
            self.chk_mp4.setToolTip("H.264 clip at MP4 size below (video backend present)")
        else:
            self.chk_mp4.setEnabled(False)
            self.chk_mp4.setToolTip("Settings → Extras → Install video")
        for chk in (self.chk_image, self.chk_thumb,
                    self.chk_vector, self.chk_anim, self.chk_webp, self.chk_sep, self.chk_meta,
                    self.chk_black, self.chk_mp4, self.chk_sp404):
            chk.stateChanged.connect(self._refresh_plan)
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
        enc_row = QHBoxLayout()
        enc_row.addWidget(QLabel("MP4 encoder:"))
        self.cmb_mp4_encoder = _Cmb()
        try:
            from app.video_io import available_encoders
            encs = available_encoders()
        except Exception:  # noqa: BLE001
            encs = ["libx264"]
        items = ["auto (hardware if available)"] + encs
        self.cmb_mp4_encoder.addItems(items)
        cur_enc = str(mp4_encoder or "libx264")
        if cur_enc == "auto":
            self.cmb_mp4_encoder.setCurrentIndex(0)
        elif cur_enc in encs:
            self.cmb_mp4_encoder.setCurrentText(cur_enc)
        else:
            self.cmb_mp4_encoder.setCurrentText("libx264")
        self.cmb_mp4_encoder.setToolTip("H.264 encoder: hardware (NVENC/QSV/AMF) is faster, software libx264 always works (automatic fallback)")
        self.cmb_mp4_encoder.currentTextChanged.connect(self._refresh_plan)
        enc_row.addWidget(self.cmb_mp4_encoder, 1)
        col.addLayout(enc_row)
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
        # -- plan (classic editors show estimated size: here the list + ~weight) --
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
            self.lbl_dims.setText(f"{w}×{h} (from CANVAS)")
            self.lbl_dims.setToolTip("Main image renders at the CANVAS document size")
            if note:
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
            )
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
        if self.chk_sep.isChecked():
            # R9: plate hexes need the render (SOURCE extracts); the plan
            # shows the count line, the post-accept alert lists exact files.
            try:
                from app.separations import estimate_sep, plate_count

                dw, dh = self._doc_wh()
                n_plates = plate_count(getattr(self, "_preset", None))
                est_s = estimate_sep(dw, dh, n_plates)
                safe = sanitize_base(self.edit_base.text().strip() or "cover")
                self.list_files.addItem(f"{safe}_sep_*.png  ({n_plates} plates · {_fmt_size(est_s)})")
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
        self.lbl_total.setText(f"{n} file(s) · {_fmt_size(total)} total (approx)")
        self.btn_export.setEnabled(n > 0)
        try:
            dest = Path(self.edit_dir.text())
            clashing = sum(1 for _, fname, _ in plan if (dest / fname).exists())
            if mp4_fname and (dest / mp4_fname).exists():
                clashing += 1
            if webp_fname and (dest / webp_fname).exists():
                clashing += 1
            if self.chk_sep.isChecked():
                try:
                    safe = sanitize_base(self.edit_base.text().strip() or "cover")
                    clashing += sum(1 for _ in dest.glob(f"{safe}_sep_*.png"))
                except OSError:
                    pass
        except OSError:
            clashing = 0
        notes = []
        if clashing:
            notes.append(f"⚠ {clashing} already exist — you'll be asked")
        if mp4_hint:
            notes.append(mp4_hint)
        self.lbl_exists.setText("\n".join(notes))

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
            f"· {w}×{h}px (canvas){extra}. Edit it in VIDEO."
        )

    def _gif_opts(self) -> dict:
        g = dict(getattr(self, "_gif_spec", {}))
        g["size"] = self._current_size()  # canvas rules the still + GIF
        g["pingpong"] = bool(g.get("pingpong", False))
        g["mp4"] = bool(self.chk_mp4.isChecked() and self._video_ok)
        g["webp"] = bool(self.chk_webp.isChecked())
        g["sep"] = bool(self.chk_sep.isChecked())
        g["sp404"] = bool(self.chk_sp404.isChecked())
        try:
            g["mp4_size"] = str(self.cmb_mp4_size.currentText())
        except Exception:  # noqa: BLE001
            g["mp4_size"] = "1080p"
        try:
            txt = str(self.cmb_mp4_encoder.currentText())
            g["mp4_encoder"] = "auto" if txt.startswith("auto") else txt
        except Exception:  # noqa: BLE001
            g["mp4_encoder"] = "libx264"
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
