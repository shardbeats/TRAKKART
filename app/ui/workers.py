"""Dedicated QThread workers — batch without freezing the UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal

from app.batch import batch_process
from app.presets import Preset
from app.ui.base_worker import WorkerBase


class BatchWorker(WorkerBase):
    """Run batch_process on a worker thread with progress."""

    progress = Signal(int, int, str)  # done, total, filename
    finished = Signal(list)           # results
    error = Signal(str)

    def __init__(
        self,
        input_dir: str | Path,
        out_dir: str | Path,
        preset: Preset,
        skip_existing: bool = True,
        store=None,
        jobs: int = 1,
        cancel: list | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.input_dir = Path(input_dir)
        self.out_dir = Path(out_dir)
        self.preset = preset
        self.skip_existing = skip_existing
        self.store = store
        self.jobs = jobs
        self.cancel = cancel

    def work(self) -> None:
        results = batch_process(
            self.input_dir,
            self.out_dir,
            self.preset,
            skip_existing=self.skip_existing,
            progress_cb=self.progress.emit,
            store=self.store,
            jobs=self.jobs,
            cancel=self.cancel,
        )
        self.finished.emit(results)

    def _report_error(self, exc: Exception) -> None:
        from app.log import report_error

        try:
            preset_name = str(getattr(self.preset, "name", "?"))
        except Exception:  # noqa: BLE001
            preset_name = "?"
        rid = report_error("batch", exc,
                           {"preset": preset_name,
                            "input": getattr(self.input_dir, "name", "?"),
                            "output": getattr(self.out_dir, "name", "?"),
                            "jobs": self.jobs})
        self.error.emit(f"[{rid}] {exc}")
