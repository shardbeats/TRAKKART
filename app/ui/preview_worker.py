"""TRAKKART preview worker: renders off the GUI thread.

Only the LATEST token is applied; stale renders are discarded.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Signal

from app.ui.base_worker import WorkerBase

PREVIEW_LONG_SIDE = 640


def _copy_morph(morph_src):
    """Deep-ish copy of morph extras (PIL images or {img,...} entries)."""
    if isinstance(morph_src, list):
        out = []
        for m in morph_src:
            if isinstance(m, dict):
                img = m.get("img")
                if img is None:
                    continue
                out.append({**m, "img": img.copy()})
            elif m is not None:
                try:
                    out.append(m.copy())
                except Exception:  # noqa: BLE001
                    pass
        return out or None
    if morph_src is None:
        return None
    try:
        return morph_src.copy()
    except Exception:  # noqa: BLE001
        return morph_src


def preview_params(img: Image.Image, params: dict, max_side: int = PREVIEW_LONG_SIDE) -> tuple[Image.Image, int]:
    """Return (downscaled image, effective pixel) keeping relative size."""
    from app.services.render_service import compensate_preview_params, downscale_for_preview

    small, f = downscale_for_preview(img, max_side)
    return small, int(compensate_preview_params(dict(params), f).get("pixel_size", 1))


class PreviewWorker(WorkerBase):
    finished_ok = Signal(object, object, int)  # QImage, PIL, token
    finished_err = Signal(str, int)

    def __init__(self, src: Image.Image, params: dict, token: int, parent=None,
                 *, full: bool = False, target: tuple[int, int] | None = None,
                 max_side: int = PREVIEW_LONG_SIDE) -> None:
        super().__init__(parent)
        self.src = src
        self.params = dict(params)
        self.token = int(token)
        self.full = bool(full)
        self.target = target
        self.max_side = int(max_side)

    def work(self) -> None:
        from app.ui.qt_image import pil_to_qimage

        try:
            if self.full:
                from app import gpu as _gpu

                try:
                    out = _gpu.render_full_kwargs(self.src, dict(self.params))
                except Exception:  # noqa: BLE001
                    from app.pipeline import render as _render

                    out = _render(self.src, **self.params)
                if self.target is not None and out.size != tuple(self.target):
                    out = out.resize(tuple(self.target), Image.NEAREST)
            else:
                from app import gpu as _gpu

                out, _backend = _gpu.render_kwargs_or_cpu(
                    self.src, dict(self.params), max_side=self.max_side)
        except Exception:  # noqa: BLE001
            from app.pipeline import render as _render
            from app.services.render_service import (
                compensate_preview_params,
                downscale_for_preview,
            )

            small, f = downscale_for_preview(self.src, max_side=self.max_side)
            p = compensate_preview_params(dict(self.params), f)
            out = _render(small, **p)
        rgb = out.convert("RGB")
        self.finished_ok.emit(pil_to_qimage(rgb), rgb.copy(), self.token)

    def _report_error(self, exc: Exception) -> None:
        from app.log import report_error

        rid = report_error("still preview", exc,
                           {"max_side": self.max_side, "full": self.full,
                            "target": self.target})
        self.finished_err.emit(f"[{rid}] {exc}" or type(exc).__name__, self.token)


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
        self.morph_src = _copy_morph(morph_src)

    def work(self) -> None:
        from app.gif import gif_frames as _gif_frames

        out = _gif_frames(
            self.src, self.preset, frames=self.frames, mode=self.mode,
            max_side=self.video_size, pingpong=self.pingpong,
            img_b=self.morph_src, fps=self.fps,
        )
        self.finished_ok.emit(out, self.token)

    def _report_error(self, exc: Exception) -> None:
        from app.log import report_error

        try:
            mode = str(self.mode)
        except Exception:  # noqa: BLE001
            mode = "?"
        rid = report_error("video preview", exc,
                           {"mode": mode, "frames": self.frames,
                            "size": self.video_size, "fps": self.fps})
        self.finished_err.emit(f"[{rid}] {exc}" or type(exc).__name__, self.token)

    @staticmethod
    def current_params_snapshot(preset) -> dict:
        """Convert a Preset to pipeline.render() kwargs (no duplication)."""
        from app.render_params import preset_to_render_kwargs

        d = preset_to_render_kwargs(preset)
        d.pop("phase", None)
        return d
