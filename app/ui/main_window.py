"""TRAKKART main window — dither preview + export + cover flow.

Refactorizado: la ventana orquesta, no implementa.
- Construcción UI -> app.ui.panels
- Conversiones Qt/PIL -> app.ui.qt_image
- Carga IO (fs/web/clipboard) -> app.services.image_io
- Render/export -> app.services.render_service / export_service
- Params únicos -> Preset.to_render_kwargs (app.render_params)

API pública intacta (tests test_ui_* dependen de ella).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.adjust import Adjust
from app.batch import batch_process
from app.canvas import CROP_MODES, ratio_names
from app.dither import METHODS
from app.history import HistoryStore
from app.ops import ImageHistory, flip_h, flip_v, invert, rotate_left, rotate_right
from app.palettes import palette_names
from app.paths import get_db_path, get_out_dir
from app.presets import Preset, ensure_bundled, list_presets, load_preset, save_preset
from app.render_params import normalize_scanlines, normalize_slice_bands
from app.export_prefs import ExportPrefs, load_prefs, save_prefs
from app.exporter import ExportSelection
from app.ui.batch_dialog import BatchDialog
from app.ui.export_dialog import ExportDialog
from app.ui.qt_image import pil_to_pixmap as _pil_to_pixmap_impl
from app.ui.qt_image import qimage_to_pil
from app.ui.workers import BatchWorker


def pil_to_pixmap(img: Image.Image, max_side: int = 520) -> QPixmap:
    """Compat: implementación única en app.ui.qt_image."""
    return _pil_to_pixmap_impl(img, max_side=max_side)


class MainWindow(QMainWindow):
    def __init__(self, out_dir: Path | None = None, db_path: Path | None = None,
                 prefs_path: Path | None = None) -> None:
        super().__init__()
        self.src: Image.Image | None = None
        self.src_name: str = "trakkart_cover"
        self.result: Image.Image | None = None
        self.zoom: float = 1.0
        self.history = ImageHistory()
        self.crop_fx = 50.0
        self.crop_fy = 50.0
        self.crop_zoom = 1.0
        self.setAcceptDrops(True)
        self.out_dir = Path(out_dir) if out_dir else get_out_dir()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.store = HistoryStore(db_path if db_path else get_db_path())
        self._prefs_path = Path(prefs_path) if prefs_path else None
        self._batch_start: float = 0.0
        self._batch_out: Path | None = None
        # Salidas vector/GIF + tamaño/formato: viven en el preset (receta);
        # cada diálogo elige por operación (sin panel duplicado).
        self._vector_export: bool = False
        self._vector_cell: int = 8
        self._gif_export: bool = False
        self._gif_frames: int = 6
        self._gif_mode: str = "both"
        self._export_size: int = 3000
        self._export_format: str = "png"
        self._export_quality: int = 90
        self.duotone_dark: str = ""
        self.duotone_light: str = ""
        self.border_color: str = "#000000"
        # La paleta en uso es la tira custom (los presets con nombre son
        # puntos de partida). _palette_base recuerda de cuál se derivó.
        self._palette_base: str = "SLIME"
        self._palette_dirty: bool = False
        ensure_bundled()
        from app.palette_library import ensure_bundled_palettes

        ensure_bundled_palettes()
        self._batch_worker: BatchWorker | None = None
        self._batch_cancel: list[bool] = [False]
        self._preview_worker = None
        self._preview_token = 0
        self._preview_pending = False
        from PySide6.QtCore import QTimer

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(350)  # family-style debounce (never freeze UI)
        self._preview_timer.timeout.connect(self.refresh)
        self._setup_ui()
        self._build_menus()
        self.refresh_presets()
        self.refresh_palette_list()
        self._apply_preset("SLIME_FS")
        self._status("Open an image to start.")

    def closeEvent(self, event) -> None:  # noqa: N802
        """Limpieza determinista: sin timers ni slots huerfanos tras cerrar.

        Sin esto, una ventana cerrada puede sobrevivir al GC con el timer
        de debounce armado y renderizar sobre UI muerta (caza de los E2E).
        """
        try:
            self._preview_timer.stop()
        except Exception:  # noqa: BLE001
            pass
        self._batch_cancel[0] = True
        for worker in (self._preview_worker, self._batch_worker):
            try:
                if worker is not None:
                    worker.blockSignals(True)  # sus slots nunca tocan UI muerta
            except Exception:  # noqa: BLE001
                pass
        super().closeEvent(event)

    def _schedule_refresh(self) -> None:
        """Deferred 350ms re-render: sliders never freeze the UI."""
        if not self._preview_timer.isActive():
            self._preview_timer.start()

    def _labeled_slider(self, parent, label, lo, hi, val, tooltip="", div=None):
        """Row [label | slider | value]. Double-click resets to default."""
        from app.ui import panels as _panels

        return _panels.labeled_slider(self, parent, label, lo, hi, val, tooltip, div)

    def _mini_slider(self, lo, hi, val, tooltip="", div=None):
        """Slider + value label (for shared rows)."""
        from app.ui import panels as _panels

        return _panels.mini_slider(self, lo, hi, val, tooltip, div)

    def _status(self, msg: str) -> None:
        """Single status point: label + status bar (family pattern)."""
        self.lbl_status.setText(msg)
        try:
            self.statusBar().showMessage(msg)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction (orquesta panels.py; cada sección < 30 líneas)
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        self.setWindowTitle(f"TRAKKART v{__version__} — dither covers")
        self.resize(1280, 780)
        self.setMinimumSize(1060, 640)
        icon = Path(__file__).resolve().parent.parent.parent / "icon.png"
        if icon.exists():
            from PySide6.QtGui import QIcon

            self.setWindowIcon(QIcon(str(icon)))
        try:
            from app.ui.theme import load_stylesheet

            qss = load_stylesheet()
            if qss:
                self.setStyleSheet(qss)
        except Exception:
            pass
        central = QWidget()
        self.setCentralWidget(central)
        col = QVBoxLayout(central)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("TRAKKART")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        subtitle = QLabel(f"v{__version__} · offline dither covers")
        subtitle.setObjectName("subtitleLabel")
        header.addWidget(subtitle)
        header.addStretch()
        col.addLayout(header)

        root = QHBoxLayout()
        root.setSpacing(8)
        col.addLayout(root, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(360)
        scroll.setMaximumWidth(460)
        panel_host = QWidget()
        panel = QVBoxLayout(panel_host)
        panel.setContentsMargins(2, 2, 6, 2)
        scroll.setWidget(panel_host)
        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.addWidget(scroll, 1)
        root.addLayout(left_col, 0)
        self._action_bar = QVBoxLayout()
        self._action_bar.setSpacing(4)
        left_col.addLayout(self._action_bar)

        self._setup_control_panel(panel)
        self._setup_action_bar()
        self._setup_previews(root)

        self.statusBar().showMessage("TRAKKART ready")
        ver = QLabel(f"v{__version__} offline")
        ver.setObjectName("subtitleLabel")
        self.statusBar().addPermanentWidget(ver)
        self._sync_crop_label()

    def _setup_control_panel(self, panel: QVBoxLayout) -> None:
        from app.ui import panels as P

        P.build_image_section(self, P.make_group(panel, "IMAGE"))
        P.build_preset_section(self, P.make_group(panel, "PRESET"))
        P.build_method_section(self, P.make_group(panel, "METHOD"), METHODS)
        P.build_pixel_section(self, P.make_group(panel, "PIXEL"))
        P.build_color_section(self, P.make_group(panel, "COLOR"))
        P.build_canvas_section(self, P.make_group(panel, "CANVAS"), ratio_names(), CROP_MODES)
        P.build_pre_section(self, P.make_group(panel, "PRE-PROCESS"))
        P.build_grade_section(self, P.make_group(panel, "GRADE"))
        P.build_texture_section(self, P.make_group(panel, "TEXTURE"))
        P.build_glitch_section(self, P.make_group(panel, "GLITCH"))
        P.build_custom_palette_section(self, P.make_group(panel, "CUSTOM PALETTE"))
        panel.addStretch()

    def _setup_action_bar(self) -> None:
        self.btn_export = QPushButton("Export…")
        self.btn_export.setToolTip("Export with options (Ctrl+Shift+S) · Quick export (Ctrl+S)")
        self.btn_export.setObjectName("exportBtn")
        self.btn_export.clicked.connect(lambda: self.export(False))
        self._action_bar.addWidget(self.btn_export)

        batch_row = QHBoxLayout()
        self.btn_batch = QPushButton("Batch folder...")
        self.btn_batch.setToolTip("Process every image in a folder with the current preset")
        self.btn_batch.clicked.connect(self.run_batch_dialog)
        batch_row.addWidget(self.btn_batch, 1)
        self.btn_cancel = QPushButton("X")
        self.btn_cancel.setToolTip("Cancel batch")
        self.btn_cancel.clicked.connect(self.cancel_batch)
        self.btn_cancel.hide()
        batch_row.addWidget(self.btn_cancel)
        self.chk_batch_drop = QCheckBox("Drop=Batch")
        self.chk_batch_drop.setToolTip("OFF = dropping only loads images. ON = dropping a folder asks for confirmation and processes it.")
        self.chk_batch_drop.setChecked(False)
        batch_row.addWidget(self.chk_batch_drop)
        batch_row.addWidget(QLabel("Jobs:"))
        from PySide6.QtWidgets import QSpinBox

        self.spn_jobs = QSpinBox()
        self.spn_jobs.setRange(1, 8)
        self.spn_jobs.setValue(1)
        self.spn_jobs.setFixedWidth(56)
        self.spn_jobs.setToolTip("1 = sequential (safe). >1 = multiprocessing.")
        batch_row.addWidget(self.spn_jobs)
        self._action_bar.addLayout(batch_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        self._action_bar.addWidget(self.progress)
        self.lbl_status = QLabel("Open an image to start.")
        self.lbl_status.setWordWrap(True)
        self._action_bar.addWidget(self.lbl_status)

    def _setup_previews(self, root: QHBoxLayout) -> None:
        previews = QHBoxLayout()
        previews.setSpacing(8)
        orig_col = QVBoxLayout()
        self.lbl_orig_title = QLabel("ORIGINAL")
        self.lbl_orig_title.setObjectName("previewTitle")
        self.lbl_orig_title.setAlignment(Qt.AlignCenter)
        orig_col.addWidget(self.lbl_orig_title)
        self.lbl_orig = QLabel("NO IMAGE")
        self.lbl_orig.setObjectName("previewFrame")
        self.lbl_orig.setAlignment(Qt.AlignCenter)
        self.lbl_orig.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_orig.setMinimumSize(200, 200)
        orig_col.addWidget(self.lbl_orig, 1)
        previews.addLayout(orig_col, 1)
        res_col = QVBoxLayout()
        self.lbl_res_title = QLabel("DITHER")
        self.lbl_res_title.setObjectName("previewTitle")
        self.lbl_res_title.setAlignment(Qt.AlignCenter)
        res_col.addWidget(self.lbl_res_title)
        self.lbl_res = QLabel("NO IMAGE")
        self.lbl_res.setObjectName("previewFrame")
        self.lbl_res.setAlignment(Qt.AlignCenter)
        self.lbl_res.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_res.setMinimumSize(200, 200)
        res_col.addWidget(self.lbl_res, 1)
        previews.addLayout(res_col, 1)
        root.addLayout(previews, 1)

    def open_image(self) -> None:
        """Compat: opens dialog (use open_image_dialog)."""
        self.open_image_dialog()

    # ------------------------------------------------------------------
    # Params: current_params() es la única fuente; _render_kwargs delega.
    # ------------------------------------------------------------------
    def _render_kwargs(self) -> dict:
        return self.current_params().to_render_kwargs()

    def refresh(self) -> None:
        if self.src is None:
            return
        try:
            from app.services.render_service import render_full, should_render_async

            if should_render_async(self.src):
                self._start_preview_async()  # no numba and big: do not freeze
                return
            self.result = render_full(self.src, self.current_params())
            self._show_preview(self.src, self.result)
        except Exception as e:  # noqa: BLE001
            self._status(f"Error: {e}")

    def _show_preview(self, orig: Image.Image, res: Image.Image) -> None:
        zoomed = int(520 * self.zoom)
        self.lbl_orig.setPixmap(pil_to_pixmap(orig, max_side=zoomed))
        self.lbl_orig_title.setText(f"ORIGINAL · {orig.width}x{orig.height}")
        self.lbl_res.setPixmap(pil_to_pixmap(res, max_side=zoomed))
        self.lbl_res_title.setText(f"DITHER · {res.width}x{res.height}")

    def _start_preview_async(self) -> None:
        from app.ui.preview_worker import PreviewWorker

        if self._preview_worker is not None and self._preview_worker.isRunning():
            self._preview_pending = True
            self._status("Rendering heavy preview in the background...")
            return
        self._preview_token += 1
        self._preview_worker = PreviewWorker(
            self.src.copy(), self._render_kwargs(), self._preview_token
        )
        self._preview_worker.finished_ok.connect(self._on_preview_done)
        self._preview_worker.finished_err.connect(self._on_preview_error)
        self._status("Rendering heavy preview in the background...")
        self._preview_worker.start()

    def _on_preview_done(self, qimg, pil_img, token: int) -> None:
        from PySide6.QtGui import QPixmap

        if token != self._preview_token:
            return  # stale: another render is already on its way
        self.result = pil_img
        self.lbl_res.setPixmap(QPixmap.fromImage(qimg))
        self.lbl_res_title.setText(f"DITHER · {pil_img.width}x{pil_img.height}")
        self._status("Preview ready")
        if self._preview_pending:
            self._preview_pending = False
            self._start_preview_async()

    def _on_preview_error(self, msg: str, token: int) -> None:
        if token != self._preview_token:
            return
        if self._preview_pending:
            self._preview_pending = False
            self._start_preview_async()
            return
        self._status(f"Preview error: {msg}")

    def _valid_slice_bands(self) -> int:
        return normalize_slice_bands(int(self.spn_slice.value()))

    def current_adjust(self) -> Adjust:
        return Adjust(
            brightness=self.sld_bri.value() / 100.0,
            contrast=self.sld_con.value() / 100.0,
            saturation=self.sld_sat.value() / 100.0,
        )

    # -- presets --
    def current_params(self) -> Preset:
        from app.render_params import (
            normalize_grille,
            normalize_halftone,
            normalize_posterize,
        )

        base = self._palette_base if self._palette_base in palette_names() else "SLIME"
        return Preset(
            name=self.cmb_preset.currentText(),
            method=self.cmb_method.currentText(),
            palette=base,
            pixel_size=int(self.spn_pixel.value()),
            threshold=int(self.sld_thr.value()),
            brightness=self.sld_bri.value() / 100.0,
            contrast=self.sld_con.value() / 100.0,
            saturation=self.sld_sat.value() / 100.0,
            ratio=self.cmb_ratio.currentText(),
            crop_mode=self.cmb_crop.currentText(),
            focus_x=float(self.crop_fx),
            focus_y=float(self.crop_fy),
            crop_zoom=float(self.crop_zoom),
            pre_blur=self.sld_blur.value() / 10.0,
            pre_sharpen=int(self.spn_sharp.value()),
            pre_hue=float(self.sld_hue.value()),
            pre_denoise=int(self.spn_denoise.value()),
            pre_smooth=self.sld_smooth.value() / 10.0,
            glow_radius=float(self.spn_glowrad.value()) if self.sld_glow.value() > 0 else 0.0,
            glow_intensity=float(self.sld_glow.value()),
            glow_threshold=int(self.spn_glowthr.value()),
            grain=float(self.sld_grain.value()),
            vignette=float(self.sld_vig.value()),
            scanlines=normalize_scanlines(int(self.spn_scan.value())),
            replace_color=self.brand_color,
            custom_palette=[list(c) for c in self.custom_colors] or None,
            vector_export=bool(self._vector_export),
            vector_cell=int(self._vector_cell),
            gif_export=bool(self._gif_export),
            gif_frames=int(self._gif_frames),
            gif_mode=str(self._gif_mode),
            export_size=int(self._export_size),
            export_format=str(self._export_format),
            export_quality=int(self._export_quality),
            duotone_dark=self.duotone_dark,
            duotone_light=self.duotone_light,
            duotone_mid=float(self.sld_duo_mid.value()),
            posterize=normalize_posterize(int(self.spn_poster.value())),
            split_tone=float(self.sld_split.value()),
            fade=float(self.sld_fade.value()),
            halftone=normalize_halftone(int(self.spn_halftone.value())),
            halftone_shape=self.cmb_halftone.currentText(),
            dust=float(self.sld_dust.value()),
            border=int(self.spn_border.value()),
            border_color=self.border_color,
            letterbox=int(self.spn_letterbox.value()),
            glitch_chroma=int(self.sld_chroma.value()),
            glitch_slice_bands=self._valid_slice_bands(),
            glitch_slice_max=24,
            pixelsort=int(self.spn_pixelsort.value()),
            wave=int(self.spn_wave.value()),
            mosh=float(self.sld_mosh.value()),
            grille=normalize_grille(int(self.spn_grille.value())),
        )

    def pick_brand_color(self) -> None:
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        self.set_brand_color(color.name().upper())

    def set_brand_color(self, hex_color: str) -> None:
        from app.fx import parse_hex

        if hex_color and parse_hex(hex_color) is None:
            self._status("Invalid brand color (use #RRGGBB)")
            return
        self.brand_color = hex_color or ""
        self.lbl_brand.setText(self.brand_color if self.brand_color else "(no brand)")
        self.refresh()

    def pick_duotone_color(self, which: str) -> None:
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        self.set_duotone_color(which, color.name().upper())

    def set_duotone_color(self, which: str, hex_color: str) -> None:
        from app.fx import parse_hex

        if hex_color and parse_hex(hex_color) is None:
            self._status("Invalid duotone color (use #RRGGBB)")
            return
        hex_color = (hex_color or "").upper()
        if which == "light":
            self.duotone_light = hex_color
        else:
            self.duotone_dark = hex_color
        self._sync_duo_label()
        self.refresh()

    def clear_duotone(self) -> None:
        self.duotone_dark = ""
        self.duotone_light = ""
        self._sync_duo_label()
        self.refresh()

    def _sync_duo_label(self) -> None:
        if self.duotone_dark or self.duotone_light:
            self.lbl_duo.setText(f"{self.duotone_dark or '—'} → {self.duotone_light or '—'}")
        else:
            self.lbl_duo.setText("(off)")

    def pick_border_color(self) -> None:
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        self.set_border_color(color.name().upper())

    def set_border_color(self, hex_color: str) -> None:
        from app.fx import parse_hex

        if not hex_color or parse_hex(hex_color) is None:
            self._status("Invalid border color (use #RRGGBB)")
            return
        self.border_color = hex_color.upper()
        self.lbl_border.setText(self.border_color)
        self.refresh()

    def add_custom_color(self) -> None:
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        rgb = (color.red(), color.green(), color.blue())
        if rgb not in self.custom_colors and len(self.custom_colors) < 16:
            self._set_custom_colors([*self.custom_colors, rgb])
        self.refresh()

    def gen_palette(self) -> None:
        """🎲 Sorpresa: genera una paleta armoniosa (ramp/harmony en Oklch)."""
        from app.palette_gen import generate_palette

        n = max(2, len(self.custom_colors) or 4)
        style = self.cmb_palgen.currentText().lower() if hasattr(self, "cmb_palgen") else "ramp"
        self._set_custom_colors(generate_palette(n, style=style))
        self.refresh()
        self._status(f"Generated {style} palette: {len(self.custom_colors)} colors (editable)")

    def edit_custom_palette(self) -> None:
        """Full editor: swatches, hex, roles, usage, reorder, sort."""
        from app.ui.palette_dialog import CustomPaletteDialog

        dlg = CustomPaletteDialog(
            self.custom_colors, preview=self._palette_preview_small(), parent=self
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        self._set_custom_colors([tuple(c) for c in dlg.colors])
        self.refresh()
        self._status(f"Custom palette: {len(self.custom_colors)} colors")

    def _remove_custom_color(self, i: int) -> None:
        if 0 <= i < len(self.custom_colors):
            self._set_custom_colors([c for j, c in enumerate(self.custom_colors) if j != i])
            self.refresh()

    def _palette_preview_small(self):
        """Canvas actual reducido (160px) para el % de uso. None sin imagen."""
        if self.src is None:
            return None
        try:
            from app.canvas import to_canvas

            canvas = to_canvas(
                self.src, ratio=self.cmb_ratio.currentText(), mode=self.cmb_crop.currentText(),
                fx=float(self.crop_fx), fy=float(self.crop_fy), zoom=float(self.crop_zoom),
            )
            m = max(canvas.size)
            if m > 160:
                f = 160.0 / m
                canvas = canvas.resize(
                    (max(1, round(canvas.width * f)), max(1, round(canvas.height * f))),
                    Image.BICUBIC,
                )
            return canvas
        except Exception:  # noqa: BLE001
            return None

    def clear_custom_colors(self) -> None:
        self._set_custom_colors([])
        self.refresh()

    def _set_custom_colors(self, colors: list, dirty: bool = True) -> None:
        """Único punto de escritura: actualiza tira + estado dirty."""
        from app.palette_library import CUSTOM_SENTINEL

        self.custom_colors = [tuple(c) for c in colors]
        if dirty:
            self._palette_dirty = True
            if self.cmb_pal_preset.findText(CUSTOM_SENTINEL) < 0:
                self.cmb_pal_preset.addItem(CUSTOM_SENTINEL)
            self.cmb_pal_preset.blockSignals(True)
            self.cmb_pal_preset.setCurrentText(CUSTOM_SENTINEL)
            self.cmb_pal_preset.blockSignals(False)
        self._sync_custom_label()

    def _sync_custom_label(self) -> None:
        from app.ui.palette_dialog import ColorSwatch, luminance_roles, rgb_to_hex

        n = len(self.custom_colors)
        self.lbl_custom.setText(f"{n}/16")
        lay = self.palette_strip
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        roles = luminance_roles(self.custom_colors)
        for i, rgb in enumerate(self.custom_colors):
            sw = ColorSwatch(rgb, i, size=26)
            sw.setToolTip(f"{rgb_to_hex(rgb)} · {roles[i]} — click to remove")
            sw.picked.connect(self._remove_custom_color)
            lay.addWidget(sw)
        lay.addStretch()
        if n == 1:
            self.lbl_palette_hint.setText("1 color is ignored: custom needs 2–16 colors.")
        else:
            self.lbl_palette_hint.setText("")

    def refresh_presets(self) -> None:
        self.cmb_preset.blockSignals(True)
        self.cmb_preset.clear()
        self.cmb_preset.addItems(list_presets())
        self.cmb_preset.blockSignals(False)

    def refresh_palette_list(self) -> None:
        """Combo de la biblioteca (built-ins + usuario)."""
        from app.palette_library import CUSTOM_SENTINEL, list_palettes

        self.cmb_pal_preset.blockSignals(True)
        self.cmb_pal_preset.clear()
        self.cmb_pal_preset.addItems(list_palettes())
        if self._palette_dirty and self.cmb_pal_preset.findText(CUSTOM_SENTINEL) < 0:
            self.cmb_pal_preset.addItem(CUSTOM_SENTINEL)
        cur = CUSTOM_SENTINEL if self._palette_dirty else self._palette_base
        if self.cmb_pal_preset.findText(cur) >= 0:
            self.cmb_pal_preset.setCurrentText(cur)
        self.cmb_pal_preset.blockSignals(False)

    def _on_palette_preset_changed(self, name: str) -> None:
        """Elegir paleta = cargarla como copia editable (dither-guy style)."""
        from app.palette_library import CUSTOM_SENTINEL, palette_colors

        if not name or name == CUSTOM_SENTINEL:
            return
        try:
            colors = palette_colors(name)
        except ValueError:
            return
        self._palette_base = name
        self._set_custom_colors(colors, dirty=False)
        self.refresh()
        self._status(f"Palette loaded: {name} (editable)")

    def save_palette_preset(self) -> None:
        from app.palette_library import save_palette

        name, ok = QInputDialog.getText(self, "Save palette", "Name:")
        if not ok or not name.strip():
            return
        try:
            save_palette(name.strip(), [list(c) for c in self.custom_colors])
            self._palette_base = name.strip()
            self._palette_dirty = False
            self.refresh_palette_list()
            self.cmb_pal_preset.setCurrentText(name.strip())
            self._status(f"Palette saved: {name.strip()}")
        except ValueError as e:
            QMessageBox.warning(self, "TRAKKART", f"Could not save:\n{e}")

    def _on_preset_changed(self, name: str) -> None:
        if name:
            self._apply_preset(name)

    def _apply_preset(self, name: str) -> None:
        try:
            p = load_preset(name)
        except Exception:
            return
        self.cmb_method.setCurrentText(p.method)
        self.spn_pixel.setValue(int(p.pixel_size))
        self.sld_thr.setValue(int(p.threshold))
        self.sld_bri.setValue(int(float(p.brightness) * 100))
        self.sld_con.setValue(int(float(p.contrast) * 100))
        self.sld_sat.setValue(int(float(p.saturation) * 100))
        if self.cmb_ratio.findText(p.ratio) >= 0:
            self.cmb_ratio.setCurrentText(p.ratio)
        if self.cmb_crop.findText(p.crop_mode) >= 0:
            self.cmb_crop.setCurrentText(p.crop_mode)
        self.crop_fx = float(p.focus_x)
        self.crop_fy = float(p.focus_y)
        self.crop_zoom = float(p.crop_zoom)
        self._sync_crop_label()
        self.sld_blur.setValue(int(round(float(p.pre_blur) * 10)))
        self.spn_sharp.setValue(int(p.pre_sharpen))
        self.sld_hue.setValue(int(float(p.pre_hue)))
        self.spn_denoise.setValue(int(p.pre_denoise))
        self.sld_smooth.setValue(int(round(float(p.pre_smooth) * 10)))
        self.sld_glow.setValue(int(float(p.glow_intensity)))
        self.spn_glowrad.setValue(int(float(p.glow_radius)))
        self.spn_glowthr.setValue(int(p.glow_threshold))
        self.sld_grain.setValue(int(float(p.grain)))
        self.sld_vig.setValue(int(float(p.vignette)))
        self.spn_scan.setValue(int(p.scanlines))
        self.set_brand_color(p.replace_color)
        # La paleta en uso es la tira custom: del preset, o la built-in base.
        from app.palette_library import palette_colors

        self._palette_base = p.palette
        base_colors = palette_colors(p.palette)
        self._set_custom_colors(
            [tuple(c) for c in (p.custom_palette or [])] or base_colors,
            dirty=False,
        )
        self._palette_dirty = False
        self.refresh_palette_list()
        # Salidas: el preset es la receta; los diálogos las aplican por operación.
        self._vector_export = bool(p.vector_export)
        self._vector_cell = int(p.vector_cell)
        self._gif_export = bool(p.gif_export)
        self._gif_frames = int(p.gif_frames)
        self._gif_mode = str(p.gif_mode)
        self._export_size = int(p.export_size)
        self._export_format = str(p.export_format)
        self._export_quality = int(p.export_quality)
        # Grade pack.
        self.duotone_dark = str(p.duotone_dark or "")
        self.duotone_light = str(p.duotone_light or "")
        self.sld_duo_mid.setValue(int(float(p.duotone_mid)))
        self._sync_duo_label()
        self.spn_poster.setValue(int(p.posterize))
        self.sld_split.setValue(int(float(p.split_tone)))
        self.sld_fade.setValue(int(float(p.fade)))
        self._sync_duo_label()
        # Texture pack.
        self.spn_halftone.setValue(int(p.halftone))
        if self.cmb_halftone.findText(p.halftone_shape) >= 0:
            self.cmb_halftone.setCurrentText(p.halftone_shape)
        self.sld_dust.setValue(int(float(p.dust)))
        self.spn_border.setValue(int(p.border))
        self.border_color = str(p.border_color or "#000000")
        self.lbl_border.setText(self.border_color)
        self.spn_letterbox.setValue(int(p.letterbox))
        self.sld_chroma.setValue(int(p.glitch_chroma))
        self.spn_slice.setValue(int(p.glitch_slice_bands))
        # Glitch extra pack.
        self.spn_pixelsort.setValue(int(p.pixelsort))
        self.spn_wave.setValue(int(p.wave))
        self.sld_mosh.setValue(int(float(p.mosh)))
        self.spn_grille.setValue(int(p.grille))
        if self.cmb_preset.findText(name) < 0:
            self.refresh_presets()
        self.cmb_preset.setCurrentText(name)
        self.refresh()

    def _sync_crop_label(self) -> None:
        self.lbl_crop.setText(f"{self.crop_fx:.0f}, {self.crop_fy:.0f} · {self.crop_zoom:.1f}x")

    def open_crop_editor(self) -> None:
        """Visual crop editor (frame + grid + drag + zoom). Applies on Done."""
        if self.src is None:
            QMessageBox.information(self, "TRAKKART", "Open an image first.")
            return
        from app.ui.crop_editor import CropEditorDialog

        dlg = CropEditorDialog(
            self.src.copy(),
            ratio=self.cmb_ratio.currentText(),
            mode=self.cmb_crop.currentText(),
            fx=float(self.crop_fx), fy=float(self.crop_fy),
            zoom=float(self.crop_zoom),
            parent=self,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            self._status("Crop unchanged")
            return
        if dlg.turns:
            self.history.push(self.src)
            self.src = dlg.image
        if self.cmb_ratio.findText(dlg.ratio) >= 0:
            self.cmb_ratio.setCurrentText(dlg.ratio)
        if self.cmb_crop.findText(dlg.mode) >= 0:
            self.cmb_crop.setCurrentText(dlg.mode)
        self.crop_fx, self.crop_fy, self.crop_zoom = dlg.fx, dlg.fy, dlg.zoom
        self._sync_crop_label()
        self.refresh()
        self._status(f"Crop set: {dlg.ratio} {dlg.mode} "
                     f"({dlg.fx:.0f}, {dlg.fy:.0f} · {dlg.zoom:.1f}x)")

    def save_current_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save preset", "Name:")
        if not ok or not name.strip():
            return
        try:
            p = self.current_params()
            p.name = name.strip()
            save_preset(p)
            self.refresh_presets()
            self.cmb_preset.setCurrentText(name.strip())
            self._status(f"Preset saved: {name.strip()}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TRAKKART", f"Could not save:\n{e}")

    # -- batch --
    def run_batch_dialog(self) -> None:
        """Un solo diálogo validado (dither-guy style), no dos seguidos a ciegas."""
        from dataclasses import replace

        preset = self.current_params()
        canvas_size = None
        if self.src is not None:
            try:
                from app.canvas import to_canvas

                canvas = to_canvas(
                    self.src, ratio=self.cmb_ratio.currentText(), mode=self.cmb_crop.currentText(),
                    fx=float(self.crop_fx), fy=float(self.crop_fy), zoom=float(self.crop_zoom),
                )
                canvas_size = (canvas.width, canvas.height)
            except Exception:  # noqa: BLE001
                canvas_size = None
        dlg = BatchDialog(
            in_dir="", out_dir=str(self.out_dir), jobs=int(self.spn_jobs.value()),
            vector_export=bool(preset.vector_export), vector_cell=int(preset.vector_cell),
            gif_export=bool(preset.gif_export), gif_frames=int(preset.gif_frames),
            gif_mode=preset.gif_mode, canvas_size=canvas_size,
            size=int(preset.export_size), format=str(preset.export_format),
            quality=int(preset.export_quality), parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        src, dst, jobs = dlg.paths()
        outs = dlg.output_options()
        preset = replace(
            preset, vector_export=outs["vector_export"], vector_cell=outs["vector_cell"],
            gif_export=outs["gif_export"], gif_frames=outs["gif_frames"],
            gif_mode=outs["gif_mode"], export_size=outs["export_size"],
            export_format=outs["export_format"], export_quality=outs["export_quality"])
        self.run_batch(src, dst, jobs=jobs, preset=preset)

    def run_batch(self, src: Path, dst: Path, jobs: int | None = None,
                  preset: Preset | None = None) -> None:
        import time

        if self._batch_worker is not None and self._batch_worker.isRunning():
            return
        try:
            preset = preset or self.current_params()
            preset.validate()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TRAKKART", f"Invalid preset:\n{e}")
            return
        self._batch_cancel[0] = False
        self._batch_start = time.time()
        self._batch_out = Path(dst)
        self._batch_worker = BatchWorker(
            src, dst, preset, store=self.store,
            jobs=int(jobs) if jobs else int(self.spn_jobs.value()), cancel=self._batch_cancel)
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished.connect(self._on_batch_finished)
        self._batch_worker.error.connect(self._on_batch_error)
        self.btn_batch.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.btn_cancel.show()
        self._batch_worker.start()

    def cancel_batch(self) -> None:
        self._batch_cancel[0] = True
        self._status("Cancelling batch...")

    def run_batch_sync(self, src: Path, dst: Path) -> list[dict]:
        """Synchronous batch (tests + scripts)."""
        return batch_process(src, dst, self.current_params(), store=self.store)

    def _on_batch_progress(self, done: int, total: int, name: str) -> None:
        import time

        self.progress.setValue(int(done / total * 100) if total else 100)
        elapsed = time.time() - (self._batch_start or time.time())
        fps = done / elapsed if elapsed > 0 else 0.0
        if fps > 0:
            eta = (total - done) / fps
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            eta_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
        else:
            eta_str = "…"
        short = name if len(name) <= 24 else name[:21] + "…"
        self._status(f"Batch {done}/{total} · {fps:.1f} img/s · ETA {eta_str} · {short}")

    def _on_batch_finished(self, results: list[dict]) -> None:
        self.btn_batch.setEnabled(True)
        self.progress.hide()
        self.btn_cancel.hide()
        ok = sum(1 for r in results if r["status"] == "ok")
        sk = sum(1 for r in results if r["status"] == "skipped")
        er = sum(1 for r in results if r["status"] == "error")
        cancelled = " (cancelled)" if self._batch_cancel[0] else ""
        where = f" → {self._batch_out}" if self._batch_out else ""
        self._status(f"Batch done: {ok} ok, {sk} skipped, {er} errors{cancelled}{where}")
        QMessageBox.information(self, "TRAKKART", f"Batch done:\n{ok} ok, {sk} skipped, {er} errors{cancelled}.\n{where}")

    def _on_batch_error(self, msg: str) -> None:
        self.btn_batch.setEnabled(True)
        self.progress.hide()
        self.btn_cancel.hide()
        QMessageBox.warning(self, "TRAKKART", f"Batch error:\n{msg}")

    # -- menus --
    def _build_menus(self) -> None:
        bar = self.menuBar()

        m_file = bar.addMenu("File")
        for label, shortcut, slot in [
            ("Open image...", "Ctrl+O", self.open_image_dialog),
            ("Export…", "Ctrl+Shift+S", lambda: self.export(False)),
            ("Quick export", "Ctrl+S", lambda: self.export(True)),
            ("Batch folder...", "Ctrl+B", self.run_batch_dialog),
            ("Export preset...", "", self.share_preset_export),
            ("Import preset...", "", self.share_preset_import),
        ]:
            a = QAction(label, self)
            if shortcut:
                a.setShortcut(shortcut)
            a.triggered.connect(slot)
            m_file.addAction(a)

        m_edit = bar.addMenu("Edit")
        for label, shortcut, slot in [
            ("Undo image", "Ctrl+Z", self.undo_image),
            ("Random", "Ctrl+R", self.randomize),
            ("Rotate left", "", lambda: self._op_image(rotate_left, "rotate left")),
            ("Rotate right", "", lambda: self._op_image(rotate_right, "rotate right")),
            ("Flip H", "", lambda: self._op_image(flip_h, "flip H")),
            ("Flip V", "", lambda: self._op_image(flip_v, "flip V")),
            ("Invert", "", lambda: self._op_image(invert, "invert")),
        ]:
            a = QAction(label, self)
            if shortcut:
                a.setShortcut(shortcut)
            a.triggered.connect(slot)
            m_edit.addAction(a)

        m_view = bar.addMenu("View")
        for label, shortcut, slot in [
            ("Zoom +", "Ctrl+=", lambda: self._zoom_step(1.25)),
            ("Zoom -", "Ctrl+-", lambda: self._zoom_step(1 / 1.25)),
            ("Fit", "Ctrl+0", self._zoom_fit),
            ("100%", "Ctrl+1", self._zoom_full),
            ("Copy result", "Ctrl+C", self.copy_result),
            ("Paste image", "Ctrl+V", self.paste_image),
        ]:
            a = QAction(label, self)
            if shortcut:
                a.setShortcut(shortcut)
            a.triggered.connect(slot)
            m_view.addAction(a)

    # -- image ops + undo --
    def _op_image(self, fn, what: str) -> None:
        if self.src is None:
            return
        self.history.push(self.src)
        self.src = fn(self.src)
        self.refresh()
        self._status(f"{what} (Ctrl+Z to undo)")

    def undo_image(self) -> None:
        prev = self.history.undo()
        if prev is None:
            self._status("Nothing to undo")
            return
        self.src = prev
        self.refresh()
        self._status("Undone")

    def randomize(self) -> None:
        from app.palette_library import list_palettes

        self.cmb_method.setCurrentText(random.choice(list(METHODS)))
        names = list_palettes() or palette_names()
        self._on_palette_preset_changed(random.choice(names))
        self.sld_thr.setValue(random.randint(80, 180))
        self.spn_pixel.setValue(random.randint(1, 4))
        self.refresh()
        self._status("Random applied (save the preset if you like it)")

    # -- zoom / clipboard / dnd --
    def _zoom_step(self, factor: float) -> None:
        self.zoom = min(4.0, max(0.25, self.zoom * factor))
        self.refresh()

    def _zoom_fit(self) -> None:
        self.zoom = 1.0
        self.refresh()

    def _zoom_full(self) -> None:
        self.zoom = 4.0
        self.refresh()

    def copy_result(self) -> None:
        if self.result is None:
            return
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setPixmap(pil_to_pixmap(self.result, max_side=1920))
        self._status("Result copied to clipboard")

    def paste_image(self) -> None:
        from PySide6.QtGui import QGuiApplication

        cb = QGuiApplication.clipboard()
        qimg = cb.image()
        if qimg.isNull():
            self._status("No image in the clipboard")
            return
        try:
            self._load_pil(qimage_to_pil(qimg))
        except ValueError:
            self._status("No image in the clipboard")

    def _set_drag_hover(self, on: bool) -> None:
        for lbl in (self.lbl_orig, self.lbl_res):
            lbl.setProperty("dragHover", "true" if on else "false")
            st = lbl.style()
            st.unpolish(lbl)
            st.polish(lbl)
            lbl.update()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_drag_hover(True)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_drag_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        from app.dnd import classify_drop
        from app.safety import MAX_BYTES as _MAX_URL_BYTES

        self._set_drag_hover(False)
        mime = event.mimeData()
        if mime.hasImage():
            # Browsers sometimes drag the raw pixels
            self._load_qimage(mime.imageData())
            return
        handled = False
        for url in mime.urls():
            kind = classify_drop(url.toString())
            if kind == "http":
                self._load_url(url.toString(), max_bytes=_MAX_URL_BYTES)
                handled = True
                break
            if kind == "data":
                self._load_data_url(url.toString())
                handled = True
                break
            if kind == "blob":
                self._status("That link (blob:) only lives in the browser: save the image or copy it (Ctrl+C)")
                handled = True
                break
            if kind == "local":
                p = Path(url.toLocalFile())
                if not (p.is_absolute() and p.exists()):
                    continue  # ghost path: never a folder nor a file
                if p.is_dir():
                    self._on_drop_folder(p)
                    handled = True
                    break
                if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                    self._load_path(p)
                    handled = True
                    break
        if not handled:
            self._status("Nothing to import: drop images, an image URL or a folder")

    def _load_qimage(self, qimg) -> None:
        try:
            self._load_pil(qimage_to_pil(qimg))
        except ValueError:
            self._status("Nothing to drop: no image")

    def _load_url(self, url: str, max_bytes: int = 40_000_000, timeout: int = 15) -> None:
        """Download a dropped image from the browser (explicit user action)."""
        from app.safety import TooBigError
        from app.services.image_io import download_image

        self._status("Downloading image...")
        try:
            img, nbytes = download_image(url, max_bytes=max_bytes, timeout=timeout)
            self._load_pil(img)
            self._status(f"Loaded from web ({nbytes // 1024}KB)")
        except TooBigError as e:
            QMessageBox.warning(self, "TRAKKART", f"Image too large:\n{e}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TRAKKART", f"Could not download:\n{e}")

    def _load_data_url(self, url: str) -> None:
        """Decode a dropped data:image/... base64 blob from the browser (no network)."""
        from app.safety import TooBigError
        from app.services.image_io import decode_data_url

        try:
            img, nbytes = decode_data_url(url)
            self._load_pil(img)
            self._status(f"Loaded from browser ({nbytes // 1024}KB)")
        except TooBigError as e:
            QMessageBox.warning(self, "TRAKKART", f"Image too large:\n{e}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TRAKKART", f"Could not read what was dropped:\n{e}")

    def run_batch_with_input(self, src: Path) -> None:
        dst = QFileDialog.getExistingDirectory(self, "Output folder")
        if not dst:
            return
        self.run_batch(Path(src), Path(dst))

    def _on_drop_folder(self, src: Path) -> None:
        """Dropping a folder ONLY processes with the toggle armed + confirmation."""
        from app.batch import EXTS

        if not self.chk_batch_drop.isChecked():
            self._status("Folder received: enable 'Drop folder = batch' or use the Batch button")
            return
        try:
            files = [f for f in src.iterdir() if f.is_file() and f.suffix.lower() in EXTS]
        except OSError as e:
            QMessageBox.warning(self, "TRAKKART", f"Could not read the folder:\n{e}")
            return
        if not files:
            self._status("The folder has no compatible images")
            return
        preset = self.current_params()
        ok = QMessageBox.question(
            self, "Drop batch",
            f"Process {len(files)} images with preset '{preset.name or 'current'}'?\nOutput: {self.out_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            self._status("Batch cancelled")
            return
        self.run_batch(src, self.out_dir)

    def open_image_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._load_path(Path(path))

    def _load_path(self, path: Path) -> None:
        from app.safety import TooBigError
        from app.services.image_io import load_path

        try:
            self._load_pil(load_path(path))
            self.src_name = Path(path).stem  # default export base (GIMP style)
            self._status(f"Loaded: {path.name}")
        except TooBigError as e:
            QMessageBox.warning(self, "TRAKKART", f"Image too large:\n{e}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TRAKKART", f"Could not open:\n{e}")

    def _load_pil(self, img: Image.Image) -> None:
        from app.safety import TooBigError, check_image

        try:
            check_image(img)
        except TooBigError as e:
            QMessageBox.warning(self, "TRAKKART", f"Image too large:\n{e}")
            return
        self.history.clear()
        self.history.push(img)
        self.src = img
        self.refresh()

    # -- preset share --
    def share_preset_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export preset", "my_preset.json", "JSON (*.json)")
        if not path:
            return
        try:
            p = self.current_params()
            p.name = Path(path).stem
            Path(path).write_text(json.dumps(p.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            self._status(f"Preset exported: {Path(path).name}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TRAKKART", f"Could not export:\n{e}")

    def share_preset_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import preset", "", "JSON (*.json)")
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            p = Preset.from_dict(raw)
            save_preset(p)
            self.refresh_presets()
            self._apply_preset(p.name)
            self._status(f"Preset imported: {p.name}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TRAKKART", f"Invalid preset:\n{e}")

    def export(self, quick: bool = False) -> None:
        """Export bundle. Dialogo profesional por defecto; `quick` repite el último.

        GIMP-style: Quick export reusa la última config sin preguntar.
        La primera vez (sin prefs) siempre abre el diálogo.
        """
        if self.src is None:
            QMessageBox.information(self, "TRAKKART", "Open an image first.")
            return
        try:
            preset = self.current_params()
            prefs = load_prefs(self._prefs_path)
            if quick and prefs.out_dir:
                selection = prefs.to_selection()
                self._run_export(
                    base=prefs.base or self.src_name, out_dir=Path(prefs.out_dir),
                    selection=selection, gif_frames=prefs.gif_frames,
                    gif_mode=prefs.gif_mode, overwrite=prefs.overwrite,
                    size=prefs.size, format=prefs.format, quality=prefs.quality,
                )
                return
            if prefs.out_dir:
                init_sel = prefs.to_selection()
                init_base, init_out = prefs.base, prefs.out_dir
                init_gframes, init_gmode = prefs.gif_frames, prefs.gif_mode
                init_overwrite = prefs.overwrite
                init_size, init_fmt, init_q = prefs.size, prefs.format, prefs.quality
            else:
                init_sel = ExportSelection(vector=bool(preset.vector_export),
                                           anim=bool(preset.gif_export))
                init_base, init_out = self.src_name, str(self.out_dir)
                init_gframes, init_gmode = int(preset.gif_frames), preset.gif_mode
                init_overwrite = "overwrite"
                init_size, init_fmt, init_q = (int(preset.export_size),
                                               str(preset.export_format), int(preset.export_quality))
            dlg = ExportDialog(
                self.src, preset.meta(), base=init_base, out_dir=init_out,
                selection=init_sel, gif_frames=init_gframes, gif_mode=init_gmode,
                overwrite=init_overwrite, vector_cells=self._estimate_vector_cells(preset),
                preset=preset, size=init_size, format=init_fmt, quality=init_q,
                parent=self,
            )
            if dlg.exec() != dlg.DialogCode.Accepted:
                self._status("Export cancelled")
                return
            options, out_dir, gframes, gmode = dlg.options()
            self._run_export(
                base=options.base, out_dir=out_dir, selection=options.selection,
                gif_frames=gframes, gif_mode=gmode, overwrite=options.overwrite,
                size=options.size, format=options.format, quality=options.quality,
            )
            save_prefs(ExportPrefs(
                out_dir=str(out_dir), base=options.base,
                image=options.selection.image,
                thumb_1080p=options.selection.thumb_1080p,
                vector=options.selection.vector, anim=options.selection.anim,
                metadata=options.selection.metadata,
                gif_frames=gframes, gif_mode=gmode, overwrite=options.overwrite,
                size=options.size, format=options.format, quality=options.quality,
            ), self._prefs_path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TRAKKART", f"Export error: {e}")

    def _estimate_vector_cells(self, preset) -> tuple[int, int] | None:
        """Celdas SVG estimadas para el plan del diálogo (barato, sin dither)."""
        if self.src is None:
            return None
        try:
            from app.canvas import to_canvas
            from app.vector import estimate_cells

            canvas = to_canvas(
                self.src, ratio=preset.ratio, mode=preset.crop_mode,
                fx=float(preset.focus_x), fy=float(preset.focus_y),
                zoom=float(preset.crop_zoom),
            )
            return estimate_cells(canvas.width, canvas.height, int(preset.vector_cell))
        except Exception:  # noqa: BLE001
            return None

    def _run_export(self, base: str, out_dir: Path, selection, gif_frames: int,
                    gif_mode: str, overwrite: str, size: int, format: str,
                    quality: int) -> None:
        """Render full-res + bundle según opciones. Full-res siempre."""
        from app.services.export_service import export_full

        preset = self.current_params()
        paths, skipped = export_full(
            self.src, preset, out_dir, base=base, store=self.store,
            preset_name=self.cmb_preset.currentText(), selection=selection,
            overwrite=overwrite, gif_frames=int(gif_frames), gif_mode=gif_mode,
            size=int(size), format=str(format), quality=int(quality),
        )
        if skipped and not paths:
            QMessageBox.information(
                self, "TRAKKART",
                f"Skipped: {base} already exists (policy: skip).")
            self._status(f"Export skipped (exists): {base}")
            return
        QMessageBox.information(self, "TRAKKART", "Exported:\n" + "\n".join(p.name for p in paths.values()))
        self._status(f"Exported to {Path(out_dir).resolve()}")
