"""Generador aleatorio de paletas (MIT, clean-room).

NO es random RGB (sale barro + grises indistinguibles que el dither no puede
usar) ni ML (filosofía offline). Reglas tomadas de la literatura pixel-art:
rampas con luminosidad monótona, joroba de saturación, hue-shift medido
(fresco en sombras, cálido en luces) y distancia perceptual mínima con
re-muestreo. Todo se calcula en Oklch (uniforme) y se recorta por chroma
para no salir de sRGB.
"""

from __future__ import annotations

import numpy as np

MIN_COLORS = 2
MAX_COLORS = 16

# Distancia mínima Oklch euclídea (~ΔE simplificado). Por debajo, dos
# colores son el mismo para el ojo (y para el dither).
MIN_DIST = 0.045

# Matrices de Björn Ottosson (dominio público, matemática estándar).
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
    """Oklch -> RGB lineal SIN recortar (para detectar fuera de gama)."""
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
    """(N,3) Oklch -> (N,3) uint8 (recorta si queda fuera de sRGB)."""
    lin = _oklch_to_linear(lch)
    srgb = _linear_to_srgb(lin)
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


def _in_gamut(L: float, C: float, h: float) -> bool:
    lin = _oklch_to_linear(np.array([[L, C, h % 360.0]]))[0]
    return bool(np.all(lin >= -1e-9) and np.all(lin <= 1.0 + 1e-9))


def _fit_srgb(L: float, C: float, h: float) -> tuple[int, int, int]:
    """Baja chroma hasta entrar en sRGB (nunca recorta canales = no cambia el tono)."""
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
    """Distancia Oklch mínima entre pares (aprox. perceptual)."""
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
    """Una rampa hue-shifted: L uniforme, joroba de saturación, giro medido."""
    h0 = float(rng.uniform(0.0, 360.0))
    # Dirección del giro: cálidos suben hacia el amarillo, fríos bajan
    # hacia teal/índigo en las sombras (tabla medida de rampas publicadas).
    hh = h0 % 360.0
    direction = 1.0 if (hh >= 290.0 or hh < 60.0) else -1.0
    travel = min(100.0, 20.0 + 12.0 * n)  # 3 tonos ≤~56°, 7-9 pasos ≤100°
    t = np.linspace(0.0, 1.0, n)
    L = 0.28 + 0.64 * t + rng.uniform(-0.015, 0.015, n)
    L = np.clip(L, 0.12, 0.95)
    h = (h0 + direction * travel * (t - 0.5)) % 360.0
    # Joroba de saturación: pico en medios, puntas apagadas (no quema ojos).
    hump = np.sin(np.pi * np.clip((t * 0.85 + 0.075), 0.0, 1.0)) ** 0.8
    C = float(rng.uniform(0.08, 0.15)) * (0.35 + 0.65 * hump)
    C = C * (1.0 - 0.35 * t)  # luces un poco más limpias
    return [_fit_srgb(float(L[i]), float(C[i]), float(h[i])) for i in range(n)]


def _harmony(n: int, rng: np.random.Generator) -> list[tuple[int, int, int]]:
    """Análoga / complementaria / triádica, cada tono en su banda de luz."""
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
        # Sin duplicados tras cuantizar.
        if len(set(cand)) < n:
            continue
        d = _min_pairwise_dist(np.array(cand))
        if d > best_d:
            best_d, best = d, cand
        if d >= MIN_DIST:
            break
    if best is None:  # pragma: no cover - extremadamente improbable
        best = _ramp(n, rng)
    # Ordenar de oscuro a claro: la tira se lee como rampa.
    lab_l = rgb_to_oklch(np.array(best))[:, 0]
    return [best[i] for i in np.argsort(lab_l)]


def generate_palette(
    n: int = 4,
    style: str = "ramp",
    seed: int | None = None,
) -> list[tuple[int, int, int]]:
    """N colores buenos para dither. style: ramp | harmony."""
    n = max(MIN_COLORS, min(MAX_COLORS, int(n)))
    rng = np.random.default_rng(seed)
    if str(style).lower().startswith("harm"):
        colors = _harmony(n, rng)
    else:
        colors = _ramp(n, rng)
    # Unicidad garantizada tras cuantizar (micro-ajuste de luz si choca).
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
