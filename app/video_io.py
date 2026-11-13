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

# Hardware H.264 encoders probed in this order (v1.7 Phase C); anything
# missing or failing falls back to libx264 (software, always present).
HW_ENCODERS = ("h264_nvenc", "h264_qsv", "h264_amf")
SOFTWARE_ENCODER = "libx264"

_encoder_cache: list[str] | None = None


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


def reset_encoder_cache() -> None:
    """Forget the probed encoder list (tests)."""
    global _encoder_cache
    _encoder_cache = None


def available_encoders() -> list[str]:
    """H.264 encoders the bundled ffmpeg offers (software always first).

    Probes `<ffmpeg> -encoders` for NVENC/QSV/AMF; unparsable output or
    a missing backend yields software-only. Result is cached.
    """
    global _encoder_cache
    if _encoder_cache is not None:
        return list(_encoder_cache)
    found = [SOFTWARE_ENCODER]
    try:
        import subprocess

        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        out = subprocess.run([exe, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=30)
        text = str(getattr(out, "stdout", "") or "")
        for name in HW_ENCODERS:
            if name in text:
                found.append(name)
    except Exception:  # noqa: BLE001
        pass
    _encoder_cache = found
    return list(found)


def resolve_encoder(requested: str | None = None) -> str:
    """Map a UI/prefs encoder choice to a usable ffmpeg encoder name.

    None/""/"libx264" (the historic default: every existing caller) =
    software, always present. "auto" = first probed hardware encoder,
    else software. Unknown names -> libx264 (the writers retry in
    software anyway, so this never raises).
    """
    want = str(requested if requested is not None else "").strip().lower()
    if want in ("", SOFTWARE_ENCODER):
        return SOFTWARE_ENCODER
    if want == "auto":
        avail = available_encoders()
        for name in HW_ENCODERS:
            if name in avail:
                return name
        return SOFTWARE_ENCODER
    if want in available_encoders():
        return want
    return SOFTWARE_ENCODER


def write_mp4(frames: list[Image.Image], path: str | Path, fps: int = 24,
              codec: str | None = None) -> Path:
    """Write RGB frames to MP4 (H.264 via imageio-ffmpeg). Deterministic input order."""
    _require_video()
    import imageio.v3 as iio
    import numpy as np

    if not frames:
        raise ValueError("no frames")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = max(MIN_MP4_FPS, min(MAX_MP4_FPS, int(fps)))
    arr = [np.asarray(f.convert("RGB"), dtype=np.uint8) for f in frames]
    # No explicit -pix_fmt: imageio adds yuv420p itself (passing it twice
    # only spams ffmpeg's "Multiple -pix_fmt options specified" warning).
    enc = resolve_encoder(codec)
    try:
        iio.imwrite(str(out), arr, fps=fps, codec=enc, quality=8,
                    macro_block_size=2,
                    ffmpeg_params=["-movflags", "+faststart"])
    except Exception:  # noqa: BLE001
        if enc == SOFTWARE_ENCODER:
            raise
        enc = SOFTWARE_ENCODER
        iio.imwrite(str(out), arr, fps=fps, codec=enc, quality=8,
                    macro_block_size=2,
                    ffmpeg_params=["-movflags", "+faststart"])
    if enc != SOFTWARE_ENCODER:
        # Some hw encoders fail silently (0-byte file, e.g. frames below
        # the encoder's minimum dimensions): retry once in software.
        try:
            empty = out.stat().st_size == 0
        except OSError:
            empty = True
        if empty:
            iio.imwrite(str(out), arr, fps=fps, codec=SOFTWARE_ENCODER, quality=8,
                        macro_block_size=2,
                        ffmpeg_params=["-movflags", "+faststart"])
    return out


def write_mp4_iter(frame_iter, path: str | Path, fps: int = 24,
                   codec: str | None = None) -> tuple[Path, int]:
    """Stream frames to MP4 without holding the list in RAM (O(1) memory).

    `frame_iter` yields PIL images. Returns (path, n_written). Lets
    long hold-heavy dissolve/morph clips export on full-doc canvas:
    3600 frames stream at ~27MB where a list would need ~38GB at 3000px.
    Hardware encoder on request with a software retry (same rule as
    `write_mp4`); the hw path buffers the iterable (list) so the retry
    can replay it, while software keeps true O(1) streaming.
    """
    _require_video()
    import imageio.v2 as iio2
    import numpy as np

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = max(MIN_MP4_FPS, min(MAX_MP4_FPS, int(fps)))
    enc = resolve_encoder(codec)
    if enc != SOFTWARE_ENCODER:
        frame_iter = list(frame_iter)
    n = 0
    try:
        writer = iio2.get_writer(str(out), fps=fps, codec=enc, quality=8,
                                 macro_block_size=2,
                                 ffmpeg_params=["-movflags", "+faststart"])
    except Exception:  # noqa: BLE001
        enc = SOFTWARE_ENCODER
        writer = iio2.get_writer(str(out), fps=fps, codec=enc, quality=8,
                                 macro_block_size=2,
                                 ffmpeg_params=["-movflags", "+faststart"])
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
    if enc != SOFTWARE_ENCODER:
        # Same silent-hw-failure rule as write_mp4 (buffered above, replayable).
        try:
            empty = out.stat().st_size == 0
        except OSError:
            empty = True
        if empty:
            return write_mp4_iter(frame_iter, path, fps=fps,
                                  codec=SOFTWARE_ENCODER)
    return out, n


__all__ = [
    "VideoBackendMissing",
    "has_video",
    "write_mp4",
    "write_mp4_iter",
    "available_encoders",
    "resolve_encoder",
    "reset_encoder_cache",
    "HW_ENCODERS",
    "SOFTWARE_ENCODER",
]
