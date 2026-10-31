"""TRAKKART visual crop editor — mobile-style frame (grid + drag + zoom).

Modal dialog replacing the old focus X/Y sliders: a fixed-ratio frame with
a rule-of-thirds grid, dimmed surroundings, drag-to-pan and wheel-to-zoom,
plus Rotate / Reset / ratio / mode controls (Cancel / Done on top).
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.canvas import (
    CROP_MODES,
    CUSTOM_RATIO,
    MAX_DIM,
    MIN_DIM,
    canvas_ratios,
    crop_box_for,
    ratio_label,
    ratio_names,
    ratio_value,
)
from app.ops import rotate_right

MIN_ZOOM = 1.0
MAX_ZOOM = 4.0


def _pil_to_pixmap(img: Image.Image) -> QPixmap:
    """Compat: uses the single ui.qt_image implementation."""
    from app.ui.qt_image import pil_to_pixmap

    return pil_to_pixmap(img, max_side=4096)


class CropView(QWidget):
    """Image + ratio frame (dimmed outside, thirds grid). Drag pans, wheel zooms."""

    cropChanged = Signal()

    def __init__(self, img: Image.Image, ratio: str = "1:1", mode: str = "cover",
                 fx: float = 50.0, fy: float = 50.0, zoom: float = 1.0,
                 canvas_w: int = 0, canvas_h: int = 0,
                 parent=None) -> None:
        super().__init__(parent)
        self._img = img.convert("RGB")
        self.ratio = ratio
        self.mode = mode
        self.fx = float(fx)
        self.fy = float(fy)
        self.zoom = min(MAX_ZOOM, max(MIN_ZOOM, float(zoom)))
        self.canvas_w = int(canvas_w or 0)
        self.canvas_h = int(canvas_h or 0)
        self._drag_from: QPointF | None = None
        # Paint cache (P1): the photo itself never changes while dragging
        # (only the frame moves), so converting PIL->QPixmap every paint
        # wastes full-res work at drag rate. Cached by object identity;
        # rotate replaces _img, which invalidates automatically.
        self._pix_src: Image.Image | None = None
        self._pix_cache: QPixmap | None = None
        # Owned box (source px, floats): gestures mutate it directly so the
        # zoom anchor round-trips exactly. fx/fy stay synced for the dialog
        # result + summary; crop_box_for is only the seeder (ratio/mode/
        # canvas/rotate/reset), never part of the gesture loop.
        self._box: list[float] = [0.0, 0.0, 1.0, 1.0]
        self._reseed()
        self.setMinimumSize(420, 420)
        self.setMouseTracking(False)
        self.setCursor(Qt.OpenHandCursor)

    def _reseed(self) -> None:
        """Recompute the box from fx/fy/zoom (structural changes only)."""
        iw, ih = self._img.width, self._img.height
        bx, by, bw, bh = crop_box_for(iw, ih, self.ratio, self.fx, self.fy, self.zoom,
                                      canvas_w=self.canvas_w, canvas_h=self.canvas_h)
        self._box = [float(bx), float(by), float(bw), float(bh)]
        self._sync_focus()

    def _sync_focus(self) -> None:
        """fx/fy describe where the owned box sits inside its slack."""
        iw, ih = self._img.width, self._img.height
        _bx, _by, bw, bh = self._box
        slack_x, slack_y = iw - bw, ih - bh
        if slack_x > 0:
            self.fx = min(100.0, max(0.0, 100.0 * _bx / slack_x))
        if slack_y > 0:
            self.fy = min(100.0, max(0.0, 100.0 * _by / slack_y))

    # -- geometry (source px <-> widget px) --
    def _layout(self) -> dict:
        w, h = max(1, self.width()), max(1, self.height())
        iw, ih = self._img.width, self._img.height
        if self.mode != "cover":
            from app.canvas import to_canvas

            canvas = to_canvas(self._img, self.ratio, self.mode,
                               canvas_w=self.canvas_w, canvas_h=self.canvas_h)
            cw, ch = canvas.width, canvas.height
            s = min(w / cw, h / ch)
            dw, dh = cw * s, ch * s
            ox, oy = (w - dw) / 2.0, (h - dh) / 2.0
            return {"mode": self.mode, "canvas": canvas, "s": s, "ox": ox, "oy": oy,
                    "frame": QRectF(ox, oy, dw, dh), "img_rect": QRectF(ox, oy, dw, dh)}
        s = min(w / iw, h / ih)
        dw, dh = iw * s, ih * s
        ox, oy = (w - dw) / 2.0, (h - dh) / 2.0
        bx, by, bw, bh = self._box
        frame = QRectF(ox + bx * s, oy + by * s, bw * s, bh * s)
        return {"mode": "cover", "s": s, "ox": ox, "oy": oy,
                "frame": frame, "img_rect": QRectF(ox, oy, dw, dh),
                "box": (bx, by, bw, bh)}

    def _cover_pixmap(self) -> QPixmap:
        """Full-res pixmap of the source, cached across paints."""
        if self._pix_cache is None or self._pix_src is not self._img:
            self._pix_src = self._img
            self._pix_cache = _pil_to_pixmap(self._img)
        return self._pix_cache

    # -- painting --
    def paintEvent(self, _event) -> None:  # noqa: N802
        lay = self._layout()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), Qt.black)
        if lay["mode"] != "cover":
            pix = _pil_to_pixmap(lay["canvas"])
            p.drawPixmap(lay["img_rect"].toRect(), pix)
        else:
            p.drawPixmap(lay["img_rect"].toRect(), self._cover_pixmap())
        frame: QRectF = lay["frame"]
        radius = min(28.0, frame.width() / 8.0, frame.height() / 8.0)
        frame_path = QPainterPath()
        frame_path.addRoundedRect(frame, radius, radius)
        dim = QPainterPath()
        dim.addRect(QRectF(self.rect()))
        dim = dim.subtracted(frame_path)
        p.fillPath(dim, QColor(0, 0, 0, 150))
        p.setClipPath(frame_path)
        grid_pen = QPen(Qt.white)
        grid_pen.setWidth(1)
        grid_pen.setColor(QColor(255, 255, 255, 110))
        p.setPen(grid_pen)
        for i in (1, 2):
            x = frame.left() + frame.width() * i / 3.0
            p.drawLine(QPointF(x, frame.top()), QPointF(x, frame.bottom()))
            y = frame.top() + frame.height() * i / 3.0
            p.drawLine(QPointF(frame.left(), y), QPointF(frame.right(), y))
        p.setClipping(False)
        border = QPen(Qt.white)
        border.setWidth(3)
        p.setPen(border)
        p.drawRoundedRect(frame, radius, radius)
        p.end()

    # -- interaction --
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.mode == "cover":
            self._drag_from = QPointF(event.position())
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is None or self.mode != "cover":
            return
        lay = self._layout()
        s = lay["s"]
        dx = (event.position().x() - self._drag_from.x()) / s
        dy = (event.position().y() - self._drag_from.y()) / s
        self._drag_from = QPointF(event.position())
        # The photo is static, the frame moves: frame follows the finger.
        self.pan_by(dx, dy)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_from = None
            self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self.mode != "cover":
            return
        steps = event.angleDelta().y() / 120.0
        if not steps:
            return
        self.zoom_at(QPointF(event.position()), 1.15 ** steps)

    # -- crop math (source pixels, on the owned box) --
    def pan_by(self, dx: float, dy: float) -> None:
        """Shift the crop box by (dx, dy) source px (drag moves the frame)."""
        iw, ih = self._img.width, self._img.height
        bx, by, bw, bh = self._box
        self._box[0] = min(iw - bw, max(0.0, bx + dx))
        self._box[1] = min(ih - bh, max(0.0, by + dy))
        self._sync_focus()
        self.cropChanged.emit()
        self.update()

    def zoom_at(self, pos: QPointF, factor: float) -> None:
        """Zoom anchored at a widget point (clamped 1-4x).

        The anchor is read from the owned box, so the source point under
        the cursor survives every step (no snap-back loop).
        """
        new_zoom = min(MAX_ZOOM, max(MIN_ZOOM, self.zoom * factor))
        if new_zoom <= MIN_ZOOM:
            self.zoom = MIN_ZOOM
            self._reseed()
            self.cropChanged.emit()
            self.update()
            return
        lay = self._layout()
        s, ox, oy = lay["s"], lay["ox"], lay["oy"]
        iw, ih = self._img.width, self._img.height
        cx = (pos.x() - ox) / s
        cy = (pos.y() - oy) / s
        obx, oby, obw, obh = self._box
        _nx, _ny, nbw, nbh = crop_box_for(iw, ih, self.ratio, self.fx, self.fy,
                                          new_zoom, canvas_w=self.canvas_w,
                                          canvas_h=self.canvas_h)
        if obw > 0 and obh > 0 and nbw > 0 and nbh > 0:
            # Keep the source point under the cursor fixed. The cursor may sit
            # over the black bars (outside the image): clamp the anchor to the
            # box so zoom leans to the nearest edge instead of snapping away.
            rx = min(1.0, max(0.0, (cx - obx) / obw))
            ry = min(1.0, max(0.0, (cy - oby) / obh))
            slack_x, slack_y = iw - nbw, ih - nbh
            self._box[0] = min(slack_x, max(0.0, cx - rx * nbw)) if slack_x > 0 else 0.0
            self._box[1] = min(slack_y, max(0.0, cy - ry * nbh)) if slack_y > 0 else 0.0
            self._box[2], self._box[3] = float(nbw), float(nbh)
        self.zoom = new_zoom
        self._sync_focus()
        self.cropChanged.emit()
        self.update()

    def reset_crop(self) -> None:
        self.fx, self.fy, self.zoom = 50.0, 50.0, 1.0
        self._reseed()
        self.cropChanged.emit()
        self.update()


class CropEditorDialog(QDialog):
    """Modal crop editor: Cancel/Done on top, view, Rotate/Reset/ratio/mode.

    With fixed_frame=True the frame is locked (ratio/mode/W/H disabled):
    for callers that fit the crop into a pre-set canvas (e.g. the MORPH
    chain, where every image covers A's box).
    """

    def __init__(self, img: Image.Image, ratio: str = "1:1", mode: str = "cover",
                 fx: float = 50.0, fy: float = 50.0, zoom: float = 1.0,
                 canvas_w: int = 0, canvas_h: int = 0,
                 fixed_frame: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adjust crop")
        self.setMinimumSize(560, 640)
        self.image = img.convert("RGB")
        self.turns = 0
        if ratio not in ratio_names() and ratio != CUSTOM_RATIO:
            ratio = "1:1"
        if mode not in CROP_MODES:
            mode = "cover"
        self._doc_w = max(MIN_DIM, min(MAX_DIM, int(canvas_w or 0) or 3000))
        self._doc_h = max(MIN_DIM, min(MAX_DIM, int(canvas_h or 0) or 3000))

        col = QVBoxLayout(self)
        top = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        top.addWidget(self.btn_cancel)
        top.addStretch()
        self.btn_done = QPushButton("Done")
        self.btn_done.setObjectName("exportBtn")
        self.btn_done.setDefault(True)
        self.btn_done.clicked.connect(self.accept)
        top.addWidget(self.btn_done)
        col.addLayout(top)

        self.view = CropView(self.image, ratio, mode, fx, fy, zoom,
                             canvas_w=self._doc_w, canvas_h=self._doc_h)
        col.addWidget(self.view, 1)

        self.lbl_hint = QLabel("Drag to move · Mouse wheel to zoom")
        self.lbl_hint.setAlignment(Qt.AlignCenter)
        col.addWidget(self.lbl_hint)
        self.lbl_summary = QLabel()
        self.lbl_summary.setAlignment(Qt.AlignCenter)
        col.addWidget(self.lbl_summary)

        from PySide6.QtWidgets import QSpinBox

        wh_row = QHBoxLayout()
        wh_row.addWidget(QLabel("W:"))
        self.spn_w = QSpinBox()
        self.spn_w.setRange(MIN_DIM, MAX_DIM)
        self.spn_w.setValue(self._doc_w)
        self.spn_w.setSuffix(" px")
        self.spn_w.valueChanged.connect(self._on_wh)
        wh_row.addWidget(self.spn_w, 1)
        wh_row.addWidget(QLabel("H:"))
        self.spn_h = QSpinBox()
        self.spn_h.setRange(MIN_DIM, MAX_DIM)
        self.spn_h.setValue(self._doc_h)
        self.spn_h.setSuffix(" px")
        self.spn_h.valueChanged.connect(self._on_wh)
        wh_row.addWidget(self.spn_h, 1)
        col.addLayout(wh_row)

        bottom = QHBoxLayout()
        self.btn_rotate = QPushButton("Rotate")
        self.btn_rotate.setToolTip("Rotate 90° clockwise")
        self.btn_rotate.clicked.connect(self.rotate_cw)
        bottom.addWidget(self.btn_rotate)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self.reset_crop)
        bottom.addWidget(self.btn_reset)
        bottom.addWidget(QLabel("Ratio:"))
        self.cmb_ratio = QComboBox()
        self.cmb_ratio.addItems(canvas_ratios())
        self.cmb_ratio.setCurrentText(ratio_label(self.view.ratio))
        self.cmb_ratio.currentTextChanged.connect(self._on_ratio)
        bottom.addWidget(self.cmb_ratio, 1)
        bottom.addWidget(QLabel("Mode:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(list(CROP_MODES))
        self.cmb_mode.setCurrentText(self.view.mode)
        self.cmb_mode.currentTextChanged.connect(self._on_mode)
        bottom.addWidget(self.cmb_mode, 1)
        col.addLayout(bottom)

        self.view.cropChanged.connect(self._sync_summary)
        self._sync_wh_enabled()
        self._sync_summary()
        if fixed_frame:
            for w in (self.cmb_ratio, self.cmb_mode, self.spn_w, self.spn_h):
                try:
                    w.setEnabled(False)
                except Exception:  # noqa: BLE001
                    pass
            self.lbl_hint.setText("Frame locked to chain canvas (A) — drag to move, wheel to zoom")

    def _sync_wh_enabled(self) -> None:
        custom = self.view.ratio == CUSTOM_RATIO
        self.spn_w.setEnabled(custom)
        self.spn_h.setEnabled(custom)
        self.lbl_hint.setText(
            "Set free W×H (custom canvas)" if custom
            else "Drag to move · Mouse wheel to zoom")

    # -- slots --
    def _on_ratio(self, name: str) -> None:
        self.view.ratio = ratio_value(name)
        self.view._reseed()
        self._sync_wh_enabled()
        self.view.update()
        self._sync_summary()

    def _on_wh(self) -> None:
        doc_w = int(self.spn_w.value())
        doc_h = int(self.spn_h.value())
        self.view.canvas_w = doc_w
        self.view.canvas_h = doc_h
        if self.view.ratio != CUSTOM_RATIO:
            self.cmb_ratio.blockSignals(True)
            self.cmb_ratio.setCurrentText(ratio_label(CUSTOM_RATIO))
            self.cmb_ratio.blockSignals(False)
            self.view.ratio = CUSTOM_RATIO
            self._sync_wh_enabled()
        self.view._reseed()
        self.view.update()
        self._sync_summary()

    def _on_mode(self, name: str) -> None:
        self.view.mode = name
        if name != "cover":
            self.view.reset_crop()
        else:
            self.view._reseed()
        self.view.update()
        self._sync_summary()

    def rotate_cw(self) -> None:
        self.image = rotate_right(self.image)
        self.turns = (self.turns + 1) % 4
        self.view._img = self.image
        self.view._reseed()
        self.view.update()

    def reset_crop(self) -> None:
        self.view.reset_crop()

    def _sync_summary(self) -> None:
        if self.view.ratio == CUSTOM_RATIO:
            dims = f"{self.doc_w}×{self.doc_h}"
        else:
            dims = f"{ratio_label(self.view.ratio)}"
        self.lbl_summary.setText(
            f"{dims} · {self.view.mode} · "
            f"focus {self.view.fx:.0f}, {self.view.fy:.0f} · {self.view.zoom:.1f}x"
        )

    # -- results (valid after accept) --
    @property
    def ratio(self) -> str:
        return self.view.ratio

    @property
    def mode(self) -> str:
        return self.view.mode

    @property
    def fx(self) -> float:
        return float(self.view.fx)

    @property
    def fy(self) -> float:
        return float(self.view.fy)

    @property
    def zoom(self) -> float:
        return float(self.view.zoom)

    @property
    def doc_w(self) -> int:
        return int(self.spn_w.value())

    @property
    def doc_h(self) -> int:
        return int(self.spn_h.value())
