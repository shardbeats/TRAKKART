"""Batch flow: folder dialog + threaded worker + progress + sync runner.

State (`_batch_worker/_cancel/_start/_out`) and widgets stay on MainWindow;
this module holds the behavior. The window keeps `run_batch_dialog()` /
`run_batch()` / `cancel_batch()` / `run_batch_sync()` / `_on_batch_*()` by
delegation. `run_batch_with_input` / `_on_drop_folder` (drag&drop glue that
ends in a batch) live here too.
"""

from __future__ import annotations


def _dialog_cls():
    # La clase se resuelve en el namespace de main_window (no import directo)
    # para que los tests puedan sustituirla (monkeypatch MW.BatchDialog).
    from app.ui import main_window as _mw

    return _mw.BatchDialog


def run_batch_dialog(win) -> None:
    """Un solo diálogo validado, no dos seguidos a ciegas."""
    from dataclasses import replace

    BatchDialog = _dialog_cls()

    preset = win.current_params()
    canvas_size = None
    if win.src is not None:
        try:
            from app.canvas import to_canvas

            canvas = to_canvas(
                win.src, ratio=win.cmb_ratio.currentText(), mode=win.cmb_crop.currentText(),
                fx=float(win.crop_fx), fy=float(win.crop_fy), zoom=float(win.crop_zoom),
            )
            canvas_size = (canvas.width, canvas.height)
        except Exception:  # noqa: BLE001
            canvas_size = None
    dlg = BatchDialog(
        in_dir="", out_dir=str(win.out_dir), jobs=int(win.spn_jobs.value()),
        vector_export=bool(preset.vector_export), vector_cell=int(preset.vector_cell),
        gif_export=bool(preset.gif_export), gif_frames=int(preset.gif_frames),
        gif_mode=preset.gif_mode, gif_fps=int(getattr(preset, "gif_fps", 8)),
        gif_pingpong=bool(getattr(preset, "gif_pingpong", False)),
        canvas_size=canvas_size,
        size=int(preset.export_size), format=str(preset.export_format),
        quality=int(preset.export_quality), parent=win)
    if dlg.exec() != dlg.DialogCode.Accepted:
        return
    src, dst, jobs = dlg.paths()
    outs = dlg.output_options()
    preset = replace(
        preset, vector_export=outs["vector_export"], vector_cell=outs["vector_cell"],
        gif_export=outs["gif_export"], gif_frames=outs["gif_frames"],
        gif_mode=outs["gif_mode"], gif_fps=outs.get("gif_fps", 8),
        gif_size=outs.get("gif_size", 1200),
        gif_pingpong=outs.get("gif_pingpong", False),
        export_size=outs["export_size"],
        export_format=outs["export_format"], export_quality=outs["export_quality"])
    win.run_batch(src, dst, jobs=jobs, preset=preset)


def _worker_cls():
    # Igual que _dialog_cls: resoluble vía MW para los stubs de tests.
    from app.ui import main_window as _mw

    return _mw.BatchWorker


def run_batch(win, src, dst, jobs: int | None = None, preset=None) -> None:
    import time
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    BatchWorker = _worker_cls()

    if win._batch_worker is not None and win._batch_worker.isRunning():
        return
    try:
        preset = preset or win.current_params()
        preset.validate()
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Invalid preset:\n{e}")
        return
    win._batch_cancel[0] = False
    win._batch_start = time.time()
    win._batch_out = Path(dst)
    win._batch_worker = BatchWorker(
        src, dst, preset, store=win.store,
        jobs=int(jobs) if jobs else int(win.spn_jobs.value()), cancel=win._batch_cancel)
    win._batch_worker.progress.connect(win._on_batch_progress)
    win._batch_worker.finished.connect(win._on_batch_finished)
    win._batch_worker.error.connect(win._on_batch_error)
    win.btn_batch.setEnabled(False)
    win.progress.setValue(0)
    win.progress.show()
    win.btn_cancel.show()
    win._batch_worker.start()


def cancel_batch(win) -> None:
    win._batch_cancel[0] = True
    win._status("Cancelling batch...")


def run_batch_sync(win, src, dst) -> list[dict]:
    """Synchronous batch (tests + scripts)."""
    from app.batch import batch_process

    return batch_process(src, dst, win.current_params(), store=win.store)


def on_progress(win, done: int, total: int, name: str) -> None:
    import time

    win.progress.setValue(int(done / total * 100) if total else 100)
    elapsed = time.time() - (win._batch_start or time.time())
    fps = done / elapsed if elapsed > 0 else 0.0
    if fps > 0:
        eta = (total - done) / fps
        m, s = divmod(int(eta), 60)
        h, m = divmod(m, 60)
        eta_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
    else:
        eta_str = "…"
    short = name if len(name) <= 24 else name[:21] + "…"
    win._status(f"Batch {done}/{total} · {fps:.1f} img/s · ETA {eta_str} · {short}")


def on_finished(win, results: list[dict]) -> None:
    from PySide6.QtWidgets import QMessageBox

    win.btn_batch.setEnabled(True)
    win.progress.hide()
    win.btn_cancel.hide()
    ok = sum(1 for r in results if r["status"] == "ok")
    sk = sum(1 for r in results if r["status"] == "skipped")
    er = sum(1 for r in results if r["status"] == "error")
    cancelled = " (cancelled)" if win._batch_cancel[0] else ""
    where = f" → {win._batch_out}" if win._batch_out else ""
    win._status(f"Batch done: {ok} ok, {sk} skipped, {er} errors{cancelled}{where}")
    QMessageBox.information(win, "TRAKKART", f"Batch done:\n{ok} ok, {sk} skipped, {er} errors{cancelled}.\n{where}")


def on_error(win, msg: str) -> None:
    from PySide6.QtWidgets import QMessageBox

    win.btn_batch.setEnabled(True)
    win.progress.hide()
    win.btn_cancel.hide()
    QMessageBox.warning(win, "TRAKKART", f"Batch error:\n{msg}")


def run_batch_with_input(win, src) -> None:
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog

    dst = QFileDialog.getExistingDirectory(win, "Output folder")
    if not dst:
        return
    win.run_batch(Path(src), Path(dst))


def on_drop_folder(win, src) -> None:
    """Dropping a folder ONLY processes with the toggle armed + confirmation."""
    from PySide6.QtWidgets import QMessageBox

    from app.batch import EXTS

    if not win.chk_batch_drop.isChecked():
        win._status("Folder received: enable 'Drop folder = batch' or use the Batch button")
        return
    try:
        files = [f for f in src.iterdir() if f.is_file() and f.suffix.lower() in EXTS]
    except OSError as e:
        QMessageBox.warning(win, "TRAKKART", f"Could not read the folder:\n{e}")
        return
    if not files:
        win._status("The folder has no compatible images")
        return
    preset = win.current_params()
    ok = QMessageBox.question(
        win, "Drop batch",
        f"Process {len(files)} images with preset '{preset.name or 'current'}'?\nOutput: {win.out_dir}",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if ok != QMessageBox.StandardButton.Yes:
        win._status("Batch cancelled")
        return
    win.run_batch(src, win.out_dir)
