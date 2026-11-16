"""TRAKKART clip import (v2.0 Fase A): short clips as first-class input.

Stills stay the core product; a short clip becomes a session-only input
that the still pipeline dithers frame by frame (Fase B). Offline,
Pillow+numpy only (+ imageio-ffmpeg for MP4, same opt-in video backend
as MP4 export). Deterministic, no network.

Rules (see ROADMAP v2.0):
- Session-only: frames live in RAM, never in presets/batch.
- Cap 120f at a 720p proxy (long side <= 720): editing stays light.
- Supported: .mp4 / .gif / .webp. Without the video backend every
  entry point raises VideoBackendMissing (clean message, no traceback).
- Trim is a [start, end] index range over the imported frames.
- Audio: none in-app (visual preview only); a soundtrack joins at
  MP4 export (Fase C mux).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.video_io import VideoBackendMissing, has_video

CLIP_MAX_FRAMES = 120
CLIP_PROXY_SIDE = 720
CLIP_EXTS = (".mp4", ".gif", ".webp")

MIN_CLIP_FPS = 2
MAX_CLIP_FPS = 60


def has_clip_io() -> bool:
    """True when clip import is available (same video backend as MP4)."""
    return bool(has_video())


def _require_clip_io() -> None:
    if not has_clip_io():
        raise VideoBackendMissing()


def _fit_proxy(img: Image.Image, proxy_side: int) -> Image.Image:
    side = max(64, min(1920, int(proxy_side or CLIP_PROXY_SIDE)))
    r = side / max(img.width, img.height)
    if r >= 1.0:
        return img.copy()
    return img.resize((max(1, round(img.width * r)),
                       max(1, round(img.height * r))), Image.BICUBIC)


def _clamp_fps(fps) -> int:
    try:
        return max(MIN_CLIP_FPS, min(MAX_CLIP_FPS, int(round(float(fps)))))
    except (TypeError, ValueError):
        return 24


def _read_anim_pil(path: Path, max_frames: int, proxy_side: int) -> tuple[list, int, bool]:
    """Read .gif/.webp via Pillow (offline, no ffmpeg frames needed)."""
    frames: list[Image.Image] = []
    fps = 8
    truncated = False
    with Image.open(path) as im:
        total = int(getattr(im, "n_frames", 1) or 1)
        try:
            dur = float(im.info.get("duration", 125) or 125)
            fps = _clamp_fps(1000.0 / max(1.0, dur))
        except (AttributeError, TypeError, ValueError):
            fps = 8
        n = min(int(total), max(1, int(max_frames)))
        truncated = bool(total > n)
        for i in range(n):
            try:
                im.seek(i)
            except EOFError:
                break
            frames.append(_fit_proxy(im.convert("RGB"), proxy_side))
    if not frames:
        raise ValueError(f"no frames: {path}")
    return frames, fps, truncated


def _read_mp4(path: Path, max_frames: int, proxy_side: int) -> tuple[list, int, bool]:
    """Read .mp4 via imageio-ffmpeg (first N frames, session proxy)."""
    import imageio.v2 as iio2

    frames: list[Image.Image] = []
    fps = 24
    truncated = False
    reader = iio2.get_reader(str(path))
    try:
        try:
            meta = reader.get_meta_data() or {}
            fps = _clamp_fps(meta.get("fps", 24))
            total = meta.get("nframes", None)
        except Exception:  # noqa: BLE001
            total = None
        n = 0
        cap = max(1, int(max_frames))
        for arr in reader:
            if n >= cap:
                truncated = True
                break
            frames.append(_fit_proxy(Image.fromarray(arr).convert("RGB"), proxy_side))
            n += 1
        if total is not None:
            try:
                import math as _math

                t = float(total)
                truncated = bool(_math.isfinite(t) and int(t) > len(frames))
            except (TypeError, ValueError, OverflowError):
                pass
    finally:
        try:
            reader.close()
        except Exception:  # noqa: BLE001
            pass
    if not frames:
        raise ValueError(f"no frames: {path}")
    return frames, fps, truncated


def import_clip(path: str | Path, max_frames: int = CLIP_MAX_FRAMES,
                proxy_side: int = CLIP_PROXY_SIDE) -> tuple[list[Image.Image], dict]:
    """Import a short clip (session-only proxy frames + info).

    Returns (frames, info) with info {path, frames, fps, truncated,
    size}. Raises VideoBackendMissing without the video extra,
    FileNotFoundError for missing paths, ValueError for bad ext/empty.
    """
    _require_clip_io()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"clip not found: {path}")
    ext = p.suffix.lower()
    if ext not in CLIP_EXTS:
        raise ValueError(f"clip must be {CLIP_EXTS}: {path}")
    cap = max(1, min(CLIP_MAX_FRAMES, int(max_frames or CLIP_MAX_FRAMES)))
    side = max(64, min(1920, int(proxy_side or CLIP_PROXY_SIDE)))
    if ext in (".gif", ".webp"):
        frames, fps, truncated = _read_anim_pil(p, cap, side)
    else:
        frames, fps, truncated = _read_mp4(p, cap, side)
    info = {"path": str(p), "frames": len(frames), "fps": int(fps),
            "truncated": bool(truncated), "size": [frames[0].width, frames[0].height]}
    return frames, info


def trim_clip(frames: list[Image.Image], start: int, end: int) -> list[Image.Image]:
    """Trim to the inclusive [start, end] range (clamped, deterministic)."""
    n = len(frames or [])
    if n == 0:
        raise ValueError("no frames")
    try:
        s = int(start)
    except (TypeError, ValueError):
        s = 0
    try:
        e = int(end)
    except (TypeError, ValueError):
        e = n - 1
    s = max(0, min(n - 1, s))
    e = max(0, min(n - 1, e))
    if s > e:
        raise ValueError(f"empty range: {start}-{end}")
    return list(frames[s:e + 1])


def clip_duration(frames: int, fps: int) -> float:
    """Derived clip length in seconds (frames / fps, preview math)."""
    return max(0.0, float(int(frames or 0)) / max(1, _clamp_fps(fps)))


__all__ = ["CLIP_MAX_FRAMES", "CLIP_PROXY_SIDE", "CLIP_EXTS",
           "VideoBackendMissing", "has_clip_io",
           "import_clip", "trim_clip", "clip_duration"]
