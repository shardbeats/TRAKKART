"""Layout regression: the control panel must fit its scroll viewport.

Catches horizontal-clipping bugs (long headers, wide combos, dense rows):
content minimum width must stay within a fixed budget so no control is
cut off with the horizontal scrollbar disabled.
"""

PANEL_BUDGET = 480  # scroll viewport is 452 at 1280px; budget holds font variance


def test_panel_fits_viewport(window):
    window.resize(1280, 780)
    window.show()
    from PySide6.QtWidgets import QScrollArea

    scrolls = window.findChildren(QScrollArea)
    assert len(scrolls) == 1
    sc = scrolls[0]
    inner = sc.widget()
    assert inner is not None
    content_w = inner.minimumSizeHint().width()
    assert content_w <= PANEL_BUDGET, f"panel overflows: {content_w}px"


def test_no_empty_combos(window):
    from PySide6.QtWidgets import QComboBox

    empties = [c for c in window.findChildren(QComboBox) if c.count() == 0]
    assert empties == []


def test_menus_complete(window):
    names = [a.text() for a in window.menuBar().actions()]
    assert names == ["File", "Edit", "View", "Help"]

    def items(menu_name):
        for a in window.menuBar().actions():
            if a.text() == menu_name and a.menu():
                return [x.text() for x in a.menu().actions()]
        return []

    view = items("View")
    assert "Refresh preview" in view
    assert "Viewport" in view and "Theme" not in view
    file_items = items("File")
    assert "Settings..." in file_items
    assert items("Help") == ["Quick tour...", "Open samples folder",
                             "Keyboard shortcuts...", "User manual...",
                             "Show logs folder", "Copy last error report",
                             "About TRAKKART..."]


def test_viewport_actions_synced(window):
    window.set_viewport_mode("still")
    assert window._act_viewport_still.isChecked()
    assert not window._act_viewport_live.isChecked()
