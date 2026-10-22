"""Settings dialog: default output + export defaults + general behavior.

Single place to configure what File > Export/Batch reuse:
- Output: default export folder (Browse / Reset / Open).
- Export defaults: format, quality, size + which outputs are on by default.
- General: batch jobs, Drop=Batch, default viewport, recents, data folder.

Pure Qt here; persistence lives in app.export_prefs (same JSON, new fields
are backward-compatible). Orchestration (load/show/save/apply) lives in
app.ui.settings_flow; builders below keep __init__ flat (one per group).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.export_prefs import is_writable_dir
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    """Edit defaults. `values()` only valid after Accept."""

    def __init__(self, prefs, data_dir: str | Path | None = None,
                 recent_count: int = 0, parent=None, prefs_path=None) -> None:
        from app.exporter import MAX_SIDE, MIN_SIDE

        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self._min_side = int(MIN_SIDE)
        self._max_side = int(MAX_SIDE)
        self._data_dir = str(data_dir or "")
        self._recents_cleared = False
        self._prefs_path = prefs_path

        col = QVBoxLayout(self)
        col.addWidget(self._build_output(prefs))
        col.addWidget(self._build_export(prefs))
        col.addWidget(self._build_general(prefs, recent_count))
        col.addWidget(self._build_extras())
        col.addLayout(self._build_buttons())
        self._refresh_hint()

    def _build_output(self, prefs) -> QGroupBox:
        """Output group: default folder + reset/open + hint."""
        from app.ui.dialog_fields import build_folder_row

        out_box = QGroupBox("Output")
        out_col = QVBoxLayout(out_box)
        folder_row, self.edit_out, self.btn_browse = build_folder_row(
            "Default folder:", str(getattr(prefs, "out_dir", "") or ""), self,
            on_browse=self._browse)
        self.edit_out.setPlaceholderText("System default")
        out_col.addLayout(folder_row)
        out_btns = QHBoxLayout()
        self.btn_reset = QPushButton("Reset to default")
        self.btn_reset.setToolTip("Back to the system output folder")
        self.btn_reset.clicked.connect(self._reset)
        out_btns.addWidget(self.btn_reset)
        self.btn_open = QPushButton("Open folder")
        self.btn_open.setToolTip("Show the current folder in the file manager")
        self.btn_open.clicked.connect(self._open_folder)
        out_btns.addWidget(self.btn_open)
        out_btns.addStretch()
        out_col.addLayout(out_btns)
        self.lbl_out_hint = QLabel()
        self.lbl_out_hint.setObjectName("subtitleLabel")
        self.lbl_out_hint.setWordWrap(True)
        out_col.addWidget(self.lbl_out_hint)
        return out_box

    def _build_export(self, prefs) -> QGroupBox:
        """Export defaults group: format/quality/size + output checks."""
        from app.ui.dialog_fields import build_format_quality

        exp_box = QGroupBox("Export defaults")
        exp_col = QVBoxLayout(exp_box)
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.cmb_format, self.spn_quality = build_format_quality(
            str(getattr(prefs, "format", "png")), getattr(prefs, "quality", 90))
        fmt_row.addWidget(self.cmb_format)
        fmt_row.addWidget(QLabel("Quality:"))
        self.spn_quality.setToolTip("Quality for JPG/WebP (PNG ignores it)")
        fmt_row.addWidget(self.spn_quality)
        fmt_row.addWidget(QLabel("Size:"))
        self.spn_size = QSpinBox()
        self.spn_size.setRange(self._min_side, self._max_side)
        try:
            self.spn_size.setValue(max(self._min_side, min(self._max_side, int(getattr(prefs, "size", 3000)))))
        except (TypeError, ValueError):
            self.spn_size.setValue(3000)
        self.spn_size.setToolTip("Long side of the main image")
        fmt_row.addWidget(self.spn_size)
        exp_col.addLayout(fmt_row)
        self.chk_image = QCheckBox("Main image")
        self.chk_image.setChecked(bool(getattr(prefs, "image", True)))
        self.chk_thumb = QCheckBox("Social thumb 1080p")
        self.chk_thumb.setChecked(bool(getattr(prefs, "thumb_1080p", True)))
        self.chk_vector = QCheckBox("Vector SVG")
        self.chk_vector.setChecked(bool(getattr(prefs, "vector", False)))
        self.chk_anim = QCheckBox("Animation GIF")
        self.chk_anim.setChecked(bool(getattr(prefs, "anim", False)))
        self.chk_meta = QCheckBox("Metadata JSON")
        self.chk_meta.setChecked(bool(getattr(prefs, "metadata", True)))
        for chk in (self.chk_image, self.chk_thumb, self.chk_vector,
                    self.chk_anim, self.chk_meta):
            exp_col.addWidget(chk)
        return exp_box

    def _build_general(self, prefs, recent_count: int) -> QGroupBox:
        """General group: jobs, drop, viewport, recents, data folder."""
        from app.ui.dialog_fields import build_jobs_spin

        gen_box = QGroupBox("General")
        gen_col = QVBoxLayout(gen_box)
        jobs_row = QHBoxLayout()
        jobs_row.addWidget(QLabel("Batch jobs:"))
        self.spn_jobs = build_jobs_spin(getattr(prefs, "jobs", 1))
        jobs_row.addWidget(self.spn_jobs)
        jobs_row.addWidget(QLabel("Viewport:"))
        self.cmb_viewport = QComboBox()
        self.cmb_viewport.addItems(["full", "live", "still"])
        vp = str(getattr(prefs, "viewport", "live")).lower()
        self.cmb_viewport.setCurrentText(vp if vp in ("full", "live", "still") else "live")
        self.cmb_viewport.setToolTip("Default preview mode for new windows")
        jobs_row.addWidget(self.cmb_viewport)
        jobs_row.addStretch()
        gen_col.addLayout(jobs_row)
        self.chk_drop = QCheckBox("Drop folder = Batch")
        self.chk_drop.setChecked(bool(getattr(prefs, "drop_batch", False)))
        self.chk_drop.setToolTip("OFF = dropping only loads images. ON = dropping a folder asks for batch.")
        gen_col.addWidget(self.chk_drop)
        self.chk_session = QCheckBox("Reopen last image on startup")
        self.chk_session.setChecked(bool(getattr(prefs, "restore_session", True)))
        self.chk_session.setToolTip("OFF = always start empty. ON = reopen last image + preset.")
        gen_col.addWidget(self.chk_session)
        recent_row = QHBoxLayout()
        self.lbl_recent = QLabel(f"{int(recent_count)} recent file(s)")
        recent_row.addWidget(self.lbl_recent, 1)
        self.btn_clear_recent = QPushButton("Clear recents")
        self.btn_clear_recent.setToolTip("Forget the File > Open recent list")
        self.btn_clear_recent.clicked.connect(self._clear_recent_label)
        recent_row.addWidget(self.btn_clear_recent)
        gen_col.addLayout(recent_row)
        data_row = QHBoxLayout()
        data_row.addWidget(QLabel("Data:"))
        self.lbl_data = QLabel(self._data_dir)
        self.lbl_data.setObjectName("subtitleLabel")
        self.lbl_data.setWordWrap(True)
        data_row.addWidget(self.lbl_data, 1)
        self.btn_data = QPushButton("Open")
        self.btn_data.setToolTip("Open the data folder (prefs, db, samples)")
        self.btn_data.clicked.connect(self._open_data)
        data_row.addWidget(self.btn_data)
        gen_col.addLayout(data_row)
        return gen_box

    def _build_extras(self) -> QGroupBox:
        """Extras group: acceleration + MP4 state, 1-click install on dev."""
        from app import extras as _ex

        box = QGroupBox("Extras (optional)")
        col = QVBoxLayout(box)
        self.lbl_accel = QLabel()
        self.lbl_accel.setWordWrap(True)
        col.addWidget(self.lbl_accel)
        row_a = QHBoxLayout()
        row_a.addWidget(QLabel("Acceleration:"))
        self.btn_accel = QPushButton("Install acceleration")
        self.btn_accel.setToolTip("pip install numba (dev version only)")
        self.btn_accel.clicked.connect(lambda: self._install_extra("accel"))
        row_a.addWidget(self.btn_accel)
        row_a.addStretch()
        col.addLayout(row_a)
        self.lbl_video = QLabel()
        self.lbl_video.setWordWrap(True)
        col.addWidget(self.lbl_video)
        row_v = QHBoxLayout()
        row_v.addWidget(QLabel("MP4 video:"))
        self.btn_video = QPushButton("Install video")
        self.btn_video.setToolTip("pip install imageio imageio-ffmpeg (dev only)")
        self.btn_video.clicked.connect(lambda: self._install_extra("video"))
        row_v.addWidget(self.btn_video)
        row_v.addStretch()
        col.addLayout(row_v)
        self.lbl_extra_note = QLabel()
        self.lbl_extra_note.setObjectName("subtitleLabel")
        self.lbl_extra_note.setWordWrap(True)
        col.addWidget(self.lbl_extra_note)
        self._frozen = bool(_ex.is_frozen())
        self._refresh_extras()
        return box

    def _refresh_extras(self) -> None:
        from app import extras as _ex

        accel_ok, accel_txt = _ex.accel_status()
        video_ok, video_txt = _ex.video_status()
        self.lbl_accel.setText(f"Acceleration: {accel_txt}")
        self.lbl_video.setText(f"MP4 video: {video_txt}")
        if self._frozen:
            self.btn_accel.setEnabled(False)
            self.btn_video.setEnabled(False)
            if accel_ok and video_ok:
                self.lbl_extra_note.setText(
                    "All extras included in this build (acceleration + MP4).")
            else:
                self.lbl_extra_note.setText(
                    "Extras missing from this build. Use the official "
                    "TRAKKART.exe or the dev version with pip packages.")
        else:
            self.btn_accel.setEnabled(not accel_ok)
            self.btn_video.setEnabled(not video_ok)
            self.lbl_extra_note.setText(
                "Installation takes minutes (numba) and needs internet. "
                "Restart the app to apply.")

    def _install_extra(self, kind: str) -> None:
        if self._frozen:
            return
        for btn in (self.btn_accel, self.btn_video):
            btn.setEnabled(False)
        self.lbl_extra_note.setText(f"Installing {kind} with pip… do not close Settings.")
        self._pip_worker = _PipWorker(kind, self)
        self._pip_worker.done.connect(self._on_extra_done)
        self._pip_worker.start()

    def _on_extra_done(self, kind: str, ok: bool, log: str) -> None:
        self._refresh_extras()
        if ok:
            self.lbl_extra_note.setText(
                f"{kind} installed. Restart the app to use it.")
        else:
            self.lbl_extra_note.setText(f"Failed to install {kind}: {log}")
        try:
            self._pip_worker.deleteLater()
        except Exception:  # noqa: BLE001
            pass

    def _build_buttons(self) -> QHBoxLayout:
        """Dialog buttons row (backup left, Cancel/Save right)."""
        bar = QHBoxLayout()
        self.btn_backup_export = QPushButton("Export...")
        self.btn_backup_export.setToolTip("Save all settings to a .json backup file")
        self.btn_backup_export.clicked.connect(self._on_export_backup)
        bar.addWidget(self.btn_backup_export)
        self.btn_backup_import = QPushButton("Import...")
        self.btn_backup_import.setToolTip("Restore settings from a .json backup file")
        self.btn_backup_import.clicked.connect(self._on_import_backup)
        bar.addWidget(self.btn_backup_import)
        bar.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bar.addWidget(self.btn_cancel)
        self.btn_ok = QPushButton("Save")
        self.btn_ok.setObjectName("exportBtn")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_save)
        bar.addWidget(self.btn_ok)
        return bar

    # -- slots --
    def _browse(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        start = self.edit_out.text().strip() or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "Default export folder", start)
        if d:
            self.edit_out.setText(d)
            self._refresh_hint()

    def _reset(self) -> None:
        from app.paths import get_out_dir

        try:
            self.edit_out.setText(str(get_out_dir()))
        except Exception:  # noqa: BLE001
            self.edit_out.setText("")
        self._refresh_hint()

    def _open_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        target = self.edit_out.text().strip() or self._data_dir
        if not target:
            return
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))
        except Exception:  # noqa: BLE001
            pass

    def _open_data(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if not self._data_dir:
            return
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._data_dir))
        except Exception:  # noqa: BLE001
            pass

    def _clear_recent_label(self) -> None:
        self._recents_cleared = True
        self.lbl_recent.setText("0 recent file(s) — will clear on Save")

    def _refresh_hint(self) -> None:
        target = self.edit_out.text().strip()
        if not target:
            self.lbl_out_hint.setText("Empty = system default (data/out). Quick export reuses this folder.")
            return
        if is_writable_dir(target):
            self.lbl_out_hint.setText(f"Exports default to: {target}")
        else:
            self.lbl_out_hint.setText("Not writable — pick another folder.")

    def _on_save(self) -> None:
        if not self.chk_image.isChecked() and not self.chk_thumb.isChecked() \
                and not self.chk_vector.isChecked() and not self.chk_anim.isChecked() \
                and not self.chk_meta.isChecked():
            self.chk_image.setChecked(True)
        self.accept()

    def _on_export_backup(self) -> None:
        """Save dialog values + stored prefs to a .json backup file."""
        from PySide6.QtWidgets import QFileDialog

        from app.export_prefs import apply_dialog_values, load_prefs, normalize_prefs, save_prefs

        path, _ = QFileDialog.getSaveFileName(
            self, "Export settings", "trakkart-settings.json", "JSON (*.json)")
        if not path:
            return
        try:
            prefs = apply_dialog_values(load_prefs(self._prefs_path), self.values())
            normalize_prefs(prefs)
            save_prefs(prefs, path)
            self.lbl_out_hint.setText(f"Backup saved: {path}")
        except Exception as e:  # noqa: BLE001
            self.lbl_out_hint.setText(f"Backup failed: {e}")

    def _on_import_backup(self) -> None:
        """Load a .json backup file into the dialog (Save to apply)."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from app.export_prefs import load_backup_file

        path, _ = QFileDialog.getOpenFileName(
            self, "Import settings", "", "JSON (*.json)")
        if not path:
            return
        try:
            prefs = load_backup_file(path)
        except ValueError as e:
            QMessageBox.warning(self, "Settings", f"Could not import:\n{e}")
            return
        self._set_values(prefs)
        self._refresh_hint()

    def _set_values(self, prefs) -> None:
        """Refresh every widget from prefs (backup import)."""
        self.edit_out.setText(str(getattr(prefs, "out_dir", "") or ""))
        self.cmb_format.setCurrentText(str(getattr(prefs, "format", "png")))
        self.spn_quality.setValue(max(1, min(100, int(getattr(prefs, "quality", 90)))))
        size = max(self._min_side, min(self._max_side, int(getattr(prefs, "size", 3000))))
        self.spn_size.setValue(size)
        self.chk_image.setChecked(bool(getattr(prefs, "image", True)))
        self.chk_thumb.setChecked(bool(getattr(prefs, "thumb_1080p", True)))
        self.chk_vector.setChecked(bool(getattr(prefs, "vector", False)))
        self.chk_anim.setChecked(bool(getattr(prefs, "anim", False)))
        self.chk_meta.setChecked(bool(getattr(prefs, "metadata", True)))
        self.spn_jobs.setValue(max(1, min(8, int(getattr(prefs, "jobs", 1)))))
        self.chk_drop.setChecked(bool(getattr(prefs, "drop_batch", False)))
        vp = str(getattr(prefs, "viewport", "live")).lower()
        self.cmb_viewport.setCurrentText(vp if vp in ("full", "live", "still") else "live")
        self.chk_session.setChecked(bool(getattr(prefs, "restore_session", True)))

    # -- result --
    def values(self) -> dict:
        """Validated settings dict. Only valid after Accept."""
        return {
            "out_dir": self.edit_out.text().strip(),
            "format": self.cmb_format.currentText(),
            "quality": int(self.spn_quality.value()),
            "size": int(self.spn_size.value()),
            "image": self.chk_image.isChecked(),
            "thumb_1080p": self.chk_thumb.isChecked(),
            "vector": self.chk_vector.isChecked(),
            "anim": self.chk_anim.isChecked(),
            "metadata": self.chk_meta.isChecked(),
            "jobs": int(self.spn_jobs.value()),
            "drop_batch": bool(self.chk_drop.isChecked()),
            "viewport": str(self.cmb_viewport.currentText()),
            "restore_session": bool(self.chk_session.isChecked()),
            "clear_recents": bool(self._recents_cleared),
        }


__all__ = ["SettingsDialog"]


class _PipWorker(QThread):
    """pip install in background (minutes for numba): never block the UI."""

    done = Signal(str, bool, str)  # kind, ok, log tail

    def __init__(self, kind: str, parent=None) -> None:
        super().__init__(parent)
        self._kind = kind

    def run(self) -> None:  # noqa: N802 (Qt override)
        from app.extras import missing_packages, run_pip_install

        try:
            ok, log = run_pip_install(missing_packages(self._kind))
        except Exception as e:  # noqa: BLE001
            ok, log = False, str(e)
        self.done.emit(self._kind, ok, log)
