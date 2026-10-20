"""TRAKKART export bundle: cover per ratio + 1080p thumb + metadata.json.

Profesional: `export_bundle()` sigue siendo el motor simple (lo usan batch
y tests). Encima, `ExportOptions` + `export_with_options()` añaden selección
de salidas, vista previa (`plan_export()`) y política de colisión
(overwrite/skip/rename) como Photoshop/GIMP.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter

from app import __version__
from app.canvas import canvas_size_for

OVERWRITE_MODES = ("overwrite", "skip", "rename")

SUFFIXES = {
    "cover": "_cover.png",
    "small": "_small.png",
    "thumb_1080p": "_1080p.png",
    "vector": "_vector.svg",
    "anim": "_anim.gif",
    "metadata": "_metadata.json",
}


def sanitize_base(base: str) -> str:
    """Nombre seguro para ficheros (GIMP deja escribirlo libre; aquí se sanea)."""
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (base or ""))
    return safe or "cover"


@dataclass
class ExportSelection:
    cover: bool = True
    small: bool = True
    thumb_1080p: bool = True
    vector: bool = False
    anim: bool = False
    metadata: bool = True

    def keys(self) -> list[str]:
        return [k for k in ("cover", "small", "thumb_1080p", "vector", "anim", "metadata")
                if getattr(self, k)]


@dataclass
class ExportOptions:
    base: str = "trakkart_cover"
    selection: ExportSelection = field(default_factory=ExportSelection)
    overwrite: str = "overwrite"  # overwrite | skip | rename

    def __post_init__(self) -> None:
        self.base = sanitize_base(self.base)
        if self.overwrite not in OVERWRITE_MODES:
            raise ValueError(f"overwrite debe ser {OVERWRITE_MODES}: {self.overwrite!r}")


def _unique_base(out_dir: Path, base: str, suffixes: list[str]) -> str:
    """rename: trakkart_cover -> trakkart_cover_2, _3… hasta base libre."""
    if not any((out_dir / f"{base}{s}").exists() for s in suffixes):
        return base
    i = 2
    while any((out_dir / f"{base}_{i}{s}").exists() for s in suffixes):
        i += 1
    return f"{base}_{i}"


def _estimate_bytes(key: str, w: int, h: int, extra: dict | None = None) -> int:
    """Estimación grosera (~) para la vista previa del diálogo.

    PNG dither plano comprime muy bien: ~0.35 B/px. Etiquetar siempre con ~.
    """
    extra = extra or {}
    if key in ("cover", "small", "thumb_1080p"):
        return int(w * h * 0.35)
    if key == "vector":
        cols, rows = extra.get("vector_cells", (0, 0))
        from app.vector import estimate_bytes

        return estimate_bytes(cols, rows)
    if key == "anim":
        n = max(1, int(extra.get("gif_frames", 1)))
        return int(w * h * 0.5 * n)
    if key == "metadata":
        return 2048
    return 0


def plan_export(
    img: Image.Image,
    options: ExportOptions,
    meta: dict | None = None,
    has_vector: bool = False,
    has_gif: bool = False,
    extra: dict | None = None,
) -> list[tuple[str, str, int]]:
    """[(key, filename, ~bytes)] sin escribir nada. Lo que ves es lo que sale."""
    rgb = img.convert("RGB")
    ratio = (meta or {}).get("ratio", "1:1")
    try:
        big_w, big_h = canvas_size_for(ratio, 3000)
        small_w, small_h = canvas_size_for(ratio, 960)
    except KeyError:
        big_w, big_h = (3000, 3000)
        small_w, small_h = (960, 960)
    dims = {"cover": (big_w, big_h), "small": (small_w, small_h),
            "thumb_1080p": (1920, 1080),
            "anim": (min(rgb.width, 480), min(rgb.height, 480)),
            "vector": (0, 0), "metadata": (0, 0)}
    plan: list[tuple[str, str, int]] = []
    for key in options.selection.keys():
        if key == "vector" and not has_vector:
            continue
        if key == "anim" and not has_gif:
            continue
        w, h = dims[key]
        plan.append((key, f"{options.base}{SUFFIXES[key]}", _estimate_bytes(key, w, h, extra)))
    return plan


def export_with_options(
    img: Image.Image,
    out_dir: str | Path,
    options: ExportOptions,
    meta: dict | None = None,
    vector_svg: str | None = None,
    gif_frames: list[Image.Image] | None = None,
) -> tuple[dict[str, Path], list[str]]:
    """Exporta según opciones. Retorna (paths escritos, keys omitidas por skip).

    rename resuelve la base libre ANTES de escribir (todas las salidas juntas,
    como Photoshop: el set es atómico por base).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = [k for k in options.selection.keys()
            if not (k == "vector" and not vector_svg)
            and not (k == "anim" and not gif_frames)]
    suffixes = [SUFFIXES[k] for k in keys]
    base = options.base
    if options.overwrite == "rename":
        base = _unique_base(out_dir, base, suffixes)
    if options.overwrite == "skip" and all((out_dir / f"{base}{s}").exists() for s in suffixes):
        return {}, keys  # nada que hacer: todo existe
    return _write_bundle(img, out_dir, base, keys, meta, vector_svg, gif_frames), []


