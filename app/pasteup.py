"""TRAKKART Paste-Up overlays (MIT). Numpy + Pillow only.

Procedural paper/texture overlays generated in-app (no image files, so
presets stay portable and offline): paper grain, riso tooth, fiber
streaks. Blended over the dithered image post-dither as the `pasteup`
stack effect. Seeded + deterministic.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

PASTE_MODES = ("off", "paper", "riso", "fiber")
PASTE_BLOTS = ("overlay", "multiply", "screen")
PASTE_SEED = 0x9A57


def make_texture(h: int, w: int, mode: str = "paper", seed: int = PASTE_SEED) -> np.ndarray:
    """Grayscale RGB texture 0..255 for blending. Deterministic per size+mode."""
    if mode not in PASTE_MODES or mode == "off":
        return np.full((h, w, 3), 128.0, dtype=np.float32)
    rng = np.random.default_rng(int(seed) + len(mode) * 131)
    if mode == "paper":
        grain = rng.random((h, w), dtype=np.float32) * 46.0
        cw = max(1, -(-w // 6))
        fib = (rng.random((h, cw), dtype=np.float32) > 0.93).astype(np.float32)
        fibers = np.repeat(fib, 6, axis=1)[:, :w] * 22.0
        tex = 128.0 + grain - 23.0 + fibers - 11.0
    elif mode == "riso":
        coarse_h, coarse_w = max(1, -(-h // 5)), max(1, -(-w // 5))
        coarse = rng.random((coarse_h, coarse_w), dtype=np.float32)
        tex = np.repeat(np.repeat(coarse, 5, axis=0), 5, axis=1)[:h, :w] * 70.0 + 93.0
    else:  # fiber: long horizontal streaks + speckle
        rows = rng.random((h, 1), dtype=np.float32)
        streak = np.repeat(rows, w, axis=1) * 40.0
        speck = (rng.random((h, w), dtype=np.float32) > 0.985).astype(np.float32) * 60.0
        tex = 128.0 + streak - 20.0 + speck - 30.0
    gray = np.clip(tex, 0.0, 255.0).astype(np.float32)
    return np.stack([gray, gray, gray], axis=-1)


def _blend_overlay(base: np.ndarray, tex: np.ndarray) -> np.ndarray:
    b, t = base / 255.0, tex / 255.0
    out = np.where(b <= 0.5, 2 * b * t, 1 - 2 * (1 - b) * (1 - t))
    return out * 255.0


def _blend_multiply(base: np.ndarray, tex: np.ndarray) -> np.ndarray:
    return base * tex / 255.0


def _blend_screen(base: np.ndarray, tex: np.ndarray) -> np.ndarray:
    return 255.0 - (255.0 - base) * (255.0 - tex) / 255.0


def apply_paste(img: Image.Image, mode: str = "off", opacity: float = 0.0,
                blend: str = "overlay", seed: int = PASTE_SEED) -> Image.Image:
    """Overlay a procedural texture. opacity 0-100, 0/off = no-op."""
    op = float(opacity or 0.0)
    if op <= 0 or mode not in PASTE_MODES or mode == "off":
        return img
    op = min(100.0, max(0.0, op)) / 100.0
    base = img.convert("RGB")
    h, w = base.height, base.width
    tex = make_texture(h, w, mode=mode, seed=int(seed))
    arr = np.asarray(base, dtype=np.float32)
    if blend == "multiply":
        mixed = _blend_multiply(arr, tex)
    elif blend == "screen":
        mixed = _blend_screen(arr, tex)
    else:
        mixed = _blend_overlay(arr, tex)
    out = arr + (mixed - arr) * op
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


__all__ = ["PASTE_BLOTS", "PASTE_MODES", "PASTE_SEED", "apply_paste", "make_texture"]
