"""Qt <-> PIL image conversions. Single implementation.

Antes: `main_window.pil_to_pixmap` y `crop_editor._pil_to_pixmap`
duplicaban la misma conversión, y `MainWindow._load_qimage` /
`paste_image` duplicaban QImage -> PIL con numpy.
"""

from __future__ import annotations

from PIL import Image


def pil_to_pixmap(img: Image.Image, max_side: int = 520):
    """PIL -> QPixmap, downscaleando el lado largo a max_side. No muta."""
    from PySide6.QtGui import QImage, QPixmap

    rgb = img.convert("RGB")
    r = max_side / max(rgb.width, rgb.height)
    if r < 1.0:
        rgb = rgb.resize((int(rgb.width * r), int(rgb.height * r)))
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def pil_to_qimage(img: Image.Image):
    """PIL -> QImage (copia independiente, sin downscale)."""
    from PySide6.QtGui import QImage

    rgb = img.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    return qimg.copy()


def qimage_to_pil(qimg) -> Image.Image:
    """QImage -> PIL RGB. Lanza ValueError si es nula."""
    from PySide6.QtGui import QImage

    import numpy as np

    if qimg is None or getattr(qimg, "isNull", lambda: True)():
        raise ValueError("empty QImage")
    conv = qimg.convertToFormat(QImage.Format_RGB888)
    w, h = conv.width(), conv.height()
    arr = np.frombuffer(conv.bits(), dtype=np.uint8).reshape(h, w, 3).copy()
    return Image.fromarray(arr)


__all__ = ["pil_to_pixmap", "pil_to_qimage", "qimage_to_pil"]
