"""Timeline controller: animation layers list + editors + locks + drift UI.

Single source: win.anim_layers_data = [{prop, frm, to, ease, start, end}].
Animated props lock their panel controls (disable + tooltip) so slider
fights can't happen while the timeline owns the value.
"""

from __future__ import annotations

# prop -> MainWindow widget attribute (locked while animated).
PROP_WIDGETS: dict[str, str] = {
    "threshold": "sld_thr",
    "pixel_size": "spn_pixel",
    "pre_hue": "sld_hue",
    "grain": "sld_grain",
    "glow_intensity": "sld_glow",
    "glitch_chroma": "sld_chroma",
    "wave": "spn_wave",
    "jpeg": "sld_jpeg",
    "fade": "sld_fade",
    "split_tone": "sld_split",
}


def _labels():
    from app.timeline import ANIM_PROPS

    return ANIM_PROPS


def get_layers(win) -> list:
    from app.timeline import normalize_layers

    return normalize_layers(list(getattr(win, "anim_layers_data", []) or []))


def set_layers(win, layers: list | None) -> None:
    from app.timeline import normalize_layers

    win.anim_layers_data = normalize_layers(layers)
    sync_list(win)
    sync_locks(win)


def sync_list(win) -> None:
    data = get_layers(win)
    win.anim_layers_data = data
    lst = win.anim_list
    try:
        lst.blockSignals(True)
        lst.clear()
        for e in data:
            from PySide6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(
                f"{e['prop']} {e['frm']:g}→{e['to']:g} {e['ease']} [{e['start']}-{e['end']}]")
            item.setData(256, (e["prop"], e["start"], e["end"]))
            lst.addItem(item)
    finally:
        lst.blockSignals(False)
    sync_editors(win)


def _selected(win) -> int:
    try:
        return int(win.anim_list.currentRow())
    except Exception:  # noqa: BLE001
        return -1


def add_layer(win) -> None:
    data = get_layers(win)
    last_prop = data[-1]["prop"] if data else "threshold"
    data.append({"prop": last_prop, "frm": 128.0, "to": 200.0, "ease": "linear",
                 "start": 0, "end": 23})
    win.anim_layers_data = data
    sync_list(win)
    sync_locks(win)
    try:
        win.anim_list.setCurrentRow(len(data) - 1)
    except Exception:  # noqa: BLE001
        pass
    win._schedule_refresh()


def remove_layer(win) -> None:
    idx = _selected(win)
    data = get_layers(win)
    if 0 <= idx < len(data):
        del data[idx]
        win.anim_layers_data = data
        sync_list(win)
        sync_locks(win)
        win._schedule_refresh()


def sync_editors(win) -> None:
    """Load the selected layer into the editor widgets (no-op if none)."""
    from app.timeline import EASES

    idx = _selected(win)
    data = get_layers(win)
    has = 0 <= idx < len(data)
    for w in (win.cmb_anim_prop, win.spn_anim_from, win.spn_anim_to,
              win.cmb_anim_ease, win.spn_anim_start, win.spn_anim_end,
              win.btn_anim_remove):
        try:
            w.setEnabled(has)
        except Exception:  # noqa: BLE001
            pass
    if not has:
        return
    e = data[idx]
    try:
        win.cmb_anim_prop.blockSignals(True)
        if win.cmb_anim_prop.findText(e["prop"]) >= 0:
            win.cmb_anim_prop.setCurrentText(e["prop"])
    finally:
        win.cmb_anim_prop.blockSignals(False)
    for attr, key in (("spn_anim_from", "frm"), ("spn_anim_to", "to")):
        try:
            getattr(win, attr).blockSignals(True)
            getattr(win, attr).setValue(float(e[key]))
        finally:
            getattr(win, attr).blockSignals(False)
    try:
        win.cmb_anim_ease.blockSignals(True)
        if win.cmb_anim_ease.findText(e["ease"]) >= 0:
            win.cmb_anim_ease.setCurrentText(e["ease"])
    finally:
        win.cmb_anim_ease.blockSignals(False)
    for attr, key in (("spn_anim_start", "start"), ("spn_anim_end", "end")):
        try:
            getattr(win, attr).blockSignals(True)
            getattr(win, attr).setValue(int(e[key]))
        finally:
            getattr(win, attr).blockSignals(False)
    _ = EASES


def read_editors(win) -> None:
    """Write editor widgets back into the selected layer."""
    idx = _selected(win)
    data = get_layers(win)
    if not 0 <= idx < len(data):
        return
    e = dict(data[idx])
    try:
        e["prop"] = str(win.cmb_anim_prop.currentText())
        e["frm"] = float(win.spn_anim_from.value())
        e["to"] = float(win.spn_anim_to.value())
        e["ease"] = str(win.cmb_anim_ease.currentText())
        e["start"] = int(win.spn_anim_start.value())
        e["end"] = int(win.spn_anim_end.value())
    except Exception:  # noqa: BLE001
        return
    from app.timeline import normalize_layers

    data[idx] = e
    win.anim_layers_data = normalize_layers(data)
    sync_list(win)
    try:
        win.anim_list.setCurrentRow(idx)
    except Exception:  # noqa: BLE001
        pass
    sync_locks(win)
    win._schedule_refresh()


def sync_locks(win) -> None:
    """Disable panel controls owned by the timeline (+ tooltip)."""
    from app.timeline import animated_props

    owned = set(animated_props(getattr(win, "anim_layers_data", [])))
    for prop, attr in PROP_WIDGETS.items():
        w = getattr(win, attr, None)
        if w is None:
            continue
        try:
            locked = prop in owned
            w.setEnabled(not locked)
            w.setToolTip(("Animated by timeline (remove the layer to edit)"
                          if locked else w.toolTip()))
        except Exception:  # noqa: BLE001
            pass
