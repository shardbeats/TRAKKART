"""TRAKKART main window — dither preview + export + cover flow.

Refactored: the window orchestrates, it does not implement.
- UI construction -> app.ui.panels
- Qt/PIL conversions -> app.ui.qt_image
- IO loading (fs/web/clipboard) -> app.services.image_io
- Render/export -> app.services.render_service / export_service
- Single params -> Preset.to_render_kwargs (app.render_params)

Public API intact (tests test_ui_* depend on it).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (  # noqa: F401 (QMessageBox: test seam, see note below)
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
)

from app.adjust import Adjust
from app.history import HistoryStore
from app.ops import ImageHistory
from app.paths import get_db_path, get_out_dir, get_presets_dir
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
        # Vector/GIF outputs + size/format: live in the preset (recipe);
        # each dialog picks per operation (no duplicated panel).
        self._vector_export: bool = False
        self._vector_cell: int = 8
        self._vector_black: bool = False
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
        # The palette in use is the custom strip (named presets are
        # starting points). _palette_base remembers which one it came from.
        self._palette_base: str = "SLIME"
        self._palette_dirty: bool = False
        self._palette_locks: list[bool] = []
        self._adjust_locks: dict[str, bool] = {}
        self.fx_stack_data: list = []
        ensure_bundled(get_presets_dir())
        from app.palette_library import ensure_bundled_palettes
        from app.paths import get_palettes_dir

        ensure_bundled_palettes(get_palettes_dir())
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

        # -- viewport: prefs default BEFORE _build_menus (actions read it) --
        self.viewport_mode: str = "live"
        try:
            from app.export_prefs import load_prefs as _load_prefs

            _vp = str(getattr(_load_prefs(prefs_path), "viewport", "live")).lower()
            if _vp in ("full", "live", "still"):
                self.viewport_mode = _vp
        except Exception:  # noqa: BLE001
            pass
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(350)  # live default; modes retime it
        self._preview_timer.timeout.connect(self.refresh)
        self._video_timer = QTimer(self)
        self._video_timer.timeout.connect(self._next_video_frame)
        self._video_timer.setInterval(125)  # 8fps default
        self._setup_ui()
        self._build_menus()
        # -- general prefs: jobs / drop / output (action bar exists now) --
        try:
            from app.export_prefs import load_prefs as _load_prefs2, resolve_out_dir as _resolve

            _p = _load_prefs2(self._prefs_path)
            if out_dir is None and getattr(_p, "out_dir", ""):
                try:
                    self.out_dir = _resolve(str(_p.out_dir))
                except Exception:  # noqa: BLE001
                    pass
            try:
                self.spn_jobs.setValue(max(1, min(8, int(getattr(_p, "jobs", 1)))))
            except Exception:  # noqa: BLE001
                pass
            try:
                self.chk_batch_drop.setChecked(bool(getattr(_p, "drop_batch", False)))
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass
        from app.viewport import mode_label as _mode_label

        self.lbl_viewport = QLabel(f"Viewport: {_mode_label(self.viewport_mode)}")
        self.lbl_viewport.setObjectName("subtitleLabel")
        self.statusBar().addPermanentWidget(self.lbl_viewport)
        self.refresh_presets()
        self.refresh_palette_list()
        self._apply_preset("SLIME_FS")
        self._status("Open an image to start.")
        self._session_restored = False
        try:
            from app.ui import session_flow as _sess

            self._session_restored = bool(_sess.restore(self))
        except Exception:  # noqa: BLE001
            pass
        self._maybe_first_run()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Deterministic cleanup: no orphan timers/slots after closing.

        Without this, a closed window can outlive GC with the debounce
        timer armed and render over dead UI (hunting the E2E tests).
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
        try:
            from app.ui import session_flow as _sess

            _sess.save_on_close(self)
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)

    def _schedule_refresh(self) -> None:
        """Viewport-aware re-render: full = now, live = debounced, still = F5 only."""
        from app.viewport import normalize_mode, resolve_interval

        mode = normalize_mode(getattr(self, "viewport_mode", "live"))
        if mode == "still":
            try:
                self._preview_timer.stop()  # cancel any pending auto-refresh
            except Exception:  # noqa: BLE001
                pass
            self._status("Still mode: press Refresh (F5) to update")
            return
        if mode == "full":
            self.refresh()
            return
        try:
            fast = bool(self.sender().property("fast"))
        except Exception:  # noqa: BLE001
            fast = False
        interval = int(resolve_interval("live", fast=fast) or 350)
        if not self._preview_timer.isActive():
            self._preview_timer.setInterval(interval)
            self._preview_timer.start()

    def set_viewport_mode(self, mode: str) -> None:
        from app.viewport import mode_label, normalize_mode

        self.viewport_mode = normalize_mode(mode)
        for m in ("full", "live", "still"):
            try:
                getattr(self, f"_act_viewport_{m}").setChecked(m == self.viewport_mode)
            except Exception:  # noqa: BLE001
                pass
        try:
            self.lbl_viewport.setText(f"Viewport: {mode_label(self.viewport_mode)}")
        except Exception:  # noqa: BLE001
            pass
        self._status(f"Viewport: {mode_label(self.viewport_mode)}")
        if self.viewport_mode in ("full", "live"):
            self.refresh()

    def show_tutorial(self, manual: bool = False) -> None:
        from app.tutorial import ensure_samples, mark_seen
        from app.ui.tutorial_dialog import TutorialDialog

        try:
            ensure_samples()
        except Exception:  # noqa: BLE001
            pass
        dlg = TutorialDialog(parent=self)
        dlg.exec()
        try:
            mark_seen()
        except Exception:  # noqa: BLE001
            pass
        if manual:
            self._status("Quick tour done")

    def open_samples(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from app.tutorial import ensure_samples

        try:
            paths = ensure_samples()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths[0].parent)))
            self._status(f"Samples: {len(paths)} images")
        except Exception as e:  # noqa: BLE001
            self._status(f"Samples unavailable: {e}")

    def show_about(self) -> None:
        from app.ui import about_dialog as _about

        _about.show_about(self)

    def show_shortcuts(self) -> None:
        from app.ui import shortcuts_dialog as _keys

        _keys.show_shortcuts(self)

    def open_manual(self) -> None:
        from app.ui import about_dialog as _about

        _about.show_manual(self)

    def open_logs(self) -> None:
        from app.ui import about_dialog as _about

        _about.show_logs(self)

    def open_settings(self) -> None:
        """File > Settings: default output + export defaults + general."""
        from app.ui import settings_flow as _sf

        _sf.open_settings(self)

    def _sync_motif_visibility(self) -> None:
        """MOTIF config only matters for method `motif`: hide it otherwise."""
        try:
            box = self._motif_box
        except AttributeError:
            return
        try:
            box.setVisible(self.cmb_method.currentText() == "motif")
        except Exception:  # noqa: BLE001
            pass

    def _maybe_first_run(self) -> None:
        """First launch: samples + tour once. Never blocks tests/headless."""
        import os

        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TRAKKART_SKIP_FIRST_RUN"):
            return
        if getattr(self, "_session_restored", False):
            return  # returning user with a restored session: no tour
        try:
            from app.tutorial import ensure_samples, first_run_needed

            if not first_run_needed():
                return
            ensure_samples()
            self.show_tutorial(manual=False)
        except Exception:  # noqa: BLE001
            pass

    def _status(self, msg: str) -> None:
        """Single status point: label + status bar (SUITE pattern)."""
        self.lbl_status.setText(msg)
        try:
            self.statusBar().showMessage(msg)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction (body in window_assembly; orchestrates, does not build)
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
    # Params: current_params() is the single source; _render_kwargs delegates.
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
    # Single doc (CANVAS) + single anim (VIDEO): one size source each
    # ------------------------------------------------------------------
    # Widget readers (doc CANVAS + anim VIDEO): params_controller is the single source.
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

    def _sync_duration_ui(self) -> None:
        from app.ui import video_controller as _vc

        _vc.sync_duration_ui(self)

    def _on_duration_changed(self) -> None:
        from app.ui import video_controller as _vc

        _vc.duration_changed(self)

    def _on_video_proxy_changed(self) -> None:
        from app.ui import video_controller as _vc

        _vc.proxy_changed(self)

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

    # -- presets (body in params_controller) --
    def current_params(self) -> Preset:
        from app.ui import params_controller as _par

        return _par.build_params(self)

    # -- color/palette actions (body in color_actions) --
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
        """🎲 Surprise: generates a harmonious palette (ramp/harmony in Oklch)."""
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
        """Small current canvas (160px) for usage %. None without image."""
        from app.ui import color_actions as _ca

        return _ca.palette_preview_small(self)

    def clear_custom_colors(self) -> None:
        from app.ui import color_actions as _ca

        _ca.clear_custom_colors(self)

    def _set_custom_colors(self, colors: list, dirty: bool = True) -> None:
        """Single write point: updates strip + dirty state."""
        from app.ui import color_actions as _ca

        _ca.set_custom_colors(self, colors, dirty)

    def _sync_custom_label(self) -> None:
        from app.ui import color_actions as _ca

        _ca.sync_custom_label(self)

    def refresh_presets(self) -> None:
        from app.ui import params_controller as _par

        _par.refresh_presets(self)

    def refresh_palette_list(self) -> None:
        """Library combo (built-ins + user)."""
        from app.ui import color_actions as _ca

        _ca.refresh_palette_list(self)

    def _on_palette_preset_changed(self, name: str) -> None:
        """Choosing a palette = loading it as an editable copy into the strip."""
        from app.ui import color_actions as _ca

        _ca.on_palette_preset_changed(self, name)

    def save_palette_preset(self) -> None:
        from app.ui import color_actions as _ca

        _ca.save_palette_preset(self)

    def extract_palette_from_image(self) -> None:
        from app.ui import color_actions as _ca

        _ca.extract_from_image(self)

    def import_palette_file(self) -> None:
        from app.ui import color_actions as _ca

        _ca.import_palette_file(self)

    def export_palette_file(self) -> None:
        from app.ui import color_actions as _ca

        _ca.export_palette_file(self)

    def shuffle_palette(self) -> None:
        from app.ui import color_actions as _ca

        _ca.shuffle_custom_colors(self)

    # -- FX stack (body in fx_stack_controller) --
    def _on_fx_toggled(self) -> None:
        from app.ui import fx_stack_controller as _fx

        _fx.on_toggled(self)

    def _on_fx_move_up(self) -> None:
        from app.ui import fx_stack_controller as _fx

        _fx.move_selected(self, -1)

    def _on_fx_move_down(self) -> None:
        from app.ui import fx_stack_controller as _fx

        _fx.move_selected(self, 1)

    def _on_fx_add(self, label: str) -> None:
        from app.ui import fx_stack_controller as _fx

        _fx.on_add(self, label)

    def _sync_anim_ui(self) -> None:
        from app.ui import params_controller as _par

        _par.sync_anim_ui(self)

    def _use_ordered_method(self) -> None:
        if self.cmb_method.findText("bayer8") >= 0:
            self.cmb_method.setCurrentText("bayer8")
        self._sync_anim_ui()
        self._schedule_refresh()

    def step_method(self, delta: int) -> str:
        """Arrow-stepping through algorithms (without touching the combo by hand)."""
        from app.dither import METHODS

        methods = list(METHODS)
        try:
            cur = self.cmb_method.currentText()
            idx = methods.index(cur) if cur in methods else 0
        except Exception:  # noqa: BLE001
            idx = 0
        nxt = methods[(idx + int(delta)) % len(methods)]
        self.cmb_method.setCurrentText(nxt)
        self._schedule_refresh()
        self._status(f"Method: {nxt}")
        return nxt

    def _sync_fx_list(self) -> None:
        from app.ui import fx_stack_controller as _fx

        _fx.sync_list(self)

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

    # -- batch (body in batch_flow) --
    def run_batch_dialog(self) -> None:
        """Single validated dialog, no two blind dialogs in a row."""
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

    # -- menus (body in menus.py) --
    def _build_menus(self) -> None:
        from app.ui import menus as _menus

        _menus.build_menus(self)

    # -- image ops + undo (body in image_flow) --
    def _op_image(self, fn, what: str) -> None:
        from app.ui import image_flow as _im

        _im.op_image(self, fn, what)

    def undo_image(self) -> None:
        from app.ui import image_flow as _im

        _im.undo_image(self)

    def redo_image(self) -> None:
        from app.ui import image_flow as _im

        _im.redo_image(self)

    def randomize(self) -> None:
        from app.ui import image_flow as _im

        _im.randomize(self)

    # -- zoom / clipboard (body in image_flow) --
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
    def lbl_orig(self):  # compat: single canvas (dnd/old tests)
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

    # -- preset share (body in params_controller) --
    def share_preset_export(self) -> None:
        from app.ui import params_controller as _par

        _par.share_export(self)

    def share_preset_import(self) -> None:
        from app.ui import params_controller as _par

        _par.share_import(self)

    def export(self, quick: bool = False) -> None:
        """Export bundle. Pro dialog by default; `quick` repeats the last one."""
        from app.ui import export_flow as _ef

        _ef.export(self, quick)

    def _estimate_vector_cells(self, preset) -> tuple[int, int] | None:
        from app.ui import export_flow as _ef

        return _ef.estimate_vector_cells(self, preset)

    def _run_export(self, base: str, out_dir: Path, selection, gif_opts: dict,
                    overwrite: str, size: int, format: str,
                    quality: int, mp4: bool = False) -> None:
        """Render full-res + bundle per options. Always full-res."""
        from app.ui import export_flow as _ef

        _ef.run_export(self, base, out_dir, selection, gif_opts,
                       overwrite, size, format, quality, mp4)
