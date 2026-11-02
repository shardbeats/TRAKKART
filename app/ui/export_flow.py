"""Export flow: dialog orchestration + full-res render + bundle + history.

Classic behavior: Quick export reuses the last config; the first run (no prefs)
always opens the dialog. State and widgets stay on MainWindow; this module
holds the behavior. The window keeps `export()` / `_run_export()` /
`_estimate_vector_cells()` by delegation.
"""

from __future__ import annotations


def _gif_opts_from_prefs(prefs) -> dict:
    return {"frames": prefs.gif_frames, "mode": prefs.gif_mode,
            "fps": getattr(prefs, "gif_fps", 8),
            "size": getattr(prefs, "gif_size", 1200),
            "pingpong": getattr(prefs, "gif_pingpong", False),
            "mp4_size": getattr(prefs, "mp4_size", "1080p")}


def _gif_opts_from_preset(preset) -> dict:
    return {"frames": int(preset.gif_frames), "mode": preset.gif_mode,
            "fps": int(getattr(preset, "gif_fps", 8)),
            "size": int(getattr(preset, "gif_size", 1200)),
            "pingpong": bool(getattr(preset, "gif_pingpong", False)),
            "mp4_size": "1080p"}


def export(win, quick: bool = False) -> None:
    """Export bundle. Pro dialog by default; `quick` repeats the last one."""
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from app.export_prefs import ExportPrefs, load_prefs, save_prefs
    from app.exporter import ExportSelection
    from app.ui.export_dialog import ExportDialog

    if win.src is None:
        QMessageBox.information(win, "TRAKKART", "Open an image first.")
        return
    try:
        preset = win.current_params()
        prefs = load_prefs(win._prefs_path)
        recent_files = list(getattr(prefs, "recent_files", []) or [])
        # Stale-name guard: prefs belong to the image they were saved for.
        # New image (or untracked old prefs) -> fresh defaults, never the
        # previous name. Quick with a new image falls through to the dialog
        # on purpose: silent writes must not reuse a stale base.
        prefs_match = (not getattr(prefs, "src_name", "")) or prefs.src_name == win.src_name
        if quick and prefs.out_dir and prefs_match:
            selection = prefs.to_selection()
            win._run_export(
                base=prefs.base or win.src_name, out_dir=Path(prefs.out_dir),
                selection=selection,
                gif_opts=_gif_opts_from_prefs(prefs),
                overwrite="rename",  # never lose a file (old prefs may say otherwise)
                size=prefs.size, format=prefs.format, quality=prefs.quality,
            )
            return
        if prefs.out_dir and prefs_match:
            init_sel = prefs.to_selection()
            init_base, init_out = prefs.base, prefs.out_dir
            init_size, init_fmt, init_q = prefs.size, prefs.format, prefs.quality
        else:
            init_sel = ExportSelection(vector=bool(preset.vector_export),
                                       anim=bool(preset.gif_export))
            init_base, init_out = win.src_name, str(win.out_dir)
            init_size, init_fmt, init_q = (int(preset.export_size),
                                           str(preset.export_format), int(preset.export_quality))
        # Animation spec ALWAYS comes from the live VIDEO section (preset),
        # never from stale prefs: the dialog itself says "Edit it in VIDEO".
        # Prefs only persist destination/name/size/format + the MP4 size.
        init_gopts = _gif_opts_from_preset(preset)
        if prefs.out_dir and prefs_match:
            init_gopts["mp4_size"] = getattr(prefs, "mp4_size", "1080p")
        if getattr(win, "_video_on", False):
            # VIDEO preview is ON: the user is watching motion, so the dialog
            # pre-checks Animation GIF (still uncheckable, ~MB plan visible).
            # Quick export above is untouched on purpose: silent big writes, no.
            from dataclasses import replace

            init_sel = replace(init_sel, anim=True)
        dlg = ExportDialog(
            win.src, preset.meta(), base=init_base, out_dir=init_out,
            selection=init_sel,
            gif_frames=int(init_gopts["frames"]), gif_mode=str(init_gopts["mode"]),
            gif_fps=int(init_gopts["fps"]),
            gif_pingpong=bool(init_gopts["pingpong"]),
            vector_cells=win._estimate_vector_cells(preset),
            preset=preset, size=init_size, format=init_fmt, quality=init_q,
            mp4_size=str(init_gopts.get("mp4_size", "1080p")),
            parent=win,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            dlg.deleteLater()  # no hoard hidden dialogs (they linger in topLevelWidgets)
            win._status("Export cancelled")
            return
        options, out_dir, gopts = dlg.options()
        dlg.deleteLater()
        choice = resolve_collision(win, out_dir, options,
                                   want_mp4=bool(gopts.get("mp4", False)),
                                   want_webp=bool(gopts.get("webp", False)),
                                   want_sep=bool(gopts.get("sep", False)))
        if choice is None:
            win._status("Export cancelled")
            return
        win._run_export(
            base=options.base, out_dir=out_dir, selection=options.selection,
            gif_opts=gopts, overwrite=choice,
            size=options.size, format=options.format, quality=options.quality,
            mp4=bool(gopts.get("mp4", False)),
            mp4_size=str(gopts.get("mp4_size", "1080p")),
            webp=bool(gopts.get("webp", False)),
            sep=bool(gopts.get("sep", False)),
        )
        save_prefs(ExportPrefs(
            out_dir=str(out_dir), base=options.base,
            image=options.selection.image,
            thumb_1080p=options.selection.thumb_1080p,
            vector=options.selection.vector, anim=options.selection.anim,
            metadata=options.selection.metadata,
            gif_frames=int(gopts["frames"]), gif_mode=str(gopts["mode"]),
            gif_fps=int(gopts["fps"]), gif_size=int(gopts["size"]),
            gif_pingpong=bool(gopts["pingpong"]),
            mp4_size=str(gopts.get("mp4_size", "1080p")),
            overwrite="rename",  # per-run choice is not persisted (quick is always safe)
            size=options.size, format=options.format, quality=options.quality,
            recent_files=recent_files, src_name=win.src_name,
        ), win._prefs_path)
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Export error: {e}")


def resolve_collision(win, out_dir, options, want_mp4: bool = False,
                      want_webp: bool = False, want_sep: bool = False) -> str | None:
    """Post-accept collision check: "overwrite" | "rename" | None (cancel).

    No collision -> "rename" without asking (rename of a free base is a
    no-op). With collision -> modal listing files, safe default = Rename.
    Module-level so tests can stub it like show_exported.
    """
    from pathlib import Path

    from app.exporter import _unique_base, bundle_filenames, mp4_name, webp_name

    out_dir = Path(out_dir)
    sel = options.selection
    names = bundle_filenames(options, has_vector=bool(sel.vector), has_gif=bool(sel.anim))
    if want_mp4:
        names["video"] = mp4_name(options.base)
    if want_webp:
        names["webp"] = webp_name(options.base)
    if want_sep:
        # Plate hexes need the render; glob the family's exact files.
        try:
            for i, p in enumerate(sorted(out_dir.glob(f"{options.base}_sep_*.png"))):
                names[f"sep{i}"] = p.name
        except OSError:
            pass
    try:
        existing = [f for f in names.values() if (out_dir / f).exists()]
    except OSError:
        return "rename"
    if not existing:
        return "rename"
    new_base = _unique_base(out_dir, options.base, list(names.values()))
    listed = "\n".join(f"- {f}" for f in existing[:8])
    if len(existing) > 8:
        listed += f"\n- …and {len(existing) - 8} more"
    from PySide6.QtWidgets import QMessageBox

    msg = QMessageBox(QMessageBox.Icon.Warning, "Name exists",
                      f"These files already exist:\n{listed}\n\n"
                      f"Overwrite them, or save as {new_base}?",
                      QMessageBox.StandardButton.Cancel, win)
    b_over = msg.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
    b_rename = msg.addButton(f"Rename as {new_base}", QMessageBox.ButtonRole.ActionRole)
    msg.setDefaultButton(b_rename)
    msg.exec()
    clicked = msg.clickedButton()
    if clicked is b_over:
        return "overwrite"
    if clicked is b_rename:
        return "rename"
    return None


def show_exported(win, out_dir, names: list[str]) -> None:
    """Exported dialog with a 'Show in folder' action (module-level for tests).

    Tests stub this (like QMessageBox.information) so no modal ever blocks CI.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox

    msg = QMessageBox(QMessageBox.Icon.Information, "TRAKKART",
                      "Exported:\n" + "\n".join(names),
                      QMessageBox.StandardButton.Close, win)
    show_btn = msg.addButton("Show in folder", QMessageBox.ButtonRole.ActionRole)
    msg.exec()
    if msg.clickedButton() is show_btn:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))


def estimate_vector_cells(win, preset) -> tuple[int, int] | None:
    """Estimated SVG cells for the dialog plan (cheap, no dither)."""
    if win.src is None:
        return None
    try:
        from app.canvas import to_canvas
        from app.vector import estimate_cells

        canvas = to_canvas(
            win.src, ratio=preset.ratio, mode=preset.crop_mode,
            fx=float(preset.focus_x), fy=float(preset.focus_y),
            zoom=float(preset.crop_zoom),
            canvas_w=int(getattr(preset, "canvas_w", 0) or 0),
            canvas_h=int(getattr(preset, "canvas_h", 0) or 0),
        )
        return estimate_cells(canvas.width, canvas.height, int(preset.vector_cell))
    except Exception:  # noqa: BLE001
        return None


def _morph_imgs(win) -> list | None:
    """Chain entries (with per-image crop) for morph export (None = dissolve)."""
    try:
        from app.ui import params_controller as _par

        chain = _par.morph_chain_data(win)
        if chain:
            return chain
        single = getattr(win, "morph_src", None)
        return [single] if single is not None else None
    except Exception:  # noqa: BLE001
        return None


def morph_src_for_mode(win, mode: str) -> list | None:
    """Session chain only feeds particle modes; anything else ignores it.

    Without this gate a stale MORPH playlist leaks into mix/phase/hue
    exports (the engine ignores img_b there today, but the export must
    not depend on that coincidence).
    """
    if str(mode) not in ("dissolve", "morph"):
        return None
    return _morph_imgs(win)


def run_export(win, base: str, out_dir, selection, gif_opts: dict,
               overwrite: str, size: int, format: str,
               quality: int, mp4: bool = False,
               mp4_size: str = "1080p", webp: bool = False,
               sep: bool = False) -> None:
    """Render full-res + bundle (+MP4/WebP/seps) per options. Stills always full-res;
    MP4 uses its own size (Canvas/1080p/720p) so 3000px docs don't ship GBs;
    WebP reuses the GIF frames at ~1/3 the weight; seps write one PNG per ink."""
    from dataclasses import replace
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from app.services.export_service import export_full
    from app.video_io import VideoBackendMissing

    preset = win.current_params()
    if bool(getattr(selection, "black_vector", False)):
        preset = replace(preset, vector_black=True)
    go = dict(gif_opts) if isinstance(gif_opts, dict) else {"frames": gif_opts}
    mode_go = str(go.get("mode", "both"))
    try:
        paths, skipped = export_full(
            win.src, preset, out_dir, base=base, store=win.store,
            preset_name=win.cmb_preset.currentText(), selection=selection,
            overwrite=overwrite,
            gif_frames=int(go.get("frames", 6)), gif_mode=mode_go,
            gif_fps=int(go.get("fps", 8)), gif_size=int(go.get("size", 1200)),
            gif_pingpong=bool(go.get("pingpong", False)),
            size=int(size), format=str(format), quality=int(quality),
            mp4=bool(mp4),
            mp4_fps=int(go.get("fps", 8)),
            mp4_size=str(go.get("mp4_size", mp4_size)),
            webp=bool(webp),
            sep=bool(sep),
            morph_src=morph_src_for_mode(win, mode_go),
        )
    except VideoBackendMissing as e:
        QMessageBox.warning(win, "TRAKKART", str(e))
        win._status("MP4 needs the video extra (still exports skipped)")
        return
    if skipped and not paths:
        QMessageBox.information(
            win, "TRAKKART",
            f"Skipped: {base} already exists (policy: skip).")
        win._status(f"Export skipped (exists): {base}")
        return
    show_exported(win, Path(out_dir).resolve(), [p.name for p in paths.values()])
    win._status(f"Exported to {Path(out_dir).resolve()}")
