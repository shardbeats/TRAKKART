"""Palette library: named palettes as JSON, editable presets.

Builtins (BW/SLIME/VAPOR/EMBER) se crean si faltan (nunca se sobrescriben,
mismo patrón que presets). Elegir una la carga como copia editable en
CUSTOM PALETTE; guardar crea un JSON que aparece en el combo.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.fx import normalize_custom_palette

PALETTES_DIR = Path(__file__).resolve().parent.parent / "palettes"

CUSTOM_SENTINEL = "(Custom)"


def _safe_name(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    return safe or "palette"


def ensure_bundled_palettes(palettes_dir: Path | None = None) -> list[str]:
    """Crea los JSON built-in que falten. Retorna los creados."""
    from app.palettes import PALETTES

    d = Path(palettes_dir) if palettes_dir else PALETTES_DIR
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


def list_palettes(palettes_dir: Path | None = None) -> list[str]:
    d = Path(palettes_dir) if palettes_dir else PALETTES_DIR
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def palette_colors(name: str, palettes_dir: Path | None = None) -> list[tuple[int, int, int]]:
    """Colores de la paleta: librería primero, builtin después. Validados."""
    from app.palettes import get_palette

    d = Path(palettes_dir) if palettes_dir else PALETTES_DIR
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
    pal = get_palette(name)
    if pal is None:  # BW: 2 celdas, el motor usa la ruta rápida solo
        from app.palettes import PALETTES

        return [tuple(c) for c in PALETTES["BW"]]
    return [tuple(c) for c in pal]


def save_palette(name: str, colors: list, palettes_dir: Path | None = None) -> Path:
    """Guarda (o actualiza) una paleta de usuario. Valida 2-16 colores."""
    valid = normalize_custom_palette(colors)
    if valid is None:
        raise ValueError("palette needs 2-16 colors")
    if not (name or "").strip():
        raise ValueError("palette needs a name")
    d = Path(palettes_dir) if palettes_dir else PALETTES_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_safe_name(name)}.json"
    path.write_text(
        json.dumps({"name": name.strip(), "colors": [list(c) for c in valid]}, indent=2),
        encoding="utf-8",
    )
    return path


def is_bw(cells: list | None) -> bool:
    """¿Esta selección equivale al B&W puro? → el motor usa la ruta rápida."""
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
    "save_palette",
]
