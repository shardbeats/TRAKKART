"""FX stack controller: list order + on/off (params live in sliders).

Single source: win.fx_stack_data = [{id, enabled}]. The checkable Qlist
mirrors the data; any change re-renders (350ms debounce).
"""

from __future__ import annotations


def _labels():
    from app.fx_stack import FX_LABELS

    return FX_LABELS


def get_stack(win) -> list:
    from app.fx_stack import normalize_stack

    data = list(getattr(win, "fx_stack_data", []) or [])
    if not data:
        return normalize_stack(None)
    return normalize_stack(data)


def set_stack(win, stack: list | None) -> None:
    from app.fx_stack import normalize_stack

    win.fx_stack_data = normalize_stack(stack)
    sync_list(win, refresh_add=True)


def sync_list(win, refresh_add: bool = True) -> None:
    from PySide6.QtCore import Qt

    from app.fx_stack import normalize_stack

    data = normalize_stack(getattr(win, "fx_stack_data", None))
    win.fx_stack_data = data
    lst = win.fx_list
    try:
        lst.blockSignals(True)
        lst.clear()
        for entry in data:
            fid = entry["id"]
            from PySide6.QtWidgets import QListWidgetItem

            label = _labels().get(fid, fid)
            item = QListWidgetItem(f"{label}")
            item.setData(256, fid)  # Qt.UserRole
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if entry.get("enabled", True) else Qt.Unchecked)
            lst.addItem(item)
    finally:
        lst.blockSignals(False)
    if refresh_add:
        sync_add_combo(win)


def sync_add_combo(win) -> None:
    data = get_stack(win)
    disabled = [e["id"] for e in data if not e.get("enabled", True)]
    cmb = win.cmb_fx_add
    try:
        cmb.blockSignals(True)
        cmb.clear()
        if disabled:
            labels = _labels()
            cmb.addItems([f"{labels.get(fid, fid)}" for fid in disabled])
            cmb.setEnabled(True)
        else:
            cmb.addItem("(all enabled)")
            cmb.setEnabled(False)
    finally:
        cmb.blockSignals(False)


def on_toggled(win) -> None:
    from PySide6.QtCore import Qt

    data: list = []
    for i in range(win.fx_list.count()):
        item = win.fx_list.item(i)
        fid = item.data(256)
        data.append({"id": fid, "enabled": item.checkState() == Qt.Checked})
    win.fx_stack_data = data
    sync_add_combo(win)
    win._schedule_refresh()


def _selected_fid(win) -> str | None:
    items = win.fx_list.selectedItems()
    if not items:
        return None
    return items[0].data(256)


def move_selected(win, delta: int) -> None:
    data = get_stack(win)
    fid = _selected_fid(win)
    if fid is None:
        return
    idx = next((i for i, e in enumerate(data) if e["id"] == fid), -1)
    j = idx + delta
    if idx < 0 or not 0 <= j < len(data):
        return
    data[idx], data[j] = data[j], data[idx]
    win.fx_stack_data = data
    sync_list(win, refresh_add=False)
    # Reselect the moved one.
    for i in range(win.fx_list.count()):
        if win.fx_list.item(i).data(256) == fid:
            win.fx_list.setCurrentRow(i)
            break
    sync_add_combo(win)
    win._schedule_refresh()


def on_add(win, label: str) -> None:
    labels = _labels()
    inv = {v: k for k, v in labels.items()}
    fid = inv.get(label, "")
    if not fid:
        return
    data = get_stack(win)
    for e in data:
        if e["id"] == fid:
            e["enabled"] = True
    win.fx_stack_data = data
    sync_list(win)
    win._schedule_refresh()
