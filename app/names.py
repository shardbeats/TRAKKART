"""File/display-name sanitizers (MIT, clean-room). Single home for the three
use sites that grew the same regex by hand: presets, palette library and
the exporter (which adds no-spaces + collapse + edge-trim on top).
"""

from __future__ import annotations


def safe_stem(name: str, fallback: str = "file",
              keep: tuple[str, ...] = (" ", "-", "_"), fill: str = "") -> str:
    """Keep alphanumerics + `keep`; anything else becomes `fill` (drop by
    default, `_` for filename mapping). Stripped, never empty (fallback)."""
    safe = "".join(c if c.isalnum() or c in keep else fill for c in str(name or ""))
    return safe.strip() or fallback


__all__ = ["safe_stem"]
