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
    vector_cells: tuple[int, int] | None = None,
) -> tuple[dict[str, Path], list[str]]:
    """Renderiza, genera SVG/GIF si se piden, guarda bundle y loguea.

    Retorna (paths escritos, keys omitidas por skip). Sin `selection`
    equivale al bundle completo clásico.
    """
    from app.vector import estimate_cells

    sel = selection or ExportSelection(
        vector=bool(preset.vector_export), anim=bool(preset.gif_export),
    )
    # La selección (diálogo o prefs) manda; el preset aporta parámetros
    # (celda, ratio, frames/mode por defecto). El batch usa el preset directo.
    want_vector = bool(sel.vector)
    want_gif = bool(sel.anim)
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
    if want_gif:
        from app.gif import gif_frames as _gif_frames  # alias: no shadow al parámetro

        frames = _gif_frames(
            src, preset,
            frames=int(gif_frames if gif_frames is not None else preset.gif_frames),
            mode=gif_mode if gif_mode is not None else preset.gif_mode,
        )

    options = ExportOptions(base=base, selection=sel, overwrite=overwrite)
    paths, skipped = export_with_options(
        res, out_dir, options, meta=preset.meta(),
        vector_svg=svg, gif_frames=frames,
    )
    if store is not None and paths:
        try:
            store.log_export(options.base, preset_name, preset.meta(),
                             [str(p) for p in paths.values()])
        except Exception:
            pass
    return paths, skipped


__all__ = ["export_full"]
