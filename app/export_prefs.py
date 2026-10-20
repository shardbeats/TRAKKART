"""Export prefs: recuerda la última configuración (Quick Export style).

JSON en el data dir (testeable sin Qt). MainWindow acepta prefs_path
inyectado para tests.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.paths import get_data_dir

PREFS_FILENAME = "export_prefs.json"


@dataclass
class ExportPrefs:
    out_dir: str = ""
    base: str = "trakkart_cover"
    image: bool = True
    thumb_1080p: bool = True
    vector: bool = False
    anim: bool = False
    metadata: bool = True
    gif_frames: int = 6
    gif_mode: str = "both"
    gif_fps: int = 8
    gif_size: int = 1200
    gif_pingpong: bool = False
    overwrite: str = "overwrite"
    size: int = 3000
    format: str = "png"
    quality: int = 90

    def to_selection(self) -> dict:
        from app.exporter import ExportSelection

        return ExportSelection(
            image=self.image, thumb_1080p=self.thumb_1080p,
            vector=self.vector, anim=self.anim, metadata=self.metadata,
        )


def _prefs_path(data_dir: Path | None = None) -> Path:
    d = Path(data_dir) if data_dir else get_data_dir()
    return d / PREFS_FILENAME


def load_prefs(prefs_path: str | Path | None = None) -> ExportPrefs:
    """Lee prefs; si no existen o están rotas, devuelve defaults."""
    p = Path(prefs_path) if prefs_path else _prefs_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        known = {f for f in ExportPrefs.__dataclass_fields__}
        return ExportPrefs(**{k: v for k, v in raw.items() if k in known})
    except (OSError, ValueError, TypeError):
        return ExportPrefs()


def save_prefs(prefs: ExportPrefs, prefs_path: str | Path | None = None) -> Path:
    p = Path(prefs_path) if prefs_path else _prefs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(prefs), indent=2, ensure_ascii=False), encoding="utf-8")
    return p


__all__ = ["ExportPrefs", "load_prefs", "save_prefs", "PREFS_FILENAME"]
