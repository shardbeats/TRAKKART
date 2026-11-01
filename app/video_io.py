"""TRAKKART video I/O (ships in the bundle since v1).

MP4 export of still-based animation via imageio + imageio-ffmpeg.
A dev install without them still works: every entry point checks
`has_video()` first and raises `VideoBackendMissing` with install
instructions instead of an ImportError traceback.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

MIN_MP4_FPS = 2
MAX_MP4_FPS = 60


class VideoBackendMissing(RuntimeError):
    """Raised when video I/O is requested without the video backend."""

    def __init__(self) -> None:
        super().__init__(
            "Video support needs imageio + imageio-ffmpeg: "
            "pip install -r requirements.txt"
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


def write_mp4_iter(frame_iter, path: str | Path, fps: int = 24) -> tuple[Path, int]:
    """Stream frames to MP4 without holding the list in RAM (O(1) memory).

    `frame_iter` yields PIL images. Returns (path, n_written). Lets
    dissolve/morph honor Length 0.5-60s (up to 3600f) on full-doc canvas:
    60s @ 3000px would need ~38GB as a list, ~27MB streaming.
    """
    _require_video()
    import imageio.v2 as iio2
    import numpy as np

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = max(MIN_MP4_FPS, min(MAX_MP4_FPS, int(fps)))
    n = 0
    writer = iio2.get_writer(str(out), fps=fps, codec="libx264", quality=8,
                             ffmpeg_params=["-pix_fmt", "yuv420p"])
    try:
        for frame in frame_iter:
            if frame is None:
                continue
            writer.append_data(np.asarray(frame.convert("RGB"), dtype=np.uint8))
            n += 1
            # Defensive: never write past the 60s cap even if the caller
            # mis-plans (3600 = 60s * 60fps).
            if n >= 3600:
                break
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass
    if n == 0:
        raise ValueError("no frames")
    return out, n


__all__ = [
    "VideoBackendMissing",
    "has_video",
    "write_mp4",
    "write_mp4_iter",
]
