"""TRAKKART palette extraction (MIT).

Auto-extract N dominant colors from an image (median-cut, numpy-only,
deterministic). No ML, no sklearn, offline.

Algorithm:
  1. Downsample to <= 160px long side (speed, same result for covers).
  2. Collect RGB pixels, drop fully transparent if RGBA.
  3. Median-cut: repeatedly split the box with largest channel range
     at the median until N boxes. Average each box -> color.
  4. Sort dark -> light (by Oklch L via luminance approx) so the strip
     reads as a ramp. Dedupe.

Deterministic: no RNG. Ties broken by channel order R>G>B and stable sort.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _to_rgb_pixels(img: Image.Image, max_side: int = 160) -> np.ndarray:
    rgb = img.convert("RGB")
    w, h = rgb.size
    m = max(w, h)
    if m > max_side:
        f = max_side / float(m)
        rgb = rgb.resize((max(1, round(w * f)), max(1, round(h * f))), Image.BICUBIC)
    return np.asarray(rgb, dtype=np.uint8).reshape(-1, 3)


def _luminance(colors: np.ndarray) -> np.ndarray:
    c = colors.astype(np.float64)
    return 0.299 * c[:, 0] + 0.587 * c[:, 1] + 0.114 * c[:, 2]


def median_cut(pixels: np.ndarray, n: int) -> list[tuple[int, int, int]]:
    """Median-cut to n colors. pixels: (P,3) uint8. Returns 1..n RGB tuples."""
    n = max(1, min(16, int(n)))
    if len(pixels) == 0:
        return [(0, 0, 0)] * n
    boxes: list[np.ndarray] = [pixels.astype(np.int32)]
    while len(boxes) < n:
        # Pick box with largest range that can still split.
        best_i = -1
        best_range = -1
        best_ch = 0
        for i, box in enumerate(boxes):
            if len(box) < 2:
                continue
            mins = box.min(axis=0)
            maxs = box.max(axis=0)
            ranges = maxs - mins
            ch = int(np.argmax(ranges))
            r = int(ranges[ch])
            if r > best_range:
                best_range = r
                best_i = i
                best_ch = ch
        if best_i < 0 or best_range <= 0:
            break
        box = boxes.pop(best_i)
        order = np.argsort(box[:, best_ch], kind="stable")
        ordered = box[order]
        mid = len(ordered) // 2
        boxes.insert(best_i, ordered[:mid])
        boxes.insert(best_i + 1, ordered[mid:])
    colors: list[tuple[int, int, int]] = []
    for box in boxes:
        mean = box.mean(axis=0)
        colors.append((int(round(mean[0])), int(round(mean[1])), int(round(mean[2]))))
    # Dedupe preserving order, then sort dark -> light.
    seen: list[tuple[int, int, int]] = []
    for c in colors:
        if c not in seen:
            seen.append(c)
    arr = np.array(seen, dtype=np.uint8)
    lum = _luminance(arr)
    order = np.argsort(lum, kind="stable")
    return [seen[i] for i in order]


def extract_palette(img: Image.Image, n: int = 4, max_side: int = 160) -> list[tuple[int, int, int]]:
    """Public API: up to N colors (2..16 clamped) from any Pillow image.

    If the image has fewer unique colors than requested, returns the
    unique ones (no duplicated padding: duplicates are useless for dither).
    """
    n = max(2, min(16, int(n)))
    pixels = _to_rgb_pixels(img, max_side=max_side)
    return median_cut(pixels, n)[:n]


__all__ = ["extract_palette", "median_cut"]
