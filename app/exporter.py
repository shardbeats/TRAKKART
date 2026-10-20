"""TRAKKART export: tamaño + formato elegidos por el usuario (GIMP/Photoshop style).

Modelo nuevo: UNA imagen principal (lado largo + formato configurables) +
extras opcionales (thumb 1080p, SVG, GIF, metadata). `export_bundle()` queda
como motor legacy intacto (lo usa `export_with_options` NO; batch migra al
nuevo via preset).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter

from app import __version__
from app.canvas import canvas_size_for

OVERWRITE_MODES = ("overwrite", "skip", "rename")
EXPORT_FORMATS = ("png", "jpg", "webp")
SIZE_PRESETS = (960, 1080, 1920, 3000, 4096)
MIN_SIDE = 64
MAX_SIDE = 8000
THUMB_LONG_SIDE = 1920
THUMB_SHORT_SIDE = 1080

SUFFIXES = {
    "image": "",  # -> {base}.{ext} según formato
    "thumb_1080p": "_thumb1080p",  # -> {base}_thumb1080p.{ext}
    "vector": "_vector.svg",
    "anim": "_anim.gif",
    "metadata": "_metadata.json",
}

_FORMAT_EXT = {"png": "png", "jpg": "jpg", "webp": "webp"}


def sanitize_base(base: str) -> str:
    """Nombre seguro para ficheros (GIMP deja escribirlo libre; aquí se sanea)."""
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (base or ""))
    return safe or "cover"


def _raster_name(base: str, key: str, fmt: str) -> str:
    ext = _FORMAT_EXT[fmt]
    if key == "image":
        return f"{base}.{ext}"
    if key == "thumb_1080p":
        return f"{base}_thumb1080p.{ext}"
    raise KeyError(key)


def _raster_keys() -> tuple[str, ...]:
    return ("image", "thumb_1080p")


@dataclass
class ExportSelection:
    image: bool = True
    thumb_1080p: bool = True
    vector: bool = False
    anim: bool = False
    metadata: bool = True

    def keys(self) -> list[str]:
        return [k for k in ("image", "thumb_1080p", "vector", "anim", "metadata")
                if getattr(self, k)]


@dataclass
class ExportOptions:
    base: str = "trakkart_cover"
    selection: ExportSelection = field(default_factory=ExportSelection)
    overwrite: str = "overwrite"  # overwrite | skip | rename
    size: int = 3000  # lado largo px de la imagen principal
    format: str = "png"  # png | jpg | webp
    quality: int = 90  # solo jpg/webp, 1-100

    def __post_init__(self) -> None:
        self.base = sanitize_base(self.base)
        if self.overwrite not in OVERWRITE_MODES:
            raise ValueError(f"overwrite debe ser {OVERWRITE_MODES}: {self.overwrite!r}")
        if not MIN_SIDE <= int(self.size) <= MAX_SIDE:
            raise ValueError(f"size fuera de {MIN_SIDE}-{MAX_SIDE}: {self.size}")
        if str(self.format) not in EXPORT_FORMATS:
            raise ValueError(f"format debe ser {EXPORT_FORMATS}: {self.format!r}")
        if not 1 <= int(self.quality) <= 100:
            raise ValueError(f"quality fuera de 1-100: {self.quality}")
        self.size = int(self.size)
        self.quality = int(self.quality)
        self.format = str(self.format)


def bundle_filenames(
    options: ExportOptions,
    has_vector: bool = False,
    has_gif: bool = False,
) -> dict[str, str]:
    """{key: filename} del set, sin escribir. Para skip/rename y batch."""
    names: dict[str, str] = {}
    for key in options.selection.keys():
        if key == "vector" and not has_vector:
            continue
        if key == "anim" and not has_gif:
            continue
        if key in _raster_keys():
            names[key] = _raster_name(options.base, key, options.format)
        else:
            names[key] = f"{options.base}{SUFFIXES[key]}"
    return names


def _unique_base(out_dir: Path, base: str, filenames: list[str]) -> str:
    """rename: base -> base_2, _3… hasta set libre (atómico por base)."""
    if not any((out_dir / f).exists() for f in filenames):
        return base
    i = 2
    while True:
        cand = f"{base}_{i}"
        # Los nombres derivan de la base: re-sufijar con el candidato.
        remapped = [f.replace(base, cand, 1) for f in filenames]
        if not any((out_dir / f).exists() for f in remapped):
            return cand
        i += 1


def _estimate_bytes(key: str, w: int, h: int, fmt: str, quality: int, extra: dict | None = None) -> int:
    """Estimación grosera (~) para la vista previa del diálogo."""
    extra = extra or {}
    if key in _raster_keys():
        bpp = {"png": 0.35, "jpg": 0.05 + 0.002 * quality, "webp": 0.04 + 0.001 * quality}[fmt]
        return int(w * h * bpp)
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


def _main_dims(meta: dict | None, size: int) -> tuple[int, int]:
    ratio = (meta or {}).get("ratio", "1:1")
    try:
        return canvas_size_for(ratio, int(size))
    except KeyError:
        return (int(size), int(size))


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
    main_w, main_h = _main_dims(meta, options.size)
    dims = {"image": (main_w, main_h), "thumb_1080p": (THUMB_LONG_SIDE, THUMB_SHORT_SIDE),
            "anim": (min(rgb.width, 480), min(rgb.height, 480)),
            "vector": (0, 0), "metadata": (0, 0)}
    plan: list[tuple[str, str, int]] = []
    for key, fname in bundle_filenames(options, has_vector, has_gif).items():
        w, h = dims[key]
        plan.append((key, fname, _estimate_bytes(key, w, h, options.format, options.quality, extra)))
    return plan


def _save_raster(img: Image.Image, path: Path, fmt: str, quality: int) -> None:
    if fmt == "png":
        img.save(str(path), "PNG")
    elif fmt == "jpg":
        img.convert("RGB").save(str(path), "JPEG", quality=int(quality))
    elif fmt == "webp":
        img.convert("RGB").save(str(path), "WebP", quality=int(quality))
    else:  # pragma: no cover - validado en ExportOptions
        raise ValueError(f"formato no soportado: {fmt}")


def export_with_options(
    img: Image.Image,
    out_dir: str | Path,
    options: ExportOptions,
    meta: dict | None = None,
    vector_svg: str | None = None,
    gif_frames: list[Image.Image] | None = None,
) -> tuple[dict[str, Path], list[str]]:
    """Exporta según opciones. Retorna (paths escritos, keys omitidas por skip)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = bundle_filenames(options, has_vector=bool(vector_svg), has_gif=bool(gif_frames))
    keys = list(names)
    base = options.base
    if options.overwrite == "rename" and keys:
        base = _unique_base(out_dir, base, list(names.values()))
        names = bundle_filenames(replace(options, base=base),
                                 has_vector=bool(vector_svg), has_gif=bool(gif_frames))
        keys = list(names)
    if options.overwrite == "skip" and keys and all((out_dir / f).exists() for f in names.values()):
        return {}, keys  # nada que hacer: todo existe
    return _write_bundle(img, out_dir, base, keys, options, meta, vector_svg, gif_frames), []


