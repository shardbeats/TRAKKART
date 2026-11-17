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
            "mp4_size": getattr(prefs, "mp4_size", "1080p"),
            "mp4": getattr(prefs, "mp4", False),
            "webp": getattr(prefs, "webp", False),
            "tiff": getattr(prefs, "tiff", False),
            "social": getattr(prefs, "social", False),
            "sep": getattr(prefs, "sep", False),
            "sep_trap": getattr(prefs, "sep_trap", False),
            "sp404": getattr(prefs, "sp404", False)}


def _gif_opts_from_preset(preset) -> dict:
    return {"frames": int(preset.gif_frames), "mode": preset.gif_mode,
            "fps": int(getattr(preset, "gif_fps", 8)),
            "size": int(getattr(preset, "gif_size", 1200)),
            "pingpong": bool(getattr(preset, "gif_pingpong", False)),
            "mp4_size": "1080p",
            "mp4": False, "webp": False, "tiff": False, "social": False,
            "sep": False, "sep_trap": False, "sp404": False}


def _clip_info_for_dialog(win) -> dict | None:
    """Session-clip summary for the Export window (None when no clip)."""
    from app.clip import clip_duration
    from app.ui import clip_controller as _cc

    if not _cc.has_clip(win):
        return None
    try:
        info = dict(getattr(win, "_clip_info", {}) or {})
        n = len(getattr(win, "_clip_frames", []) or [])
        s = max(0, min(n - 1, int(win._clip_start)))
        e = max(0, min(n - 1, int(win._clip_end)))
        fps = _cc.clip_fps(win)
        span = max(0, e - s + 1)
        name = __import__("pathlib").Path(str(info.get("path", "clip"))).stem
        return {"name": name, "frames": n, "fps": fps, "start": s, "end": e,
                "span": span, "duration": clip_duration(span, fps),
                "start_s": float(info.get("start_s", 0.0) or 0.0),
                "truncated": bool(info.get("truncated", False)),
                "path": str(info.get("path", "") or ""),
                "size": list(info.get("size", [0, 0]) or [0, 0])}
    except Exception:  # noqa: BLE001
        return None