def _write_bundle(
    img: Image.Image,
    out_dir: Path,
    base: str,
    keys: list[str],
    meta: dict | None,
    vector_svg: str | None,
    gif_frames: list[Image.Image] | None,
) -> dict[str, Path]:
    """Escritura real del set (todas las variantes pasan por aquí)."""
    ratio = (meta or {}).get("ratio", "1:1")
    try:
        big_w, big_h = canvas_size_for(ratio, 3000)
        small_w, small_h = canvas_size_for(ratio, 960)
    except KeyError:
        big_w, big_h = (3000, 3000)
        small_w, small_h = (960, 960)

    rgb = img.convert("RGB")
    result: dict[str, Path] = {}
    if "cover" in keys:
        pcover = out_dir / f"{base}{SUFFIXES['cover']}"
        rgb.resize((big_w, big_h), Image.NEAREST).save(str(pcover), "PNG")
        result["cover"] = pcover
    if "small" in keys:
        psmall = out_dir / f"{base}{SUFFIXES['small']}"
        rgb.resize((small_w, small_h), Image.NEAREST).save(str(psmall), "PNG")
        result["small"] = psmall

    files: list[str] = []
    if "thumb_1080p" in keys:
        # 1080p thumb: cover fitted over a blurred background (works for any ratio)
        bg_src = rgb.resize((1920, 1080)).filter(ImageFilter.GaussianBlur(40))
        dim = Image.new("RGB", (1920, 1080), (0, 0, 0))
        bg = Image.blend(bg_src, dim, 0.25)
        r = min(1920 / rgb.width, 1080 / rgb.height)
        nw, nh = max(1, round(rgb.width * r)), max(1, round(rgb.height * r))
        small_fit = rgb.resize((nw, nh), Image.NEAREST)
        bg.paste(small_fit, ((1920 - nw) // 2, (1080 - nh) // 2))
        p1080 = out_dir / f"{base}{SUFFIXES['thumb_1080p']}"
        bg.save(str(p1080), "PNG")
        result["thumb_1080p"] = p1080
        files.append(p1080.name)
    # Mantener orden clásico cover, small, thumb en info["files"]:
    files = [result[k].name for k in ("cover", "small", "thumb_1080p") if k in result]

    info = {
        "app": "TRAKKART",
        "version": __version__,
        "base": base,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": files,
    }
    if meta:
        info["params"] = meta
    if vector_svg and "vector" in keys:
        pvec = out_dir / f"{base}{SUFFIXES['vector']}"
        pvec.write_text(vector_svg, encoding="utf-8")
        info["files"].append(pvec.name)
        result["vector"] = pvec
        info["vector"] = {"bytes": len(vector_svg.encode("utf-8"))}
    if gif_frames and "anim" in keys:
        from app.gif import save_gif

        panim = out_dir / f"{base}{SUFFIXES['anim']}"
        save_gif(gif_frames, panim)
        info["files"].append(panim.name)
        info["gif"] = {"bytes": panim.stat().st_size, "frames": len(gif_frames)}
        result["anim"] = panim
    if "metadata" in keys:
        pmeta = out_dir / f"{base}{SUFFIXES['metadata']}"
        pmeta.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        result["metadata"] = pmeta
    return result


def export_bundle(
    img: Image.Image,
    out_dir: str | Path,
    base: str = "cover",
    meta: dict | None = None,
    vector_svg: str | None = None,
    gif_frames: list[Image.Image] | None = None,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = ["cover", "small", "thumb_1080p", "metadata"]
    if vector_svg:
        keys.insert(3, "vector")
    if gif_frames:
        keys.insert(4 if "vector" in keys else 3, "anim")
    return _write_bundle(img, out_dir, sanitize_base(base), keys, meta, vector_svg, gif_frames)
