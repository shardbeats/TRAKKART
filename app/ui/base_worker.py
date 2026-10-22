"""Shared QThread base — before PreviewWorker and BatchWorker duplicated
the QThread + try/except + error-signal pattern each on their own."""

from __future__ import annotations

from PySide6.QtCore import QThread


class WorkerBase(QThread):
    """Template-method: `work()` does the job, `run()` wraps it.

    Subclasses implement `work()` and `_report_error()`. The public API
    (signals and constructor) of each worker is unchanged.
    """

    def run(self) -> None:  # noqa: N802
        try:
            self.work()
        except Exception as e:  # noqa: BLE001
            self._report_error(e)

    def work(self) -> None:
        raise NotImplementedError

    def _report_error(self, exc: Exception) -> None:
        raise NotImplementedError


__all__ = ["WorkerBase"]
