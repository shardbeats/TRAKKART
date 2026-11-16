"""Envelope UI: session-only curves for motion/drift/grain (candidate #3).

Session-only like chain crops/repeats: never in presets, never in batch.
Three rows (Motion ×/Drift/Grain), each: kind combo (Off/Flat/Ramp/LFO)
+ two small spins (A/B). Flat: A=value. Ramp: A=v0 B=v1. LFO: A=base
B=amp (loops=1, loop-perfect). Off follows the preset (byte-identical).
"""

from __future__ import annotations

PARAMS = ("motion_amount", "drift_amount", "grain")
LABELS = {"motion_amount": "Motion", "drift_amount": "Drift", "grain": "Grain"}
LIMITS = {"motion_amount": (0.0, 3.0, 2), "drift_amount": (0.0, 100.0, 1), "grain": (0.0, 100.0, 1)}
KINDS = ("Off", "Flat", "Ramp", "LFO")


def init_envelopes(win) -> None:
    try:
        win._envelopes = dict(getattr(win, "_envelopes", {}) or {})
    except Exception:  # noqa: BLE001
        pass


def read_envelopes(win) -> dict:
    """Widgets -> canonical session dict (off rows dropped). Never raises."""
    from app.envelopes import normalize_envelopes

    raw: dict = {}
    try:
        for param in PARAMS:
            cmb = getattr(win, f"cmb_env_{param}", None)
            a = getattr(win, f"spn_env_{param}_a", None)
            b = getattr(win, f"spn_env_{param}_b", None)
            if cmb is None or a is None or b is None:
                continue
            kind = str(cmb.currentText() or "Off").lower()
            if kind == "off":
                continue
            va = float(a.value())
            vb = float(b.value())
            if kind == "flat":
                raw[param] = {"kind": "flat", "value": va}
            elif kind == "ramp":
                raw[param] = {"kind": "ramp", "v0": va, "v1": vb}
            elif kind == "lfo":
                raw[param] = {"kind": "lfo", "base": va, "amp": vb, "loops": 1}
    except Exception:  # noqa: BLE001
        return {}
    try:
        return normalize_envelopes(raw)
    except Exception:  # noqa: BLE001
        return {}


def sync_envelopes(win) -> None:
    """Push widgets -> win._envelopes + refresh preview/stale badge."""
    try:
        win._envelopes = read_envelopes(win)
    except Exception:  # noqa: BLE001
        pass
    try:
        for param in PARAMS:
            cmb = getattr(win, f"cmb_env_{param}", None)
            a = getattr(win, f"spn_env_{param}_a", None)
            b = getattr(win, f"spn_env_{param}_b", None)
            if cmb is None or a is None or b is None:
                continue
            kind = str(cmb.currentText() or "Off").lower()
            try:
                a.setEnabled(kind != "off")
                b.setEnabled(kind in ("ramp", "lfo"))
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    try:
        win._schedule_refresh()
    except Exception:  # noqa: BLE001
        pass


def clear_envelopes(win) -> None:
    """Reset to Off (new project / reset settings). Never raises."""
    try:
        win._envelopes = {}
    except Exception:  # noqa: BLE001
        pass
    for param in PARAMS:
        try:
            cmb = getattr(win, f"cmb_env_{param}", None)
            if cmb is not None:
                cmb.blockSignals(True)
                cmb.setCurrentText("Off")
                cmb.blockSignals(False)
        except Exception:  # noqa: BLE001
            pass
    try:
        from app.ui.envelope_controller import sync_envelopes as _sync

        _sync(win)
    except Exception:  # noqa: BLE001
        pass


def build_envelope_section(win, layout) -> None:
    """Three compact rows inside MOTION Details (respects 480px budget)."""
    from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel

    from app.ui.panels.widgets import hlab

    hlab(layout, "Envelopes (session-only):")
    for param in PARAMS:
        lo, hi, dec = LIMITS[param]
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{LABELS[param]}:"))
        cmb = QComboBox()
        cmb.addItems(list(KINDS))
        cmb.setCurrentText("Off")
        cmb.setToolTip("Off=follow preset · Flat=hold value · Ramp=v0→v1 · LFO=sine loop")
        cmb.setFixedWidth(72)
        row.addWidget(cmb)
        setattr(win, f"cmb_env_{param}", cmb)
        for suffix, tip in (("a", "Flat value / Ramp start / LFO base"),
                            ("b", "Ramp end / LFO amount (Flat ignores it)")):
            spn = QDoubleSpinBox()
            spn.setRange(lo, hi)
            spn.setDecimals(dec)
            spn.setSingleStep(0.5 if hi > 10 else 0.1)
            spn.setValue(1.0 if param == "motion_amount" and suffix == "a" else 0.0)
            spn.setFixedWidth(64)
            spn.setToolTip(tip)
            spn.setEnabled(False)
            row.addWidget(spn)
            setattr(win, f"spn_env_{param}_{suffix}", spn)
        row.addStretch()
        layout.addLayout(row)
        cmb.currentTextChanged.connect(lambda _t, _w=win: sync_envelopes(_w))
        for suffix in ("a", "b"):
            spn = getattr(win, f"spn_env_{param}_{suffix}")
            spn.valueChanged.connect(lambda _v, _w=win: sync_envelopes(_w))
    hint = QLabel("Curves over the clip (t=0→1): Ramp sweeps, LFO breathes. Empty = preset.")
    hint.setWordWrap(True)
    hint.setObjectName("subtitleLabel")
    layout.addWidget(hint)


__all__ = ["PARAMS", "build_envelope_section", "read_envelopes",
           "sync_envelopes", "clear_envelopes", "init_envelopes"]
