"""Export prefs: recuerda la última configuración (Quick Export style).

JSON en el data dir (testeable sin Qt). MainWindow acepta prefs_path
inyectado para tests.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
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
    overwrite: str = "rename"  # fixed: never lose a file (engine keeps all modes)
    size: int = 3000
    format: str = "png"
    quality: int = 90
    recent_files: list = field(default_factory=list)
    src_name: str = ""  # image these prefs were saved for (stale-name guard)
    # -- general app settings (same JSON, backward-compatible) --
    jobs: int = 1  # batch jobs 1-8
    drop_batch: bool = False  # OFF = drop loads images, ON = drop asks for batch
    viewport: str = "live"  # default viewport mode (full/live/still)
    # -- session (reopen where you left off) --
    last_image: str = ""  # absolute path of the last opened image
    last_preset: str = ""  # preset name active when the window closed
    restore_session: bool = True  # reopen last image + preset on startup

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
        prefs = ExportPrefs(**{k: v for k, v in raw.items() if k in known})
    except (OSError, ValueError, TypeError):
        return ExportPrefs()
    return normalize_prefs(prefs)


def _clamp_int(value, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def normalize_prefs(prefs: ExportPrefs) -> ExportPrefs:
    """Clamp every numeric/enum pref (corrupt JSON -> safe defaults)."""
    from app.gif import GIF_MODES

    prefs.jobs = _clamp_int(getattr(prefs, "jobs", 1), 1, 8, 1)
    prefs.gif_frames = _clamp_int(getattr(prefs, "gif_frames", 6), 2, 24, 6)
    prefs.gif_fps = _clamp_int(getattr(prefs, "gif_fps", 8), 2, 60, 8)
    prefs.gif_size = _clamp_int(getattr(prefs, "gif_size", 1200), 64, 8000, 1200)
    prefs.quality = _clamp_int(getattr(prefs, "quality", 90), 1, 100, 90)
    try:
        from app.exporter import MAX_SIDE, MIN_SIDE

        prefs.size = _clamp_int(getattr(prefs, "size", 3000), int(MIN_SIDE), int(MAX_SIDE), 3000)
    except Exception:  # noqa: BLE001
        prefs.size = _clamp_int(getattr(prefs, "size", 3000), 64, 8000, 3000)
    for flag in ("image", "thumb_1080p", "vector", "anim", "metadata",
                 "gif_pingpong", "drop_batch", "restore_session"):
        try:
            setattr(prefs, flag, bool(getattr(prefs, flag)))
        except Exception:  # noqa: BLE001
            pass
    if str(getattr(prefs, "gif_mode", "")) not in GIF_MODES:
        prefs.gif_mode = "both"
    if str(getattr(prefs, "viewport", "")).lower() not in ("full", "live", "still"):
        prefs.viewport = "live"
    else:
        prefs.viewport = str(prefs.viewport).lower()
    if str(getattr(prefs, "format", "")) not in ("png", "jpg", "webp"):
        prefs.format = "png"
    if not str(getattr(prefs, "base", "") or "").strip():
        prefs.base = "trakkart_cover"
    prefs.overwrite = "rename"  # fixed policy: never lose a file
    try:
        prefs.recent_files = [str(s) for s in (prefs.recent_files or []) if str(s).strip()]
    except TypeError:
        prefs.recent_files = []
    try:
        prefs.src_name = str(getattr(prefs, "src_name", "") or "")
    except Exception:  # noqa: BLE001
        prefs.src_name = ""
    for field_name in ("last_image", "last_preset"):
        try:
            setattr(prefs, field_name, str(getattr(prefs, field_name, "") or ""))
        except Exception:  # noqa: BLE001
            setattr(prefs, field_name, "")
    try:
        prefs.out_dir = str(getattr(prefs, "out_dir", "") or "")
    except Exception:  # noqa: BLE001
        prefs.out_dir = ""
    return prefs


def is_writable_dir(path: str | Path | None) -> bool:
    """True when `path` is (or could be created under) a writable dir."""
    if not path or not str(path).strip():
        return False
    try:
        p = Path(str(path))
        if p.is_dir():
            return os.access(str(p), os.W_OK)
        parent = p.parent
        while not parent.exists() and len(parent.parts) > 1:
            parent = parent.parent
        return parent.is_dir() and os.access(str(parent), os.W_OK)
    except (OSError, TypeError):
        return False


def resolve_out_dir(preferred: str | Path | None = None,
                    fallback: str | Path | None = None) -> Path:
    """First writable dir: preferred -> system out -> fallback -> home."""
    from app.paths import get_out_dir

    cands: list[Path] = []
    if preferred and str(preferred).strip():
        cands.append(Path(str(preferred)))
    try:
        cands.append(get_out_dir())
    except Exception:  # noqa: BLE001
        pass
    if fallback is not None and str(fallback).strip():
        cands.append(Path(str(fallback)))
    cands.append(Path.home())
    for c in cands:
        try:
            if not c.exists():
                c.mkdir(parents=True, exist_ok=True)
            if c.is_dir() and os.access(str(c), os.W_OK):
                return c
        except (OSError, TypeError):
            continue
    return Path.home()


def save_prefs(prefs: ExportPrefs, prefs_path: str | Path | None = None) -> Path:
    p = Path(prefs_path) if prefs_path else _prefs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(prefs), indent=2, ensure_ascii=False), encoding="utf-8")
    return p


#: Settings-dialog fields (shared by save, backup export and backup import).
DIALOG_FIELDS = ("out_dir", "format", "quality", "size", "image", "thumb_1080p",
                 "vector", "anim", "metadata", "jobs", "drop_batch",
                 "viewport", "restore_session")


def apply_dialog_values(prefs: ExportPrefs, v: dict) -> ExportPrefs:
    """Copy Settings-dialog `values()` into prefs (raw; caller normalizes)."""
    for name in DIALOG_FIELDS:
        if name in v:
            try:
                setattr(prefs, name, v[name])
            except Exception:  # noqa: BLE001
                pass
    if v.get("clear_recents"):
        try:
            prefs.recent_files = []
        except Exception:  # noqa: BLE001
            pass
    return prefs


def load_backup_file(path: str | Path) -> ExportPrefs:
    """Load a settings backup. Raises ValueError when it is not one."""
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"not a settings file: {p}") from e
    if not isinstance(raw, dict):
        raise ValueError(f"not a settings file: {p}")
    known = set(ExportPrefs.__dataclass_fields__)
    if not any(k in known for k in raw):
        raise ValueError(f"not a settings file: {p}")
    return normalize_prefs(ExportPrefs(**{k: v for k, v in raw.items() if k in known}))


__all__ = ["DIALOG_FIELDS", "ExportPrefs", "apply_dialog_values", "is_writable_dir",
           "load_backup_file", "load_prefs", "normalize_prefs",
           "resolve_out_dir", "save_prefs", "PREFS_FILENAME"]
