"""TRAKKART preview worker: renders off the GUI thread.

Only the LATEST token is applied; stale renders are discarded.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Signal

from app.ui.base_worker import WorkerBase

PREVIEW_LONG_SIDE = 640


def preview_params(img: Image.Image, params: dict, max_side: int = PREVIEW_LONG_SIDE) -> tuple[Image.Image, int]:
    """Return (downscaled image, effective pixel) keeping relative size."""
    from app.services.render_service import downscale_for_preview

    small, f = downscale_for_preview(img, max_side)
    pixel = int(params.get("pixel_size", 1)) if f >= 1.0 else max(1, round(int(params.get("pixel_size", 1)) / f))
    return small, pixel


class PreviewWorker(WorkerBase):
    finished_ok = Signal(object, object, int)  # QImage, PIL, token
    finished_err = Signal(str, int)

    def __init__(self, src: Image.Image, params: dict, token: int, parent=None) -> None:
        super().__init__(parent)
        self.src = src
        self.params = dict(params)
        self.token = int(token)

    def work(self) -> None:
        from app.pipeline import render as _render
        from app.ui.qt_image import pil_to_qimage

        small, pixel = preview_params(self.src, self.params)
        p = dict(self.params)
        p["pixel_size"] = pixel
        out = _render(small, **p)
        rgb = out.convert("RGB")
        self.finished_ok.emit(pil_to_qimage(rgb), rgb.copy(), self.token)

    def _report_error(self, exc: Exception) -> None:
        self.finished_err.emit(str(exc) or type(exc).__name__, self.token)


class VideoWorker(WorkerBase):
    """Full-canvas video preview: N frames in thread, no freeze.

    Uses gif_frames() with max_side=video_size (default 1200). Only the
    latest token is applied; old renders are discarded.
    """

    finished_ok = Signal(object, int)  # list[PIL], token
    finished_err = Signal(str, int)

    def __init__(self, src: Image.Image, preset, video_size: int,
                 frames: int, mode: str, pingpong: bool, token: int,
                 morph_src=None, fps: int | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.src = src
        self.preset = preset
        self.video_size = int(video_size)
        self.frames = int(frames)
        self.mode = str(mode)
        self.pingpong = bool(pingpong)
        self.token = int(token)
        self.fps = None if fps is None else int(fps)
        if isinstance(morph_src, list):
            self.morph_src = [m.copy() for m in morph_src if m is not None]
        elif morph_src is not None:
            self.morph_src = morph_src.copy()
        else:
            self.morph_src = None

    def work(self) -> None:
        from app.gif import gif_frames as _gif_frames

        out = _gif_frames(
            self.src, self.preset, frames=self.frames, mode=self.mode,
            max_side=self.video_size, pingpong=self.pingpong,
            img_b=self.morph_src, fps=self.fps,
        )
        self.finished_ok.emit(out, self.token)

    def _report_error(self, exc: Exception) -> None:
        self.finished_err.emit(str(exc) or type(exc).__name__, self.token)

    @staticmethod
    def current_params_snapshot(preset) -> dict:
        """Convert a Preset to pipeline.render() kwargs (no duplication)."""
        from app.render_params import preset_to_render_kwargs

        d = preset_to_render_kwargs(preset)
        d.pop("phase", None)
        return d
