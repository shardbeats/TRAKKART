"""TRAKKART ASCII engine (MIT). Pillow + numpy.

Design rules:
- Density is resolution-independent: `columns` (not cell px). The same
  columns/rows appear in the 640px preview, Full, 100%, GIF and export.
- Cells are character-shaped (width/height ≈ `aspect`), so the image keeps
  its proportions instead of looking stretched.
- Luminance is perceptual (Rec.709), optionally gamma-mapped and Bayer
  dithered between adjacent glyphs.
- Charset is customizable (dark → light) with presets; unsupported glyphs
  fall back to `?` (UI can warn).
- Color modes: mono ink/background, source cell color, or nearest palette.
- `pixel_size` is intentionally ignored for ASCII (density = columns).
- `phase` rotates the ramp (animation), deterministic.

Direct callers that pass no `config` keep the legacy look: cell px,
square cells, source colors (used by old presets/tests).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont

RAMP = "@%#*+=-:. "

CHARSET_PRESETS: dict[str, str] = {
    "Classic": RAMP,
    "Blocks": "█▓▒░ ",
    "Bars": "█▉▊▋▌▍▎▏ ",
    "Binary": "10",
    "Dots": "●•·. ",
    "Minimal": "#. ",
    "Dense": "@&%$#*+=-:. ",
}

COLOR_MODES = ("mono", "source", "palette")

ASCII_DEFAULTS = {
    "charset": RAMP,
    "columns": 100,
    "gamma": 1.0,
    "invert": False,
    "color": "mono",
    "ink": "#FFFFFF",
    "bg": "#000000",
    "dither": 0.0,
    "aspect": 0.6,
}

# 4x4 Bayer thresholds (0..15).
_BAYER4 = np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
], dtype=np.float32) / 16.0


def _hex_rgb(value, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    try:
        rgb = ImageColor.getrgb(str(value))
        if len(rgb) == 4:
            rgb = rgb[:3]
        return (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    except Exception:  # noqa: BLE001
        return fallback


def _hex_str(value, fallback: str) -> str:
    r, g, b = _hex_rgb(value, _hex_rgb(fallback, (0, 0, 0)))
    return f"#{r:02X}{g:02X}{b:02X}"


def _clean_charset(value) -> str:
    s = str(value or "")
    seen: set[str] = set()
    chars: list[str] = []
    for ch in s:
        if ch in "\r\n\t":
            continue
        if ch not in seen:
            seen.add(ch)
            chars.append(ch)
        if len(chars) >= 64:
            break
    if not chars:
        chars = list(RAMP)
    if len(chars) == 1:
        chars.append(" ")
    return "".join(chars)


def normalize_config(cfg: dict | None) -> dict:
    """Clamp/validate an ASCII config (unknown keys are ignored)."""
    src = dict(ASCII_DEFAULTS)
    if isinstance(cfg, dict):
        src.update({k: v for k, v in cfg.items() if k in ASCII_DEFAULTS})
    try:
        columns = int(float(src.get("columns", 100)))
    except (TypeError, ValueError):
        columns = 100
    try:
        gamma = float(src.get("gamma", 1.0))
    except (TypeError, ValueError):
        gamma = 1.0
    try:
        dither = float(src.get("dither", 0.0))
    except (TypeError, ValueError):
        dither = 0.0
    try:
        aspect = float(src.get("aspect", 0.6))
    except (TypeError, ValueError):
        aspect = 0.6
    color = str(src.get("color", "mono") or "mono").lower()
    if color not in COLOR_MODES:
        color = "mono"
    return {
        "charset": _clean_charset(src.get("charset")),
        "columns": max(20, min(300, columns)),
        "gamma": max(0.5, min(2.5, gamma)),
        "invert": bool(src.get("invert", False)),
        "color": color,
        "ink": _hex_str(src.get("ink", "#FFFFFF"), "#FFFFFF"),
        "bg": _hex_str(src.get("bg", "#000000"), "#000000"),
        "dither": max(0.0, min(100.0, dither)),
        "aspect": max(0.35, min(1.0, aspect)),
    }


def _legacy_config(width: int, cell: int) -> dict:
    """Old behavior for callers without config: cell px, square, source color."""
    cols = max(1, int(width) // max(4, int(cell)))
    return {
        "charset": RAMP,
        "columns": max(1, min(300, cols)),
        "gamma": 1.0,
        "invert": False,
        "color": "source",
        "ink": "#FFFFFF",
        "bg": "#000000",
        "dither": 0.0,
        "aspect": 1.0,
    }


@lru_cache(maxsize=64)
def _font(size: int):
    """Bundled JetBrains Mono (OFL), with Pillow default as last resort."""
    from pathlib import Path

    from app.paths import bundle_path

    size = max(1, int(size))
    for path in (
        bundle_path("app", "fonts", "JetBrainsMono-Regular.ttf"),
        Path(__file__).with_name("fonts") / "JetBrainsMono-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:  # noqa: BLE001
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10
        return ImageFont.load_default()


def glyph_supported(font, glyph: str) -> bool:
    """True when the font has a visible mask for the glyph (space is valid)."""
    if not glyph:
        return False
    if glyph.isspace():
        return True
    try:
        mask = font.getmask(glyph)
        return mask.getbbox() is not None
    except Exception:  # noqa: BLE001
        return False


def unsupported_glyphs(charset: str, cell: int = 16) -> list[str]:
    """Chars the bundled font cannot draw (for the UI warning)."""
    font = _font(max(6, int(cell)))
    return [ch for ch in str(charset) if not glyph_supported(font, ch)]


def _draw_glyph(draw: ImageDraw.ImageDraw, xy: tuple[float, float], glyph: str,
                font, fill: tuple[int, int, int]) -> None:
    try:
        draw.text(xy, glyph, font=font, fill=fill, anchor="mm")
        return
    except TypeError:  # Pillow without anchor
        pass
    try:
        bbox = font.getbbox(glyph)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text((xy[0] - w / 2.0, xy[1] - h / 2.0), glyph, font=font, fill=fill)
    except Exception:  # noqa: BLE001
        draw.text(xy, glyph, font=font, fill=fill)


def ascii_render(img: Image.Image, palette: list | None = None, threshold: float = 128.0,
                 pixel_size: int = 1, phase: int = 0, cell: int = 8,
                 config: dict | None = None) -> Image.Image:
    """Render ASCII art.

    `config` is the new resolution-independent model (`columns`, charset,
    colors, dither...). Without it, legacy cell-px behavior is kept so old
    presets/tests stay stable. `pixel_size` is ignored (columns rule).
    """
    base = img.convert("RGB")
    width, height = base.size
    if width < 1 or height < 1:
        return base
    cfg = normalize_config(config) if config is not None else _legacy_config(width, cell)
    if config is None and palette is not None:
        cfg = dict(cfg, color="palette")
    chars = cfg["charset"]
    n = len(chars)
    cols = max(1, int(cfg["columns"]))
    aspect = float(cfg["aspect"])

    # Target cell width from the column count; clamp height for extreme
    # wide images (e.g. 8000x64) and let columns grow to keep the aspect.
    cell_w = width / float(cols)
    cell_h = cell_w / max(0.01, aspect)
    if cell_h > height:
        cell_h = float(height)
        cell_w = cell_h * aspect
        cols = max(1, int(round(width / max(1.0, cell_w))))
    rows = max(1, int(round(height / max(0.01, cell_h))))
    # Exact output size: cells are drawn at W/cols x H/rows.
    cw = width / float(cols)
    ch = height / float(rows)

    small = base.resize((cols, rows), Image.Resampling.BOX)
    arr = np.asarray(small, dtype=np.float32)
    lum = (0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1]
           + 0.0722 * arr[:, :, 2]) / 255.0
    lum = np.clip(lum, 0.0, 1.0) ** (1.0 / max(0.01, float(cfg["gamma"])))
    shift = (float(threshold) - 128.0) / 128.0 * (n / 2.0)
    values = lum * (n - 1) + shift
    if cfg["dither"] > 0:
        yy = np.arange(rows)[:, None] % 4
        xx = np.arange(cols)[None, :] % 4
        values = values + (_BAYER4[yy, xx] - 0.5) * (float(cfg["dither"]) / 100.0)
    idx = np.clip(np.rint(values), 0, n - 1).astype(np.int32)
    if cfg["invert"]:
        idx = (n - 1) - idx
    if phase:
        idx = (idx + int(phase)) % n

    pal = np.asarray(palette, dtype=np.float32) if palette else None
    ink = _hex_rgb(cfg["ink"], (255, 255, 255))
    bg = _hex_rgb(cfg["bg"], (0, 0, 0))
    color_mode = str(cfg["color"])
    out = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(out)
    font_size = max(1, int(round(ch * 0.92)))
    font = _font(font_size)
    supported = {ch_: glyph_supported(font, ch_) for ch_ in chars}

    for y in range(rows):
        cy = (y + 0.5) * ch
        row = idx[y]
        for x in range(cols):
            glyph = chars[int(row[x])]
            if not supported.get(glyph, True):
                glyph = "?"
            if color_mode == "source":
                rgb = tuple(int(v) for v in arr[y, x])
            elif color_mode == "palette" and pal is not None:
                d = ((pal - arr[y, x]) ** 2).sum(axis=1)
                rgb = tuple(int(v) for v in pal[int(d.argmin())])
            else:
                rgb = ink
            _draw_glyph(draw, ((x + 0.5) * cw, cy), glyph, font, rgb)
    return out


__all__ = [
    "ASCII_DEFAULTS",
    "CHARSET_PRESETS",
    "COLOR_MODES",
    "RAMP",
    "ascii_render",
    "glyph_supported",
    "normalize_config",
    "unsupported_glyphs",
]
