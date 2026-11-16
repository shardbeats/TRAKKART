"""Tiny vector icons drawn with QPainter (no emoji-font dependency).

Emoji glyphs (🔗, 🔒, 🎲) render differently per Windows font pack: the
W×H link showed as a stray "S" on machines without color-emoji fallback.
Icons that carry meaning are drawn here instead, so they look the same
everywhere and follow the theme accent when toggled on.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

INK = "#C9CBCE"
ACCENT = "#F5A623"


def _check_pixmap(size: int = 28) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    try:
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#161617"))
        pen.setWidthF(3.4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        k = size / 28.0
        p.drawPolyline([QPointF(6 * k, 14.5 * k),
                        QPointF(11.5 * k, 20 * k),
                        QPointF(22 * k, 8.5 * k)])
    finally:
        p.end()
    return pm


def ensure_theme_assets(folder: Path) -> str:
    """Write the QSS-only bitmaps once; return the check-mark path."""
    folder.mkdir(parents=True, exist_ok=True)
    check = folder / "check.png"
    if not check.exists():
        _check_pixmap().save(str(check), "PNG")
    return check.as_posix()


def _chain_pixmap(color: str, size: int = 16) -> QPixmap:
    scale = 4
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(scale)
    p = QPainter(pm)
    try:
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(color))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.translate(size / 2, size / 2)
        p.rotate(-45)
        for dx in (-3.1, 1.1):
            p.drawRoundedRect(QRectF(dx, -3.6, 6.4, 7.2), 3.2, 3.2)
    finally:
        p.end()
    return pm


def chain_icon() -> QIcon:
    """Interlocking-link icon: dim when off, accent when on."""
    icon = QIcon()
    icon.addPixmap(_chain_pixmap(INK), QIcon.Normal, QIcon.Off)
    icon.addPixmap(_chain_pixmap(ACCENT), QIcon.Normal, QIcon.On)
    icon.addPixmap(_chain_pixmap("#5A5D61"), QIcon.Disabled, QIcon.Off)
    return icon
