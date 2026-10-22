"""Palette library: named palettes as JSON, editable presets.

Builtins (BW/SLIME/VAPOR/EMBER) are created when missing (never overwritten,
same pattern as presets). Picking one loads it as an editable copy in
CUSTOM PALETTE; saving creates a JSON that shows up in the combo.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.fx import normalize_custom_palette

PALETTES_DIR = Path(__file__).resolve().parent.parent / "palettes"

CUSTOM_SENTINEL = "(Custom)"

_BUNDLED_DIR = PALETTES_DIR  # repo copy (frozen: _MEIPASS, read-only seed)


def _user_dir() -> Path:
    """Writable user dir (data/palettes). Frozen-safe; explicit arg wins."""
    from app.paths import get_palettes_dir

    return get_palettes_dir()


def _default_dir() -> Path:
    # Test seam: a monkeypatched PALETTES_DIR keeps working as the default.
    if PALETTES_DIR != _BUNDLED_DIR:
        return Path(PALETTES_DIR)
    return _user_dir()


def _safe_name(name: str) -> str:
    from app.names import safe_stem

    return safe_stem(name, "palette")


def ensure_bundled_palettes(palettes_dir: Path | None = None) -> list[str]:
    """Creates the missing built-in JSONs. Returns the created ones."""
    from app.palettes import PALETTES

    d = Path(palettes_dir) if palettes_dir else _default_dir()
    d.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name, colors in PALETTES.items():
        path = d / f"{_safe_name(name)}.json"
        if not path.exists():
            path.write_text(
                json.dumps({"name": name, "colors": [list(c) for c in colors]}, indent=2),
                encoding="utf-8",
            )
            created.append(name)
    return created


def _stems(d: Path) -> list[str]:
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def list_palettes(palettes_dir: Path | None = None) -> list[str]:
    if palettes_dir is not None:
        return _stems(Path(palettes_dir))
    if PALETTES_DIR != _BUNDLED_DIR:
        return _stems(Path(PALETTES_DIR))  # test seam
    return sorted(set(_stems(_user_dir())) | set(_stems(PALETTES_DIR)))


def palette_colors(name: str, palettes_dir: Path | None = None) -> list[tuple[int, int, int]]:
    """Palette colors: library first, builtin after. Validated."""
    from app.palettes import get_palette

    if name == "SOURCE":
        raise ValueError("SOURCE is auto-extracted at render time, not a swatch list")
    # User dir first (own edits shadow builtins), repo copy as fallback.
    if palettes_dir is not None:
        dirs = [Path(palettes_dir)]
    elif PALETTES_DIR != _BUNDLED_DIR:
        dirs = [Path(PALETTES_DIR)]  # test seam
    else:
        dirs = [_user_dir(), PALETTES_DIR]
    for d in dirs:
        path = d / f"{_safe_name(name)}.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                colors = raw.get("colors", raw) if isinstance(raw, dict) else raw
                valid = normalize_custom_palette(colors)
                if valid is not None:
                    return valid
            except (ValueError, OSError):
                pass
            break  # file exists but invalid: fall through to builtin, not next dir
    pal = get_palette(name)
    if pal is None:  # BW: 2 cells, the engine only uses the fast path
        from app.palettes import PALETTES

        return [tuple(c) for c in PALETTES["BW"]]
    if isinstance(pal, str):  # SOURCE sentinel: never a list
        raise ValueError("SOURCE is auto-extracted at render time")
    return [tuple(c) for c in pal]


def parse_gpl(text: str) -> tuple[str, list[tuple[int, int, int]]]:
    """Parse GIMP .gpl (offline, no deps). Returns (name, colors)."""
    name = ""
    colors: list[tuple[int, int, int]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("gimp palette"):
            continue
        if s.lower().startswith("name:"):
            name = s.split(":", 1)[1].strip()
            continue
        if s.lower().startswith("columns:"):
            continue
        parts = s.split()
        if len(parts) >= 3:
            try:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                continue
            if all(0 <= v <= 255 for v in (r, g, b)):
                colors.append((r, g, b))
    valid = normalize_custom_palette(colors)
    if valid is None:
        raise ValueError("GPL needs 2-16 valid colors")
    return (name or "imported", valid)


def to_gpl(name: str, colors: list) -> str:
    """Swatches -> .gpl text (for offline sharing with GIMP/others)."""
    valid = normalize_custom_palette([list(c) for c in colors])
    if valid is None:
        raise ValueError("palette needs 2-16 colors")
    lines = ["GIMP Palette", f"Name: {(name or 'trakkart').strip()}", "Columns: 4", "#"]
    for c in valid:
        lines.append(f"{c[0]:3d} {c[1]:3d} {c[2]:3d}\t#{c[0]:02X}{c[1]:02X}{c[2]:02X}")
    return "\n".join(lines) + "\n"


def save_palette(name: str, colors: list, palettes_dir: Path | None = None) -> Path:
    """Saves (or updates) a user palette. Validates 2-16 colors."""
    valid = normalize_custom_palette(colors)
    if valid is None:
        raise ValueError("palette needs 2-16 colors")
    if not (name or "").strip():
        raise ValueError("palette needs a name")
    d = Path(palettes_dir) if palettes_dir else _default_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_safe_name(name)}.json"
    path.write_text(
        json.dumps({"name": name.strip(), "colors": [list(c) for c in valid]}, indent=2),
        encoding="utf-8",
    )
    return path


def is_bw(cells: list | None) -> bool:
    """Does this selection equal pure B&W? → the engine uses the fast path."""
    if not cells:
        return False
    try:
        from app.palettes import PALETTES

        norm = sorted(tuple(c) for c in normalize_custom_palette(cells) or [])
        return norm == sorted(tuple(c) for c in PALETTES["BW"])
    except (ValueError, TypeError):
        return False


__all__ = [
    "CUSTOM_SENTINEL",
    "PALETTES_DIR",
    "ensure_bundled_palettes",
    "is_bw",
    "list_palettes",
    "palette_colors",
    "parse_gpl",
    "save_palette",
    "to_gpl",
]
