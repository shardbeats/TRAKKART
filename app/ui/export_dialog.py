"""Export dialog — Photoshop/GIMP style: name, destination, outputs, collision.

El motor (`export_bundle`/`export_with_options`) no pregunta nada;
este diálogo pregunta todo y previsualiza lo que va a salir.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.exporter import ExportOptions, ExportSelection, plan_export


def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"~{n / (1024 * 1024):.1f}MB"
    if n >= 1024:
        return f"~{n // 1024}KB"
    return f"~{n}B"


class ExportDialog(QDialog):
    """Qué sale, dónde y con qué nombre. `options()` solo válido tras Accept."""

    def __init__(
        self,
        img: Image.Image,
        meta: dict | None,
        base: str = "trakkart_cover",
        out_dir: str | Path = ".",
        selection: ExportSelection | None = None,
        gif_frames: int = 6,
        gif_mode: str = "both",
        overwrite: str = "overwrite",
        vector_cells: tuple[int, int] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setMinimumWidth(480)
        self._img = img
        self._meta = meta or {}
        self._vector_cells = vector_cells
        self._gif_count = max(1, int(gif_frames))
        self._ready = False  # las señales del __init__ no pintan nada aún

        col = QVBoxLayout(self)
        # -- nombre --
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self.edit_base = QLineEdit(base)
        self.edit_base.setPlaceholderText("trakkart_cover")
        self.edit_base.textChanged.connect(self._refresh_plan)
        name_row.addWidget(self.edit_base, 1)
        col.addLayout(name_row)
        # -- destino --
        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Folder:"))
        self.edit_dir = QLineEdit(str(out_dir))
        self.edit_dir.setReadOnly(True)
        dest_row.addWidget(self.edit_dir, 1)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse)
        dest_row.addWidget(self.btn_browse)
        col.addLayout(dest_row)
        # -- salidas --
        col.addWidget(QLabel("Include:"))
        self.chk_cover = QCheckBox("Cover PNG (3000px long side)")
        self.chk_small = QCheckBox("Small PNG (960px)")
        self.chk_thumb = QCheckBox("Thumb 1080p")
        self.chk_vector = QCheckBox("Vector SVG")
        self.chk_anim = QCheckBox("Animation GIF")
        self.chk_meta = QCheckBox("Metadata JSON")
        sel = selection or ExportSelection()
        self.chk_cover.setChecked(sel.cover)
        self.chk_small.setChecked(sel.small)
        self.chk_thumb.setChecked(sel.thumb_1080p)
        self.chk_vector.setChecked(sel.vector)
        self.chk_vector.setToolTip("Vector for logos/merch (no post-fx)")
        self.chk_anim.setChecked(sel.anim)
        self.chk_anim.setToolTip("Animation for socials (Pillow only)")
        self.chk_meta.setChecked(sel.metadata)
        for chk in (self.chk_cover, self.chk_small, self.chk_thumb,
                    self.chk_vector, self.chk_anim, self.chk_meta):
            chk.stateChanged.connect(self._refresh_plan)
            col.addWidget(chk)
        # -- gif --
        gif_row = QHBoxLayout()
        gif_row.addWidget(QLabel("GIF frames:"))
        self.spn_gframes = QSpinBox()
        self.spn_gframes.setRange(2, 8)
        self.spn_gframes.setValue(int(gif_frames))
        self.spn_gframes.valueChanged.connect(self._refresh_plan)
        gif_row.addWidget(self.spn_gframes)
        self.cmb_gifmode = QComboBox()
        self.cmb_gifmode.addItems(["phase", "hue", "both"])
        self.cmb_gifmode.setCurrentText(gif_mode if gif_mode in ("phase", "hue", "both") else "both")
        self.cmb_gifmode.currentTextChanged.connect(self._refresh_plan)
        gif_row.addWidget(self.cmb_gifmode, 1)
        col.addLayout(gif_row)
        # -- colisión (GIMP pregunta; aquí se elige política) --
        ow_row = QHBoxLayout()
        ow_row.addWidget(QLabel("If files exist:"))
        self.cmb_overwrite = QComboBox()
        self.cmb_overwrite.addItems(["overwrite", "skip", "rename"])
        self.cmb_overwrite.setCurrentText(overwrite if overwrite in ("overwrite", "skip", "rename") else "overwrite")
        self.cmb_overwrite.setToolTip("overwrite: replace · skip: keep existing · rename: save as name_2…")
        ow_row.addWidget(self.cmb_overwrite, 1)
        col.addLayout(ow_row)
        # -- plan (GIMP muestra tamaño estimado: aquí la lista + ~peso) --
        col.addWidget(QLabel("Files to write:"))
        self.list_files = QListWidget()
        self.list_files.setMinimumHeight(110)
        col.addWidget(self.list_files, 1)
        self.lbl_total = QLabel()
        col.addWidget(self.lbl_total)
        # -- botones --
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

    # -- plan en vivo --
    def _current_selection(self) -> ExportSelection:
        return ExportSelection(
            cover=self.chk_cover.isChecked(),
            small=self.chk_small.isChecked(),
            thumb_1080p=self.chk_thumb.isChecked(),
            vector=self.chk_vector.isChecked(),
            anim=self.chk_anim.isChecked(),
            metadata=self.chk_meta.isChecked(),
        )

    def _refresh_plan(self) -> None:
        if not getattr(self, "_ready", False):
            return
        try:
            opts = ExportOptions(
                base=self.edit_base.text().strip() or "cover",
                selection=self._current_selection(),
                overwrite=self.cmb_overwrite.currentText(),
            )
            plan = plan_export(
                self._img, opts, meta=self._meta,
                has_vector=True, has_gif=True,
                extra={"vector_cells": self._vector_cells or (0, 0),
                       "gif_frames": int(self.spn_gframes.value())},
            )
        except ValueError:
            plan = []
        self.list_files.clear()
        total = 0
        for _, fname, est in plan:
            self.list_files.addItem(f"{fname}  ({_fmt_size(est)})")
            total += est
        n = len(plan)
        self.lbl_total.setText(f"{n} file(s) · {_fmt_size(total)} total (approx)")
        self.btn_export.setEnabled(n > 0)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Export folder", self.edit_dir.text())
        if d:
            self.edit_dir.setText(d)

    def _on_export(self) -> None:
        if not self.edit_base.text().strip():
            self.edit_base.setText("cover")
        self.accept()

    # -- resultado --
    def options(self) -> tuple[ExportOptions, Path, int, str]:
        """(opciones, destino, gif_frames, gif_mode). Solo tras Accept."""
        opts = ExportOptions(
            base=self.edit_base.text().strip() or "cover",
            selection=self._current_selection(),
            overwrite=self.cmb_overwrite.currentText(),
        )
        return opts, Path(self.edit_dir.text()), int(self.spn_gframes.value()), self.cmb_gifmode.currentText()


__all__ = ["ExportDialog"]
