"""File/display-name sanitizers (GPL-3.0-only). Single home for the three
use sites that grew the same regex by hand: presets, palette library and
the exporter (which adds no-spaces + collapse + edge-trim on top).
"""

from __future__ import annotations

#: Windows device names are unusable as file stems, extension included
#: ("CON.json", "nul.png"...). Kept Windows-strict on every OS so exported
#: bundles and preset files stay portable.
RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def is_reserved(name: str) -> bool:
    """True when `name` is a Windows reserved stem (trailing dots/spaces
    are ignored by the OS, so they do not make it usable)."""
    return str(name).strip().rstrip(" .").upper() in RESERVED_NAMES


def safe_stem(name: str, fallback: str = "file",
              keep: tuple[str, ...] = (" ", "-", "_"), fill: str = "") -> str:
    """Keep alphanumerics + `keep`; anything else becomes `fill` (drop by
    default, `_` for filename mapping). Stripped, never empty (fallback);
    reserved Windows stems get a trailing `_` so they can be written."""
    safe = "".join(c if c.isalnum() or c in keep else fill for c in str(name or ""))
    safe = safe.strip() or fallback
    return f"{safe}_" if safe and is_reserved(safe) else safe


__all__ = ["RESERVED_NAMES", "is_reserved", "safe_stem"]
