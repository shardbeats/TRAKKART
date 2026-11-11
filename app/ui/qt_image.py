"""Qt <-> PIL image conversions. Single implementation.

Before: `main_window.pil_to_pixmap` and `crop_editor._pil_to_pixmap`
duplicated the same conversion, and `MainWindow._load_qimage` /
`paste_image` duplicated QImage -> PIL with numpy.
"""

from __future__ import annotations

from PIL import Image


def pil_to_pixmap(img: Image.Image, max_side: int = 520):
    """PIL -> QPixmap, downscaling the long side to max_side. No mutation.

    BICUBIC downscale (smooth on photos, not chunky) with HiDPI backing:
    on a 2x screen the pixmap carries 2x pixels and reports the ratio, so
    the label keeps the same logical size, crisp. No-op at ratio 1.
    """
    from PySide6.QtGui import QImage, QPixmap

    try:
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
    except Exception:  # noqa: BLE001
        dpr = 1.0
    if not dpr > 1.0:
        dpr = 1.0
    rgb = img.convert("RGB")
    if rgb.width < 1 or rgb.height < 1:
        return QPixmap()  # empty render: never divide by a zero side
    r = (max_side * dpr) / max(rgb.width, rgb.height)
    if r < 1.0:
        rgb = rgb.resize((max(1, int(rgb.width * r)), max(1, int(rgb.height * r))), Image.BICUBIC)
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    pix = QPixmap.fromImage(qimg.copy())
    if dpr > 1.0:
        pix.setDevicePixelRatio(dpr)
    return pix


def pil_to_qimage(img: Image.Image):
    """PIL -> QImage (independent copy, no downscale)."""
    from PySide6.QtGui import QImage

    rgb = img.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    return qimg.copy()


def qimage_to_pil(qimg) -> Image.Image:
    """QImage -> PIL RGB. Raises ValueError when null."""
    from PySide6.QtGui import QImage

    import numpy as np

    if qimg is None or getattr(qimg, "isNull", lambda: True)():
        raise ValueError("empty QImage")
    conv = qimg.convertToFormat(QImage.Format_RGB888)
    w, h = conv.width(), conv.height()
    arr = np.frombuffer(conv.bits(), dtype=np.uint8).reshape(h, w, 3).copy()
    return Image.fromarray(arr)


__all__ = ["pil_to_pixmap", "pil_to_qimage", "qimage_to_pil"]
