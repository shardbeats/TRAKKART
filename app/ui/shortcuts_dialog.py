"""Keyboard-shortcut editor (Help > Keyboard shortcuts...).

Table of actions with press-to-capture assignment: click a shortcut
cell, press the keys (Esc cancels, Del clears). Conflicts are refused
with a message naming the other action. Changes save immediately to
shortcuts.json and apply live; Reset restores defaults.
"""

from __future__ import annotations

# Back-compat export: (label, default keys), same shape as before.
# New code should use app.shortcuts.ACTIONS instead.
from app.shortcuts import ACTIONS as _ACTIONS

SHORTCUTS: tuple[tuple[str, str], ...] = tuple(
    (label, default) for _, label, default in _ACTIONS)


def _capture_filter(on_key):
    from PySide6.QtCore import QObject

    class _Filter(QObject):
        def eventFilter(self, obj, event):  # noqa: N802
            from PySide6.QtCore import QEvent

            if event.type() == QEvent.Type.KeyPress:
                return bool(on_key(event))
            return False

    return _Filter()


def assign_binding(win, action_id: str, keys: str) -> tuple[bool, str]:
    """Validate + save + apply one binding. Returns (ok, message)."""
    from app import shortcuts as _keys

    norm = _keys.normalize_keys(keys)
    if not norm and keys.strip():
        return False, f"'{keys.strip()}' is not a valid shortcut."
    custom = dict(_keys.current_custom(win))
    if not norm:
        custom.pop(action_id, None)
        if _keys.default_keys(action_id):
            custom[action_id] = ""  # explicit unbind beats the default
    else:
        for other in _keys.action_ids():
            if other != action_id and _keys.effective_for(win, other) == norm:
                return False, (f"{norm} is already used by "
                               f"'{_keys.action_label(other)}'.")
        custom[action_id] = norm
    try:
        _keys.save_custom(custom)
    except Exception as e:  # noqa: BLE001
        return False, f"Could not save: {e}"
    try:
        _keys.apply_shortcuts(win, custom)
    except Exception as e:  # noqa: BLE001
        return False, f"Could not apply: {e}"
    shown = norm if norm else "(unbound)"
    return True, f"{_keys.action_label(action_id)} → {shown}"


def build_shortcuts_dialog(win):
    """Construct the editor dialog (no exec: testable)."""
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QDialog,
        QDialogButtonBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )

    from app import shortcuts as _keys

    dlg = QDialog(win)
    dlg.setWindowTitle("Keyboard shortcuts — click a shortcut, press keys")
    dlg.setMinimumWidth(460)
    col = QVBoxLayout(dlg)
    table = QTableWidget(len(_keys.ACTIONS), 2, dlg)
    table.setHorizontalHeaderLabels(["Action", "Shortcut"])
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    state = {"listening": None, "filter": None}

    def refresh_table():
        custom = _keys.current_custom(win)
        for row, (aid, label, _default) in enumerate(_keys.ACTIONS):
            keys = _keys.effective_keys(aid, custom)
            table.setItem(row, 0, QTableWidgetItem(label))
            shown = keys if keys else "(unbound)"
            if state["listening"] == aid:
                shown = "Press keys… (Esc cancels, Del clears)"
            table.setItem(row, 1, QTableWidgetItem(shown))
        table.resizeColumnsToContents()

    refresh_table()
    status = QLabel("Click a shortcut cell, then press the keys. "
                    "Del clears, Esc cancels.")
    status.setWordWrap(True)
    status.setObjectName("subtitleLabel")

    def stop_listening():
        filt = state.pop("filter", None)
        try:
            from PySide6.QtWidgets import QApplication

            if filt is not None:
                QApplication.instance().removeEventFilter(filt)
        except Exception:  # noqa: BLE001
            pass
        state["listening"] = None

    def on_key(event):
        from PySide6.QtCore import Qt as _Qt

        aid = state.get("listening")
        if aid is None:
            return False
        try:
            if event.key() in (_Qt.Key.Key_Escape,):
                status.setText("Cancelled — pick a shortcut cell to retry.")
                stop_listening()
                refresh_table()
                return True
            if event.key() in (_Qt.Key.Key_Delete, _Qt.Key.Key_Backspace):
                ok, msg = assign_binding(win, aid, "")
                status.setText(msg)
                stop_listening()
                refresh_table()
                return True
            if event.key() in (_Qt.Key.Key_Return, _Qt.Key.Key_Enter,
                               _Qt.Key.Key_Tab, _Qt.Key.Key_Backtab):
                return True  # navigation keys are not shortcuts
            text = _keys.event_to_text(event)
        except Exception:  # noqa: BLE001
            return True
        if not text:
            status.setText("Press a complete combination (e.g. Ctrl+Shift+E).")
            return True
        ok, msg = assign_binding(win, aid, text)
        status.setText(msg if ok else f"Not assigned: {msg}")
        stop_listening()
        refresh_table()
        return True

    def on_cell(row, _col):
        if _col != 1:
            return
        ids = _keys.action_ids()
        if 0 <= row < len(ids):
            stop_listening()
            state["listening"] = ids[row]
            filt = _capture_filter(on_key)
            state["filter"] = filt
            try:
                from PySide6.QtWidgets import QApplication

                QApplication.instance().installEventFilter(filt)
            except Exception:  # noqa: BLE001
                pass
            status.setText(f"Press keys for '{_keys.action_label(ids[row])}'… "
                           f"(Esc cancels, Del clears)")
            refresh_table()

    table.cellClicked.connect(on_cell)
    col.addWidget(table)
    col.addWidget(status)

    brow = QHBoxLayout()
    btn_reset = QPushButton("Reset defaults")
    btn_reset.setToolTip("Forget all custom shortcuts")

    def _on_reset():
        try:
            _keys.reset_custom()
            custom = {}
            try:
                win._shortcuts_custom = {}
            except Exception:  # noqa: BLE001
                pass
            _keys.apply_shortcuts(win, custom)
            status.setText("Defaults restored.")
        except Exception as e:  # noqa: BLE001
            status.setText(f"Reset failed: {e}")
        refresh_table()

    btn_reset.clicked.connect(_on_reset)
    brow.addWidget(btn_reset)
    brow.addStretch()
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dlg.reject)
    brow.addWidget(buttons)
    col.addLayout(brow)
    dlg._refresh_table = refresh_table  # test seam (no exec needed)
    orig_reject = dlg.reject

    def _reject():
        stop_listening()
        orig_reject()

    dlg.reject = _reject
    return dlg


def show_shortcuts(win) -> None:
    dlg = build_shortcuts_dialog(win)
    dlg.exec()


__all__ = ["SHORTCUTS", "assign_binding", "build_shortcuts_dialog",
           "show_shortcuts"]
