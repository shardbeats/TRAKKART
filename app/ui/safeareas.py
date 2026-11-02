"""Safe-area guides (R12): 9:16 chrome overlays for social canvas.

IG/TikTok/Shorts cover roughly 250px top + bottom of a 1080x1920
frame with player chrome. Bands are fractions of the height, so the
same code paints display pixmaps (preview) and widget rects (crop
editor) at any scale. Display-only: never touches document pixels.
"""

from __future__ import annotations

TOP_FRAC = 250.0 / 1920.0
BOTTOM_FRAC = 250.0 / 1920.0
GUIDE_AMBER = (245, 166, 35)


def is_916(w: int, h: int) -> bool:
    """True when the aspect is 9:16 within 1% (zero-safe)."""
    try:
        if max(1, int(h)) <= 0 or max(1, int(w)) <= 0:
            return False
        return abs(float(w) / float(h) - 9.0 / 16.0) < 0.01
    except (TypeError, ValueError, ZeroDivisionError):
        return False


def band_rows(h: int) -> tuple[int, int]:
    """(top_rows, bottom_rows) of chrome for a height of h px."""
    h = max(1, int(h))
    return (int(round(h * TOP_FRAC)), int(round(h * BOTTOM_FRAC)))


def paint_guides(pixmap):
    """Copy of a 9:16 pixmap with translucent chrome bands + amber edges."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPen

    out = pixmap.copy()
    w, h = out.width(), out.height()
    if w <= 0 or h <= 0 or not is_916(w, h):
        return out
    top, bottom = band_rows(h)
    p = QPainter(out)
    try:
        p.fillRect(0, 0, w, top, QColor(0, 0, 0, 90))
        p.fillRect(0, h - bottom, w, bottom, QColor(0, 0, 0, 90))
        pen = QPen(QColor(*GUIDE_AMBER))
        pen.setWidth(max(1, h // 500))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawLine(0, top, w, top)
        p.drawLine(0, h - bottom, w, h - bottom)
    finally:
        p.end()
    return out


def paint_rect_guides(painter, rect) -> None:
    """Chrome bands over a widget rect (crop editor frame). No-op unless 9:16."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPen

    try:
        w, h = float(rect.width()), float(rect.height())
    except Exception:  # noqa: BLE001
        return
    if not is_916(w, h):
        return
    top, bottom = band_rows(h)
    painter.fillRect(rect.left(), rect.top(), w, top, QColor(0, 0, 0, 90))
    painter.fillRect(rect.left(), rect.bottom() - bottom, w, bottom, QColor(0, 0, 0, 90))
    pen = QPen(QColor(*GUIDE_AMBER))
    pen.setWidth(max(1, int(h) // 500))
    pen.setStyle(Qt.DashLine)
    painter.setPen(pen)
    painter.drawLine(rect.left(), rect.top() + top, rect.right(), rect.top() + top)
    painter.drawLine(rect.left(), rect.bottom() - bottom, rect.right(), rect.bottom() - bottom)


__all__ = [
    "BOTTOM_FRAC",
    "GUIDE_AMBER",
    "TOP_FRAC",
    "band_rows",
    "is_916",
    "paint_guides",
    "paint_rect_guides",
]
