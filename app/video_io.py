"""TRAKKART video I/O (OPT-IN extra, never in the base exe).

MP4 export of still-based animation via imageio + imageio-ffmpeg.
Base install (Pillow + numpy + PySide6) has neither: every entry point
checks `has_video()` first and raises `VideoBackendMissing` with install
instructions instead of an ImportError traceback.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

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
    "VideoBackendMissing",
    "has_video",
    "write_mp4",
]
