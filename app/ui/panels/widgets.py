"""Shared widget helpers (rows, sliders, wrapped headers, combo caps).

Split out of app/ui/panels.py (mechanical move, no logic change).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def make_group(host: QVBoxLayout, title: str) -> QVBoxLayout:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    lay.setSpacing(4)
    host.addWidget(box)
    return lay


def make_accordion(host: QVBoxLayout):
    """Accordion pages in the single panel scroll (no nested QScrollArea).

    Returns `(add_page, pages)`: `add_page(title)` appends a collapsible
    page and returns its layout; opening one page closes the others.
    The first page starts open.
    """
    from PySide6.QtWidgets import QPushButton

    holders: list = []

    def add_page(title: str) -> QVBoxLayout:
        btn = QPushButton(title)
        btn.setCheckable(True)
        host.addWidget(btn)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(4)
        lay.setContentsMargins(2, 2, 2, 2)
        host.addWidget(content)

        def _on_toggle(on: bool, _content=content) -> None:
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
    """Section header that wraps instead of forcing panel width."""
    lab = QLabel(text)
    lab.setWordWrap(True)
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


def labeled_slider(win, parent, label, lo, hi, val, tooltip="", div=None):
    """Fila [label | slider | valor]. Doble-click resetea (ValueSlider)."""
    row = QHBoxLayout()
    lab = QLabel(label)
    lab.setMinimumWidth(120)
    row.addWidget(lab)
    sld, val_lbl = mini_slider(win, lo, hi, val, tooltip, div)
    row.addWidget(sld, 1)
    row.addWidget(val_lbl)
    parent.addLayout(row)
    return sld, val_lbl


def mini_slider(win, lo, hi, val, tooltip="", div=None):
    from app.ui.widgets import ValueSlider

    sld = ValueSlider(Qt.Horizontal)
    sld.setRange(lo, hi)
    sld.setValue(val)
    sld.setDefault(val)
    if tooltip:
        sld.setToolTip(tooltip)
    val_lbl = QLabel()
    val_lbl.setObjectName("valueLabel")
    val_lbl.setMinimumWidth(40)
    val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def _show(v, _lbl=val_lbl, _div=div):
        _lbl.setText(f"{(v / _div if _div else v):g}")

    sld.valueChanged.connect(_show)
    sld.valueChanged.connect(lambda _: win._schedule_refresh())
    _show(val)
    return sld, val_lbl


def spin_row(parent, label: str, lo: int, hi: int, val: int, tooltip: str = "") -> QSpinBox:
    spn = QSpinBox()
    spn.setRange(lo, hi)
    spn.setValue(val)
    if tooltip:
        spn.setToolTip(tooltip)
    spn.setFixedWidth(56)
    row = QHBoxLayout()
    row.addWidget(QLabel(label))
    row.addWidget(spn, 1)
    parent.addLayout(row)
    return spn
