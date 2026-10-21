"""Export service: render full-res + optional SVG/GIF + bundle + history.

Extraído de MainWindow.export() (que mezclaba UI + pipeline + IO).
La UI solo muestra diálogos; esto hace el trabajo testeable.
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
) -> tuple[dict[str, Path], list[str]]:
    """Renderiza, genera SVG/GIF/MP4 si se piden, guarda bundle y loguea.

    Retorna (paths escritos, keys omitidas por skip). Sin `selection`
    equivale al bundle completo clásico. size/format/quality pisan al preset
    (los elige el diálogo); None = valor del preset.
    MP4 se escribe como fichero extra `{base}_anim.mp4` fuera del bundle
    (single-export; el batch sigue ruta GIF).
    """
    from app.vector import estimate_cells

    sel = selection or ExportSelection(
        vector=bool(preset.vector_export), anim=bool(preset.gif_export),
    )
    # La selección (diálogo o prefs) manda; el preset aporta parámetros
    # (celda, ratio, frames/mode por defecto). El batch usa el preset directo.
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
        from app.gif import gif_frames as _gif_frames  # alias: no shadow al parámetro

        frames = _gif_frames(
            src, preset,
            frames=int(gif_frames if gif_frames is not None else preset.gif_frames),
            mode=gif_mode if gif_mode is not None else preset.gif_mode,
            max_side=int(gif_size if gif_size is not None else getattr(preset, "gif_size", 480)),
            pingpong=bool(gif_pingpong if gif_pingpong is not None
                          else getattr(preset, "gif_pingpong", False)),
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
