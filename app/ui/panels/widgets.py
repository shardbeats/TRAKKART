"""Shared widget helpers (rows, sliders, wrapped headers, combo caps).

Split out of app/ui/panels.py (mechanical move, no logic change).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def make_group(host: QVBoxLayout, title: str) -> QVBoxLayout:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    lay.setSpacing(8)
    host.addWidget(box)
    return lay


def make_accordion(host: QVBoxLayout):
    """Accordion pages in the single panel scroll (no nested QScrollArea).

    Returns `(add_page, pages)`: `add_page(title)` appends a collapsible
    page and returns its layout; opening one page closes the others.
    The first page starts open. The header reads as navigation (left
    chevron + accent when open), not as a generic action button.
    """
    holders: list = []

    def add_page(title: str) -> QVBoxLayout:
        btn = QPushButton(f"▸ {title}")
        btn.setObjectName("accordion")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        host.addWidget(btn)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(8)
        lay.setContentsMargins(4, 4, 4, 4)
        host.addWidget(content)

        def _on_toggle(on: bool, _content=content, _btn=btn, _title=title) -> None:
            _btn.setText(f"{'▾' if on else '▸'} {_title}")
            if on:
                for _b, _c in holders:
                    if _c is not _content:
                        _b.setChecked(False)
                _content.setVisible(True)
            else:
                _content.setVisible(False)

        btn.toggled.connect(_on_toggle)
        holders.append((btn, content))
        if len(holders) == 1:
            btn.setChecked(True)
        else:
            content.setVisible(False)
        return lay

    return add_page, holders


def hlab(parent, text: str) -> QLabel:
    """Section header: quieter than the page button, wraps inside the panel."""
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setObjectName("sectionLabel")
    parent.addWidget(lab)
    return lab


def tight(cmb, chars: int = 12):
    """Cap combo min-width so long items don't blow the panel (tooltips stay full)."""
    try:
        cmb.setSizeAdjustPolicy(cmb.AdjustToMinimumContentsLengthWithIcon)
        cmb.setMinimumContentsLength(max(4, int(chars)))
    except Exception:  # noqa: BLE001
        pass
    return cmb


def labeled_slider(win, parent, label, lo, hi, val, tooltip="", div=None, unit=""):
    """Row [label | slider | value]. Double-click resets (ValueSlider).

    `div` keeps the legacy normalized storage (100 = 1.0). The readout
    keeps one decimal when normalized, so "1" no longer hides a 1.0×
    multiplier: 100 -> "1.0×", 125 -> "1.25×".
    """
    row = QHBoxLayout()
    lab = QLabel(label)
    lab.setMinimumWidth(120)
    row.addWidget(lab)
    sld, val_lbl = mini_slider(win, lo, hi, val, tooltip, div, unit, label=label)
    lab.setBuddy(sld)
    row.addWidget(sld, 1)
    row.addWidget(val_lbl)
    parent.addLayout(row)
    return sld, val_lbl


def value_text(v, div=None, unit: str = "") -> str:
    """Human readout for a normalized slider value."""
    if div and div != 1:
        text = f"{v / div:.2f}".rstrip("0").rstrip(".")
        if "." not in text:
            text += ".0"
    else:
        text = f"{v:g}"
    return f"{text}{unit}"


def mini_slider(win, lo, hi, val, tooltip="", div=None, unit="", label="Value"):
    from app.ui.widgets import ValueSlider

    sld = ValueSlider(Qt.Horizontal)
    sld.setRange(lo, hi)
    sld.setValue(val)
    sld.setDefault(val)
    sld.setAccessibleName(label)
    if tooltip:
        sld.setToolTip(tooltip)
        sld.setAccessibleDescription(tooltip)
    val_lbl = QLabel()
    val_lbl.setObjectName("valueLabel")
    val_lbl.setMinimumWidth(46)
    val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    val_lbl.setAccessibleName(f"{label} value")
    val_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def _show(v, _lbl=val_lbl, _div=div, _unit=unit):
        _lbl.setText(value_text(v, _div, _unit))

    sld.valueChanged.connect(_show)
    sld.valueChanged.connect(lambda _: win._schedule_refresh())
    _show(val)
    return sld, val_lbl


def spin_row(parent, label: str, lo: int, hi: int, val: int, tooltip: str = "") -> QSpinBox:
    spn = QSpinBox()
    spn.setRange(lo, hi)
    spn.setValue(val)
    spn.setAccessibleName(label)
    if tooltip:
        spn.setToolTip(tooltip)
        spn.setAccessibleDescription(tooltip)
    spn.setFixedWidth(56)
    lab = QLabel(label)
    lab.setBuddy(spn)
    row = QHBoxLayout()
    row.addWidget(lab)
    row.addWidget(spn)
    row.addStretch()
    parent.addLayout(row)
    return spn


def seed_row(parent, win, spin_attr: str, dice_attr: str, label_text: str,
             value: int, tooltip: str = "", dice_tip: str = "",
             on_roll=None) -> tuple:
    """One seed per row: [96px label | 80px spin | Roll | stretch].

    Shared geometry so seed rows never overflow the 360-460px panel
    (the scroll has no horizontal bar: wide rows get hard-clipped).
    Sets `win.<spin_attr>` / `win.<dice_attr>` and wires valueChanged
    to the live refresh, like every other seed control.
    """
    row = QHBoxLayout()
    lab = QLabel(label_text)
    lab.setFixedWidth(88)
    row.addWidget(lab)
    spn = QSpinBox()
    spn.setRange(0, 999999)
    spn.setValue(int(value))
    spn.setFixedWidth(72)
    spn.setAccessibleName(label_text)
    if tooltip:
        spn.setToolTip(tooltip)
        spn.setAccessibleDescription(tooltip)
    lab.setBuddy(spn)
    spn.valueChanged.connect(lambda _: win._schedule_refresh())
    row.addWidget(spn)
    dice = QPushButton("Roll")
    dice.setObjectName("opBtn")
    dice.setFixedWidth(56)
    dice.setAccessibleName(f"{label_text} random roll")
    if dice_tip:
        dice.setToolTip(dice_tip)
        dice.setAccessibleDescription(dice_tip)
    if on_roll is not None:
        dice.clicked.connect(on_roll)
    row.addWidget(dice)
    row.addStretch()
    parent.addLayout(row)
    setattr(win, spin_attr, spn)
    setattr(win, dice_attr, dice)
    return spn, dice


def roll_seed(win, spin_attr: str, label: str, after=None) -> int:
    """One dice behavior for every seed control: fresh 0-999999 + status.

    `after` runs once the spin is set (palette rolls then regenerate).
    """
    import random

    seed = random.randint(0, 999999)
    try:
        getattr(win, spin_attr).setValue(seed)
    except Exception:  # noqa: BLE001
        pass
    try:
        win._status(f"{label} re-rolled (seed {seed})")
    except Exception:  # noqa: BLE001
        pass
    if after is not None:
        try:
            after()
        except Exception:  # noqa: BLE001
            pass
    return seed