def export(win, quick: bool = False) -> None:
    """Export bundle. Pro dialog by default; `quick` repeats the last one."""
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from app.export_prefs import ExportPrefs, load_prefs, save_prefs
    from app.exporter import ExportSelection
    from app.ui.export_dialog import ExportDialog

    clip_info = _clip_info_for_dialog(win)
    if win.src is None and clip_info is None:
        QMessageBox.information(win, "TRAKKART", "Open an image first.")
        return
    try:
        preset = win.current_params()
        prefs = load_prefs(win._prefs_path)
        recent_files = list(getattr(prefs, "recent_files", []) or [])
        if win.src is None:
            # Clip-only export (no still open): fresh dialog, no prefs,
            # no quick path (quick repeats still bundles only).
            prefs_match = False
        else:
            # Stale-name guard: prefs belong to the image they were saved for.
            # New image (or untracked old prefs) -> fresh defaults, never the
            # previous name. Quick with a new image falls through to the dialog
            # on purpose: silent writes must not reuse a stale base.
            prefs_match = ((not getattr(prefs, "src_name", ""))
                           or prefs.src_name == win.src_name)
        if quick and prefs.out_dir and prefs_match:
            selection = prefs.to_selection()
            gopts_prefs = _gif_opts_from_prefs(prefs)
            win._run_export(
                base=prefs.base or win.src_name, out_dir=Path(prefs.out_dir),
                selection=selection,
                gif_opts=gopts_prefs,
                overwrite="rename",  # never lose a file (old prefs may say otherwise)
                size=prefs.size, format=prefs.format, quality=prefs.quality,
                mp4=bool(gopts_prefs.get("mp4", False)),
                mp4_size=str(gopts_prefs.get("mp4_size", "1080p")),
                webp=bool(gopts_prefs.get("webp", False)),
                tiff=bool(gopts_prefs.get("tiff", False)),
                social=bool(gopts_prefs.get("social", False)),
                dpi=int(getattr(prefs, "dpi", 300) or 300),
                sep=bool(gopts_prefs.get("sep", False)),
                sep_trap=bool(gopts_prefs.get("sep_trap", False)),
                sp404=bool(gopts_prefs.get("sp404", False)),
            )
            return
        if prefs.out_dir and prefs_match:
            init_sel = prefs.to_selection()
            init_base, init_out = prefs.base, prefs.out_dir
            init_size, init_fmt, init_q = prefs.size, prefs.format, prefs.quality
            init_dpi = int(getattr(prefs, "dpi", 300) or 300)
        else:
            init_sel = ExportSelection(vector=bool(preset.vector_export),
                                       anim=bool(preset.gif_export))
            if win.src is None:
                init_base, init_out = str(clip_info.get("name", "clip")), str(win.out_dir)
            else:
                init_base, init_out = win.src_name, str(win.out_dir)
            init_dpi = 300
            init_size, init_fmt, init_q = (int(preset.export_size),
                                           str(preset.export_format), int(preset.export_quality))
        # Animation spec ALWAYS comes from the live VIDEO section (preset),
        # never from stale prefs: the dialog itself says "Edit it in MOTION".
        # Prefs only persist destination/name/size/format/quality/DPI + MP4 size.
        init_gopts = _gif_opts_from_preset(preset)
        if prefs.out_dir and prefs_match:
            init_gopts["mp4_size"] = getattr(prefs, "mp4_size", "1080p")
            for key in ("mp4", "webp", "tiff", "social", "sep", "sep_trap", "sp404"):
                init_gopts[key] = bool(getattr(prefs, key, False))
        if getattr(win, "_video_on", False):
            # VIDEO preview is ON: the user is watching motion, so the dialog
            # pre-checks Animation GIF (still uncheckable, ~MB plan visible).
            # Quick export above is untouched on purpose: silent big writes, no.
            from dataclasses import replace

            init_sel = replace(init_sel, anim=True)
        dlg = ExportDialog(
            win.src, preset.meta() if win.src is not None else {},
            base=init_base, out_dir=init_out,
            selection=init_sel,
            gif_frames=int(init_gopts["frames"]), gif_mode=str(init_gopts["mode"]),
            gif_fps=int(init_gopts["fps"]),
            gif_pingpong=bool(init_gopts["pingpong"]),
            vector_cells=win._estimate_vector_cells(preset),
            preset=preset, size=init_size, format=init_fmt, quality=init_q,
            mp4_size=str(init_gopts.get("mp4_size", "1080p")),
            mp4=bool(init_gopts.get("mp4", False)),
            webp=bool(init_gopts.get("webp", False)),
            tiff=bool(init_gopts.get("tiff", False)),
            social=bool(init_gopts.get("social", False)),
            dpi=int(init_dpi),
            sep=bool(init_gopts.get("sep", False)),
            sep_trap=bool(init_gopts.get("sep_trap", False)),
            sp404=bool(init_gopts.get("sp404", False)),
            clip_info=clip_info,
            clip_fps=int(clip_info["fps"]) if clip_info else None,
            clip_track=str(getattr(win, "_clip_audio", "") or ""),
            still_enabled=win.src is not None,
            parent=win,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            dlg.deleteLater()  # no hoard hidden dialogs (they linger in topLevelWidgets)
            win._status("Export cancelled")
            return
        options, out_dir, gopts = dlg.options()
        clip = dlg.clip_options()
        if clip and clip.get("track"):
            win._clip_audio = str(clip["track"])  # session persists
        dlg.deleteLater()
        choice = resolve_collision(win, out_dir, options,
                                   want_mp4=bool(gopts.get("mp4", False)),
                                   want_webp=bool(gopts.get("webp", False)),
                                   want_tiff=bool(gopts.get("tiff", False)),
                                   want_social=bool(gopts.get("social", False)),
                                   want_sep=bool(gopts.get("sep", False)),
                                   want_clip=clip)
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
            tiff=bool(gopts.get("tiff", False)),
            social=bool(gopts.get("social", False)),
            dpi=int(options.dpi),
            sep=bool(gopts.get("sep", False)),
            sep_trap=bool(gopts.get("sep_trap", False)),
            sp404=bool(gopts.get("sp404", False)),
            clip=clip,
        )
        # Clip-only runs never touch still prefs (they belong to an image).
        if win.src is not None:
            save_prefs(ExportPrefs(
                out_dir=str(out_dir), base=options.base,
                image=options.selection.image,
                thumb_1080p=options.selection.thumb_1080p,
                vector=options.selection.vector, anim=options.selection.anim,
                metadata=options.selection.metadata,
                webp=bool(gopts.get("webp", False)),
                tiff=bool(gopts.get("tiff", False)),
                social=bool(gopts.get("social", False)),
                sep=bool(gopts.get("sep", False)),
                sep_trap=bool(gopts.get("sep_trap", False)),
                sp404=bool(gopts.get("sp404", False)),
                mp4=bool(gopts.get("mp4", False)),
                gif_frames=int(gopts["frames"]), gif_mode=str(gopts["mode"]),
                gif_fps=int(gopts["fps"]), gif_size=int(gopts["size"]),
                gif_pingpong=bool(gopts["pingpong"]),
                mp4_size=str(gopts.get("mp4_size", "1080p")),
                overwrite="rename",  # per-run choice is not persisted (quick is always safe)
                size=options.size, format=options.format, quality=options.quality,
                dpi=int(options.dpi),
                recent_files=recent_files, src_name=win.src_name,
            ), win._prefs_path)
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Export error: {e}")


