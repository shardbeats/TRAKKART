"""TRAKKART viewport modes (MIT). No Qt, pure logic.

Full / Live / Still (debounced live-iteration control):
- full:  debounce 0ms, every change re-renders immediately (fast machines).
- live:  debounced preview; core-adjust sliders refresh sooner (120ms)
          than heavy ones (350ms). Default.
- still:  no auto-refresh at all; refresh via Refresh (F5) only.
          For weak PCs or huge canvases.

Fast path: HEAVY_PARAMS need the long debounce; everything else is fast.
"""

from __future__ import annotations

MODES = ("full", "live", "still")

LIVE_FAST_MS = 120
LIVE_SLOW_MS = 350

# Params whose render cost spikes (blur/denoise convolve full-res).
HEAVY_PARAMS = ("pre_blur", "pre_denoise", "pre_smooth")


def normalize_mode(mode: str | None) -> str:
    m = str(mode or "").lower()
    return m if m in MODES else "live"


def resolve_interval(mode: str | None, fast: bool = False) -> int | None:
    """Debounce ms for a change, or None (still = no auto-refresh)."""
    m = normalize_mode(mode)
    if m == "full":
        return 0
    if m == "still":
        return None
    return LIVE_FAST_MS if fast else LIVE_SLOW_MS


def is_heavy_preset(preset) -> bool:
    """True when the preset uses heavy pre-fx (goes to background worker)."""
    try:
        blur = float(getattr(preset, "pre_blur", 0.0) or 0.0)
        denoise = int(getattr(preset, "pre_denoise", 0) or 0)
        smooth = float(getattr(preset, "pre_smooth", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False
    return blur > 0 or denoise > 0 or smooth > 0


def mode_label(mode: str | None) -> str:
    return {"full": "Full", "live": "Live", "still": "Still"}.get(normalize_mode(mode), "Live")


__all__ = [
    "HEAVY_PARAMS",
    "LIVE_FAST_MS",
    "LIVE_SLOW_MS",
    "MODES",
    "is_heavy_preset",
    "mode_label",
    "normalize_mode",
    "resolve_interval",
]
