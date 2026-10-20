"""TRAKKART video I/O (OPT-IN extra, never in the base exe).

MP4/GIF/WebP clip import + MP4 export via imageio + imageio-ffmpeg.
Base install (Pillow + numpy + PySide6) has neither: every entry point
checks `has_video()` first and raises `VideoBackendMissing` with install
instructions instead of an ImportError traceback.

Deterministic frame picking (evenly spaced) so the same clip + settings
always yield the same frames.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

MAX_CLIP_FRAMES = 48
MAX_CLIP_SIDE = 720
MIN_MP4_FPS = 2
MAX_MP4_FPS = 60


class VideoBackendMissing(RuntimeError):
    """Raised when video I/O is requested without the opt-in extra."""

    def __init__(self) -> None:
        super().__init__(
            "Video support needs the opt-in extra (never bundled): "
            "pip install -r requirements-video.txt (imageio + imageio-ffmpeg)"
        )


def has_video() -> bool:
    """True if imageio (+ffmpeg plugin) is importable. No side effects."""
    try:
        import imageio  # noqa: F401
        import imageio_ffmpeg  # noqa: F401
    except ImportError:
        return False
    return True


def _require_video() -> None:
    if not has_video():
        raise VideoBackendMissing()


def read_clip(path: str | Path, max_frames: int = MAX_CLIP_FRAMES,
              max_side: int = MAX_CLIP_SIDE) -> list[Image.Image]:
    """Read a clip (mp4/gif/webp) -> up to N RGB frames, capped at max_side.

    Frames are evenly spaced across the clip. Header/size validated the
    same way as stills (no decompression bombs in batch folders).
    """
    _require_video()
    import imageio.v3 as iio

    from app.safety import MAX_BYTES, TooBigError, check_image

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"clip does not exist: {path}")
    if p.stat().st_size > MAX_BYTES:
        raise TooBigError(f"clip exceeds {MAX_BYTES // 1_000_000}MB")
    try:
        meta = iio.immeta(p)
        n_total = int(meta.get("n_images", 1) or 1)
    except Exception:  # noqa: BLE001
        n_total = 1
    n_want = max(1, min(int(max_frames), MAX_CLIP_FRAMES))
    idx = [round(i * (n_total - 1) / max(n_want - 1, 1)) for i in range(min(n_want, n_total))]
    frames: list[Image.Image] = []
    try:
        for i in idx:
            arr = iio.imread(p, index=i)
            img = Image.fromarray(arr).convert("RGB")
            m = max(img.size)
            if m > max_side:
                f = float(max_side) / m
                img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))),
                                 Image.BICUBIC)
            check_image(img)
            frames.append(img)
    except VideoBackendMissing:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"could not read clip: {e}") from e
    if not frames:
        raise ValueError("clip has no readable frames")
    return frames


def write_mp4(frames: list[Image.Image], path: str | Path, fps: int = 24) -> Path:
    """Write RGB frames to MP4 (libx264 via imageio-ffmpeg). Deterministic input order."""
    _require_video()
    import imageio.v3 as iio
    import numpy as np

    if not frames:
        raise ValueError("no frames")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = max(MIN_MP4_FPS, min(MAX_MP4_FPS, int(fps)))
    arr = [np.asarray(f.convert("RGB"), dtype=np.uint8) for f in frames]
    iio.imwrite(str(out), arr, fps=fps, codec="libx264", quality=8,
                ffmpeg_params=["-pix_fmt", "yuv420p"])
    return out


__all__ = [
    "MAX_CLIP_FRAMES",
    "MAX_CLIP_SIDE",
    "VideoBackendMissing",
    "has_video",
    "read_clip",
    "write_mp4",
]