def resolve_collision(win, out_dir, options, want_mp4: bool = False,
                      want_webp: bool = False, want_tiff: bool = False,
                      want_social: bool = False,
                      want_sep: bool = False,
                      want_clip: dict | None = None) -> str | None:
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
    if want_tiff:
        from app.exporter import tiff_name as _tiff_name

        names["tiff"] = _tiff_name(options.base)
    if want_social:
        from app.social import pack_names as _pack_names

        for stem, fname in _pack_names(options.base, options.format).items():
            names[f"social_{stem}"] = fname
    if want_sep:
        # Plate hexes need the render; glob the family's exact files.
        try:
            for i, p in enumerate(sorted(out_dir.glob(f"{options.base}_sep_*.png"))):
                names[f"sep{i}"] = p.name
        except OSError:
            pass
    if want_clip:
        try:
            from app.ui.clip_controller import clip_names as _clip_names

            for kind, on in (("gif", want_clip.get("gif")), ("mp4", want_clip.get("mp4")),
                             ("zip", want_clip.get("zip"))):
                if on:
                    names[f"clip_{kind}"] = _clip_names(options.base)[kind]
        except Exception:  # noqa: BLE001
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
        from app.canvas import doc_dimensions, to_canvas
        from app.vector import capped_canvas_dims, estimate_cells

        cw = int(getattr(preset, "canvas_w", 0) or 0)
        ch = int(getattr(preset, "canvas_h", 0) or 0)
        canvas = to_canvas(
            win.src, ratio=preset.ratio, mode=preset.crop_mode,
            fx=float(preset.focus_x), fy=float(preset.focus_y),
            zoom=float(preset.crop_zoom),
            canvas_w=cw,
            canvas_h=ch,
        )
        doc_w, doc_h = doc_dimensions(
            preset.ratio, int(getattr(preset, "export_size", 3000) or 3000), cw, ch)
        gw, gh = capped_canvas_dims(canvas.width, canvas.height, doc_w, doc_h)
        return estimate_cells(gw, gh, int(preset.vector_cell))
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


def _snapshot_morph(src_list):
    """Copy morph chain entries so the worker never touches live images."""
    if not src_list:
        return src_list
    out = []
    for entry in src_list:
        if isinstance(entry, dict):
            img = entry.get("img")
            try:
                cp = img.copy() if img is not None else None
            except Exception:  # noqa: BLE001
                cp = img
            out.append({**entry, "img": cp} if cp is not None else entry)
        else:
            try:
                out.append(entry.copy())
            except Exception:  # noqa: BLE001
                out.append(entry)
    return out


def on_export_done(win, paths: dict, skipped: bool, base: str, out_dir) -> None:
    """Export worker success slot (GUI thread): dialogs + status + cleanup."""
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from app.ui.thread_safe import retire

    w = getattr(win, "_export_worker", None)
    win._export_worker = None
    retire(w)  # the emit happens inside run(): never drop a live QThread
    if skipped and not paths:
        QMessageBox.information(
            win, "TRAKKART",
            f"Skipped: {base} already exists (policy: skip).")
        win._status(f"Export skipped (exists): {base}")
        return
    show_exported(win, Path(out_dir).resolve(), [p.name for p in paths.values()])
    win._status(f"Exported to {Path(out_dir).resolve()}")


def on_export_error(win, msg: str) -> None:
    """Export worker error slot (GUI thread): report + cleanup."""
    from app.ui.thread_safe import retire

    w = getattr(win, "_export_worker", None)
    win._export_worker = None
    retire(w)
    win._report_error("Export error", msg)


