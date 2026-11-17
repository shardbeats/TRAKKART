"""TRAKKART cross-dissolve frame interpolation (numpy-only, MIT).

Optional smoothing between clip/dissolve frames: `steps` linear blends
inserted per gap (numpy lerp, rounded, deterministic — no seeds, no
random). Strict 0=off: amount<=0 or steps<=0 returns the inputs
untouched (identity, same objects). Default off everywhere (flicker
stays the aesthetic); callers opt in explicitly.

Cap behavior: blends are the elastic part — inputs are never dropped,
blends fill only while the total stays within `cap` (default
MAX_TOTAL_FRAMES; streaming MP4 callers pass MAX_MP4_FRAMES).
"""

from __future__ import annotations

from PIL import Image

import numpy as np

from app.anim.limits import MAX_TOTAL_FRAMES

__all__ = ["normalize_xfade", "normalize_xfade_steps", "xfade_pair",
           "xfade_frames", "xfade_stream",
           "MAX_XFADE_STEPS"]


#: Hard ceiling per gap (RAM + sanity: blends are full RGB frames).
MAX_XFADE_STEPS = 8


def normalize_xfade(amount) -> float:
    """Clamp to 0..1 (0 = off). Non-numeric -> 0."""
    try:
        return min(1.0, max(0.0, float(amount or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def normalize_xfade_steps(steps) -> int:
    """Clamp to 0..MAX_XFADE_STEPS (0 = off). Non-numeric -> 0."""
    try:
        return min(MAX_XFADE_STEPS, max(0, int(steps or 0)))
    except (TypeError, ValueError):
        return 0


def xfade_pair(a: Image.Image, b: Image.Image, t: float) -> Image.Image:
    """Single linear blend: t=0 -> A, t=1 -> B (rounded, deterministic).

    Size mismatch: B is cover-resized to A so the output stays uniform
    (morph/clip frames already share HxW; this only guards callers).
    """
    t = min(1.0, max(0.0, float(t)))
    aa = a.convert("RGB")
    bb = b.convert("RGB")
    if bb.size != aa.size:
        bb = bb.resize(aa.size, Image.BICUBIC)
    if t <= 0.0:
        return aa.copy()
    if t >= 1.0:
        return bb.copy()
    arr = np.round(np.asarray(aa, dtype=np.float32) * (1.0 - t)
                   + np.asarray(bb, dtype=np.float32) * t)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _gaps(n: int, loop: bool) -> int:
    if n < 2:
        return 0
    return n if loop else n - 1


def xfade_frames(frames, amount: float = 0.0, steps: int = 1,
                 cap: int = MAX_TOTAL_FRAMES, loop: bool = False) -> list:
    """Insert `steps` blends per gap (loop also closes last -> first).

    0=off (amount<=0 or steps<=0 or <2 frames): same objects, new list.
    Oversized requests clamp steps so blends fit `cap`; inputs are
    never dropped (n > cap returns the inputs as-is).
    """
    out = list(frames or [])
    amt = normalize_xfade(amount)
    st = normalize_xfade_steps(steps)
    n = len(out)
    if amt <= 0.0 or st <= 0 or n < 2:
        return out
    try:
        cap = max(0, int(cap))
    except (TypeError, ValueError):
        cap = MAX_TOTAL_FRAMES
    if cap < n:
        return out  # never drop inputs; blends need room that isn't there
    gaps = _gaps(n, bool(loop))
    if gaps <= 0:
        return out
    st = min(st, (cap - n) // gaps)  # cap behavior: shrink blends to fit
    if st <= 0:
        return out
    res = []
    for i, frm in enumerate(out):
        res.append(frm)
        nxt = out[(i + 1) % n] if bool(loop) else (out[i + 1] if i + 1 < n else None)
        if nxt is None:
            continue
        for k in range(1, st + 1):
            res.append(xfade_pair(frm, nxt, amt * k / (st + 1)))
    return res


def xfade_stream(frames_iter, amount: float = 0.0, steps: int = 1,
                 cap: int = MAX_TOTAL_FRAMES, loop: bool = False):
    """Streaming twin of xfade_frames: O(1) extra RAM (buffers 1 + first).

    Originals always pass through (never dropped); blends emit while
    the running total stays under `cap`. loop retains the first frame
    and closes last -> first at the end.
    """
    amt = normalize_xfade(amount)
    st = normalize_xfade_steps(steps)
    if amt <= 0.0 or st <= 0:
        yield from frames_iter
        return
    try:
        cap = max(0, int(cap))
    except (TypeError, ValueError):
        cap = MAX_TOTAL_FRAMES
    emitted = 0
    prev = None
    first = None
    for frm in frames_iter:
        if first is None:
            first = frm
        if prev is not None:
            for k in range(1, st + 1):
                if emitted >= cap:
                    break
                yield xfade_pair(prev, frm, amt * k / (st + 1))
                emitted += 1
        yield frm
        emitted += 1
        prev = frm
    if bool(loop) and prev is not None and first is not None and prev is not first:
        for k in range(1, st + 1):
            if emitted >= cap:
                break
            yield xfade_pair(prev, first, amt * k / (st + 1))
            emitted += 1
