"""Preview canvas: fit, real 100%, pan/clamp and layout safety."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap

from app.ui.preview_canvas import PreviewCanvas


def test_fit_uses_viewport_and_centers(qt_app):
    view = PreviewCanvas()
    view.resize(800, 600)
    view.setPixmap(QPixmap(400, 300))
    view.fit()
    rect = view.target_rect()
    assert rect.width() <= 800 and rect.height() <= 600
    assert rect.width() >= 750 and rect.height() >= 560  # fills the canvas
    assert abs(rect.center().x() - 400) < 1
    assert abs(rect.center().y() - 300) < 1
    assert view.zoom_text() == "Fit"


def test_actual_size_is_real_100_percent_and_pan_clamps(qt_app):
    view = PreviewCanvas()
    view.resize(400, 300)
    view.setPixmap(QPixmap(1000, 800))
    view.actual_size()
    assert view.zoom_text() == "100%"
    rect = view.target_rect()
    assert (round(rect.width()), round(rect.height())) == (1000, 800)
    view.pan_by(-10000, -10000)
    rect = view.target_rect()
    assert abs(rect.left() - (400 - 1000)) < 1  # right edge flush
    view.pan_by(10000, 10000)
    rect = view.target_rect()
    assert abs(rect.left()) < 1  # left edge flush


def test_zoom_is_manual_and_clamped(qt_app):
    view = PreviewCanvas()
    view.resize(400, 300)
    view.setPixmap(QPixmap(200, 200))
    view.actual_size()
    view.zoom_step(2.0)
    assert view.zoom_text() == "200%"
    view.zoom_step(100.0)
    assert view.zoom_text() == "800%"
    view.fit()
    assert view.is_fit() is True


def test_big_pixmap_never_drives_minimum_size(qt_app):
    view = PreviewCanvas()
    view.setPixmap(QPixmap(3000, 3000))
    assert view.minimumSizeHint() == QSize(200, 200)


def test_empty_canvas_paints_placeholder(qt_app):
    view = PreviewCanvas()
    view.resize(300, 200)
    view.setText("NO IMAGE")
    view.grab()  # super().paintEvent placeholder path, no crash
    assert view.pixmap().isNull()
