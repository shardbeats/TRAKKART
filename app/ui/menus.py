"""Main-window menus: File / Edit / View / Help.

Pure assembly: creates actions and wires them to `win.*` methods (which
delegate to controllers). The window keeps `_build_menus()` by delegation.

Layout (one group per block, separated):
- File: open | export/batch | preset share
- Edit: undo/randomize | clipboard | method stepping | transforms
- View: refresh/compare | zoom | Viewport proxy | Theme
- Help: tour/samples (unchanged)
"""

from __future__ import annotations


def _act(win, menu, label, slot, shortcut="", tip=""):
    from PySide6.QtGui import QAction

    a = QAction(label, win)
    if shortcut:
        a.setShortcut(shortcut)
    if tip:
        a.setToolTip(tip)
    a.triggered.connect(slot)
    menu.addAction(a)
    return a


def build_menus(win) -> None:
    from app.ops import flip_h, flip_v, invert, rotate_left, rotate_right

    bar = win.menuBar()

    m_file = bar.addMenu("File")
    _act(win, m_file, "Open image...", win.open_image_dialog,
         "Ctrl+O", "Open an image into the canvas")
    m_file.addSeparator()
    _act(win, m_file, "Export…", lambda: win.export(False),
         "Ctrl+Shift+S", "Export with options at canvas size")
    _act(win, m_file, "Quick export", lambda: win.export(True),
         "Ctrl+S", "Repeat the last export setup")
    _act(win, m_file, "Batch folder...", win.run_batch_dialog,
         "Ctrl+B", "Process a folder with the current preset")
    m_file.addSeparator()
    _act(win, m_file, "Export preset...", win.share_preset_export,
         "", "Share the current preset as a .json file (offline)")
    _act(win, m_file, "Import preset...", win.share_preset_import,
         "", "Load a preset from a .json file (offline)")

    m_edit = bar.addMenu("Edit")
    _act(win, m_edit, "Undo image", win.undo_image,
         "Ctrl+Z", "Undo the last image op")
    _act(win, m_edit, "Surprise me", win.randomize,
         "Ctrl+R", "Randomize method/palette/params")
    m_edit.addSeparator()
    _act(win, m_edit, "Copy result", win.copy_result,
         "Ctrl+C", "Copy the dithered result to the clipboard")
    _act(win, m_edit, "Paste image", win.paste_image,
         "Ctrl+V", "Load an image from the clipboard")
    m_edit.addSeparator()
    _act(win, m_edit, "Previous method", lambda: win.step_method(-1),
         "", "Step to the previous dither engine (Alt+Left)")
    _act(win, m_edit, "Next method", lambda: win.step_method(1),
         "", "Step to the next dither engine (Alt+Right)")
    m_edit.addSeparator()
    for label, tip, fn in [
        ("Rotate left", "Rotate left", lambda: win._op_image(rotate_left, "rotate left")),
        ("Rotate right", "Rotate right", lambda: win._op_image(rotate_right, "rotate right")),
        ("Flip H", "Flip H", lambda: win._op_image(flip_h, "flip H")),
        ("Flip V", "Flip V", lambda: win._op_image(flip_v, "flip V")),
        ("Invert", "Invert", lambda: win._op_image(invert, "invert")),
    ]:
        _act(win, m_edit, label, fn, "", tip)

    m_view = bar.addMenu("View")
    _act(win, m_view, "Refresh preview", win.refresh,
         "F5", "Re-render the preview now")
    _act_compare(win, m_view)
    m_view.addSeparator()
    _act(win, m_view, "Zoom +", lambda: win._zoom_step(1.25),
         "Ctrl+=", "Zoom the preview in")
    _act(win, m_view, "Zoom -", lambda: win._zoom_step(1 / 1.25),
         "Ctrl+-", "Zoom the preview out")
    _act(win, m_view, "Fit", win._zoom_fit,
         "Ctrl+0", "Fit the preview to the canvas area")
    _act(win, m_view, "100%", win._zoom_full,
         "Ctrl+1", "Preview at 100%")
    m_view.addSeparator()
    _viewport_menu(win, m_view)
    _theme_menu(win, m_view)

    m_help = bar.addMenu("Help")
    _act(win, m_help, "Quick tour...", lambda: win.show_tutorial(manual=True),
         "", "Replay the 5-step tour")
    _act(win, m_help, "Open samples folder", win.open_samples,
         "", "Open the offline sample pack")


def _act_compare(win, m_view):
    """Checkable 'Show original': same pixels as holding Space, discoverable.

    No Space shortcut on purpose: Space is already handled by
    `keyPressEvent` (hold semantics), and a shortcut here would double-fire
    and hijack typing in the editable Frames/FPS combos.
    """
    from PySide6.QtGui import QAction

    a = QAction("Show original", win)
    a.setCheckable(True)
    a.setToolTip("Same as holding Space: shows ORIGINAL while checked")

    def _on_toggle(on: bool) -> None:
        if on:
            if win.src is None:
                a.setChecked(False)
                win._status("Open an image first")
                return
            win._compare_pressed()
        else:
            win._compare_released()

    a.toggled.connect(_on_toggle)
    m_view.addAction(a)
    win._act_compare = a


def _viewport_menu(win, m_view) -> None:
    from PySide6.QtGui import QAction

    from app.viewport import MODES, mode_label

    m_viewport = m_view.addMenu("Viewport")
    for mode in MODES:
        a = QAction(f"{mode_label(mode)} (auto)" if mode == "live" else mode_label(mode), win)
        a.setCheckable(True)
        a.setChecked(win.viewport_mode == mode)
        a.triggered.connect(lambda _=False, _m=mode: win.set_viewport_mode(_m))
        setattr(win, f"_act_viewport_{mode}", a)
        m_viewport.addAction(a)


def _theme_menu(win, m_view) -> None:
    from PySide6.QtGui import QAction

    from app.ui.theme import theme_label, theme_names

    m_themes = m_view.addMenu("Theme")
    for name in theme_names():
        a = QAction(theme_label(name), win)
        a.setCheckable(True)
        a.setChecked(win.app_theme == name)
        a.triggered.connect(lambda _=False, _n=name: win.set_theme(_n))
        setattr(win, f"_act_theme_{name}", a)
        m_themes.addAction(a)
