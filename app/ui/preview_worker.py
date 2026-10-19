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
        self.finished_err.emit(str(exc), self.token)

    @staticmethod
    def current_params_snapshot(preset) -> dict:
        """Convert a Preset to pipeline.render() kwargs (sin duplicar)."""
        from app.render_params import preset_to_render_kwargs

        d = preset_to_render_kwargs(preset)
        d.pop("phase", None)
        return d
