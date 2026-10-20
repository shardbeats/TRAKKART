"""Batch dialog: in/out en un solo sitio, validado antes.

Valida carpetas y cuenta imágenes ANTES de lanzar (nada de dos diálogos
seguidos a ciegas). Las salidas vector/GIF se eligen aquí por operación
(photoshop-style); el preset aporta los defaults. El progreso con fps/ETA
vive en la ventana principal.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.batch import EXTS


def count_images(folder: str | Path) -> int:
    """Nº de imágenes compatibles (0 si no es carpeta). Sin lanzar nada."""
    try:
        p = Path(folder)
        if not p.is_dir():
            return 0
        return sum(1 for f in p.iterdir() if f.is_file() and f.suffix.lower() in EXTS)
    except OSError:
        return 0


class BatchDialog(QDialog):
    """Recoge in/out/jobs validados. `paths()` solo válido tras Accept."""

    GIF_MODES = ("phase", "hue", "both", "glitch", "mix")

    def __init__(
        self,
        in_dir: str | Path = "",
        out_dir: str | Path = "",
        jobs: int = 1,
        vector_export: bool = False,
        vector_cell: int = 8,
        gif_export: bool = False,
        gif_frames: int = 6,
        gif_mode: str = "both",
        gif_fps: int = 8,
        gif_size: int = 1200,
        gif_pingpong: bool = False,
        canvas_size: tuple[int, int] | None = None,
        size: int = 3000,
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
        self.edit_in = QLineEdit(str(in_dir))
        self.edit_out = QLineEdit(str(out_dir))
        for caption, edit in (("Input folder:", self.edit_in), ("Output folder:", self.edit_out)):
            row = QHBoxLayout()
            row.addWidget(QLabel(caption))
            edit.setPlaceholderText("Choose folder…")
            edit.textChanged.connect(self._validate)
            row.addWidget(edit, 1)
            btn = QPushButton("Browse...")
            btn.clicked.connect(lambda _=False, _e=edit: self._browse(_e))
            row.addWidget(btn)
            col.addLayout(row)
        jobs_row = QHBoxLayout()
        jobs_row.addWidget(QLabel("Jobs:"))
        self.spn_jobs = QSpinBox()
        self.spn_jobs.setRange(1, 8)
        self.spn_jobs.setValue(max(1, min(8, int(jobs))))
        self.spn_jobs.setToolTip("1 = sequential (safe). >1 = multiprocessing.")
        jobs_row.addWidget(self.spn_jobs)
        jobs_row.addStretch()
        col.addLayout(jobs_row)

        # -- documento único: el tamaño viene del preset CANVAS; aquí solo formato --
        from app.exporter import EXPORT_FORMATS, MAX_SIDE, MIN_SIDE

        self._doc_size = max(MIN_SIDE, min(MAX_SIDE, int(size)))
        doc_row = QHBoxLayout()
        doc_row.addWidget(QLabel("Document:"))
        self.lbl_doc = QLabel(f"{self._doc_size} px (from CANVAS preset)")
        doc_row.addWidget(self.lbl_doc, 1)
        col.addLayout(doc_row)
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(list(EXPORT_FORMATS))
        self.cmb_format.setCurrentText(format if format in EXPORT_FORMATS else "png")
        fmt_row.addWidget(self.cmb_format)
        self.spn_quality = QSpinBox()
        self.spn_quality.setRange(1, 100)
        self.spn_quality.setValue(max(1, min(100, int(quality))))
        self.spn_quality.setSuffix("%")
        fmt_row.addWidget(self.spn_quality)
        col.addLayout(fmt_row)

        # -- salidas por operación (el preset aporta los defaults) --
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
        self.lbl_vec_est = QLabel("")
        vec_row.addWidget(self.lbl_vec_est, 1)
        col.addLayout(vec_row)
        gif_row = QHBoxLayout()
        self.chk_gif = QCheckBox("GIF")
        self.chk_gif.setToolTip("Animation for socials (phase/hue/glitch/mix)")
        self.chk_gif.setChecked(bool(gif_export))
        gif_row.addWidget(self.chk_gif)
        self.spn_gframes = QSpinBox()
        self.spn_gframes.setRange(2, 12)
        self.spn_gframes.setValue(max(2, min(12, int(gif_frames))))
        self.spn_gframes.setToolTip("Frames 2-12")
        gif_row.addWidget(self.spn_gframes)
        self.cmb_gifmode = QComboBox()
        self.cmb_gifmode.addItems(list(self.GIF_MODES))
        self.cmb_gifmode.setCurrentText(gif_mode if gif_mode in self.GIF_MODES else "both")
        gif_row.addWidget(self.cmb_gifmode, 1)
        col.addLayout(gif_row)
        gif_row2 = QHBoxLayout()
        gif_row2.addWidget(QLabel("FPS:"))
        self.spn_gfps = QSpinBox()
        self.spn_gfps.setRange(2, 24)
        self.spn_gfps.setValue(max(2, min(24, int(gif_fps))))
        gif_row2.addWidget(self.spn_gfps)
        gif_row2.addWidget(QLabel("Size:"))
        self.spn_gsize = QSpinBox()
        self.spn_gsize.setRange(240, 1920)
        self.spn_gsize.setValue(max(240, min(1920, int(gif_size))))
        self.spn_gsize.setSuffix(" px")
        gif_row2.addWidget(self.spn_gsize)
        self.chk_pingpong = QCheckBox("Ping-pong")
        self.chk_pingpong.setChecked(bool(gif_pingpong))
        self.chk_pingpong.setToolTip("Forward-backward loop")
        gif_row2.addWidget(self.chk_pingpong)
        col.addLayout(gif_row2)

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

    def _browse(self, edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text() or str(Path.home()))
        if d:
            edit.setText(d)

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
        """(input, output, jobs). Solo tras Accept."""
        return Path(self.edit_in.text().strip()), Path(self.edit_out.text().strip()), int(self.spn_jobs.value())

    def output_options(self) -> dict:
        """Flags vector/gif + formato elegidos para este batch. Solo tras Accept."""
        return {
            "vector_export": self.chk_vector.isChecked(),
            "vector_cell": int(self.spn_vcell.value()),
            "gif_export": self.chk_gif.isChecked(),
            "gif_frames": int(self.spn_gframes.value()),
            "gif_mode": self.cmb_gifmode.currentText(),
            "gif_fps": int(self.spn_gfps.value()),
            "gif_size": int(self.spn_gsize.value()),
            "gif_pingpong": bool(self.chk_pingpong.isChecked()),
            "export_size": int(getattr(self, "_doc_size", 3000)),
            "export_format": self.cmb_format.currentText(),
            "export_quality": int(self.spn_quality.value()),
        }


__all__ = ["BatchDialog", "count_images"]
