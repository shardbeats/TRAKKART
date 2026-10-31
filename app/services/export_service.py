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
    morph_src: Image.Image | None = None,
) -> tuple[dict[str, Path], list[str]]:
    """Render, generate SVG/GIF/MP4 on request, write bundle and log.

    Returns (written paths, keys skipped). Without `selection` it equals
    the classic full bundle. size/format/quality override the preset
    (chosen by the dialog); None = preset value.
    MP4 is written as an extra `{base}_anim.mp4` file outside the bundle
    (single-export; batch keeps the GIF route).
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
    if want_gif or want_mp4:
        from app.gif import gif_frames as _gif_frames  # alias: no shadowing of the parameter

        frames = _gif_frames(
            src, preset,
            frames=int(gif_frames if gif_frames is not None else preset.gif_frames),
            mode=gif_mode if gif_mode is not None else preset.gif_mode,
            max_side=int(gif_size if gif_size is not None else getattr(preset, "gif_size", 480)),
            pingpong=bool(gif_pingpong if gif_pingpong is not None
                          else getattr(preset, "gif_pingpong", False)),
            img_b=morph_src,
        )

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
    if want_mp4 and frames:
        from app.video_io import write_mp4

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
            write_mp4(frames, mp4_path,
                      fps=int(mp4_fps if mp4_fps is not None else fps))
            paths["video"] = mp4_path
    if store is not None and paths:
        try:
            store.log_export(options.base, preset_name, preset.meta(),
                             [str(p) for p in paths.values()])
        except Exception:
            pass
    return paths, skipped


__all__ = ["export_full"]
