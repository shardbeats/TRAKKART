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


# ---------------------------------------------------------------------------
# Fase B — dither: the current preset recipe applied per frame.
# ---------------------------------------------------------------------------
_SEED_ATTRS = ("grain_seed", "dust_seed", "glitch_slice_seed", "wave_seed",
               "mosh_seed", "drift_seed", "paste_seed", "pixelsort_seed")


def _spec_for(preset, index: int, n: int, dpi: int = 300):
    """RenderSpec for frame `index`: base recipe + index-shifted seeds.

    Per-frame flicker is the aesthetic (documented): seeded post-fx
    (grain/dust/slice/wave/mosh/drift/paste) re-roll per frame while
    the recipe (method/palette/pixel/threshold/stack) stays put.
    Drift traverses 0->1 across the clip when enabled.
    """
    from app.pipeline import RenderSpec

    progress = float(index) / max(1, int(n) - 1) if int(n) > 1 else 0.0
    spec = RenderSpec.from_preset(preset, phase=0,
                                  drift_progress=progress, dpi=dpi)
    for attr in _SEED_ATTRS:
        try:
            setattr(spec, attr, int(getattr(spec, attr, 0) or 0) + int(index))
        except (TypeError, ValueError):
            pass
    return spec


def iter_dither_clip(frames, preset, dpi: int = 300):
    """Yield dithered frames one by one (streaming: O(1) RAM for MP4).

    Same pixels as dither_clip. Reuses render_spec, so combo/stack/
    GIF/MP4 writers inherit the recipe with zero extra plumbing.
    """
    from app.pipeline import render_spec

    seq = list(frames or [])
    if not seq:
        raise ValueError("no frames")
    n = len(seq)
    for i, frame in enumerate(seq):
        yield render_spec(frame.convert("RGB"), _spec_for(preset, i, n, dpi))


def dither_clip(frames, preset, dpi: int = 300) -> list[Image.Image]:
    """Dither every frame with the preset recipe (deterministic).

    seed = base + index: same inputs -> same bytes; consecutive
    identical frames differ only through seeded post-fx (grain/dust/...
    >0), which is the documented flicker aesthetic.
    """
    return list(iter_dither_clip(frames, preset, dpi))


# ---------------------------------------------------------------------------
# Fase C — export wiring: silent GIF, frame ZIP, MP4 (+ optional soundtrack).
# ---------------------------------------------------------------------------
def save_clip_zip(frames, out_path: str | Path) -> Path:
    """Frame ZIP: PNG sequence `frame_0001.png...` (stdlib only, offline).

    Same helper spirit as the batch bundle-ZIP (v1.8C), but the
    members are a deterministic PNG sequence instead of a folder.
    """
    import io
    import zipfile

    seq = list(frames or [])
    if not seq:
        raise ValueError("no frames")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, frame in enumerate(seq, 1):
            buf = io.BytesIO()
            frame.convert("RGB").save(buf, "PNG")
            zf.writestr(f"frame_{i:04d}.png", buf.getvalue())
    return out


def write_clip_mp4(frames_or_iter, out_path: str | Path,
                   fps: int = 24) -> Path:
    """Silent clip MP4 (software libx264-only, same writer as still MP4)."""
    from app.video_io import write_mp4, write_mp4_iter

    out = Path(out_path)
    if isinstance(frames_or_iter, list):
        return write_mp4(list(frames_or_iter), out, fps=fps)
    wrote, _ = write_mp4_iter(frames_or_iter, out, fps=fps)
    return wrote


def mux_soundtrack(silent_mp4: str | Path, audio_path: str | Path,
                   out_path: str | Path) -> Path:
    """Mux a chosen soundtrack: `-c:v copy -c:a aac -shortest` (offline).

    Video is never re-encoded (stays libx264-only by construction);
    audio joins as AAC and `-shortest` cuts at the clip end. Silent
    MP4 (no track chosen) skips this entirely — silence stays silent.
    """
    import subprocess

    from imageio_ffmpeg import get_ffmpeg_exe

    src = Path(silent_mp4)
    if not src.is_file():
        raise FileNotFoundError(f"silent mp4 not found: {silent_mp4}")
    track = Path(audio_path)
    if not track.is_file():
        raise FileNotFoundError(f"audio not found: {audio_path}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [get_ffmpeg_exe(), "-y", "-i", str(src), "-i", str(track),
           "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"ffmpeg mux failed: {proc.stderr[-500:]}")
    return out


__all__ = ["CLIP_MAX_FRAMES", "CLIP_PROXY_SIDE", "CLIP_EXTS",
           "VideoBackendMissing", "has_clip_io",
           "import_clip", "trim_clip", "clip_duration",
           "iter_dither_clip", "dither_clip",
           "save_clip_zip", "write_clip_mp4", "mux_soundtrack"]
