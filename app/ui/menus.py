"""Main-window menus: File / Edit / View.

Pure assembly: creates actions and wires them to `win.*` methods (which
delegate to controllers). The window keeps `_build_menus()` by delegation.
"""

from __future__ import annotations


def build_menus(win) -> None:
    from PySide6.QtGui import QAction

    from app.ops import flip_h, flip_v, invert, rotate_left, rotate_right

    bar = win.menuBar()

    m_file = bar.addMenu("File")
    for label, shortcut, slot in [
        ("Open image...", "Ctrl+O", win.open_image_dialog),
        ("Export…", "Ctrl+Shift+S", lambda: win.export(False)),
        ("Quick export", "Ctrl+S", lambda: win.export(True)),
        ("Batch folder...", "Ctrl+B", win.run_batch_dialog),
        ("Export preset...", "", win.share_preset_export),
        ("Import preset...", "", win.share_preset_import),
    ]:
        a = QAction(label, win)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(slot)
        m_file.addAction(a)

    m_edit = bar.addMenu("Edit")
    for label, shortcut, slot in [
        ("Undo image", "Ctrl+Z", win.undo_image),
        ("Random", "Ctrl+R", win.randomize),
        ("Rotate left", "", lambda: win._op_image(rotate_left, "rotate left")),
        ("Rotate right", "", lambda: win._op_image(rotate_right, "rotate right")),
        ("Flip H", "", lambda: win._op_image(flip_h, "flip H")),
        ("Flip V", "", lambda: win._op_image(flip_v, "flip V")),
        ("Invert", "", lambda: win._op_image(invert, "invert")),
    ]:
        a = QAction(label, win)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(slot)
        m_edit.addAction(a)

    m_view = bar.addMenu("View")
    for label, shortcut, slot in [
        ("Zoom +", "Ctrl+=", lambda: win._zoom_step(1.25)),
        ("Zoom -", "Ctrl+-", lambda: win._zoom_step(1 / 1.25)),
        ("Fit", "Ctrl+0", win._zoom_fit),
        ("100%", "Ctrl+1", win._zoom_full),
        ("Copy result", "Ctrl+C", win.copy_result),
        ("Paste image", "Ctrl+V", win.paste_image),
    ]:
        a = QAction(label, win)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(slot)
        m_view.addAction(a)
