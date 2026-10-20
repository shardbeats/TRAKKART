"""Widget get/set factories for the BINDINGS table (widgets <-> Preset).

Split out of app/ui/params_controller.py (mechanical move, no logic change).
Factores here build (get, set) pairs; the table itself stays in the controller.
"""

from __future__ import annotations


def _block(w):
    w.blockSignals(True)


def _unblock(w):
    w.blockSignals(False)


def _slider(attr: str, div: float = 1.0):
    def get(win):
        return getattr(win, attr).value() / div

    def set(win, v):
        w = getattr(win, attr)
        try:
            _block(w)
            w.setValue(int(round(float(v) * div)))
        finally:
            _unblock(w)

    return get, set


def _spin(attr: str):
    def get(win):
        return int(getattr(win, attr).value())

    def set(win, v):
        w = getattr(win, attr)
        try:
            _block(w)
            w.setValue(int(v))
        finally:
            _unblock(w)

    return get, set


def _combo(attr: str):
    def get(win):
        return getattr(win, attr).currentText()

    def set(win, v):
        w = getattr(win, attr)
        if w.findText(str(v)) < 0:
            return
        try:
            _block(w)
            w.setCurrentText(str(v))
        finally:
            _unblock(w)

    return get, set


def _anim_combo(attr: str, lo: int, hi: int, default: int):
    def get(win):
        return anim_combo_int(getattr(win, attr), default, lo, hi)

    def set(win, v):
        set_anim_combo(getattr(win, attr), max(lo, min(hi, int(v))))

    return get, set


def _brand_get(win):
    return win.brand_color


def _brand_set(win, v):
    win.set_brand_color(v or "")


def _duo_mid_get(win):
    return float(win.sld_duo_mid.value())


def _duo_mid_set(win, v):
    win.sld_duo_mid.setValue(int(float(v)))


def _border_color_get(win):
    return win.border_color


def _border_color_set(win, v):
    win.set_border_color(str(v or "#000000"))


def _scan_get(win):
    return int(win.spn_scan.value())


def _scan_set(win, v):
    win.spn_scan.setValue(int(v))


def _glow_radius_get(win):
    # Radio 0 si el glow está apagado (el spin conserva su último valor).
    if win.sld_glow.value() <= 0:
        return 0.0
    return float(win.spn_glowrad.value())


def _glow_radius_set(win, v):
    win.spn_glowrad.setValue(int(float(v)))


def anim_combo_int(cmb, default: int, lo: int, hi: int) -> int:
    """Lee un combo editable (lista sugerida + valor libre)."""
    try:
        return max(lo, min(hi, int(str(cmb.currentText()).strip())))
    except Exception:  # noqa: BLE001
        return int(default)


def set_anim_combo(cmb, value: int) -> None:
    """Fija un combo editable conservando valores custom fuera de la lista."""
    txt = str(int(value))
    try:
        if cmb.findText(txt) < 0:
            cmb.addItem(txt)
        cmb.blockSignals(True)
        cmb.setCurrentText(txt)
    finally:
        cmb.blockSignals(False)
