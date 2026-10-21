"""Keyboard-shortcut reference (static table, no logic)."""

from __future__ import annotations

SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("Open image...", "Ctrl+O"),
    ("Quick export", "Ctrl+S"),
    ("Export...", "Ctrl+Shift+S"),
    ("Batch folder...", "Ctrl+B"),
    ("Undo image", "Ctrl+Z"),
    ("Surprise me", "Ctrl+R"),
    ("Copy result", "Ctrl+C"),
    ("Paste image", "Ctrl+V"),
    ("Previous / next method", "Alt+Left / Alt+Right"),
    ("Hold to compare (original)", "Space (hold)"),
    ("Refresh preview", "F5"),
    ("Zoom in / out", "Ctrl+= / Ctrl+-"),
    ("Zoom fit / 100%", "Ctrl+0 / Ctrl+1"),
)


def show_shortcuts(win) -> None:
    from PySide6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )

    dlg = QDialog(win)
    dlg.setWindowTitle("Keyboard shortcuts")
    dlg.setMinimumWidth(380)
    col = QVBoxLayout(dlg)
    table = QTableWidget(len(SHORTCUTS), 2, dlg)
    table.setHorizontalHeaderLabels(["Action", "Shortcut"])
    for row, (action, keys) in enumerate(SHORTCUTS):
        table.setItem(row, 0, QTableWidgetItem(action))
        table.setItem(row, 1, QTableWidgetItem(keys))
    table.resizeColumnsToContents()
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    col.addWidget(table)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dlg.reject)
    col.addWidget(buttons)
    dlg.exec()


__all__ = ["SHORTCUTS", "show_shortcuts"]