def _write_bundle(
    img: Image.Image,
    out_dir: Path,
    base: str,
    keys: list[str],
    options: ExportOptions,
    meta: dict | None,
    vector_svg: str | None,
    gif_frames: list[Image.Image] | None,
) -> dict[str, Path]:
    """Escritura real del set (todas las variantes pasan por aquí)."""
    main_w, main_h = _main_dims(meta, options.size)
    rgb = img.convert("RGB")
    result: dict[str, Path] = {}
    if "image" in keys:
        pmain = out_dir / _raster_name(base, "image", options.format)
        _save_raster(rgb.resize((main_w, main_h), Image.NEAREST), pmain, options.format, options.quality)
        result["image"] = pmain

    if "thumb_1080p" in keys:
        # 1080p thumb: cover fitted over a blurred background (works for any ratio)
        bg_src = rgb.resize((THUMB_LONG_SIDE, THUMB_SHORT_SIDE)).filter(ImageFilter.GaussianBlur(40))
        dim = Image.new("RGB", (THUMB_LONG_SIDE, THUMB_SHORT_SIDE), (0, 0, 0))
        bg = Image.blend(bg_src, dim, 0.25)
        r = min(THUMB_LONG_SIDE / rgb.width, THUMB_SHORT_SIDE / rgb.height)
        nw, nh = max(1, round(rgb.width * r)), max(1, round(rgb.height * r))
        small_fit = rgb.resize((nw, nh), Image.NEAREST)
        bg.paste(small_fit, ((THUMB_LONG_SIDE - nw) // 2, (THUMB_SHORT_SIDE - nh) // 2))
        p1080 = out_dir / _raster_name(base, "thumb_1080p", options.format)
        _save_raster(bg, p1080, options.format, options.quality)
        result["thumb_1080p"] = p1080

    files = [result[k].name for k in ("image", "thumb_1080p") if k in result]

    info = {
        "app": "TRAKKART",
        "version": __version__,
        "base": base,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": files,
        "export": {"size": int(options.size), "format": str(options.format),
                   "quality": int(options.quality)},
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


# -- motor legacy: comportamiento byte-idéntico (tests + compat) --
_LEGACY_SUFFIXES = {
    "cover": "_cover.png",
    "small": "_small.png",
    "thumb_1080p": "_1080p.png",
    "vector": "_vector.svg",
    "anim": "_anim.gif",
    "metadata": "_metadata.json",
}


def _write_legacy_bundle(
    img: Image.Image,
    out_dir: Path,
    base: str,
    keys: list[str],
    meta: dict | None,
    vector_svg: str | None,
    gif_frames: list[Image.Image] | None,
) -> dict[str, Path]:
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
        pcover = out_dir / f"{base}{_LEGACY_SUFFIXES['cover']}"
        rgb.resize((big_w, big_h), Image.NEAREST).save(str(pcover), "PNG")
        result["cover"] = pcover
    if "small" in keys:
        psmall = out_dir / f"{base}{_LEGACY_SUFFIXES['small']}"
        rgb.resize((small_w, small_h), Image.NEAREST).save(str(psmall), "PNG")
        result["small"] = psmall

    files: list[str] = []
    if "thumb_1080p" in keys:
        bg_src = rgb.resize((1920, 1080)).filter(ImageFilter.GaussianBlur(40))
        dim = Image.new("RGB", (1920, 1080), (0, 0, 0))
        bg = Image.blend(bg_src, dim, 0.25)
        r = min(1920 / rgb.width, 1080 / rgb.height)
        nw, nh = max(1, round(rgb.width * r)), max(1, round(rgb.height * r))
        small_fit = rgb.resize((nw, nh), Image.NEAREST)
        bg.paste(small_fit, ((1920 - nw) // 2, (1080 - nh) // 2))
        p1080 = out_dir / f"{base}{_LEGACY_SUFFIXES['thumb_1080p']}"
        bg.save(str(p1080), "PNG")
        result["thumb_1080p"] = p1080
        files.append(p1080.name)
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
        pvec = out_dir / f"{base}{_LEGACY_SUFFIXES['vector']}"
        pvec.write_text(vector_svg, encoding="utf-8")
        info["files"].append(pvec.name)
        result["vector"] = pvec
        info["vector"] = {"bytes": len(vector_svg.encode("utf-8"))}
    if gif_frames and "anim" in keys:
        from app.gif import save_gif

        panim = out_dir / f"{base}{_LEGACY_SUFFIXES['anim']}"
        save_gif(gif_frames, panim)
        info["files"].append(panim.name)
        info["gif"] = {"bytes": panim.stat().st_size, "frames": len(gif_frames)}
        result["anim"] = panim
    if "metadata" in keys:
        pmeta = out_dir / f"{base}{_LEGACY_SUFFIXES['metadata']}"
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
    return _write_legacy_bundle(img, out_dir, sanitize_base(base), keys, meta, vector_svg, gif_frames)