def _wants_stills(selection, mp4: bool, webp: bool,
                  tiff: bool, social: bool, sep: bool, sp404: bool) -> bool:
    """Any still output on (image/thumb/vector/anim/meta + extras)."""
    try:
        sel = selection
        if any((sel.image, sel.thumb_1080p, sel.vector, sel.anim,
                sel.metadata, bool(getattr(sel, "black_vector", False)))):
            return True
    except Exception:  # noqa: BLE001
        return True
    try:
        if any((mp4, webp, tiff, social, sep, sp404)):
            return True
    except Exception:  # noqa: BLE001
        return True
    return False


def _run_clip_exports(win, base: str, out_dir, clip: dict | None,
                      preset) -> list[str]:
    """Clip files for the Export window (sync, first-free names, never overwrite)."""
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from app.ui import clip_controller as _cc
    from app.ui.clip_controller import _busy, _free_path, clip_names

    if not clip or not _cc.has_clip(win):
        return []
    span = _cc.trimmed(win)
    if not span:
        return []
    try:
        fps = _cc._export_fps(win, clip.get("fps"))
    except Exception:  # noqa: BLE001
        fps = 24
    track = str(clip.get("track", "") or "").strip()
    try:
        res = str(clip.get("res", "proxy") or "proxy").lower()
        res = "source" if res == "source" else "proxy"
    except Exception:  # noqa: BLE001
        res = "proxy"
    try:
        quality = max(0, min(10, int(clip.get("quality", 8))))
    except (TypeError, ValueError):
        quality = 8
    names: list[str] = []
    full_mp4 = bool(clip.get("mp4") and clip.get("full"))
    short_span = len(span)
    try:
        label = f"{short_span}f @{fps}fps" + (" + full-length MP4" if full_mp4 else "")
    except Exception:  # noqa: BLE001
        label = ""
    _busy(win, True, f"Exporting clip... {label}")
    try:
        for kind in ("gif", "zip", "mp4"):
            if not clip.get(kind):
                continue
            out = _free_path(Path(out_dir) / clip_names(base)[kind])
            if kind == "mp4" and full_mp4:
                try:
                    _cc.render_clip_export_long(win, preset, fps, out, track,
                                                res, quality)
                except Exception as e:  # noqa: BLE001
                    QMessageBox.warning(win, "TRAKKART", f"Clip export error ({kind}): {e}")
                    continue
                names.append(out.name)
                continue
            try:
                _cc.render_clip_export(win, kind, preset, span, fps, out, track,
                                       res, quality)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(win, "TRAKKART", f"Clip export error ({kind}): {e}")
                continue
            names.append(out.name)
    finally:
        _busy(win, False)
    if names:
        try:
            win._status(f"Clip exported: {', '.join(names)} ({len(span)}f @{fps}fps)")
        except Exception:  # noqa: BLE001
            pass
    return names


def _run_export_sync(win, base: str, out_dir, selection, gif_opts: dict,
                     overwrite: str, size: int, format: str,
                     quality: int, mp4: bool = False,
                     mp4_size: str = "1080p",
                     webp: bool = False,
                     tiff: bool = False, dpi: int = 300,
                     social: bool = False,
                     sep: bool = False, sep_trap: bool = False,
                     sp404: bool = False, clip: dict | None = None) -> None:
    """Blocking export (tests + fallback): the pre-worker behavior, intact."""
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
    clip_names = _run_clip_exports(win, base, out_dir, clip, preset)
    if not _wants_stills(selection, mp4, webp, tiff, social, sep, sp404):
        # Clip-only export (no still open): still bundle skipped.
        if clip_names:
            show_exported(win, Path(out_dir).resolve(), clip_names)
        else:
            QMessageBox.information(win, "TRAKKART", "Nothing selected to export.")
        return
    try:
        env = dict(getattr(win, "_envelopes", {}) or {})
    except Exception:  # noqa: BLE001
        env = {}
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
            tiff=bool(tiff),
            dpi=int(dpi or 300),
            social=bool(social),
            sep=bool(sep),
            sep_trap=bool(sep_trap),
            sp404=bool(sp404),
            morph_src=morph_src_for_mode(win, mode_go),
            envelopes=env,
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
    show_exported(win, Path(out_dir).resolve(),
                  [p.name for p in paths.values()] + list(clip_names))
    win._status(f"Exported to {Path(out_dir).resolve()}")


