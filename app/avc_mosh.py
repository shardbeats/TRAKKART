"""TRAKKART true-AVC datamosh engine, Phase A (frame-level, portable).

Codec-level datamosh (single keyframe + dropped/repeated P-frames at
segment cuts = real motion bleed) needs bitstream surgery that the
portable exe cannot rely on. Phase A ships the portable subset as a
deterministic frame-level emulation over the already-rendered clip
(Pillow + numpy only, no ffmpeg needed):

- `bleed` = at each segment cut, the next N frames blend the previous
  segment's last frame with a decaying alpha (motion-vector bleed).
- `smear`  = coherent horizontal drag localized at the cut window.
- `hold`   = repeat the cut frame N times (P-frame repeat).

Strict 0=off: `bleed <= 0` yields the input untouched (passthrough,
same objects). Deterministic: cut positions + blend masks derive from
`seed` (reuse `dissolve_seed` at the call site). Unknown mode falls
back to `bleed` (same rule as `app.mosh.apply_mosh`).

Phase B will wire segments into `app/anim/plan.py`; Phase C adds the
real single-keyframe re-encode behind `has_video()`. This module stays
backend-free on purpose so stills/GIF paths never break without video.
"""

from __future__ import annotations

from typing import Iterable, Iterator

import numpy as np
from PIL import Image

AVC_MODES = ("bleed", "smear", "hold")


def plan_cuts(n_frames: int, n_segs: int, seed: int = 0) -> list[int]:
    """Deterministic cut positions for `n_segs` segments over a clip.

    Returns the `n_segs - 1` interior cut indices (frame starting each
    new segment), evenly spaced with a seeded jitter of +-1 so the same
    seed replays the same plan. Empty for `n_segs <= 1`.
    """
    n = max(0, int(n_frames))
    segs = max(1, int(n_segs))
    if segs <= 1 or n <= 2:
        return []
    rng = np.random.default_rng(int(seed))
    base = [round(n * k / segs) for k in range(1, segs)]
    jitter = rng.integers(-1, 2, size=len(base))
    cuts = sorted({min(n - 1, max(1, int(b + j))) for b, j in zip(base, jitter)})
    return cuts


def _blend(a: Image.Image, b: Image.Image, alpha: float) -> Image.Image:
    arr_a = np.asarray(a.convert("RGB"), dtype=np.float32)
    arr_b = np.asarray(b.convert("RGB"), dtype=np.float32)
    out = np.clip(arr_a * (1.0 - alpha) + arr_b * alpha, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def _smear_band(frame: Image.Image, strength: float, seed: int) -> Image.Image:
    """Coherent horizontal drag (cut-local echo of `mosh_smear`)."""
    arr = np.asarray(frame.convert("RGB"))
    h, w = arr.shape[:2]
    if h == 0 or w == 0:
        return frame
    rng = np.random.default_rng(int(seed))
    amp = max(1.0, float(strength) * max(4.0, w / 32.0))
    phase = float(rng.uniform(0.0, 6.2831853))
    period = max(8.0, h / 4.0)
    raw = np.sin(np.arange(h, dtype=np.float32) / period * 6.2831853 + phase)
    offsets = np.round(raw * amp).astype(int)
    out = np.empty_like(arr)
    for y in range(h):
        out[y] = np.roll(arr[y], int(offsets[y]), axis=0)
    return Image.fromarray(out)


def avc_mosh_frames(frames: Iterable[Image.Image], bleed: int = 0,
                    mode: str = "bleed", seed: int = 0,
                    n_segs: int = 1) -> Iterator[Image.Image]:
    """Stream frames with the AVC cut effect applied (O(1) memory).

    `bleed` 0-60 = influence window per cut (0 = passthrough). `mode`
    selects bleed | smear | hold (unknown -> bleed). `n_segs` is the
    segment count; cuts come from `plan_cuts(len, n_segs, seed)` when
    the input is a sized sequence, else evenly from a running count.
    `hold` repeats the cut frame `bleed` times (callers count repeats
    for the Length budget in Phase B).
    """
    b = max(0, int(bleed or 0))
    m = str(mode or "bleed")
    if m not in AVC_MODES:
        m = "bleed"
    buf = list(frames) if not hasattr(frames, "__next__") else list(frames)
    n = len(buf)
    if b <= 0 or n == 0:
        yield from buf
        return
    cuts = sorted(plan_cuts(n, max(1, int(n_segs or 1)), int(seed)))
    cut_set = set(cuts)
    for i, frame in enumerate(buf):
        if i in cut_set:
            if m == "hold":
                for _ in range(b):
                    yield buf[i - 1] if i > 0 else frame
                yield frame
                continue
            if m == "smear":
                yield _smear_band(frame, strength=b / 10.0,
                                 seed=int(seed) + i)
                continue
        if m == "bleed" and i > 0:
            past = [c for c in cuts if c <= i]
            if past:
                d = past[-1]
                k = i - d + 1
                if 1 <= k <= b and d > 0:
                    alpha = max(0.0, min(1.0, 0.75 * (1.0 - k / (b + 1))))
                    yield _blend(frame, buf[d - 1], alpha)
                    continue
        yield frame


def apply_avc_mosh(frames: list[Image.Image], bleed: int = 0,
                   mode: str = "bleed", seed: int = 0,
                   n_segs: int = 1) -> list[Image.Image]:
    """List convenience over `avc_mosh_frames` (same order, new list)."""
    return list(avc_mosh_frames(frames, bleed=bleed, mode=mode,
                                seed=seed, n_segs=n_segs))


__all__ = ["AVC_MODES", "plan_cuts", "avc_mosh_frames", "apply_avc_mosh"]
