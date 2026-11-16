"""UI polish pins: readability of values, navigation and export grouping.

These are not pixel tests. They pin the decisions that make the panel
self-explanatory: normalized values never render as a bare "1", pages
read as navigation, the link is a drawn icon (no emoji font), and the
Export window keeps its groups/scroll contract.
"""

from __future__ import annotations


def test_normalized_values_keep_a_decimal():
    from app.ui.panels.widgets import value_text

    assert value_text(100, 100.0, "×") == "1.0×"
    assert value_text(125, 100.0) == "1.25"
    assert value_text(50, None, "%") == "50%"
    assert value_text(0, 10.0) == "0.0"
    assert value_text(3, 1.0) == "3"
    assert value_text(-40) == "-40"


def test_accordion_reads_as_navigation(window):
    pages = window._accordion_pages
    assert pages[0][0].text().startswith("▾")
    assert all(btn.text().startswith("▸") for btn, _ in pages[1:])
    pages[1][0].setChecked(True)
    assert pages[1][0].text().startswith("▾")
    assert pages[0][0].text().startswith("▸")
    assert pages[0][1].isHidden()


def test_canvas_link_uses_drawn_icon(window):
    assert not window.btn_canvas_link.icon().isNull()
    assert "__CHECK__" not in window.styleSheet()


def test_export_groups_and_scroll(window, tmp_path):
    from PySide6.QtWidgets import QLabel

    from app.ui.export_dialog import ExportDialog

    dlg = ExportDialog(window.src, {"ratio": "1:1"}, base="d", out_dir=str(tmp_path))
    try:
        assert dlg._scroll.widgetResizable() is True
        heads = [lbl.text() for lbl in dlg.findChildren(QLabel)
                 if lbl.objectName() == "sectionLabel"]
        for head in ("Stills:", "Motion:", "Print & device:", "Files to write:"):
            assert head in heads, head
    finally:
        dlg.close()
