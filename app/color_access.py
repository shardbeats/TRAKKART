"""Color confidence (v1.9 Fase C, GPL-3.0-only): daltonism preview, WCAG contrast,
Lospec-compatible offline palette parsers. Numpy + Pillow only, offline.

Daltonism preview is display-only (like the safe-area guides and the
SP-404 OLED preview): it never touches document pixels. `simulate_cvd`
maps an RGB image through a 3x3 dichromacy matrix (Viénot-style,
deterministic); unknown kinds raise, "off"/"none"/"" returns a copy.

WCAG contrast follows WCAG 2.1 (relative luminance + 1.05 ratio):
`contrast_ratio(a, b)` for two RGB colors, `accessibility_report`
over adjacent palette inks (3:1 graphics floor, 1.5 BW-collapse floor:
neighboring inks that light-print to nearly the same gray).

Parsers read palette files from disk (local files only, no network):
GIMP .gpl lives in `app.palette_library`; .hex/.txt (one #RRGGBB per
line) and JASC .pal live here. All validate to 2-16 colors (>16
truncates to the first 16, deterministic).
"""

from __future__ import annotations

import re

from PIL import Image

#: Preview-only CVD simulations (Viénot-style dichromacy, row = output).
CVD_MATRICES: dict[str, tuple[tuple[float, float, float], ...]] = {
    "protan": ((0.567, 0.433, 0.0),
               (0.558, 0.442, 0.0),
               (0.0, 0.242, 0.758)),
    "deutan": ((0.625, 0.375, 0.0),
               (0.7, 0.3, 0.0),
               (0.0, 0.3, 0.7)),
    "tritan": ((0.95, 0.05, 0.0),
               (0.0, 0.433, 0.567),
               (0.0, 0.475, 0.525)),
}

CVD_KINDS: tuple[str, ...] = ("protan", "deutan", "tritan")

#: WCAG floors used by the report (graphics vs BW-collapse).
CONTRAST_FLOOR = 3.0
COLLAPSE_FLOOR = 1.5

_HEX6 = re.compile(r"#?([0-9a-fA-F]{6})\b")


def _norm_kind(kind: str) -> str:
    return str(kind or "").strip().lower()


def simulate_cvd(img: Image.Image, kind: str) -> Image.Image:
    """Simulated dichromacy view of an RGB image (display-only copy)."""
    import numpy as np

    k = _norm_kind(kind)
    if k in ("", "off", "none"):
        return img.convert("RGB").copy()
    if k not in CVD_MATRICES:
        raise ValueError(f"unknown CVD kind: {kind!r} (off/protan/deutan/tritan)")
    m = np.asarray(CVD_MATRICES[k], dtype=np.float64)
    arr = np.asarray(img.convert("RGB"), dtype=np.float64)
    out = arr @ m.T
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode="RGB")


def _lin_channel(c: float) -> float:
    c = float(c) / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb) -> float:
    """WCAG 2.1 relative luminance of an RGB color (0..1)."""
    r, g, b = (max(0, min(255, int(v))) for v in rgb)
    return 0.2126 * _lin_channel(r) + 0.7152 * _lin_channel(g) + 0.0722 * _lin_channel(b)


