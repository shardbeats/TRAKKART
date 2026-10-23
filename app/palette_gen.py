"""Random palette generator (MIT).

NOT random RGB (that yields mud + indistinguishable grays the dither cannot
use) nor ML (offline philosophy). Rules follow standard pixel-art practice:
ramps with monotonic lightness, saturation hump, measured hue-shift
(cool in shadows, warm in lights) and minimum perceptual distance with
re-sampling. Everything is computed in Oklch (uniform) and chroma-clipped
to stay inside sRGB.
"""

from __future__ import annotations

import numpy as np

MIN_COLORS = 2
MAX_COLORS = 16

# Minimum euclidean Oklch distance (~simplified ΔE). Below it, two
# colors are the same to the eye (and to the dither).
MIN_DIST = 0.045

# Björn Ottosson's matrices (public domain, standard math).
_M1 = np.array(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ],
    dtype=np.float64,
)
_M1_INV = np.linalg.inv(_M1)


def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1.0 / 2.4)) - 0.055)


def rgb_to_oklch(rgb: np.ndarray) -> np.ndarray:
    """(N,3) uint8/float -> (N,3) Oklch [L, C, h°]."""
    lin = _srgb_to_linear(np.asarray(rgb, dtype=np.float64).reshape(-1, 3))
    lms = lin @ _M1.T
    lms_cbrt = np.cbrt(np.maximum(lms, 0.0))
    lab = lms_cbrt @ np.array(
        [
            [0.2104542553, 0.7936177850, -0.0040720468],
            [1.9779984951, -2.4285922050, 0.4505937099],
            [0.0259040371, 0.7827717662, -0.8086757660],
        ]
    ).T
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]
    C = np.hypot(a, b)
    h = np.degrees(np.arctan2(b, a)) % 360.0
    return np.stack([L, C, h], axis=1)


def _oklch_to_linear(lch: np.ndarray) -> np.ndarray:
    """Oklch -> linear RGB WITHOUT clipping (to detect out-of-gamut)."""
    lch = np.asarray(lch, dtype=np.float64).reshape(-1, 3)
    L, C, h = lch[:, 0], lch[:, 1], lch[:, 2]
    a = C * np.cos(np.radians(h))
    b = C * np.sin(np.radians(h))
    lab = np.stack([L, a, b], axis=1)
    lms = lab @ np.linalg.inv(
        np.array(
            [
                [0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660],
            ]
        )
    ).T
    return (np.maximum(lms, 0.0) ** 3) @ _M1_INV.T


def oklch_to_rgb(lch: np.ndarray) -> np.ndarray:
    """(N,3) Oklch -> (N,3) uint8 (clips when out of sRGB)."""
    lin = _oklch_to_linear(lch)
    srgb = _linear_to_srgb(lin)
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


def _in_gamut(L: float, C: float, h: float) -> bool:
    lin = _oklch_to_linear(np.array([[L, C, h % 360.0]]))[0]
    return bool(np.all(lin >= -1e-9) and np.all(lin <= 1.0 + 1e-9))


