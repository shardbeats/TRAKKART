"""Batch dialog: in/out in one place, validated first.

Validates folders and counts images BEFORE launching (no two blind
dialogs in a row). Vector/GIF outputs are chosen here per operation
(editor-style); the preset provides the defaults. Progress with fps/ETA
lives in the main window.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.batch import EXTS


def count_images(folder: str | Path) -> int:
    """Number of compatible images (0 if not a folder). Launches nothing."""
    try:
        p = Path(folder)
        if not p.is_dir():
            return 0
        return sum(1 for f in p.iterdir() if f.is_file() and f.suffix.lower() in EXTS)
    except OSError:
        return 0


class BatchDialog(QDialog):
    """Collects validated in/out/jobs. `paths()` only valid after Accept."""

    def __init__(
        self,
        in_dir: str | Path = "",
        out_dir: str | Path = "",
        jobs: int = 1,
        vector_export: bool = False,
        vector_cell: int = 8,
        vector_black: bool = False,
        gif_export: bool = False,
        gif_frames: int = 6,
        gif_mode: str = "both",
        gif_fps: int = 8,
        gif_pingpong: bool = False,
        canvas_size: tuple[int, int] | None = None,
        doc_w: int = 3000,
        doc_h: int = 3000,
        format: str = "png",
        quality: int = 90,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Batch folder")
        self.setMinimumWidth(480)
        self._canvas_size = canvas_size

        col = QVBoxLayout(self)
        col.addWidget(QLabel("Process every image in a folder with the current preset."))
        from app.ui.dialog_fields import (build_folder_row, build_format_quality,
                                          build_jobs_spin, normalize_gif_spec)

        self.edit_in = self.edit_out = None
        for caption, initial in (("Input folder:", in_dir), ("Output folder:", out_dir)):
            row, edit, _btn = build_folder_row(caption, str(initial), self, editable=True)
            edit.textChanged.connect(self._validate)
            if caption.startswith("Input"):
                self.edit_in = edit
            else:
                self.edit_out = edit
            col.addLayout(row)
        jobs_row = QHBoxLayout()
        jobs_row.addWidget(QLabel("Jobs:"))
        self.spn_jobs = build_jobs_spin(jobs)
        jobs_row.addWidget(self.spn_jobs)
        jobs_row.addStretch()
        col.addLayout(jobs_row)

        # -- single document: W/H come from the CANVAS preset; format only here --
        from app.canvas import MAX_DIM, MIN_DIM

        self._doc_w = max(MIN_DIM, min(MAX_DIM, int(doc_w)))
        self._doc_h = max(MIN_DIM, min(MAX_DIM, int(doc_h)))
        self._doc_size = max(self._doc_w, self._doc_h)
        doc_row = QHBoxLayout()
        doc_row.addWidget(QLabel("Document:"))
        self.lbl_doc = QLabel(f"{self._doc_w}×{self._doc_h} px (from CANVAS preset)")
        doc_row.addWidget(self.lbl_doc, 1)
        col.addLayout(doc_row)
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.cmb_format, self.spn_quality = build_format_quality(format, quality)
        fmt_row.addWidget(self.cmb_format)
        fmt_row.addWidget(self.spn_quality)
        self.chk_lossless = QCheckBox("Lossless PNG")
        self.chk_lossless.setToolTip("Force PNG (ignores format combo)")
        fmt_row.addWidget(self.chk_lossless)
        col.addLayout(fmt_row)

        # -- outputs per operation (preset provides the defaults) --
        col.addWidget(QLabel("Outputs:"))
        vec_row = QHBoxLayout()
        self.chk_vector = QCheckBox("SVG")
        self.chk_vector.setToolTip("Vector for logos/merch (no post-fx)")
        self.chk_vector.setChecked(bool(vector_export))
        vec_row.addWidget(self.chk_vector)
        self.spn_vcell = QSpinBox()
        self.spn_vcell.setRange(4, 16)
        self.spn_vcell.setValue(max(4, min(16, int(vector_cell))))
        self.spn_vcell.setToolTip("SVG cell 4-16 (higher = smaller file)")
        self.spn_vcell.valueChanged.connect(self._sync_vec_estimate)
        vec_row.addWidget(self.spn_vcell)
        self.chk_black = QCheckBox("Black")
        self.chk_black.setToolTip("Black ink vector for print")
        self.chk_black.setChecked(bool(vector_black))
        vec_row.addWidget(self.chk_black)
        self.lbl_vec_est = QLabel("")
        vec_row.addWidget(self.lbl_vec_est, 1)
        col.addLayout(vec_row)
        self._gif_spec = normalize_gif_spec(gif_frames, gif_mode, gif_fps, gif_pingpong)
        gif_row = QHBoxLayout()
        self.chk_gif = QCheckBox("Animation GIF")
        self.chk_gif.setToolTip("Animation uses the VIDEO panel setup at canvas size")
        self.chk_gif.setChecked(bool(gif_export))
        gif_row.addWidget(self.chk_gif)
        from app.ui.dialog_fields import gif_summary

        self.lbl_gifspec = QLabel(gif_summary(self._gif_spec, "canvas px"))
        self.lbl_gifspec.setObjectName("subtitleLabel")
        self.lbl_gifspec.setWordWrap(True)
        gif_row.addWidget(self.lbl_gifspec, 1)
        col.addLayout(gif_row)

        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        col.addWidget(self.lbl_info)

        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bar.addWidget(self.btn_cancel)
        self.btn_run = QPushButton("Run batch")
        self.btn_run.setObjectName("exportBtn")
        self.btn_run.setDefault(True)
        self.btn_run.clicked.connect(self._on_run)
        bar.addWidget(self.btn_run)
        col.addLayout(bar)

        self._validate()
        self._sync_vec_estimate()

    def _sync_vec_estimate(self) -> None:
        from app.vector import estimate_bytes, estimate_cells

        if self._canvas_size is None:
            self.lbl_vec_est.setText("")
            return
        try:
            cols, rows = estimate_cells(
                self._canvas_size[0], self._canvas_size[1], int(self.spn_vcell.value()))
            kb = estimate_bytes(cols, rows) // 1024
            warn = " (!)" if kb * 1024 > 2 * 1024 * 1024 else ""
            self.lbl_vec_est.setText(f"~{cols}x{rows} cells, ~{kb}KB{warn}")
        except Exception:  # noqa: BLE001
            self.lbl_vec_est.setText("")

    def _validate(self) -> None:
        n = count_images(self.edit_in.text().strip())
        out = self.edit_out.text().strip()
        problems: list[str] = []
        if not Path(self.edit_in.text().strip()).is_dir():
            problems.append("input folder missing")
        elif n == 0:
            problems.append("no compatible images in input")
        if not out:
            problems.append("output folder missing")
        if problems:
            self.lbl_info.setText(" · ".join(problems))
            self.btn_run.setEnabled(False)
        else:
            self.lbl_info.setText(f"{n} image(s) ready → {out}")
            self.btn_run.setEnabled(True)

    def _on_run(self) -> None:
        self._validate()
        if self.btn_run.isEnabled():
            self.accept()

    def paths(self) -> tuple[Path, Path, int]:
        """(input, output, jobs). Only after Accept."""
        return Path(self.edit_in.text().strip()), Path(self.edit_out.text().strip()), int(self.spn_jobs.value())

    def output_options(self) -> dict:
        """Vector/gif flags + format chosen for this batch. Only after Accept."""
        g = dict(getattr(self, "_gif_spec", {}))
        fmt = "png" if self.chk_lossless.isChecked() else self.cmb_format.currentText()
        return {
            "vector_export": self.chk_vector.isChecked(),
            "vector_cell": int(self.spn_vcell.value()),
            "vector_black": self.chk_black.isChecked(),
            "gif_export": self.chk_gif.isChecked(),
            "gif_frames": int(g.get("frames", 6)),
            "gif_mode": str(g.get("mode", "both")),
            "gif_fps": int(g.get("fps", 8)),
            "gif_size": int(getattr(self, "_doc_size", 3000)),
            "gif_pingpong": bool(g.get("pingpong", False)),
            "canvas_w": int(getattr(self, "_doc_w", 3000)),
            "canvas_h": int(getattr(self, "_doc_h", 3000)),
            "export_size": int(getattr(self, "_doc_size", 3000)),
            "export_format": fmt,
            "export_quality": int(self.spn_quality.value()),
        }


__all__ = ["BatchDialog", "count_images"]
