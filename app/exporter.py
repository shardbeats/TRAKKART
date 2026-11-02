"""TRAKKART export: user-chosen size + format (classic editor style).

New model: ONE main image (configurable long side + format) +
optional extras (1080p thumb, SVG, GIF, metadata). `export_bundle()` stays
as the intact legacy engine (`export_with_options` does NOT use it; batch
migrates to the new one via preset).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter

from app import __version__
from app.canvas import CUSTOM_RATIO, MIN_DIM, MAX_DIM, canvas_size_for

OVERWRITE_MODES = ("overwrite", "skip", "rename")
EXPORT_FORMATS = ("png", "jpg", "webp")
SIZE_PRESETS = (960, 1080, 1920, 3000, 4096)
MIN_SIDE = MIN_DIM
MAX_SIDE = MAX_DIM
THUMB_LONG_SIDE = 1920
THUMB_SHORT_SIDE = 1080

SUFFIXES = {
    "image": "",  # -> {base}.{ext} per format
    "thumb_1080p": "_thumb1080p",  # -> {base}_thumb1080p.{ext}
    "vector": "_vector.svg",
    "anim": "_gif.gif",
    "metadata": "_metadata.json",
}

# Animation single file (GIF + MP4 share the stem: one motion, two codecs).
MP4_SUFFIX = "_vid.mp4"


def mp4_name(base: str) -> str:
    """`{base}_vid.mp4` (same stem as the GIF)."""
    return f"{base}{MP4_SUFFIX}"


# Animated WebP (R7): same frames as the GIF, ~1/3 the weight.
WEBP_SUFFIX = "_anim.webp"


def webp_name(base: str) -> str:
    """`{base}_anim.webp` (same frames as the GIF)."""
    return f"{base}{WEBP_SUFFIX}"


_FORMAT_EXT = {"png": "png", "jpg": "jpg", "webp": "webp"}


def sanitize_base(base: str) -> str:
    """Safe base name for files (other editors let you type it freely; here it is sanitized).

    No separators (anti `../`), no `_` runs or odd edges, so
    suffixes (`_gif.gif`...) never produce `__`.
    """
    from app.names import safe_stem

    safe = safe_stem(base, "", keep=("-", "_"), fill="_")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_-") or "cover"


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
    black_vector: bool = False  # v1.3: modifier (not a file)

    def keys(self) -> list[str]:
        return [k for k in ("image", "thumb_1080p", "vector", "anim", "metadata")
                if getattr(self, k)]


@dataclass
class ExportOptions:
    base: str = "trakkart_cover"
    selection: ExportSelection = field(default_factory=ExportSelection)
    overwrite: str = "overwrite"  # overwrite | skip | rename
    size: int = 3000  # long side px of the main image
    format: str = "png"  # png | jpg | webp
    quality: int = 90  # jpg/webp only, 1-100

    def __post_init__(self) -> None:
        self.base = sanitize_base(self.base)
        if self.overwrite not in OVERWRITE_MODES:
            raise ValueError(f"overwrite must be {OVERWRITE_MODES}: {self.overwrite!r}")
        if not MIN_SIDE <= int(self.size) <= MAX_SIDE:
            raise ValueError(f"size out of {MIN_SIDE}-{MAX_SIDE}: {self.size}")
        if str(self.format) not in EXPORT_FORMATS:
            raise ValueError(f"format must be {EXPORT_FORMATS}: {self.format!r}")
        if not 1 <= int(self.quality) <= 100:
            raise ValueError(f"quality out of 1-100: {self.quality}")
        self.size = int(self.size)
        self.quality = int(self.quality)
        self.format = str(self.format)


def bundle_filenames(
    options: ExportOptions,
    has_vector: bool = False,
    has_gif: bool = False,
) -> dict[str, str]:
    """{key: filename} of the set, without writing. For skip/rename and batch."""
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
    """rename: base -> base_2, _3… until the set is free (atomic per base)."""
    if not any((out_dir / f).exists() for f in filenames):
        return base
    i = 2
    while True:
        cand = f"{base}_{i}"
        # Names derive from the base: re-suffix with the candidate.
        remapped = [f.replace(base, cand, 1) for f in filenames]
        if not any((out_dir / f).exists() for f in remapped):
            return cand
        i += 1


def _estimate_bytes(key: str, w: int, h: int, fmt: str, quality: int, extra: dict | None = None) -> int:
    """Rough estimate (~) for the dialog preview."""
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
        t = extra.get("gif_trans", None)
        f = extra.get("gif_forms", None)
        if t is None or f is None:
            return int(w * h * 0.5 * n)
        # R8 hold-collapse aware: transitions full cost + 1 frame per form.
        return int(w * h * 0.5 * max(0, int(t))) + int(w * h * 0.5 * max(0, int(f)))
    if key == "metadata":
        return 2048
    return 0


def _main_dims(meta: dict | None, size: int) -> tuple[int, int]:
    meta = meta or {}
    if meta.get("ratio") == CUSTOM_RATIO:
        c = meta.get("canvas") or {}
        try:
            w, h = int(c.get("w", 0)), int(c.get("h", 0))
        except (TypeError, ValueError):
            w, h = 0, 0
        if MIN_DIM <= w <= MAX_DIM and MIN_DIM <= h <= MAX_DIM:
            return (w, h)
        s = max(MIN_DIM, min(MAX_DIM, int(size)))  # degenerate: square long side
        return (s, s)
    ratio = meta.get("ratio", "1:1")
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
    """[(key, filename, ~bytes)] without writing anything. What you see is what ships."""
    rgb = img.convert("RGB")
    main_w, main_h = _main_dims(meta, options.size)
    gside = max(240, min(1920, int((extra or {}).get("gif_size", 1200))))
    gr = gside / max(rgb.width, rgb.height)
    gw, gh = (max(1, round(rgb.width * gr)), max(1, round(rgb.height * gr))) if gr < 1.0 else (rgb.width, rgb.height)
    dims = {"image": (main_w, main_h), "thumb_1080p": (THUMB_LONG_SIDE, THUMB_SHORT_SIDE),
            "anim": (gw, gh),
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
        raise ValueError(f"unsupported format: {fmt}")


def export_with_options(
    img: Image.Image,
    out_dir: str | Path,
    options: ExportOptions,
    meta: dict | None = None,
    vector_svg: str | None = None,
    gif_frames: list[Image.Image] | None = None,
    gif_fps: int = 8,
) -> tuple[dict[str, Path], list[str]]:
    """Exports per options. Returns (written paths, keys skipped by skip)."""
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
        return {}, keys  # nothing to do: everything exists
    return _write_bundle(img, out_dir, base, keys, options, meta, vector_svg, gif_frames, gif_fps), []


# ---------------------------------------------------------------------------
# Shared writers: the new scheme and the legacy one use the same art.
# Each writer is a thin recipe (names + dimensions); how it is written
# lives here exactly once. Byte-identical output to the previous version.
# ---------------------------------------------------------------------------
def _thumb_image(rgb: Image.Image, w: int, h: int) -> Image.Image:
    """Cover fitted over a blur background (shared: same algorithm, same bytes)."""
    bg_src = rgb.resize((w, h)).filter(ImageFilter.GaussianBlur(40))
    dim = Image.new("RGB", (w, h), (0, 0, 0))
    bg = Image.blend(bg_src, dim, 0.25)
    r = min(w / rgb.width, h / rgb.height)
    nw, nh = max(1, round(rgb.width * r)), max(1, round(rgb.height * r))
    small_fit = rgb.resize((nw, nh), Image.NEAREST)
    bg.paste(small_fit, ((w - nw) // 2, (h - nh) // 2))
    return bg


def _write_raster(rgb: Image.Image, path: Path, w: int, h: int,
                  fmt: str, quality: int) -> None:
    _save_raster(rgb.resize((w, h), Image.NEAREST), path, fmt, quality)


def _info_base(base: str, files: list[str], export: dict | None) -> dict:
    info = {
        "app": "TRAKKART",
        "version": __version__,
        "base": base,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": files,
    }
    if export is not None:
        info["export"] = export
    return info


def _attach_vector(result: dict, info: dict, out_dir: Path, base: str,
                   suffix: str, vector_svg: str) -> None:
    pvec = out_dir / f"{base}{suffix}"
    pvec.write_text(vector_svg, encoding="utf-8")
    info["files"].append(pvec.name)
    result["vector"] = pvec
    info["vector"] = {"bytes": len(vector_svg.encode("utf-8"))}


def _attach_anim(result: dict, info: dict, out_dir: Path, base: str,
                 suffix: str, gif_frames: list, fps: int | None) -> None:
    from app.gif import save_gif

    panim = out_dir / f"{base}{suffix}"
    if fps is None:
        save_gif(gif_frames, panim)  # legacy: engine default
    else:
        save_gif(gif_frames, panim, fps=int(fps))
    info["files"].append(panim.name)
    entry: dict = {"bytes": panim.stat().st_size, "frames": len(gif_frames)}
    if fps is not None:
        entry["fps"] = int(fps)
    info["gif"] = entry
    result["anim"] = panim


def _attach_meta(result: dict, info: dict, out_dir: Path, base: str, suffix: str) -> None:
    pmeta = out_dir / f"{base}{suffix}"
    pmeta.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    result["metadata"] = pmeta


def _write_bundle(
    img: Image.Image,
    out_dir: Path,
    base: str,
    keys: list[str],
    options: ExportOptions,
    meta: dict | None,
    vector_svg: str | None,
    gif_frames: list[Image.Image] | None,
    gif_fps: int = 8,
) -> dict[str, Path]:
    """Real writing of the set (every variant goes through here)."""
    main_w, main_h = _main_dims(meta, options.size)
    rgb = img.convert("RGB")
    result: dict[str, Path] = {}
    if "image" in keys:
        pmain = out_dir / _raster_name(base, "image", options.format)
        _write_raster(rgb, pmain, main_w, main_h, options.format, options.quality)
        result["image"] = pmain

    if "thumb_1080p" in keys:
        # 1080p thumb: cover fitted over a blurred background (works for any ratio)
        p1080 = out_dir / _raster_name(base, "thumb_1080p", options.format)
        _save_raster(_thumb_image(rgb, THUMB_LONG_SIDE, THUMB_SHORT_SIDE),
                     p1080, options.format, options.quality)
        result["thumb_1080p"] = p1080

    files = [result[k].name for k in ("image", "thumb_1080p") if k in result]

    info = _info_base(base, files, {"size": int(options.size),
                                    "format": str(options.format),
                                    "quality": int(options.quality)})
    if meta:
        info["params"] = meta
    if vector_svg and "vector" in keys:
        _attach_vector(result, info, out_dir, base, SUFFIXES["vector"], vector_svg)
    if gif_frames and "anim" in keys:
        _attach_anim(result, info, out_dir, base, SUFFIXES["anim"], gif_frames, gif_fps)
    if "metadata" in keys:
        _attach_meta(result, info, out_dir, base, SUFFIXES["metadata"])
    return result


# -- legacy engine: byte-identical behavior (tests + compat) --
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
    if ratio == CUSTOM_RATIO:
        from app.canvas import doc_dimensions

        c = (meta or {}).get("canvas") or {}
        big_w, big_h = doc_dimensions(ratio, 3000, int(c.get("w", 0) or 0),
                                      int(c.get("h", 0) or 0))
        r = min(960 / big_w, 960 / big_h)
        small_w, small_h = max(1, round(big_w * r)), max(1, round(big_h * r))
    else:
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
        _write_raster(rgb, pcover, big_w, big_h, "png", 90)
        result["cover"] = pcover
    if "small" in keys:
        psmall = out_dir / f"{base}{_LEGACY_SUFFIXES['small']}"
        _write_raster(rgb, psmall, small_w, small_h, "png", 90)
        result["small"] = psmall

    if "thumb_1080p" in keys:
        p1080 = out_dir / f"{base}{_LEGACY_SUFFIXES['thumb_1080p']}"
        _thumb_image(rgb, 1920, 1080).save(str(p1080), "PNG")
        result["thumb_1080p"] = p1080
    files = [result[k].name for k in ("cover", "small", "thumb_1080p") if k in result]

    info = _info_base(base, files, None)
    if meta:
        info["params"] = meta
    if vector_svg and "vector" in keys:
        _attach_vector(result, info, out_dir, base, _LEGACY_SUFFIXES["vector"], vector_svg)
    if gif_frames and "anim" in keys:
        _attach_anim(result, info, out_dir, base, _LEGACY_SUFFIXES["anim"], gif_frames, None)
    if "metadata" in keys:
        _attach_meta(result, info, out_dir, base, _LEGACY_SUFFIXES["metadata"])
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
