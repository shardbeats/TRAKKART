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
            self.chk_mp4.setToolTip("Needs the opt-in video extra: pip install -r requirements-video.txt")
        for chk in (self.chk_image, self.chk_thumb,
                    self.chk_vector, self.chk_anim, self.chk_meta,
                    self.chk_black, self.chk_mp4):
            chk.stateChanged.connect(self._refresh_plan)
            col.addWidget(chk)
        col.addWidget(self.chk_lossless)
        # -- animación: sin duplicados (se edita solo en VIDEO); aquí solo on/off --
        self._gif_spec = {
            "frames": max(2, min(24, int(gif_frames))),
            "mode": gif_mode if gif_mode in self.GIF_MODES else "both",
            "fps": max(2, min(60, int(gif_fps))),
            "pingpong": bool(gif_pingpong),
        }
        self.lbl_gifspec = QLabel()
        self.lbl_gifspec.setWordWrap(True)
        self.lbl_gifspec.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_gifspec)
        self._sync_gifspec_label()
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

    def _on_lossless(self) -> None:
        on = self.chk_lossless.isChecked()
        self.cmb_format.setEnabled(not on)
        self.spn_quality.setEnabled(not on)
        self._refresh_plan()

    # -- plan en vivo --
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
        if self.chk_mp4.isChecked() and self._video_ok:
            try:
                w, h = self._doc_wh()
                nf = int(self._gif_opts()["frames"])
                est = int(w * h * nf * 0.12)
                self.list_files.addItem(
                    f"{self.edit_base.text().strip() or 'cover'}_clip.mp4  ({_fmt_size(est)})")
                total += est
                n += 1
            except Exception:  # noqa: BLE001
                pass
        self.lbl_total.setText(f"{n} file(s) · {_fmt_size(total)} total (approx)")
        self.btn_export.setEnabled(n > 0)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Export folder", self.edit_dir.text())
        if d:
            self.edit_dir.setText(d)

    # -- animación: la spec viene de VIDEO (aquí no se edita, solo se muestra) --
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
        g["size"] = self._current_size()  # el canvas manda también en el anim
        g["pingpong"] = bool(g.get("pingpong", False))
        g["mp4"] = bool(self.chk_mp4.isChecked() and self._video_ok)
        return g

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
        fmt = "png" if self.chk_lossless.isChecked() else self.cmb_format.currentText()
        opts = ExportOptions(
            base=self.edit_base.text().strip() or "cover",
            selection=self._current_selection(),
            overwrite=self.cmb_overwrite.currentText(),
            size=self._current_size(),
            format=fmt,
            quality=int(self.spn_quality.value()),
        )
        return opts, Path(self.edit_dir.text()), self._gif_opts()

    # -- compat: (opts, out, frames, mode) para código/tests viejos --
    def legacy_options(self) -> tuple[ExportOptions, Path, int, str]:
        opts, out, g = self.options()
        return opts, out, int(g["frames"]), str(g["mode"])


__all__ = ["ExportDialog"]
