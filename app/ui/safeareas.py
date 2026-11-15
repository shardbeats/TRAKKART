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
GUIDE_TEAL = (64, 224, 208)


def grid11_rows(h: int) -> tuple[int, int]:
    """Center 1:1 rows inside a 9:16 frame (profile-grid crop zone)."""
    h = max(1, int(h))
    side = h * 9 // 16
    y0 = (h - side) // 2
    return (y0, y0 + side)


def title_rows(h: int, where: str = "top") -> tuple[int, int]:
    """Text-safe title band inside the chrome-free zone (9:16).

    Top band: first quarter of the safe zone (under the top chrome);
    bottom band: last quarter (above the bottom chrome). Display-only.
    """
    h = max(1, int(h))
    top, bottom = band_rows(h)
    safe0, safe1 = top, h - bottom
    q = max(1, (safe1 - safe0) // 4)
    if str(where).lower() == "bottom":
        return (safe1 - q, safe1)
    return (safe0, safe0 + q)


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


def paint_text_guides(pixmap, titles: tuple[str, ...] = ("top", "bottom")):
    """Copy of a 9:16 pixmap with chrome bands + 1:1 grid + title bands.

    Teal dashed lines: title-safe bands and the profile-grid square.
    Display-only: never touches document pixels.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPen

    out = paint_guides(pixmap)
    w, h = out.width(), out.height()
    if w <= 0 or h <= 0 or not is_916(w, h):
        return out
    p = QPainter(out)
    try:
        pen = QPen(QColor(*GUIDE_TEAL))
        pen.setWidth(max(1, h // 500))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        gy0, gy1 = grid11_rows(h)
        p.drawLine(0, gy0, w, gy0)
        p.drawLine(0, gy1, w, gy1)
        for where in titles:
            try:
                y0, y1 = title_rows(h, where)
            except Exception:  # noqa: BLE001
                continue
            p.fillRect(0, y0, w, y1 - y0, QColor(64, 224, 208, 40))
            p.drawLine(0, y0, w, y0)
            p.drawLine(0, y1, w, y1)
    finally:
        p.end()
    return out


__all__ = [
    "BOTTOM_FRAC",
    "GUIDE_AMBER",
    "GUIDE_TEAL",
    "TOP_FRAC",
    "band_rows",
    "grid11_rows",
    "is_916",
    "paint_guides",
    "paint_rect_guides",
    "paint_text_guides",
    "title_rows",
]
