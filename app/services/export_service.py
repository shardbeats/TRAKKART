"""Export service: render full-res + optional SVG/GIF + bundle + history.

Extraído de MainWindow.export() (que mezclaba UI + pipeline + IO).
La UI solo muestra diálogos; esto hace el trabajo testeable.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from app.exporter import export_bundle
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
) -> dict[str, Path]:
    """Renderiza, genera SVG/GIF si el preset lo pide, guarda bundle y loguea."""
    res = render_full(src, preset)

    svg = None
    if preset.vector_export:
        from app.vector import vector_bundle

        svg, _, _ = vector_bundle(src, preset)

    frames: list[Image.Image] | None = None
    if preset.gif_export:
        from app.gif import gif_frames

        frames = gif_frames(src, preset, frames=int(preset.gif_frames), mode=preset.gif_mode)

    paths = export_bundle(
        res, out_dir, base=base, meta=preset.meta(),
        vector_svg=svg, gif_frames=frames,
    )
    if store is not None:
        try:
            store.log_export(base, preset_name, preset.meta(), [str(p) for p in paths.values()])
        except Exception:
            pass
    return paths


__all__ = ["export_full"]
