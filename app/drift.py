"""TRAKKART Signal Drift (MIT). Numpy + Pillow only.

9 animated retro-screen noise patterns overlaid on the canvas BEFORE the
dither (so the dither eats them like a real CRT chain). Fully seeded and
deterministic: same inputs + phase = same pixels. `phase` marches the
animation, which is what VIDEO mode and GIF frames step per frame.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

DRIFT_SEED = 0xD81F

DRIFT_PATTERNS = (
    "hum_bar",
    "roll",
    "crawl",
    "snow",
    "weave",
    "flicker",
    "moire",
    "sweep",
    "jitter",
)


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(int(seed))


def drift_mask(h: int, w: int, pattern: str, phase: int = 0,
               seed: int = DRIFT_SEED) -> np.ndarray | None:
    """Float32 mask in 0..1 for one pattern. None for off/unknown."""
    if pattern not in DRIFT_PATTERNS:
        return None
    t = float(phase)
    ys = np.arange(h, dtype=np.float32)[:, None] * np.ones((1, w), dtype=np.float32)
    xs = np.arange(w, dtype=np.float32)[None, :] * np.ones((h, 1), dtype=np.float32)
    if pattern == "hum_bar":
        pos = ((t * 3.0) % (h + 40)) - 20.0
        return np.exp(-((ys - pos) ** 2) / (2.0 * 18.0 ** 2)).clip(0.0, 1.0)
    if pattern == "roll":
        return (0.5 + 0.5 * np.sin(ys * 0.08 - t * 0.6)).astype(np.float32)
    if pattern == "crawl":
        return ((((xs + ys).astype(int) + int(t)) % 2) == 0).astype(np.float32)
    if pattern == "snow":
        rng = _rng(seed + int(t) * 7919)
        return rng.random((h, w), dtype=np.float32)
    if pattern == "weave":
        off = np.sin(t * 0.5) * 2.0
        return ((((ys + off).astype(int)) % 2) == 0).astype(np.float32) * 0.5 + 0.25
    if pattern == "flicker":
        v = 0.5 + 0.28 * np.sin(t * 0.9) + 0.12 * np.sin(t * 2.7 + 1.3)
        return np.full((h, w), np.clip(v, 0.0, 1.0), dtype=np.float32)
    if pattern == "moire":
        return (0.5 + 0.5 * np.sin((xs + ys) * 0.11 + t * 0.4)
                * np.sin((xs - ys) * 0.07 - t * 0.3)).astype(np.float32)
    if pattern == "sweep":
        pos = ((t * 5.0) % (w + 80)) - 40.0
        return np.exp(-((xs - pos) ** 2) / (2.0 * 30.0 ** 2)).clip(0.0, 1.0)
    if pattern == "jitter":
        return (0.5 + 0.5 * np.sin(ys * 0.5 + np.sin(t * 0.7 + ys * 0.02) * 3.0)).astype(np.float32)
    return None  # pragma: no cover


def apply_drift(img: Image.Image, pattern: str = "off", amount: float = 0.0,
                phase: int = 0, seed: int = DRIFT_SEED) -> Image.Image:
    """Blend a drift mask over the image. amount 0-100, 0/off = no-op."""
    amt = float(amount or 0.0)
    if amt <= 0 or pattern not in DRIFT_PATTERNS:
        return img
    amt = min(100.0, max(0.0, amt))
    base = img.convert("RGB")
    h, w = base.height, base.width
    mask = drift_mask(h, w, pattern, phase=int(phase), seed=int(seed))
    if mask is None:
        return img
    arr = np.asarray(base, dtype=np.float32)
    # ±amt around mid gray: subtle at low values, trasher at 100.
    out = arr + (mask - 0.5)[..., None] * (2.0 * amt)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


__all__ = ["DRIFT_PATTERNS", "DRIFT_SEED", "apply_drift", "drift_mask"]
