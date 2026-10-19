"""TRAKKART SVG vector (MIT, clean-room). Logos and merch.

Re-render the pipeline to a cell grid WITHOUT post-fx (glow/grain/vignette
would generate thousands of tones) + brand. Each cell -> one <rect>,
with per-row RLE. No external dependencies: SVG is written by hand.
"""

from __future__ import annotations

from PIL import Image

from app.adjust import Adjust
from app.canvas import to_canvas
from app.dither import apply_method
from app.fx import apply_pre, replace_white
from app.pipeline import resolve_palette


def render_cells(
    img: Image.Image,
    cols: int,
    rows: int,
    method: str = "bayer4",
    palette_name: str = "SLIME",
    threshold: float = 128.0,
    adjust: Adjust | dict | None = None,
    ratio: str = "1:1",
    crop_mode: str = "cover",
    focus_x: float = 50.0,
    focus_y: float = 50.0,
    crop_zoom: float = 1.0,
    pre_blur: float = 0.0,
    pre_sharpen: int = 0,
    pre_hue: float = 0.0,
    pre_denoise: int = 0,
    pre_smooth: float = 0.0,
    replace_color: str = "",
    custom_palette: list | None = None,
) -> Image.Image:
    """Small raster (cols x rows) ready to vectorize."""
    canvas = to_canvas(img, ratio=ratio, mode=crop_mode, fx=focus_x, fy=focus_y,
                       zoom=crop_zoom)
    if pre_blur or pre_sharpen or pre_hue or pre_denoise or pre_smooth:
        canvas = apply_pre(canvas, blur=pre_blur, sharpen=pre_sharpen,
                           hue=pre_hue, denoise=pre_denoise, smooth=pre_smooth)
    small = canvas.resize((max(1, int(cols)), max(1, int(rows))), Image.BICUBIC)
    pal, _ = resolve_palette(palette_name, custom_palette)
    dithered = apply_method(small, method=method, palette=pal,
                            threshold=float(threshold), pixel_size=1, adjust=adjust)
    if replace_color:
        dithered = replace_white(dithered, color=replace_color)
    return dithered


def estimate_cells(canvas_w: int, canvas_h: int, cell: int) -> tuple[int, int]:
    """Grid columns x rows for a canvas and cell size."""
    cell = max(1, int(cell))
    return max(1, canvas_w // cell), max(1, canvas_h // cell)


def estimate_bytes(cols: int, rows: int) -> int:
    """Rough weight estimate (~60B per cell without RLE) to warn about huge SVGs."""
    return int(cols) * int(rows) * 60


def vector_bundle(img: Image.Image, preset) -> tuple[str, int, int]:
    """Build the SVG from a Preset. Returns (svg, cols, rows)."""
    from app.canvas import to_canvas
    from app.safety import check_vector_cells

    cell = max(4, min(16, int(preset.vector_cell)))
    canvas = to_canvas(img.convert("RGB"), ratio=preset.ratio, mode=preset.crop_mode,
                       fx=float(preset.focus_x), fy=float(preset.focus_y),
                       zoom=float(preset.crop_zoom))
    cols, rows = estimate_cells(canvas.width, canvas.height, cell)
    check_vector_cells(cols, rows)  # block monstrous SVGs before rendering
    raster = render_cells(
        img, cols, rows,
        method=preset.method, palette_name=preset.palette,
        threshold=float(preset.threshold), adjust=preset.adjust(),
        ratio=preset.ratio, crop_mode=preset.crop_mode,
        focus_x=float(preset.focus_x), focus_y=float(preset.focus_y),
        crop_zoom=float(preset.crop_zoom),
        pre_blur=float(preset.pre_blur), pre_sharpen=int(preset.pre_sharpen),
        pre_hue=float(preset.pre_hue), pre_denoise=int(preset.pre_denoise),
        pre_smooth=float(preset.pre_smooth),
        replace_color=preset.replace_color, custom_palette=preset.custom_palette,
    )
    return raster_to_svg(raster, cell), cols, rows


def raster_to_svg(
    raster: Image.Image,
    cell: int,
    background: tuple[int, int, int] | None = None,
) -> str:
    """Convert a grid-sized raster to SVG with per-row RLE."""
    rgb = raster.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w * cell} {h * cell}" '
        f'width="{w * cell}" height="{h * cell}" shape-rendering="crispEdges">',
    ]
    if background is not None:
        r, g, b = background
        parts.append(f'<rect width="100%" height="100%" fill="#{r:02x}{g:02x}{b:02x}"/>')
    for y in range(h):
        x = 0
        while x < w:
            color = px[x, y]
            run = 1
            while x + run < w and px[x + run, y] == color:
                run += 1
            r, g, b = color
            parts.append(
                f'<rect x="{x * cell}" y="{y * cell}" width="{run * cell}" '
                f'height="{cell}" fill="#{r:02x}{g:02x}{b:02x}"/>'
            )
            x += run
    parts.append("</svg>")
    return "".join(parts)
