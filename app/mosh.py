"""TRAKKART datamosh module (MIT). Pure numpy + Pillow.

Seven codec-damage flavors, all deterministic (per-mode base seed plus a
user `seed` variation plus an optional frame offset, so GIF animation
crawls instead of flickering) and all identity at amount <= 0 (off-safe,
like the rest of the FX):

- blocks  = random displaced blocks (legacy datamosh, byte-identical
            at size=100).
- smear   = coherent horizontal drag (motion-vector streaks).
- ghost   = displaced low-opacity duplicate (P-frame echo).
- rows    = repeated rows (corrupt-decode banding).
- chroma  = per-block R/B split (chroma-plane drift).
- crush   = macroblock posterize (quantization banding).
- speckle = burst blocks to black/white (bit-flip hits).

`size` (percent, 100 = classic) scales each mode's feature size; `seed`
re-rolls the damage pattern. `apply_mosh()` dispatches (unknown mode
falls back to blocks, same rule as the GIF modes). `glitch.datamosh`
stays as a thin compat wrapper.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

MOSH_MODES = ("blocks", "smear", "ghost", "rows", "chroma", "crush", "speckle")

_SEEDS = {
    "blocks": 0x405,
    "smear": 0x5EA2,
    "ghost": 0x6B05,
    "rows": 0x20D5,
    "chroma": 0xC420,
    "crush": 0xC245,
    "speckle": 0x5EC4,
}


def _arr(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("RGB"))


def _scale(v: int, size: float) -> int:
    """Scale a drawn quantity; size=100 reproduces the input exactly."""
    return max(1, int(round(v * size / 100.0)))


def mosh_blocks(img: Image.Image, amount: float = 0.0, seed: int = 0x405,
                size: int = 100) -> Image.Image:
    """Random displaced blocks (legacy datamosh). 0 = off."""
    a = float(amount)
    if a <= 0:
        return img
    arr = _arr(img)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(int(seed))
    n_blocks = max(1, int(a / 100.0 * 24))
    out = arr.copy()
    for _ in range(n_blocks):
        bw = _scale(int(rng.integers(16, max(17, w // 4))), size)
        bh = _scale(int(rng.integers(8, max(9, h // 8))), size)
        bw, bh = min(bw, w), min(bh, h)
        x0 = int(rng.integers(0, max(1, w - bw)))
        y0 = int(rng.integers(0, max(1, h - bh)))
        dx = int(rng.integers(-w // 6, w // 6 + 1))
        block = arr[y0:y0 + bh, x0:x0 + bw].copy()
        x1 = min(w - bw, max(0, x0 + dx))
        out[y0:y0 + bh, x1:x1 + bw] = block
    return Image.fromarray(out)


def mosh_smear(img: Image.Image, amount: float = 0.0, seed: int = 0x5EA2,
               size: int = 100) -> Image.Image:
    """Coherent horizontal drag: every row shifts, neighbors agree (streaks)."""
    a = float(amount)
    if a <= 0:
        return img
    arr = _arr(img)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(int(seed))
    amp = a / 100.0 * max(8.0, w / 8.0)
    phase = float(rng.uniform(0.0, 6.2831853))
    period = max(24.0, h / 5.0) * max(0.1, size / 100.0)
    raw = np.sin(np.arange(h, dtype=np.float32) / period * 6.2831853 + phase)
    raw += rng.uniform(-0.35, 0.35, size=h).astype(np.float32)
    offsets = np.round(raw * amp).astype(int)
    out = np.empty_like(arr)
    for y in range(h):
        out[y] = np.roll(arr[y], int(offsets[y]), axis=0)
    return Image.fromarray(out)


def mosh_ghost(img: Image.Image, amount: float = 0.0, seed: int = 0x6B05,
               size: int = 100) -> Image.Image:
    """Displaced low-opacity duplicate (motion echo). 0 = off."""
    a = float(amount)
    if a <= 0:
        return img
    arr = _arr(img).astype(np.float32)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(int(seed))
    span = a / 100.0
    k = max(0.1, size / 100.0)
    dx = int(round(float(rng.uniform(-1.0, 1.0)) * w / 6.0 * span * k))
    dy = int(round(float(rng.uniform(-1.0, 1.0)) * h / 12.0 * span * k))
    mix = 0.15 + 0.30 * span
    shifted = np.roll(np.roll(arr, dx, axis=1), dy, axis=0)
    out = np.clip(arr * (1.0 - mix) + shifted * mix, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def mosh_rows(img: Image.Image, amount: float = 0.0, seed: int = 0x20D5,
              size: int = 100) -> Image.Image:
    """Repeat random rows over bands (corrupt-decode look). 0 = off."""
    a = float(amount)
    if a <= 0:
        return img
    arr = _arr(img)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(int(seed))
    n_bands = max(1, int(a / 100.0 * 12))
    idx = np.arange(h)
    for _ in range(n_bands):
        bh = _scale(int(rng.integers(2, max(3, h // 24))), size)
        y0 = int(rng.integers(0, max(1, h - bh)))
        idx[y0:y0 + bh] = y0
    return Image.fromarray(arr[idx])


def mosh_chroma(img: Image.Image, amount: float = 0.0, seed: int = 0xC420,
                size: int = 100) -> Image.Image:
    """Per-block R/B split on a macroblock grid. 0 = off."""
    a = float(amount)
    if a <= 0:
        return img
    arr = _arr(img)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(int(seed))
    n_blocks = max(1, int(a / 100.0 * 16))
    cell = max(4, int(round(16 * size / 100.0)))
    out = arr.copy()
    for _ in range(n_blocks):
        bw = int(rng.integers(1, max(2, w // cell))) * cell
        bh = int(rng.integers(1, max(2, h // cell))) * cell
        bw, bh = min(bw, w), min(bh, h)
        x0 = int(rng.integers(0, max(1, w - bw)))
        y0 = int(rng.integers(0, max(1, h - bh)))
        dx = int(rng.integers(2, max(3, w // 32)))
        blk = arr[y0:y0 + bh, x0:x0 + bw]
        shifted = out[y0:y0 + bh, x0:x0 + bw].copy()
        shifted[..., 0] = np.roll(blk[..., 0], dx, axis=1)
        shifted[..., 2] = np.roll(blk[..., 2], -dx, axis=1)
        out[y0:y0 + bh, x0:x0 + bw] = shifted
    return Image.fromarray(out)


def mosh_crush(img: Image.Image, amount: float = 0.0, seed: int = 0xC245,
               size: int = 100) -> Image.Image:
    """Macroblock posterize: quantization banding with per-block jitter."""
    a = float(amount)
    if a <= 0:
        return img
    arr = _arr(img).astype(np.float32)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(int(seed))
    levels = max(2, 8 - int(a / 100.0 * 6))
    step = 256.0 / levels
    cell = max(4, int(round(16 * size / 100.0)))
    out = np.floor(arr / step + 0.5) * step
    for y0 in range(0, h, cell):
        for x0 in range(0, w, cell):
            if rng.random() < a / 100.0 * 0.5:
                blk = out[y0:y0 + cell, x0:x0 + cell]
                blk += float(rng.uniform(-step / 2.0, step / 2.0))
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def mosh_speckle(img: Image.Image, amount: float = 0.0, seed: int = 0x5EC4,
                 size: int = 100) -> Image.Image:
    """Burst blocks forced to black/white (bit-flip hits). 0 = off."""
    a = float(amount)
    if a <= 0:
        return img
    arr = _arr(img)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(int(seed))
    n_blocks = max(1, int(a / 100.0 * 20))
    out = arr.copy()
    for _ in range(n_blocks):
        bw = _scale(int(rng.integers(4, max(5, w // 8))), size)
        bh = _scale(int(rng.integers(4, max(5, h // 8))), size)
        bw, bh = min(bw, w), min(bh, h)
        x0 = int(rng.integers(0, max(1, w - bw)))
        y0 = int(rng.integers(0, max(1, h - bh)))
        v = 255 if rng.random() < 0.5 else 0
        out[y0:y0 + bh, x0:x0 + bw] = v
    return Image.fromarray(out)


_FNS = {
    "blocks": mosh_blocks,
    "smear": mosh_smear,
    "ghost": mosh_ghost,
    "rows": mosh_rows,
    "chroma": mosh_chroma,
    "crush": mosh_crush,
    "speckle": mosh_speckle,
}


def apply_mosh(img: Image.Image, mode: str = "blocks",
               amount: float = 0.0, seed: int = 0, size: int = 100) -> Image.Image:
    """Dispatch by mode (unknown falls back to blocks, same rule as GIF modes)."""
    fn = _FNS.get(str(mode), mosh_blocks)
    base = _SEEDS.get(str(mode), _SEEDS["blocks"])
    return fn(img, amount=amount, seed=int(base) + int(seed), size=int(size))


__all__ = ["MOSH_MODES", "apply_mosh"] + [f"mosh_{m}" for m in MOSH_MODES]