def _fit_srgb(L: float, C: float, h: float) -> tuple[int, int, int]:
    """Lowers chroma until inside sRGB (never clips channels = hue is kept)."""
    C = max(0.0, float(C))
    for _ in range(24):
        if _in_gamut(L, C, h):
            rgb = oklch_to_rgb(np.array([[L, C, h % 360.0]]))[0]
            return (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        C *= 0.92
        if C < 0.004:
            break
    gray = int(round(np.clip(L, 0.0, 1.0) * 255))
    return (gray, gray, gray)


def _min_pairwise_dist(colors: np.ndarray) -> float:
    """Minimum pairwise Oklch distance (approx. perceptual)."""
    lch = rgb_to_oklch(colors)
    lab = np.stack([lch[:, 0], lch[:, 1] * np.cos(np.radians(lch[:, 2])),
                    lch[:, 1] * np.sin(np.radians(lch[:, 2]))], axis=1)
    d = np.sqrt(((lab[:, None, :] - lab[None, :, :]) ** 2).sum(axis=-1))
    n = len(lab)
    if n < 2:
        return float("inf")
    iu = np.triu_indices(n, k=1)
    return float(d[iu].min())


def _luminance_spread(colors: np.ndarray) -> float:
    return float(rgb_to_oklch(colors)[:, 0].max() - rgb_to_oklch(colors)[:, 0].min())


def _ramp(n: int, rng: np.random.Generator) -> list[tuple[int, int, int]]:
    """A hue-shifted ramp: uniform L, saturation hump, measured turn."""
    h0 = float(rng.uniform(0.0, 360.0))
    # Turn direction: warms rise toward yellow, cools drop
    # toward teal/indigo in the shadows (measured table of published ramps).
    hh = h0 % 360.0
    direction = 1.0 if (hh >= 290.0 or hh < 60.0) else -1.0
    travel = min(100.0, 20.0 + 12.0 * n)  # 3 tones ≤~56°, 7-9 steps ≤100°
    t = np.linspace(0.0, 1.0, n)
    L = 0.28 + 0.64 * t + rng.uniform(-0.015, 0.015, n)
    L = np.clip(L, 0.12, 0.95)
    h = (h0 + direction * travel * (t - 0.5)) % 360.0
    # Saturation hump: peak in the mids, muted tips (no eye burn).
    hump = np.sin(np.pi * np.clip((t * 0.85 + 0.075), 0.0, 1.0)) ** 0.8
    C = float(rng.uniform(0.08, 0.15)) * (0.35 + 0.65 * hump)
    C = C * (1.0 - 0.35 * t)  # slightly cleaner lights
    return [_fit_srgb(float(L[i]), float(C[i]), float(h[i])) for i in range(n)]


def _harmony(n: int, rng: np.random.Generator) -> list[tuple[int, int, int]]:
    """Analogous / complementary / triadic, each hue in its light band."""
    templates = {
        "analogous": [0.0, 28.0, -28.0, 55.0, -55.0],
        "complementary": [0.0, 180.0, 25.0, 205.0, -25.0],
        "triadic": [0.0, 120.0, 240.0, 60.0, 300.0],
    }
    names = list(templates)
    best: list[tuple[int, int, int]] | None = None
    best_d = -1.0
    for _ in range(60):
        name = names[int(rng.integers(0, len(names)))]
        offs = templates[name]
        h0 = float(rng.uniform(0.0, 360.0))
        hues = [(h0 + offs[i % len(offs)] + rng.uniform(-8.0, 8.0)) % 360.0 for i in range(n)]
        L = np.linspace(0.30, 0.90, n)
        rng.shuffle(L)
        C = rng.uniform(0.07, 0.15, n)
        cand = [_fit_srgb(float(L[i]), float(C[i]), float(hues[i])) for i in range(n)]
        # No duplicates after quantizing.
        if len(set(cand)) < n:
            continue
        d = _min_pairwise_dist(np.array(cand))
        if d > best_d:
            best_d, best = d, cand
        if d >= MIN_DIST:
            break
    if best is None:  # pragma: no cover - extremely unlikely
        best = _ramp(n, rng)
    # Sort dark to light: the strip reads as a ramp.
    lab_l = rgb_to_oklch(np.array(best))[:, 0]
    return [best[i] for i in np.argsort(lab_l)]


def generate_palette(
    n: int = 4,
    style: str = "ramp",
    seed: int | None = None,
) -> list[tuple[int, int, int]]:
    """N good colors for dither. style: ramp | harmony."""
    n = max(MIN_COLORS, min(MAX_COLORS, int(n)))
    rng = np.random.default_rng(seed)
    if str(style).lower().startswith("harm"):
        colors = _harmony(n, rng)
    else:
        colors = _ramp(n, rng)
    # Uniqueness guaranteed after quantizing (light micro-tweak on clash).
    out: list[tuple[int, int, int]] = []
    for c in colors:
        cc = c
        for _ in range(8):
            if cc not in out:
                break
            lch = rgb_to_oklch(np.array([cc], dtype=np.float64))[0]
            cc = _fit_srgb(min(0.97, lch[0] + 0.03), max(0.004, lch[1]), lch[2])
        out.append(cc)
    return out[:n]


__all__ = [
    "MAX_COLORS",
    "MIN_COLORS",
    "MIN_DIST",
    "generate_palette",
    "oklch_to_rgb",
    "rgb_to_oklch",
]
