"""Export service: render full-res + optional SVG/GIF + bundle + history.

Extracted from MainWindow.export() (which mixed UI + pipeline + IO).
The UI only shows dialogs; this does the testable work.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from app.exporter import ExportOptions, ExportSelection, export_with_options
from app.services.render_service import render_full

if TYPE_CHECKING:
    from app.presets import Preset


def _morph_chain_for_export(morph_src) -> list:
    """Count chain segments for the MP4 streaming plan (no UI import)."""
    if not morph_src:
        return []
    if isinstance(morph_src, list):
        return [m for m in morph_src if m is not None]
    return [morph_src]


def export_full(
    src: Image.Image,
    preset: Preset,
    out_dir: str | Path,
    base: str = "trakkart_cover",
    store=None,
    preset_name: str = "",
    selection: ExportSelection | None = None,
    overwrite: str = "overwrite",
    gif_frames: int | None = None,
    gif_mode: str | None = None,
    gif_fps: int | None = None,
    gif_size: int | None = None,
    gif_pingpong: bool | None = None,
    vector_cells: tuple[int, int] | None = None,
    size: int | None = None,
    format: str | None = None,
    quality: int | None = None,
    mp4: bool = False,
    mp4_fps: int | None = None,
    mp4_size: str | int | None = None,
    webp: bool = False,
    sep: bool = False,
    morph_src: Image.Image | None = None,
) -> tuple[dict[str, Path], list[str]]:
    """Render, generate SVG/GIF/MP4/WebP/separations on request, write bundle and log.

    Returns (written paths, keys skipped). Without `selection` it equals
    the classic full bundle. size/format/quality override the preset
    (chosen by the dialog); None = preset value.
    MP4 is written as an extra `{base}_vid.mp4` file outside the bundle
    (single-export; batch keeps the GIF route). Stills stay full-doc;
    MP4 renders at `mp4_size` (Canvas/1080p/720p, default 1080p) so a
    3000px doc at 60fps doesn't ship hundreds of MB.
    WebP is written as an extra `{base}_anim.webp` with the same frames
    as the GIF (~1/3 the weight, full color). Dialog-only like MP4.
    Separations write one `{base}_sep_{NN}_{RRGGBB}.png` plate per
    palette ink (RISO/screen print) + registration marks. Dialog-only.
    """
    from app.vector import estimate_cells

    sel = selection or ExportSelection(
        vector=bool(preset.vector_export), anim=bool(preset.gif_export),
    )
    # The selection (dialog or prefs) wins; the preset provides parameters
    # (cell, ratio, default frames/mode). Batch uses the preset directly.
    want_vector = bool(sel.vector)
    want_gif = bool(sel.anim)
    want_mp4 = bool(mp4)
    want_webp = bool(webp)
    want_sep = bool(sep)
    res = render_full(src, preset)

    svg = None
    cols_rows = vector_cells
    if want_vector:
        from app.vector import vector_bundle

        svg, cols, rows = vector_bundle(src, preset)
        cols_rows = (cols, rows)
    if cols_rows is None and want_vector:
        from app.canvas import to_canvas

        canvas = to_canvas(
            src, ratio=preset.ratio, mode=preset.crop_mode,
            fx=float(preset.focus_x), fy=float(preset.focus_y),
            zoom=float(preset.crop_zoom),
        )
        cols_rows = estimate_cells(canvas.width, canvas.height, int(preset.vector_cell))

    frames: list[Image.Image] | None = None
    fps = int(gif_fps if gif_fps is not None else getattr(preset, "gif_fps", 8))
    mode_eff = str(gif_mode if gif_mode is not None else preset.gif_mode)
    size_eff = int(gif_size if gif_size is not None else getattr(preset, "gif_size", 480))
    n_req = int(gif_frames if gif_frames is not None else preset.gif_frames)
    pp_eff = bool(gif_pingpong if gif_pingpong is not None
                  else getattr(preset, "gif_pingpong", False))
    mp4_stream_info: dict | None = None
    mp4_size_eff = str(mp4_size) if mp4_size not in (None, "") else "1080p"
    if want_gif or want_mp4 or want_webp:
        from app.gif import gif_frames as _gif_frames  # alias: no shadowing of the parameter

        # GIF (and short MP4s) keep the capped list path (<=256f, ping-pong
        # intact). Long particle MP4s stream below without the huge list.
        frames = _gif_frames(
            src, preset,
            frames=n_req,
            mode=mode_eff,
            max_side=size_eff,
            pingpong=pp_eff,
            img_b=morph_src,
            fps=int(fps),
        )
        if want_mp4 and mode_eff in ("dissolve", "morph"):
            from app.gif import MAX_MP4_FRAMES, MAX_TOTAL_FRAMES, plan_dissolve

            segs = 1
            if mode_eff == "morph":
                chain = _morph_chain_for_export(morph_src)
                segs = max(1, len(chain)) if chain else 1
            loop_eff = bool(getattr(preset, "dissolve_loop", False)) if mode_eff == "morph" else False
            hold = float(getattr(preset, "dissolve_hold", 0.0) or 0.0)
            # Hold-manda: no Length target (derived total = trans + holds).
            plan_mp4 = plan_dissolve(n_req, segs, int(fps), hold,
                                     None, cap=MAX_MP4_FRAMES, loop=loop_eff)
            if int(plan_mp4["total"]) > int(MAX_TOTAL_FRAMES):
                # Long clip: GIF keeps its capped list; MP4 streams the full
                # clip forward-only (ping-pong a 3600f list = 7k frames in
                # RAM, so it is intentionally off here).
                from app.gif import mp4_dims

                try:
                    mw, mh = mp4_dims(res.width, res.height, mp4_size_eff)
                    mp4_long = max(mw, mh)
                except Exception:  # noqa: BLE001
                    mp4_long = 1080
                mp4_stream_info = {"plan": plan_mp4, "mode": mode_eff,
                                   "fps": int(fps), "size": int(mp4_long),
                                   "frames_req": n_req, "segs": segs,
                                   "loop": loop_eff}

    options = ExportOptions(
        base=base, selection=sel, overwrite=overwrite,
        size=int(size if size is not None else preset.export_size),
        format=str(format if format is not None else preset.export_format),
        quality=int(quality if quality is not None else preset.export_quality),
    )
    paths, skipped = export_with_options(
        res, out_dir, options, meta=preset.meta(),
        vector_svg=svg, gif_frames=frames if want_gif else None, gif_fps=fps,
    )
    if want_mp4 and (frames or mp4_stream_info):
        from app.exporter import MP4_SUFFIX, mp4_name as _mp4_name

        name = _mp4_name(options.base)
        mp4_path = Path(out_dir) / name
        if overwrite == "skip" and mp4_path.exists():
            skipped = [*skipped, "video"]
        else:
            if overwrite == "rename":
                i = 2
                while mp4_path.exists():
                    mp4_path = Path(out_dir) / f"{options.base}_{i}{MP4_SUFFIX}"
                    i += 1
            mp4_fps_eff = int(mp4_fps if mp4_fps is not None else fps)
            from app.gif import mp4_dims as _mp4_dims

            try:
                mp4_w, mp4_h = _mp4_dims(res.width, res.height, mp4_size_eff)
            except Exception:  # noqa: BLE001
                mp4_w, mp4_h = res.width, res.height
            if mp4_stream_info is not None:
                from app.gif import iter_dissolve_frames, iter_morph_frames
                from app.video_io import write_mp4_iter

                if str(mp4_stream_info["mode"]) == "morph" and morph_src:
                    stream = iter_morph_frames(
                        src, morph_src, preset,
                        frames=int(mp4_stream_info["frames_req"]),
                        max_side=int(mp4_stream_info["size"]),
                        fps=mp4_fps_eff, cap=3600,
                        loop=bool(mp4_stream_info.get("loop", False)),
                    )
                else:
                    stream = iter_dissolve_frames(
                        src, preset,
                        frames=int(mp4_stream_info["frames_req"]),
                        max_side=int(mp4_stream_info["size"]),
                        fps=mp4_fps_eff, cap=3600,
                    )
                write_mp4_iter(stream, mp4_path, fps=mp4_fps_eff)
            else:
                from app.video_io import write_mp4

                shrunk = frames or []
                if (mp4_w, mp4_h) != (res.width, res.height) and shrunk:
                    # BILINEAR: ~2x faster than bicubic on long clips, no
                    # visible difference on downscaled dither (both alias).
                    shrunk = [f.resize((mp4_w, mp4_h), Image.BILINEAR)
                              if (f.width, f.height) != (mp4_w, mp4_h) else f
                              for f in shrunk]
                write_mp4(shrunk, mp4_path, fps=mp4_fps_eff)
            paths["video"] = mp4_path
    if want_webp and frames:
        from app.exporter import WEBP_SUFFIX, webp_name as _webp_name
        from app.gif import save_webp

        webp_path = Path(out_dir) / _webp_name(options.base)
        if overwrite == "skip" and webp_path.exists():
            skipped = [*skipped, "webp"]
        else:
            if overwrite == "rename":
                i = 2
                while webp_path.exists():
                    webp_path = Path(out_dir) / f"{options.base}_{i}{WEBP_SUFFIX}"
                    i += 1
            save_webp(frames, webp_path, fps=fps)
            paths["webp"] = webp_path
    if want_sep:
        from app.separations import (add_registration_marks,
                                     effective_palette, sep_name,
                                     separation_plates)

        colors = effective_palette(preset, res)
        plates = separation_plates(res, colors)
        for i, (hexcode, plate) in enumerate(plates):
            sep_path = Path(out_dir) / sep_name(options.base, i, hexcode)
            if overwrite == "skip" and sep_path.exists():
                skipped = [*skipped, f"sep_{hexcode}"]
                continue
            if overwrite == "rename":
                stem = f"{options.base}_sep_{i + 1:02d}_{hexcode}"
                j = 2
                while sep_path.exists():
                    sep_path = Path(out_dir) / f"{stem}_{j}.png"
                    j += 1
            add_registration_marks(plate).save(str(sep_path))
            paths[f"sep_{hexcode}"] = sep_path
    if store is not None and paths:
        try:
            store.log_export(options.base, preset_name, preset.meta(),
                             [str(p) for p in paths.values()])
        except Exception:
            pass
    return paths, skipped


__all__ = ["export_full"]
