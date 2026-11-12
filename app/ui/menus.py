"""Main-window menus: File / Edit / View / Help.

Pure assembly: creates actions and wires them to `win.*` methods (which
delegate to controllers). The window keeps `_build_menus()` by delegation.

Layout (one group per block, separated):
- File: open | export/batch | preset share | settings
- Edit: undo/redo/randomize | clipboard | method stepping | transforms
- View: refresh/compare | zoom | Viewport proxy
- Help: tour/samples/manual/logs/shortcuts/about
"""

from __future__ import annotations


def _act(win, menu, label, slot, shortcut="", tip="", action_id=None):
    from PySide6.QtGui import QAction

    a = QAction(label, win)
    if action_id:
        from app import shortcuts as _keys

        keys = _keys.effective_for(win, action_id)
        if keys:
            a.setShortcuts([keys])
        try:
            registry = getattr(win, "_shortcut_actions", None)
            if registry is None:
                registry = win._shortcut_actions = {}
            registry.setdefault(action_id, []).append(a)
        except Exception:  # noqa: BLE001
            pass
    elif shortcut:
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
    _act(win, m_file, "New project", win.new_project,
         "", "Empty project: clear image and reset settings", action_id="file_new")
    _act(win, m_file, "Reset settings (keep image)", win.reset_settings_keep_image,
         "", "Back to defaults, image kept", action_id="file_reset_settings")
    m_file.addSeparator()
    _act(win, m_file, "Open image...", win.open_image_dialog,
         "", "Open an image into the canvas", action_id="file_open")
    m_recent = m_file.addMenu("Open recent")
    m_recent.aboutToShow.connect(lambda: _refresh_recent(win, m_recent))
    m_file.addSeparator()
    _act(win, m_file, "Export…", lambda: win.export(False),
         "", "Export with options at canvas size", action_id="file_export")
    _act(win, m_file, "Quick export", lambda: win.export(True),
         "", "Repeat the last export setup", action_id="file_quick_export")
    _act(win, m_file, "Batch folder...", win.run_batch_dialog,
         "", "Process a folder with the current preset", action_id="file_batch")
    win.act_watch = _act(win, m_file, "Watch folder...", win.toggle_watch,
                         "", "Auto-batch new files with a fixed preset",
                         action_id="file_watch")
    win.act_watch.setCheckable(True)
    m_file.addSeparator()
    _act(win, m_file, "Export preset...", win.share_preset_export,
         "", "Share the current preset as a .json file (offline)",
         action_id="file_share_export")
    _act(win, m_file, "Import preset...", win.share_preset_import,
         "", "Load a preset from a .json file (offline)",
         action_id="file_share_import")
    _act(win, m_file, "Import metadata...", win.import_metadata,
         "", "Restore values + image from an export _metadata.json",
         action_id="file_import_metadata")
    m_file.addSeparator()
    _act(win, m_file, "Settings...", win.open_settings,
         "", "Default output folder, export defaults and behavior",
         action_id="file_settings")

    m_edit = bar.addMenu("Edit")
    _act(win, m_edit, "Undo image", win.undo_image,
         "", "Undo the last image op", action_id="edit_undo")
    _act(win, m_edit, "Redo", win.redo_image,
         "", "Redo the last undone op", action_id="edit_redo")
    _act(win, m_edit, "Surprise me", win.surprise_me,
         "", "Randomize method/palette/params (fresh chaos seed)", action_id="edit_randomize")
    m_edit.addSeparator()
    _act(win, m_edit, "Copy result", win.copy_result,
         "", "Copy the dithered result to the clipboard", action_id="edit_copy")
    _act(win, m_edit, "Paste image", win.paste_image,
         "", "Load an image from the clipboard", action_id="edit_paste")
    m_edit.addSeparator()
    _act(win, m_edit, "Previous method", lambda: win.step_method(-1),
         "", "Step to the previous dither engine", action_id="edit_method_prev")
    _act(win, m_edit, "Next method", lambda: win.step_method(1),
         "", "Step to the next dither engine", action_id="edit_method_next")
    m_edit.addSeparator()
    for label, tip, fn, aid in [
        ("Rotate left", "Rotate left", lambda: win._op_image(rotate_left, "rotate left"), "edit_rotate_left"),
        ("Rotate right", "Rotate right", lambda: win._op_image(rotate_right, "rotate right"), "edit_rotate_right"),
        ("Flip H", "Flip H", lambda: win._op_image(flip_h, "flip H"), "edit_flip_h"),
        ("Flip V", "Flip V", lambda: win._op_image(flip_v, "flip V"), "edit_flip_v"),
        ("Invert", "Invert", lambda: win._op_image(invert, "invert"), "edit_invert"),
    ]:
        _act(win, m_edit, label, fn, "", tip, action_id=aid)

    m_view = bar.addMenu("View")
    _act(win, m_view, "Refresh preview", win.refresh,
         "", "Re-render the preview now", action_id="view_refresh")
    _act_compare(win, m_view)
    m_view.addSeparator()
    _act(win, m_view, "Zoom +", lambda: win._zoom_step(1.25),
         "", "Zoom the preview in", action_id="view_zoom_in")
    _act(win, m_view, "Zoom -", lambda: win._zoom_step(1 / 1.25),
         "", "Zoom the preview out", action_id="view_zoom_out")
    _act(win, m_view, "Fit", win._zoom_fit,
         "", "Fit the preview to the canvas area", action_id="view_zoom_fit")
    _act(win, m_view, "100%", win._zoom_full,
         "", "Preview at 100%", action_id="view_zoom_100")
    m_view.addSeparator()
    _viewport_menu(win, m_view)
    win.act_safe = _act(win, m_view, "Safe areas 9:16", win.toggle_safe_areas,
                        "", "Chrome guides for 9:16 social canvas (crop editor + still preview)")
    win.act_safe.setCheckable(True)
    win.act_safe.setChecked(True)
    win.act_sp404 = _act(win, m_view, "SP-404 OLED preview", win.toggle_sp404_preview,
                         "", "Display-only 128x64 1-bit preview for the Roland SP-404MKII (stills)")
    win.act_sp404.setCheckable(True)
    win.act_sp404.setChecked(False)

    m_help = bar.addMenu("Help")
    _act(win, m_help, "Quick tour...", lambda: win.show_tutorial(manual=True),
         "", "Replay the 5-step tour")
    _act(win, m_help, "Open samples folder", win.open_samples,
         "", "Open the offline sample pack")
    _act(win, m_help, "Keyboard shortcuts...", win.show_shortcuts,
         "", "Every shortcut in one table", action_id="help_shortcuts")
    _act(win, m_help, "User manual...", win.open_manual,
         "", "Open MANUAL.md (bundled offline handbook)", action_id="help_manual")
    _act(win, m_help, "Show logs folder", win.open_logs,
         "", "Reveal prefs, database and trakkart.log")
    _act(win, m_help, "Copy last error report", win.copy_last_error,
         "", "Copy the last logged error (code + details) for bug reports")
    _act(win, m_help, "About TRAKKART...", win.show_about,
         "", "Version, license and offline note")


def _refresh_recent(win, m_recent) -> None:
    """Rebuild Open recent from prefs (missing files skipped)."""
    from pathlib import Path

    from PySide6.QtGui import QAction

    from app.recent import existing_recent

    m_recent.clear()
    items = existing_recent(getattr(win, "_prefs_path", None))
    if not items:
        empty = QAction("(empty)", win)
        empty.setEnabled(False)
        m_recent.addAction(empty)
        return
    for p in items:
        a = QAction(Path(p).name, win)
        a.setToolTip(str(p))
        a.triggered.connect(lambda _=False, _p=Path(p): win._load_path(_p))
        m_recent.addAction(a)


def _act_compare(win, m_view):
    """Checkable 'Show original': same pixels as holding compare, discoverable.

    No shortcut on the action itself: the hold key is handled by
    keyPressEvent (hold semantics) via the shortcuts registry, and a
    shortcut here would double-fire + hijack typing in the editable
    Frames/FPS combos.
    """
    from PySide6.QtGui import QAction

    a = QAction("Show original", win)
    a.setCheckable(True)
    a.setToolTip("Same as holding the compare key: shows ORIGINAL while checked")

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
