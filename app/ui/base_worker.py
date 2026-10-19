"""Shared QThread base — antes PreviewWorker y BatchWorker duplicaban
el patrón QThread + try/except + señal de error cada uno por su lado."""

from __future__ import annotations

from PySide6.QtCore import QThread


class WorkerBase(QThread):
    """Template-method: `work()` hace el trabajo, `run()` lo envuelve.

    Las subclases implementan `work()` y `_report_error()`. La API pública
    (señales y constructor) de cada worker no cambia.
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
