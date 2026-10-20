"""TRAKKART grade pack (MIT, clean-room). Pre/post-dither color grading.

Duotone y posterize van ANTES del dither (sobre tono continuo, como los
adjustments: el dither trabaja después sobre el grade). Split-tone y fade
van después (operan bien sobre arte plano). Todo determinista, numpy+Pillow.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB")


def _luminance(arr: np.ndarray) -> np.ndarray:
    """Luminancia Rec.601 en 0-1."""
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
    """Duotone: luminancia -> degradado color_dark..color_light, corte en mid%.

    Vacío en cualquiera = off. El midpoint mueve el corte (GIMP: color stops).
    """
    c0 = _parse_hex(color_dark)
    c1 = _parse_hex(color_light)
    if c0 is None or c1 is None:
        return img
    t = float(np.clip(mid, 0.0, 100.0)) / 100.0
    # Transición suave de ±7.5% alrededor del midpoint (menos banding).
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = _luminance(arr)
    x = np.clip((lum - (t - 0.075)) / 0.15, 0.0, 1.0)
    k = x * x * (3.0 - 2.0 * x)  # smoothstep
    a = np.array(c0, dtype=np.float32)[None, None, :]
    b = np.array(c1, dtype=np.float32)[None, None, :]
    return Image.fromarray(np.clip(a + (b - a) * k[..., None], 0, 255).astype(np.uint8))


def posterize(img: Image.Image, levels: int = 0) -> Image.Image:
    """Reduce a `levels` tonos por canal. 0 o <2 = off."""
    lv = int(levels)
    if lv < 2:
        return img
    lv = min(8, lv)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    q = np.round(arr / 255.0 * (lv - 1)) / (lv - 1) * 255.0
    return Image.fromarray(np.clip(q, 0, 255).astype(np.uint8))


# Par cinematográfico fijo y documentado (el custom fino es el duotone).
_SPLIT_WARM = np.array([255.0, 170.0, 90.0], dtype=np.float32)
_SPLIT_COOL = np.array([70.0, 100.0, 255.0], dtype=np.float32)


def split_tone(img: Image.Image, strength: float = 0.0) -> Image.Image:
    """Sombras frías + luces cálidas según luminancia. 0 = off."""
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
    """Look mate: levanta los negros proporcionalmente. 0 = off."""
    s = float(amount) / 100.0
    if s <= 0:
        return img
    s = min(1.0, s)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = _luminance(arr)
    lift = s * 64.0 * (1.0 - lum) ** 2  # solo sombras, como el film matte
    return Image.fromarray(np.clip(arr + lift[..., None], 0, 255).astype(np.uint8))


__all__ = ["gradient_map", "posterize", "split_tone", "fade"]
