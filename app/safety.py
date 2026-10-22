"""TRAKKART safety/stability guards.

- Decompression bombs: cap on dimensions and megapixels per image.
- Monstrous SVGs: cap on cells before generating.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

MAX_SIDE = 8000
MAX_MP = 50
MAX_BYTES = 40_000_000  # web download cap (~40MB)
MAX_VECTOR_CELLS = 160_000


class TooBigError(ValueError):
    """Image exceeds safe limits."""


def check_image(img: Image.Image) -> None:
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        raise TooBigError(f"image is {w}x{h}: max side {MAX_SIDE}px")
    if w * h > MAX_MP * 1_000_000:
        raise TooBigError(f"image is {w}x{h}: max {MAX_MP} MP")


def check_path(path: str | Path) -> tuple[int, int]:
    """Read only the header (no decoding) and validate size."""
    p = Path(path)
    try:
        with Image.open(p) as im:
            w, h = im.size  # header: decodes no pixels
    except TooBigError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"not a valid image: {p.name} ({e})") from e
    if max(w, h) > MAX_SIDE or w * h > MAX_MP * 1_000_000:
        raise TooBigError(f"image is {w}x{h}: exceeds {MAX_SIDE}px or {MAX_MP} MP")
    return w, h


def check_vector_cells(cols: int, rows: int) -> None:
    if int(cols) * int(rows) > MAX_VECTOR_CELLS:
        raise TooBigError(
            f"grid {cols}x{rows}: use a bigger cell "
            f"(max {MAX_VECTOR_CELLS} cells)"
        )
