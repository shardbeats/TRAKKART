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
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
)

from app.exporter import (
    EXPORT_FORMATS,
    MAX_SIDE,
    MIN_SIDE,
    SIZE_PRESETS,
    ExportOptions,
    ExportSelection,
    plan_export,
)
from app.ui.qt_image import pil_to_pixmap

GIF_PREVIEW_FPS = 8
GIF_PREVIEW_MAX_SIDE = 240


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
        self._preset = preset  # para el live preview del GIF (None = sin preview)
        self._gif_count = max(1, int(gif_frames))
        self._ready = False  # las señales del __init__ no pintan nada aún
        self._gif_cache: dict[tuple[int, str], list] = {}
        self._gif_idx = 0
        self._gif_timer = None
        from PySide6.QtCore import QTimer

        self._gif_timer = QTimer(self)
        self._gif_timer.setInterval(1000 // GIF_PREVIEW_FPS)
        self._gif_timer.timeout.connect(self._next_gif_frame)

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
        # -- tamaño (GIMP/photoshop: el lienzo se dimensiona aquí) --
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self.cmb_size = QComboBox()
        self.cmb_size.addItems([str(s) for s in SIZE_PRESETS] + ["Custom"])
        self.cmb_size.setToolTip("Long side in px (presets or Custom)")
        self.cmb_size.currentTextChanged.connect(self._on_size_preset)
        size_row.addWidget(self.cmb_size)
        self.spn_size = QSpinBox()
        self.spn_size.setRange(MIN_SIDE, MAX_SIDE)
        self.spn_size.setValue(max(MIN_SIDE, min(MAX_SIDE, int(size))))
        self.spn_size.setSuffix(" px")
        self.spn_size.setToolTip("Long side of the exported image")
        self.spn_size.valueChanged.connect(self._on_size_custom)
        size_row.addWidget(self.spn_size, 1)
        self.lbl_dims = QLabel()
        self.lbl_dims.setMinimumWidth(130)
        self.lbl_dims.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        size_row.addWidget(self.lbl_dims)
        col.addLayout(size_row)
        self._sync_size_combo(int(size))
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
        self.chk_anim.stateChanged.connect(self._refresh_gif_preview)
        self.spn_gframes.valueChanged.connect(self._refresh_gif_preview)
        self.cmb_gifmode.currentTextChanged.connect(self._refresh_gif_preview)
        # -- live preview del GIF (se genera al activar, cacheado por config) --
        prev_row = QHBoxLayout()
        self.lbl_gifprev = QLabel("GIF preview off")
        self.lbl_gifprev.setAlignment(Qt.AlignCenter)
        self.lbl_gifprev.setMinimumSize(160, 120)
        self.lbl_gifprev.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.lbl_gifprev.setObjectName("previewFrame")
        prev_row.addWidget(self.lbl_gifprev, 1)
        col.addLayout(prev_row)
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
        return max(MIN_SIDE, min(MAX_SIDE, int(self.spn_size.value())))

    def _on_size_preset(self, text: str) -> None:
        if text == "Custom":
            return
        try:
            self.spn_size.blockSignals(True)
            self.spn_size.setValue(int(text))
        finally:
            self.spn_size.blockSignals(False)
        self._refresh_plan()

    def _on_size_custom(self) -> None:
        self._sync_size_combo(int(self.spn_size.value()))
        self._refresh_plan()

    def _sync_size_combo(self, size: int) -> None:
        txt = str(size) if size in SIZE_PRESETS else "Custom"
        if self.cmb_size.currentText() != txt:
            self.cmb_size.blockSignals(True)
            self.cmb_size.setCurrentText(txt)
            self.cmb_size.blockSignals(False)

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
            self.lbl_dims.setText(f"{w}×{h}")
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

    # -- live preview del GIF (cacheado por config, ~8fps como el export) --
    def _refresh_gif_preview(self) -> None:
        if not getattr(self, "_ready", False):
            return
        if not self.chk_anim.isChecked() or self._preset is None:
            self._gif_timer.stop()
            from PySide6.QtGui import QPixmap

            self.lbl_gifprev.setPixmap(QPixmap())
            self.lbl_gifprev.setText("GIF preview off")
            return
        key = (int(self.spn_gframes.value()), self.cmb_gifmode.currentText())
        if key not in self._gif_cache:
            self._gif_cache[key] = self._build_gif_preview(*key)
        self._gif_key = key
        self._gif_idx = 0
        self._show_gif_frame()
        if len(self._gif_cache.get(key, [])) > 1 and not self._gif_timer.isActive():
            self._gif_timer.start()

    def _build_gif_preview(self, frames: int, mode: str) -> list:
        """Frames reducidos (240px) con la config actual. Lento sin numba: 1 vez por config."""
        from PySide6.QtWidgets import QApplication

        from app.gif import gif_frames

        small = self._img.convert("RGB")
        m = max(small.width, small.height)
        if m > GIF_PREVIEW_MAX_SIDE:
            f = GIF_PREVIEW_MAX_SIDE / m
            small = small.resize(
                (max(1, round(small.width * f)), max(1, round(small.height * f))),
                Image.BICUBIC,
            )
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            out = gif_frames(small, self._preset, frames=int(frames), mode=mode)
            return [pil_to_pixmap(f, max_side=200) for f in out]
        except Exception:  # noqa: BLE001
            return []
        finally:
            QApplication.restoreOverrideCursor()

    def _show_gif_frame(self) -> None:
        frames = self._gif_cache.get(getattr(self, "_gif_key", None), [])
        if frames:
            self.lbl_gifprev.setPixmap(frames[self._gif_idx % len(frames)])
            self.lbl_gifprev.setText("")

    def _next_gif_frame(self) -> None:
        frames = self._gif_cache.get(getattr(self, "_gif_key", None), [])
        if not frames:
            self._gif_timer.stop()
            return
        self._gif_idx = (self._gif_idx + 1) % len(frames)
        self._show_gif_frame()

    def _stop_preview(self) -> None:
        try:
            self._gif_timer.stop()
        except Exception:  # noqa: BLE001
            pass

    def reject(self) -> None:  # noqa: N802
        self._stop_preview()
        super().reject()

    def _on_export(self) -> None:
        if not self.edit_base.text().strip():
            self.edit_base.setText("cover")
        self._stop_preview()
        self.accept()

    # -- resultado --
    def options(self) -> tuple[ExportOptions, Path, int, str]:
        """(opciones, destino, gif_frames, gif_mode). Solo tras Accept."""
        opts = ExportOptions(
            base=self.edit_base.text().strip() or "cover",
            selection=self._current_selection(),
            overwrite=self.cmb_overwrite.currentText(),
            size=self._current_size(),
            format=self.cmb_format.currentText(),
            quality=int(self.spn_quality.value()),
        )
        return opts, Path(self.edit_dir.text()), int(self.spn_gframes.value()), self.cmb_gifmode.currentText()


__all__ = ["ExportDialog"]
