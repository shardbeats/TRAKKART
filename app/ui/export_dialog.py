"""Export dialog — Photoshop/GIMP style: name, destination, outputs, collision.

El motor (`export_bundle`/`export_with_options`) no pregunta nada;
este diálogo pregunta todo y previsualiza lo que va a salir.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
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

from app.exporter import (
    EXPORT_FORMATS,
    MAX_SIDE,
    MIN_SIDE,
    ExportOptions,
    ExportSelection,
    plan_export,
)


def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"~{n / (1024 * 1024):.1f}MB"
    if n >= 1024:
        return f"~{n // 1024}KB"
    return f"~{n}B"


class ExportDialog(QDialog):
    """Qué sale, dónde y con qué nombre. `options()` solo válido tras Accept."""

    GIF_MODES = ("phase", "hue", "both", "glitch", "mix")

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
        gif_size: int = 1200,
        gif_pingpong: bool = False,
        overwrite: str = "overwrite",
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
        self._preset = preset  # se guarda por compat; el preview vive en modo Video
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
        # -- documento único: el tamaño viene de CANVAS, aquí solo se muestra --
        self._doc_size = max(MIN_SIDE, min(MAX_SIDE, int(size)))
        doc_row = QHBoxLayout()
        doc_row.addWidget(QLabel("Document:"))
        self.lbl_dims = QLabel()
        self.lbl_dims.setMinimumWidth(130)
        self.lbl_dims.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_dims.setToolTip("Main image renders at the CANVAS document size")
        doc_row.addWidget(self.lbl_dims, 1)
        col.addLayout(doc_row)
        # -- formato (GIMP: la extensión manda; aquí el combo) --
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(list(EXPORT_FORMATS))
        self.cmb_format.setCurrentText(format if format in EXPORT_FORMATS else "png")
        self.cmb_format.setToolTip("PNG: lossless, ideal dither · JPG: small, artifacts · WebP: small, modern")
        self.cmb_format.currentTextChanged.connect(self._refresh_plan)
        fmt_row.addWidget(self.cmb_format)
        self.spn_quality = QSpinBox()
        self.spn_quality.setRange(1, 100)
        self.spn_quality.setValue(max(1, min(100, int(quality))))
        self.spn_quality.setSuffix("%")
        self.spn_quality.setToolTip("Quality for JPG/WebP (PNG ignores it)")
        self.spn_quality.valueChanged.connect(self._refresh_plan)
        fmt_row.addWidget(self.spn_quality)
        col.addLayout(fmt_row)
        # -- salidas --
        col.addWidget(QLabel("Include:"))
        self.chk_image = QCheckBox("Main image")
        self.chk_thumb = QCheckBox("Social thumb 1080p")
        self.chk_vector = QCheckBox("Vector SVG")
        self.chk_anim = QCheckBox("Animation GIF")
        self.chk_meta = QCheckBox("Metadata JSON")
        sel = selection or ExportSelection()
        self.chk_image.setChecked(sel.image)
        self.chk_thumb.setChecked(sel.thumb_1080p)
        self.chk_vector.setChecked(sel.vector)
        self.chk_vector.setToolTip("Vector for logos/merch (no post-fx)")
        self.chk_anim.setChecked(sel.anim)
        self.chk_anim.setToolTip("Animation for socials (Pillow only)")
        self.chk_meta.setChecked(sel.metadata)
        for chk in (self.chk_image, self.chk_thumb,
                    self.chk_vector, self.chk_anim, self.chk_meta):
            chk.stateChanged.connect(self._refresh_plan)
            col.addWidget(chk)
        # -- gif (frames / mode / fps / size / pingpong) --
        gif_row = QHBoxLayout()
        gif_row.addWidget(QLabel("GIF frames:"))
        self.spn_gframes = QSpinBox()
        self.spn_gframes.setRange(2, 12)
        self.spn_gframes.setValue(max(2, min(12, int(gif_frames))))
        self.spn_gframes.setToolTip("2-12 frames (more = heavier)")
        self.spn_gframes.valueChanged.connect(self._refresh_plan)
        gif_row.addWidget(self.spn_gframes)
        self.cmb_gifmode = QComboBox()
        self.cmb_gifmode.addItems(list(self.GIF_MODES))
        self.cmb_gifmode.setCurrentText(gif_mode if gif_mode in self.GIF_MODES else "both")
        self.cmb_gifmode.setToolTip("phase=march · hue=cycle · both=legacy · glitch=CRT · mix=all")
        self.cmb_gifmode.currentTextChanged.connect(self._refresh_plan)
        gif_row.addWidget(self.cmb_gifmode, 1)
        col.addLayout(gif_row)
        gif_row2 = QHBoxLayout()
        gif_row2.addWidget(QLabel("FPS:"))
        self.spn_gfps = QSpinBox()
        self.spn_gfps.setRange(2, 24)
        self.spn_gfps.setValue(max(2, min(24, int(gif_fps))))
        self.spn_gfps.setToolTip("Playback speed 2-24 fps")
        self.spn_gfps.valueChanged.connect(self._refresh_plan)
        gif_row2.addWidget(self.spn_gfps)
        gif_row2.addWidget(QLabel("Size:"))
        self.spn_gsize = QSpinBox()
        self.spn_gsize.setRange(240, 1920)
        self.spn_gsize.setValue(max(240, min(1920, int(gif_size))))
        self.spn_gsize.setSuffix(" px")
        self.spn_gsize.setToolTip("Long side 240-1920px (480 = socials, 1200 = HD)")
        self.spn_gsize.valueChanged.connect(self._refresh_plan)
        gif_row2.addWidget(self.spn_gsize)
        self.chk_pingpong = QCheckBox("Ping-pong")
        self.chk_pingpong.setChecked(bool(gif_pingpong))
        self.chk_pingpong.setToolTip("Forward-backward loop (no jump cut)")
        gif_row2.addWidget(self.chk_pingpong)
        col.addLayout(gif_row2)
        col.addWidget(QLabel("Tip: preview the animation live in VIDEO mode (main window)."))
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
            image=self.chk_image.isChecked(),
            thumb_1080p=self.chk_thumb.isChecked(),
            vector=self.chk_vector.isChecked(),
            anim=self.chk_anim.isChecked(),
            metadata=self.chk_meta.isChecked(),
        )

    def _current_size(self) -> int:
        return int(getattr(self, "_doc_size", 3000))

    def _refresh_plan(self) -> None:
        if not getattr(self, "_ready", False):
            return
        try:
            from app.canvas import canvas_size_for

            ratio = (self._meta or {}).get("ratio", "1:1")
            try:
                w, h = canvas_size_for(ratio, self._current_size())
            except KeyError:
                w, h = (self._current_size(), self._current_size())
            self.lbl_dims.setText(f"{w}×{h} (from CANVAS)")
            opts = ExportOptions(
                base=self.edit_base.text().strip() or "cover",
                selection=self._current_selection(),
                overwrite=self.cmb_overwrite.currentText(),
                size=self._current_size(),
                format=self.cmb_format.currentText(),
                quality=int(self.spn_quality.value()),
            )
            plan = plan_export(
                self._img, opts, meta=self._meta,
                has_vector=True, has_gif=True,
                extra={"vector_cells": self._vector_cells or (0, 0),
                       "gif_frames": int(self.spn_gframes.value()),
                       "gif_size": int(self.spn_gsize.value())},
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

    # -- gif opts (sin preview: el preview vive en modo VIDEO) --
    def _gif_opts(self) -> dict:
        return {
            "frames": int(self.spn_gframes.value()),
            "mode": self.cmb_gifmode.currentText(),
            "fps": int(self.spn_gfps.value()),
            "size": int(self.spn_gsize.value()),
            "pingpong": bool(self.chk_pingpong.isChecked()),
        }

    def _on_export(self) -> None:
        if not self.edit_base.text().strip():
            self.edit_base.setText("cover")
        self.accept()

    # -- resultado --
    def options(self) -> tuple[ExportOptions, Path, dict]:
        """(opciones, destino, gif_opts). Solo tras Accept.

        gif_opts = {frames, mode, fps, size, pingpong}. Los callers viejos
        que desempaquetaban (opts, out, frames, mode) siguen funcionando
        via GifOpts (tupla + dict a la vez).
        """
        opts = ExportOptions(
            base=self.edit_base.text().strip() or "cover",
            selection=self._current_selection(),
            overwrite=self.cmb_overwrite.currentText(),
            size=self._current_size(),
            format=self.cmb_format.currentText(),
            quality=int(self.spn_quality.value()),
        )
        return opts, Path(self.edit_dir.text()), self._gif_opts()

    # -- compat: (opts, out, frames, mode) para código/tests viejos --
    def legacy_options(self) -> tuple[ExportOptions, Path, int, str]:
        opts, out, g = self.options()
        return opts, out, int(g["frames"]), str(g["mode"])


__all__ = ["ExportDialog"]
