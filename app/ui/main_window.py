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

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (  # noqa: F401 (QMessageBox: test seam, see note below)
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
)

from app.adjust import Adjust
from app.history import HistoryStore
from app.ops import ImageHistory
from app.paths import get_db_path, get_out_dir
from app.presets import Preset, ensure_bundled
# NOTE: QMessageBox/BatchDialog stay imported (no direct use below) because
# tests stub them as MW.QMessageBox / MW.BatchDialog. BatchWorker is resolved
# through this namespace by batch_flow for the same reason.
from app.ui.batch_dialog import BatchDialog  # noqa: F401
from app.ui.workers import BatchWorker


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
        self._gif_fps: int = 8
        self._gif_size: int = 1200
        self._gif_pingpong: bool = False
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
        # -- compare: hold-to-compare (single canvas, no ORIGINAL panel) --
        self._comparing: bool = False
        # -- video mode: full canvas preview, 1200px default --
        self._video_on: bool = False
        self._video_frames: list = []
        self._video_idx: int = 0
        self._video_playing: bool = True
        self._video_worker = None
        self._video_token: int = 0
        from PySide6.QtCore import QTimer

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(350)  # family-style debounce (never freeze UI)
        self._preview_timer.timeout.connect(self.refresh)
        self._video_timer = QTimer(self)
        self._video_timer.timeout.connect(self._next_video_frame)
        self._video_timer.setInterval(125)  # 8fps default
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
        try:
            self._video_timer.stop()
        except Exception:  # noqa: BLE001
            pass
        self._batch_cancel[0] = True
        for worker in (self._preview_worker, self._batch_worker, self._video_worker):
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

    def _status(self, msg: str) -> None:
        """Single status point: label + status bar (family pattern)."""
        self.lbl_status.setText(msg)
        try:
            self.statusBar().showMessage(msg)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction (cuerpo en window_assembly; orquesta, no construye)
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        from app.ui import window_assembly as _wa

        _wa.setup_ui(self)

    def _setup_control_panel(self, panel: QVBoxLayout) -> None:
        from app.ui import window_assembly as _wa

        _wa.setup_control_panel(self, panel)

    def _setup_action_bar(self) -> None:
        from app.ui import window_assembly as _wa

        _wa.setup_action_bar(self)

    def _setup_previews(self, root: QHBoxLayout) -> None:
        from app.ui import window_assembly as _wa

        _wa.setup_previews(self, root)

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
            self._sync_docdims()
        except Exception:  # noqa: BLE001
            pass
        if self._video_on:
            self._start_video_async()
            return
        try:
            from app.ui import preview_controller as _pc

            _pc.render_still(self)
        except Exception as e:  # noqa: BLE001
            self._status(f"Error: {e}")

    # ------------------------------------------------------------------
    # Doc único (CANVAS) + anim único (VIDEO): una sola fuente por tamaño
    # ------------------------------------------------------------------
    # Widget readers (doc CANVAS + anim VIDEO): params_controller es la única fuente.
    def _doc_size(self) -> int:
        from app.ui import params_controller as _par

        return _par.doc_size(self)

    @staticmethod
    def _anim_combo_int(cmb, default: int, lo: int, hi: int) -> int:
        from app.ui import params_controller as _par

        return _par.anim_combo_int(cmb, default, lo, hi)

    @staticmethod
    def _set_anim_combo(cmb, value: int) -> None:
        from app.ui import params_controller as _par

        _par.set_anim_combo(cmb, value)

    def _gif_anim_frames(self) -> int:
        from app.ui import params_controller as _par

        return _par.gif_anim_frames(self)

    def _gif_anim_mode(self) -> str:
        from app.ui import params_controller as _par

        return _par.gif_anim_mode(self)

    def _gif_anim_fps(self) -> int:
        from app.ui import params_controller as _par

        return _par.gif_anim_fps(self)

    def _gif_anim_size(self) -> int:
        from app.ui import params_controller as _par

        return _par.gif_anim_size(self)

    def _gif_anim_pingpong(self) -> bool:
        from app.ui import params_controller as _par

        return _par.gif_anim_pingpong(self)

    def _on_ratio_preset(self) -> None:
        from app.ui import params_controller as _par

        _par.on_ratio_preset(self)

    def _on_canvas_wh_changed(self) -> None:
        from app.ui import params_controller as _par

        _par.on_canvas_wh_changed(self)

    def _sync_docdims(self) -> None:
        from app.ui import params_controller as _par

        _par.sync_docdims(self)

    def _video_spec(self) -> dict:
        from app.ui import video_controller as _vc

        return _vc.spec(self)

    def _on_video_toggle(self) -> None:
        from app.ui import video_controller as _vc

        _vc.toggle(self)

    def _on_video_fps_changed(self) -> None:
        from app.ui import video_controller as _vc

        _vc.fps_changed(self)

    def _on_video_playpause(self) -> None:
        from app.ui import video_controller as _vc

        _vc.playpause(self)

    def _on_video_scrub(self, v: int) -> None:
        from app.ui import video_controller as _vc

        _vc.scrub(self, v)

    def _start_video_async(self) -> None:
        from app.ui import video_controller as _vc

        _vc.start_async(self)

    def _on_video_done(self, frames: list, token: int) -> None:
        from app.ui import video_controller as _vc

        _vc.on_done(self, frames, token)

    def _on_video_error(self, msg: str, token: int) -> None:
        if token != self._video_token:
            return
        self._status(f"Video error: {msg}")

    # -- hold-to-compare (single canvas; behavior in compare_controller) --
    def _compare_pressed(self) -> None:
        from app.ui import compare_controller as _cc

        _cc.pressed(self)

    def _compare_released(self) -> None:
        from app.ui import compare_controller as _cc

        _cc.released(self)

    def _paint_compare_orig(self) -> None:
        from app.ui import compare_controller as _cc

        _cc.paint_orig(self)

    def _paint_compare_result(self) -> None:
        from app.ui import compare_controller as _cc

        _cc.paint_result(self)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Space and not event.isAutoRepeat() and self.src is not None:
            self._comparing = True
            self._paint_compare_orig()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Space and not event.isAutoRepeat() and self._comparing:
            self._comparing = False
            self._paint_compare_result()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _show_video_frame(self, force: bool = False) -> None:
        from app.ui import video_controller as _vc

        _vc.show_frame(self, force=force)

    def _next_video_frame(self) -> None:
        from app.ui import video_controller as _vc

        _vc.next_frame(self)

    def _show_preview(self, orig: Image.Image, res: Image.Image) -> None:
        from app.ui import preview_controller as _pc

        _pc.show(self, orig, res)

    def _start_preview_async(self) -> None:
        from app.ui import preview_controller as _pc

        _pc.start_async(self)

    def _on_preview_done(self, qimg, pil_img, token: int) -> None:
        from app.ui import preview_controller as _pc

        _pc.on_done(self, qimg, pil_img, token)

    def _on_preview_error(self, msg: str, token: int) -> None:
        from app.ui import preview_controller as _pc

        _pc.on_error(self, msg, token)

    def _valid_slice_bands(self) -> int:
        from app.ui import params_controller as _par

        return _par.valid_slice_bands(self)

    def current_adjust(self) -> Adjust:
        from app.ui import params_controller as _par

        return _par.current_adjust(self)

    # -- presets (cuerpo en params_controller) --
    def current_params(self) -> Preset:
        from app.ui import params_controller as _par

        return _par.build_params(self)

    # -- color/palette actions (cuerpo en color_actions) --
    def pick_brand_color(self) -> None:
        from app.ui import color_actions as _ca

        _ca.pick_brand_color(self)

    def set_brand_color(self, hex_color: str) -> None:
        from app.ui import color_actions as _ca

        _ca.set_brand_color(self, hex_color)

    def pick_duotone_color(self, which: str) -> None:
        from app.ui import color_actions as _ca

        _ca.pick_duotone_color(self, which)

    def set_duotone_color(self, which: str, hex_color: str) -> None:
        from app.ui import color_actions as _ca

        _ca.set_duotone_color(self, which, hex_color)

    def clear_duotone(self) -> None:
        from app.ui import color_actions as _ca

        _ca.clear_duotone(self)

    def _sync_duo_label(self) -> None:
        from app.ui import color_actions as _ca

        _ca.sync_duo_label(self)

    def pick_border_color(self) -> None:
        from app.ui import color_actions as _ca

        _ca.pick_border_color(self)

    def set_border_color(self, hex_color: str) -> None:
        from app.ui import color_actions as _ca

        _ca.set_border_color(self, hex_color)

    def add_custom_color(self) -> None:
        from app.ui import color_actions as _ca

        _ca.add_custom_color(self)

    def gen_palette(self) -> None:
        """🎲 Sorpresa: genera una paleta armoniosa (ramp/harmony en Oklch)."""
        from app.ui import color_actions as _ca

        _ca.gen_palette(self)

    def edit_custom_palette(self) -> None:
        """Full editor: swatches, hex, roles, usage, reorder, sort."""
        from app.ui import color_actions as _ca

        _ca.edit_custom_palette(self)

    def _remove_custom_color(self, i: int) -> None:
        from app.ui import color_actions as _ca

        _ca.remove_custom_color(self, i)

    def _palette_preview_small(self):
        """Canvas actual reducido (160px) para el % de uso. None sin imagen."""
        from app.ui import color_actions as _ca

        return _ca.palette_preview_small(self)

    def clear_custom_colors(self) -> None:
        from app.ui import color_actions as _ca

        _ca.clear_custom_colors(self)

    def _set_custom_colors(self, colors: list, dirty: bool = True) -> None:
        """Único punto de escritura: actualiza tira + estado dirty."""
        from app.ui import color_actions as _ca

        _ca.set_custom_colors(self, colors, dirty)

    def _sync_custom_label(self) -> None:
        from app.ui import color_actions as _ca

        _ca.sync_custom_label(self)

    def refresh_presets(self) -> None:
        from app.ui import params_controller as _par

        _par.refresh_presets(self)

    def refresh_palette_list(self) -> None:
        """Combo de la biblioteca (built-ins + usuario)."""
        from app.ui import color_actions as _ca

        _ca.refresh_palette_list(self)

    def _on_palette_preset_changed(self, name: str) -> None:
        """Elegir paleta = cargarla como copia editable en la tira."""
        from app.ui import color_actions as _ca

        _ca.on_palette_preset_changed(self, name)

    def save_palette_preset(self) -> None:
        from app.ui import color_actions as _ca

        _ca.save_palette_preset(self)

    def _on_preset_changed(self, name: str) -> None:
        from app.ui import params_controller as _par

        _par.on_preset_changed(self, name)

    def _apply_preset(self, name: str) -> None:
        from app.ui import params_controller as _par

        _par.apply_preset(self, name)

    def _sync_crop_label(self) -> None:
        from app.ui import image_flow as _im

        _im.sync_crop_label(self)

    def open_crop_editor(self) -> None:
        """Visual crop editor (frame + grid + drag + zoom). Applies on Done."""
        from app.ui import image_flow as _im

        _im.open_crop_editor(self)

    def save_current_preset(self) -> None:
        from app.ui import params_controller as _par

        _par.save_current_preset(self)

    # -- batch (cuerpo en batch_flow) --
    def run_batch_dialog(self) -> None:
        """Un solo diálogo validado, no dos seguidos a ciegas."""
        from app.ui import batch_flow as _bf

        _bf.run_batch_dialog(self)

    def run_batch(self, src: Path, dst: Path, jobs: int | None = None,
                  preset: Preset | None = None) -> None:
        from app.ui import batch_flow as _bf

        _bf.run_batch(self, src, dst, jobs, preset)

    def cancel_batch(self) -> None:
        from app.ui import batch_flow as _bf

        _bf.cancel_batch(self)

    def run_batch_sync(self, src: Path, dst: Path) -> list[dict]:
        """Synchronous batch (tests + scripts)."""
        from app.ui import batch_flow as _bf

        return _bf.run_batch_sync(self, src, dst)

    def _on_batch_progress(self, done: int, total: int, name: str) -> None:
        from app.ui import batch_flow as _bf

        _bf.on_progress(self, done, total, name)

    def _on_batch_finished(self, results: list[dict]) -> None:
        from app.ui import batch_flow as _bf

        _bf.on_finished(self, results)

    def _on_batch_error(self, msg: str) -> None:
        from app.ui import batch_flow as _bf

        _bf.on_error(self, msg)

    # -- menus (cuerpo en menus.py) --
    def _build_menus(self) -> None:
        from app.ui import menus as _menus

        _menus.build_menus(self)

    # -- image ops + undo (cuerpo en image_flow) --
    def _op_image(self, fn, what: str) -> None:
        from app.ui import image_flow as _im

        _im.op_image(self, fn, what)

    def undo_image(self) -> None:
        from app.ui import image_flow as _im

        _im.undo_image(self)

    def randomize(self) -> None:
        from app.ui import image_flow as _im

        _im.randomize(self)

    # -- zoom / clipboard (cuerpo en image_flow) --
    def _zoom_step(self, factor: float) -> None:
        from app.ui import image_flow as _im

        _im.zoom_step(self, factor)

    def _zoom_fit(self) -> None:
        from app.ui import image_flow as _im

        _im.zoom_fit(self)

    def _zoom_full(self) -> None:
        from app.ui import image_flow as _im

        _im.zoom_full(self)

    def copy_result(self) -> None:
        from app.ui import image_flow as _im

        _im.copy_result(self)

    def paste_image(self) -> None:
        from app.ui import image_flow as _im

        _im.paste_image(self)

    @property
    def lbl_orig(self):  # compat: single canvas (dnd/tests viejos)
        return self.lbl_res

    @property
    def lbl_orig_title(self):  # compat: single canvas
        return self.lbl_res_title

    def _set_drag_hover(self, on: bool) -> None:
        from app.ui import image_flow as _im

        _im.set_drag_hover(self, on)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        from app.ui import image_flow as _im

        _im.drag_enter(self, event)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        from app.ui import image_flow as _im

        _im.drag_leave(self, event)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        from app.ui import image_flow as _im

        _im.drop(self, event)

    def _load_qimage(self, qimg) -> None:
        from app.ui import image_flow as _im

        _im.load_qimage(self, qimg)

    def _load_url(self, url: str, max_bytes: int = 40_000_000, timeout: int = 15) -> None:
        """Download a dropped image from the browser (explicit user action)."""
        from app.ui import image_flow as _im

        _im.load_url(self, url, max_bytes=max_bytes, timeout=timeout)

    def _load_data_url(self, url: str) -> None:
        """Decode a dropped data:image/... base64 blob from the browser (no network)."""
        from app.ui import image_flow as _im

        _im.load_data_url(self, url)

    def run_batch_with_input(self, src: Path) -> None:
        from app.ui import batch_flow as _bf

        _bf.run_batch_with_input(self, src)

    def _on_drop_folder(self, src: Path) -> None:
        """Dropping a folder ONLY processes with the toggle armed + confirmation."""
        from app.ui import batch_flow as _bf

        _bf.on_drop_folder(self, src)

    def open_image_dialog(self) -> None:
        from app.ui import image_flow as _im

        _im.open_image_dialog(self)

    def _load_path(self, path: Path) -> None:
        from app.ui import image_flow as _im

        _im.load_path(self, path)

    def _load_pil(self, img: Image.Image) -> None:
        from app.ui import image_flow as _im

        _im.load_pil(self, img)

    # -- preset share (cuerpo en params_controller) --
    def share_preset_export(self) -> None:
        from app.ui import params_controller as _par

        _par.share_export(self)

    def share_preset_import(self) -> None:
        from app.ui import params_controller as _par

        _par.share_import(self)

    def export(self, quick: bool = False) -> None:
        """Export bundle. Dialogo profesional por defecto; `quick` repite el último."""
        from app.ui import export_flow as _ef

        _ef.export(self, quick)

    def _estimate_vector_cells(self, preset) -> tuple[int, int] | None:
        from app.ui import export_flow as _ef

        return _ef.estimate_vector_cells(self, preset)

    def _run_export(self, base: str, out_dir: Path, selection, gif_opts: dict,
                    overwrite: str, size: int, format: str,
                    quality: int) -> None:
        """Render full-res + bundle según opciones. Full-res siempre."""
        from app.ui import export_flow as _ef

        _ef.run_export(self, base, out_dir, selection, gif_opts,
                       overwrite, size, format, quality)
