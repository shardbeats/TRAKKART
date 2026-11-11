"""TRAKKART preview canvas (single still/video view).

The old preview was a QLabel with a fixed 520px pixmap: on a large window
it floated tiny, "Fit" was just 1.0 and "100%" was 4x, and any zoom past
the label clipped the image with no way to pan. This widget paints the
pixmap at a real fit/zoom scale, keeps the whole image reachable with
drag + wheel, and never lets the pixmap drive the window's minimum size.

Contract (kept small on purpose):
- `setPixmap` / `pixmap` stay QLabel-compatible (controllers and tests).
- `fit()` = fit-to-viewport (up to 3x for small images).
- `actual_size()` = 100% (1 image px per logical px).
- `zoom_step(factor)` = manual zoom, anchored at the viewport center.
- wheel zooms at the cursor; drag pans; double-click returns to fit.
- `zoom_text()` feeds the title-row zoom badge ("Fit", "137%").
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel

#: Display pixmaps above this side are downscaled once (memory guard).
PREVIEW_MAX_SIDE = 4096
#: Small images may grow this much in Fit, never more (keeps dither crisp).
FIT_MAX_UPSCALE = 3.0
MIN_SCALE = 0.01
MAX_SCALE = 8.0
MARGIN = 12


class PreviewCanvas(QLabel):
    """QLabel that paints its pixmap with fit/zoom/pan instead of 1:1."""

    viewChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("previewFrame")
        self.setTextFormat(Qt.RichText)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(200, 200)
        self.setMinimumWidth(200)
        self.setToolTip("Wheel: zoom · drag: pan · double-click: fit")
        self.setCursor(Qt.OpenHandCursor)
        self._mode = "fit"  # "fit" | "manual"
        self._manual = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._drag_from: QPointF | None = None

    # -- QLabel compatibility ------------------------------------------------
    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Never let a big pixmap drive the window minimum (old 2080px bug)."""
        return QSize(200, 200)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(480, 480)

    def setPixmap(self, pixmap: QPixmap) -> None:  # noqa: N802
        super().setPixmap(pixmap)
        self._clamp_pan()
        self.update()
        self.viewChanged.emit()

    # -- view state ----------------------------------------------------------
    def is_fit(self) -> bool:
        return self._mode == "fit"

    def manual_scale(self) -> float:
        return float(self._manual)

    def _pixmap_size(self) -> tuple[float, float]:
        pm = self.pixmap()
        if pm is None or pm.isNull():
            return (0.0, 0.0)
        dpr = float(pm.devicePixelRatio() or 1.0)
        return (pm.width() / dpr, pm.height() / dpr)

    def _fit_scale(self) -> float:
        pw, ph = self._pixmap_size()
        if pw <= 0 or ph <= 0:
            return 1.0
        avail_w = max(1.0, float(self.width()) - MARGIN * 2)
        avail_h = max(1.0, float(self.height()) - MARGIN * 2)
        s = min(avail_w / pw, avail_h / ph)
        return min(FIT_MAX_UPSCALE, max(MIN_SCALE, s))

    def effective_scale(self) -> float:
        if self._mode == "manual":
            return float(self._manual)
        return self._fit_scale()

    def zoom_percent(self) -> int:
        return int(round(self.effective_scale() * 100.0))

    def zoom_text(self) -> str:
        return "Fit" if self._mode == "fit" else f"{self.zoom_percent()}%"

    def fit(self) -> None:
        self._mode = "fit"
        self._pan = QPointF(0.0, 0.0)
        self.update()
        self.viewChanged.emit()

    def actual_size(self) -> None:
        self._set_manual(1.0, anchor=None)

    def zoom_step(self, factor: float) -> None:
        """Multiply the current effective scale (anchored at the center)."""
        self._set_manual(self.effective_scale() * float(factor), anchor=None)

    def _set_manual(self, scale: float, anchor: QPointF | None) -> None:
        pw, ph = self._pixmap_size()
        old = self.effective_scale()
        old_rect = self._target_rect(old) if pw > 0 and ph > 0 else QRectF()
        if anchor is None:
            anchor = QPointF(self.width() / 2.0, self.height() / 2.0)
        # Image point under the anchor before zooming (0..1 of the image).
        if old_rect.width() > 0 and old_rect.height() > 0:
            rx = (float(anchor.x()) - old_rect.left()) / old_rect.width()
            ry = (float(anchor.y()) - old_rect.top()) / old_rect.height()
        else:
            rx = ry = 0.5
        rx = min(1.0, max(0.0, rx))
        ry = min(1.0, max(0.0, ry))
        new = min(MAX_SCALE, max(MIN_SCALE, float(scale)))
        self._mode = "manual"
        self._manual = new
        if pw > 0 and ph > 0:
            # Put the same source point back under the cursor.
            base_x = (self.width() - pw * new) / 2.0
            base_y = (self.height() - ph * new) / 2.0
            self._pan = QPointF(
                float(anchor.x()) - rx * pw * new - base_x,
                float(anchor.y()) - ry * ph * new - base_y,
            )
            self._clamp_pan()
        self.update()
        self.viewChanged.emit()

    # -- geometry / pan ------------------------------------------------------
    def _target_rect(self, scale: float) -> QRectF:
        pw, ph = self._pixmap_size()
        if pw <= 0 or ph <= 0:
            return QRectF()
        tw, th = pw * scale, ph * scale
        vw, vh = float(self.width()), float(self.height())
        if tw <= vw:
            x = (vw - tw) / 2.0
        else:
            x = min(0.0, max(vw - tw, (vw - tw) / 2.0 + self._pan.x()))
        if th <= vh:
            y = (vh - th) / 2.0
        else:
            y = min(0.0, max(vh - th, (vh - th) / 2.0 + self._pan.y()))
        return QRectF(x, y, tw, th)

    def target_rect(self) -> QRectF:
        """Displayed image rect in widget coordinates (tests + tooltips)."""
        return self._target_rect(self.effective_scale())

    def _clamp_pan(self) -> None:
        pw, ph = self._pixmap_size()
        scale = self.effective_scale()
        tw, th = pw * scale, ph * scale
        vw, vh = float(self.width()), float(self.height())
        if tw <= vw:
            self._pan.setX(0.0)
        else:
            lim = (tw - vw) / 2.0
            self._pan.setX(min(lim, max(-lim, self._pan.x())))
        if th <= vh:
            self._pan.setY(0.0)
        else:
            lim = (th - vh) / 2.0
            self._pan.setY(min(lim, max(-lim, self._pan.y())))

    def pan_by(self, dx: float, dy: float) -> None:
        self._pan = QPointF(self._pan.x() + dx, self._pan.y() + dy)
        self._clamp_pan()
        self.update()

    # -- events --------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._clamp_pan()
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_from = QPointF(event.position())
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is not None:
            pos = QPointF(event.position())
            self.pan_by(pos.x() - self._drag_from.x(), pos.y() - self._drag_from.y())
            self._drag_from = pos
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_from = None
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.fit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        steps = event.angleDelta().y() / 120.0
        if not steps:
            return
        self._set_manual(self.effective_scale() * (1.15 ** steps),
                         anchor=QPointF(event.position()))
        event.accept()

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        pm = self.pixmap()
        if pm is None or pm.isNull():
            super().paintEvent(event)  # NO IMAGE placeholder + QSS frame
            return
        pw, ph = self._pixmap_size()
        if pw <= 0 or ph <= 0:
            super().paintEvent(event)
            return
        scale = self.effective_scale()
        rect = self._target_rect(scale)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))
        # Downscale smooth; upscale nearest so dither pixels stay crisp.
        painter.setRenderHint(QPainter.SmoothPixmapTransform, scale < 1.0)
        painter.drawPixmap(rect, pm, QRectF(0.0, 0.0, pm.width(), pm.height()))
        hover = str(self.property("dragHover") or "").lower() == "true"
        pen = QPen(QColor("#F5A623") if hover else QColor("#45474A"))
        pen.setWidth(2 if hover else 1)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 4, 4)
        painter.end()