def run_export(win, base: str, out_dir, selection, gif_opts: dict,
               overwrite: str, size: int, format: str,
               quality: int, mp4: bool = False,
               mp4_size: str = "1080p",
               webp: bool = False,
               tiff: bool = False, dpi: int = 300,
               social: bool = False,
               sep: bool = False, sep_trap: bool = False,
               sp404: bool = False, _sync: bool = False,
               clip: dict | None = None) -> None:
    """Render full-res + bundle (+MP4/WebP/seps) per options. Stills always full-res;
    MP4 uses its own size (Canvas/1080p/720p) so 3000px docs don't ship GBs;
    WebP reuses the GIF frames at ~1/3 the weight; seps write one PNG per ink.
    Clip files (Export window section) render synchronously first.

    Async by default (ExportWorker, no GUI freeze); `_sync=True` or
    `win._export_sync` keeps the blocking path (tests).
    """
    import copy
    from dataclasses import replace

    from PySide6.QtWidgets import QMessageBox

    from app.video_io import VideoBackendMissing

    if bool(_sync) or bool(getattr(win, "_export_sync", False)):
        _run_export_sync(win, base, out_dir, selection, gif_opts,
                         overwrite, size, format, quality, mp4,
                         mp4_size, webp, tiff, dpi, social, sep, sep_trap, sp404,
                         clip=clip)
        return
    running = getattr(win, "_export_worker", None)
    try:
        is_running = bool(running is not None and running.isRunning())
    except Exception:  # noqa: BLE001
        is_running = False
    if is_running:
        win._status("Export already running...")
        return
    if win.src is None and not clip:
        QMessageBox.information(win, "TRAKKART", "Open an image first.")
        return
    try:
        preset = win.current_params()
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Export error: {e}")
        return
    if bool(getattr(selection, "black_vector", False)):
        preset = replace(preset, vector_black=True)
    # Clip files render synchronously first (same pass as the dialog plan);
    # stills follow on the worker (or not at all when clip-only).
    clip_names = _run_clip_exports(win, base, out_dir, clip, preset)
    if not _wants_stills(selection, mp4, webp, tiff, social, sep, sp404):
        from pathlib import Path as _P

        show_exported(win, _P(out_dir).resolve(), clip_names)
        return
    go = dict(gif_opts) if isinstance(gif_opts, dict) else {"frames": gif_opts}
    mode_go = str(go.get("mode", "both"))
    try:
        src_snapshot = win.src.copy()
    except Exception:  # noqa: BLE001
        src_snapshot = win.src
    try:
        preset_snapshot = copy.deepcopy(preset)
    except Exception:  # noqa: BLE001
        preset_snapshot = preset
    morph_snapshot = _snapshot_morph(morph_src_for_mode(win, mode_go))
    try:
        preset_name = win.cmb_preset.currentText()
    except Exception:  # noqa: BLE001
        preset_name = ""
    from app.ui.workers import ExportWorker

    try:
        env_snapshot = dict(getattr(win, "_envelopes", {}) or {})
    except Exception:  # noqa: BLE001
        env_snapshot = {}
    worker = ExportWorker(
        src_snapshot, preset_snapshot, out_dir, base=base, store=win.store,
        preset_name=preset_name, selection=selection, overwrite=overwrite,
        gif_frames=int(go.get("frames", 6)), gif_mode=mode_go,
        gif_fps=int(go.get("fps", 8)), gif_size=int(go.get("size", 1200)),
        gif_pingpong=bool(go.get("pingpong", False)),
        size=int(size), format=str(format), quality=int(quality),
        mp4=bool(mp4), mp4_fps=int(go.get("fps", 8)),
        mp4_size=str(go.get("mp4_size", mp4_size)),
        webp=bool(webp), tiff=bool(tiff), dpi=int(dpi or 300),
        social=bool(social),
        sep=bool(sep), sep_trap=bool(sep_trap), morph_src=morph_snapshot,
        sp404=bool(sp404), envelopes=env_snapshot,
        parent=win,
    )
    worker.finished_ok.connect(
        lambda paths, skipped: on_export_done(win, paths, skipped, base, out_dir))
    worker.error.connect(lambda msg: on_export_error(win, msg))
    win._export_worker = worker
    win._status("Exporting in background...")
    try:
        worker.start()
    except VideoBackendMissing as e:
        win._export_worker = None
        QMessageBox.warning(win, "TRAKKART", str(e))
        win._status("MP4 needs the video extra (still exports skipped)")
