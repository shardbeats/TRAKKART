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


def test_wipe_drag_emits_percent(qt_app):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    view = PreviewCanvas()
    view.resize(400, 400)
    view.setPixmap(QPixmap(400, 400))
    view.fit()
    view.set_wipe_mode(True)
    got: list[int] = []
    view.wipeDragged.connect(got.append)

    def ev(kind, x, buttons=Qt.LeftButton):
        return QMouseEvent(kind, QPointF(x, 200), Qt.LeftButton, buttons,
                           Qt.KeyboardModifier.NoModifier)

    view.mousePressEvent(ev(QMouseEvent.Type.MouseButtonPress, 100))
    view.mouseMoveEvent(ev(QMouseEvent.Type.MouseMove, 300))
    view.mouseReleaseEvent(ev(QMouseEvent.Type.MouseButtonRelease, 300,
                              Qt.MouseButton.NoButton))
    assert got
    assert 20 <= got[0] <= 28  # left quarter of the fitted image
    assert 72 <= got[-1] <= 80  # right quarter


def test_preview_max_side_tracks_viewport(qt_app):
    from types import SimpleNamespace

    from app.ui.preview_controller import preview_max_side

    view = PreviewCanvas()
    view.resize(1000, 700)
    dpr = max(1.0, float(view.devicePixelRatioF()))
    win = SimpleNamespace(lbl_res=view)
    assert preview_max_side(win) == max(640, min(1600, int(1000 * dpr)))
    view.resize(200, 200)
    assert preview_max_side(win) == 640


def test_document_target_only_when_full_has_detail(qt_app):
    from types import SimpleNamespace

    from PIL import Image

    from app.presets import Preset
    from app.ui.preview_controller import document_target

    p = Preset(name="x", ratio="9:16", canvas_w=1688, canvas_h=3000,
               export_size=3000)
    assert document_target(SimpleNamespace(src=Image.new("RGB", (4000, 3000))),
                           p) == (1688, 3000)
    assert document_target(SimpleNamespace(src=Image.new("RGB", (900, 1200))),
                           p) is None
    wide = Preset(name="x", ratio="custom", canvas_w=1920, canvas_h=800,
                  export_size=1920)
    assert document_target(SimpleNamespace(src=Image.new("RGB", (1080, 1920))),
                           wide) is None
