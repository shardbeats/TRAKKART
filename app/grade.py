"""TRAKKART grade pack (GPL-3.0-only). Pre/post-dither color grading.

Duotone and posterize run BEFORE the dither (on continuous tone, like the
adjustments: the dither works over the grade). Split-tone and fade
run after (they work well on flat art). All deterministic, numpy+Pillow.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB")


def _luminance(arr: np.ndarray) -> np.ndarray:
    """Rec.601 luminance in 0-1."""
    return (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0


def _parse_hex(color: str) -> tuple[int, int, int] | None:
    s = (color or "").strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return None


def gradient_map(
    img: Image.Image,
    color_dark: str = "",
    color_light: str = "",
    mid: float = 50.0,
) -> Image.Image:
    """Duotone: luminance -> color_dark..color_light gradient, cut at mid%.

    Empty in either = off. The midpoint moves the cut (classic color stops).
    """
    c0 = _parse_hex(color_dark)
    c1 = _parse_hex(color_light)
    if c0 is None or c1 is None:
        return img
    t = float(np.clip(mid, 0.0, 100.0)) / 100.0
    # Smooth ±7.5% transition around the midpoint (less banding).
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = _luminance(arr)
    x = np.clip((lum - (t - 0.075)) / 0.15, 0.0, 1.0)
    k = x * x * (3.0 - 2.0 * x)  # smoothstep
    a = np.array(c0, dtype=np.float32)[None, None, :]
    b = np.array(c1, dtype=np.float32)[None, None, :]
    return Image.fromarray(np.clip(a + (b - a) * k[..., None], 0, 255).astype(np.uint8))


def posterize(img: Image.Image, levels: int = 0) -> Image.Image:
    """Reduces to `levels` tones per channel. 0 or <2 = off."""
    lv = int(levels)
    if lv < 2:
        return img
    lv = min(8, lv)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    q = np.round(arr / 255.0 * (lv - 1)) / (lv - 1) * 255.0
    return Image.fromarray(np.clip(q, 0, 255).astype(np.uint8))


# Fixed cinematic pair, documented (the fine custom one is the duotone).
_SPLIT_WARM = np.array([255.0, 170.0, 90.0], dtype=np.float32)
_SPLIT_COOL = np.array([70.0, 100.0, 255.0], dtype=np.float32)


def split_tone(img: Image.Image, strength: float = 0.0) -> Image.Image:
    """Cool shadows + warm highlights by luminance. 0 = off."""
    s = float(strength) / 100.0
    if s <= 0:
        return img
    s = min(1.0, s)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = _luminance(arr)[..., None]
    warm = _SPLIT_WARM[None, None, :] * lum
    cool = _SPLIT_COOL[None, None, :] * (1.0 - lum)
    graded = arr * (1.0 - s) + (arr * 0.5 + (warm + cool) * 0.25) * s
    return Image.fromarray(np.clip(graded, 0, 255).astype(np.uint8))


def fade(img: Image.Image, amount: float = 0.0) -> Image.Image:
    """Matte look: lifts blacks proportionally. 0 = off."""
    s = float(amount) / 100.0
    if s <= 0:
        return img
    s = min(1.0, s)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = _luminance(arr)
    lift = s * 64.0 * (1.0 - lum) ** 2  # shadows only, like the film matte
    return Image.fromarray(np.clip(arr + lift[..., None], 0, 255).astype(np.uint8))


def normalize_stops(stops) -> list[tuple[float, tuple[int, int, int]]]:
    """Clean an N-stop ramp: [(pos 0-100, #RRGGBB), ...] -> sorted, valid only.

    Positions clamp to 0-100, bad hex dropped, duplicate positions keep
    the last stop. <2 valid stops = off (the caller returns the image).
    Deterministic, never raises on junk (session/UI safety).
    """
    clean: dict[float, tuple[int, int, int]] = {}
    try:
        seq = list(stops or [])
    except TypeError:
        return []
    for entry in seq:
        try:
            pos_raw, color = entry
            pos = max(0.0, min(100.0, float(pos_raw)))
            rgb = _parse_hex(str(color or ""))
        except (TypeError, ValueError):
            continue
        if rgb is None:
            continue
        clean[pos] = rgb
    return [(p, clean[p]) for p in sorted(clean)]


def gradient_stops(img: Image.Image, stops) -> Image.Image:
    """Multi-stop gradient map: luminance -> N-ink ramp (piecewise linear).

    Duotone with more stops; runs as a post-dither STACK item (recolors
    flat dithered art by luminance, like split-tone/fade). <2 valid
    stops = off (identity). Deterministic numpy, no seeds.
    """
    pts = normalize_stops(stops)
    if len(pts) < 2:
        return img
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = np.clip(_luminance(arr), 0.0, 1.0) * 100.0
    pos = np.array([p for p, _ in pts], dtype=np.float32)
    inks = np.array([c for _, c in pts], dtype=np.float32)
    # Piecewise-linear per channel over the stop positions.
    out = np.empty_like(arr)
    for ch in range(3):
        out[..., ch] = np.interp(lum, pos, inks[:, ch])
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


#: Curated ramps for the GRADE combo (engine accepts any N-stop list;
#: these are just named shortcuts, stored as plain stops in the preset).
GRADIENT_RAMPS: dict[str, list[tuple[float, str]]] = {
    "Ember": [(0.0, "#000000"), (45.0, "#7A1F00"), (75.0, "#E8641B"),
              (100.0, "#FFE9C4")],
    "Abyss": [(0.0, "#02030A"), (50.0, "#0B2A5B"), (80.0, "#1E90A8"),
              (100.0, "#D8F6F0")],
    "Acid": [(0.0, "#0A0A00"), (40.0, "#3F7A00"), (70.0, "#C6F500"),
             (100.0, "#F4FFE0")],
    "Bone": [(0.0, "#111111"), (100.0, "#F2F0E8")],
}


__all__ = ["gradient_map", "posterize", "split_tone", "fade",
           "normalize_stops", "gradient_stops", "GRADIENT_RAMPS"]