def contrast_ratio(a, b) -> float:
    """WCAG 2.1 contrast ratio of two RGB colors (1..21)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = (la, lb) if la >= lb else (lb, la)
    return (hi + 0.05) / (lo + 0.05)


def rgb_to_hex(rgb) -> str:
    r, g, b = (max(0, min(255, int(v))) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def accessibility_report(colors) -> dict:
    """Adjacent-ink contrast report for a palette strip.

    Returns {min_ratio, low_pairs: [(i, j, ratio)], bw_collapse: bool,
    message: str}. low = ratio < 3:1 (WCAG non-text floor); collapse =
    any adjacent pair < 1.5:1 (prints as one gray). Empty/single palettes
    report min 0.0 with an explanatory message (nothing to compare).
    """
    cols = [tuple(max(0, min(255, int(v))) for v in c) for c in (colors or [])]
    if len(cols) < 2:
        return {"min_ratio": 0.0, "low_pairs": [], "bw_collapse": False,
                "message": "need 2+ inks to check contrast"}
    pairs: list[tuple[int, int, float]] = []
    for i in range(len(cols) - 1):
        pairs.append((i, i + 1, contrast_ratio(cols[i], cols[i + 1])))
    low = [(i, j, r) for i, j, r in pairs if r < CONTRAST_FLOOR]
    collapse = any(r < COLLAPSE_FLOOR for _, _, r in pairs)
    worst = min(pairs, key=lambda p: p[2])
    if collapse:
        i, j, r = worst
        msg = (f"BW-collapse: {rgb_to_hex(cols[i])}~{rgb_to_hex(cols[j])} "
               f"({r:.1f}:1) prints as one gray")
    elif low:
        i, j, r = worst
        msg = (f"low contrast {rgb_to_hex(cols[i])} vs {rgb_to_hex(cols[j])} "
               f"({r:.1f}:1 < 3:1, {len(low)} pair(s))")
    else:
        msg = f"contrast ok (min {worst[2]:.1f}:1 across {len(pairs)} pair(s))"
    return {"min_ratio": worst[2], "low_pairs": low,
            "bw_collapse": bool(collapse), "message": msg}


def _tok_to_rgb(tok: str) -> tuple[int, int, int] | None:
    t = tok.strip().lstrip("#").strip()
    if len(t) == 3 and all(c in "0123456789abcdefABCDEF" for c in t):
        t = "".join(c * 2 for c in t)
    if len(t) == 6 and all(c in "0123456789abcdefABCDEF" for c in t):
        return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))
    return None


def parse_hex(text: str, name: str = "imported") -> tuple[str, list[tuple[int, int, int]]]:
    """One #RRGGBB (or RRGGBB) per line; ignores blanks and junk lines."""
    from app.fx import normalize_custom_palette

    colors: list[tuple[int, int, int]] = []
    for line in str(text or "").splitlines():
        s = line.strip()
        if not s or s.startswith(";") or s.lower().startswith("//"):
            continue
        rgb = _tok_to_rgb(s.split()[0].split(",")[0].split(";")[0])
        if rgb is None:
            m = _HEX6.search(s)
            rgb = _tok_to_rgb(m.group(1)) if m else None
        if rgb is not None and rgb not in colors:
            colors.append(rgb)
    valid = normalize_custom_palette(colors[:16])
    if valid is None:
        raise ValueError(".hex needs 2-16 valid colors (one #RRGGBB per line)")
    return (str(name or "imported").strip() or "imported", valid)


def parse_txt(text: str, name: str = "imported") -> tuple[str, list[tuple[int, int, int]]]:
    """Lospec-style .txt (same line format as .hex)."""
    return parse_hex(text, name=name)


def parse_pal(text: str, name: str = "imported") -> tuple[str, list[tuple[int, int, int]]]:
    """JASC-PAL text palettes (offline, no deps)."""
    from app.fx import normalize_custom_palette

    lines = [ln.strip() for ln in str(text or "").splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith(";")]
    if len(lines) < 4 or lines[0] != "JASC-PAL" or lines[1] != "0100":
        raise ValueError(".pal needs a JASC-PAL header (JASC-PAL/0100/count)")
    try:
        count = max(0, int(lines[2]))
    except ValueError:
        raise ValueError(".pal needs a JASC-PAL header (JASC-PAL/0100/count)") from None
    colors: list[tuple[int, int, int]] = []
    for ln in lines[3:3 + max(0, count)]:
        parts = ln.split()
        if len(parts) < 3:
            continue
        try:
            rgb = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            continue
        if all(0 <= v <= 255 for v in rgb) and rgb not in colors:
            colors.append(rgb)
    valid = normalize_custom_palette(colors[:16])
    if valid is None:
        raise ValueError(".pal needs 2-16 valid colors")
    return (str(name or "imported").strip() or "imported", valid)


def parse_palette_text(text: str, suffix: str,
                       name: str = "imported") -> tuple[str, list[tuple[int, int, int]]]:
    """Dispatch .gpl/.hex/.txt/.pal/.json text to (name, colors)."""
    s = str(suffix or "").lower().lstrip(".")
    if s == "gpl":
        from app.palette_library import parse_gpl

        return parse_gpl(text)
    if s in ("hex", "lospec"):
        return parse_hex(text, name=name)
    if s == "txt":
        return parse_txt(text, name=name)
    if s == "pal":
        return parse_pal(text, name=name)
    if s == "json":
        import json

        from app.fx import normalize_custom_palette

        raw = json.loads(text)
        colors = raw.get("colors", raw) if isinstance(raw, dict) else raw
        base = raw.get("name", name) if isinstance(raw, dict) else name
        valid = normalize_custom_palette([list(c) for c in colors][:16])
        if valid is None:
            raise ValueError(".json needs 2-16 valid colors")
        return (str(base or name or "imported").strip() or "imported", valid)
    raise ValueError(f"unsupported palette format: {suffix!r} (.json/.gpl/.hex/.txt/.pal)")


__all__ = [
    "COLLAPSE_FLOOR",
    "CONTRAST_FLOOR",
    "CVD_KINDS",
    "CVD_MATRICES",
    "accessibility_report",
    "contrast_ratio",
    "parse_hex",
    "parse_pal",
    "parse_palette_text",
    "parse_txt",
    "relative_luminance",
    "rgb_to_hex",
    "simulate_cvd",
]
