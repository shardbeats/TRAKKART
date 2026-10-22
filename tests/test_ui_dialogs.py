"""UI dialogs & actions: open/batch/crop/share/ops/layout (fixtures en conftest)."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def test_open_image_cancel(window, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window.open_image()  # must not crash on cancel


def test_run_batch_sync(window, tmp_path: Path):
    from PIL import Image as Img

    src = tmp_path / "in"
    dst = tmp_path / "dst"
    src.mkdir()
    for i in range(2):
        Img.new("RGB", (32, 32), (50, 100, 150)).save(src / f"c{i}.png")
    window.cmb_preset.setCurrentText("SLIME_FS")
    results = window.run_batch_sync(src, dst)
    assert len(results) == 2
    assert all(r["status"] == "ok" for r in results)
    assert len(list(dst.glob("*.png"))) == 4  # imagen + thumb por fichero


def test_batch_dialog_cancel(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import app.ui.main_window as MW

    class FakeDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected  # cancel: does nothing

    monkeypatch.setattr(MW, "BatchDialog", FakeDialog)
    window.run_batch_dialog()  # cancelled: does nothing


def test_batch_dialog_accept_starts_run(window, tmp_path: Path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import app.ui.main_window as MW

    src = tmp_path / "in"
    src.mkdir()
    seen: dict = {}

    def _fake(src_p, dst_p, jobs=None, preset=None):
        seen.update(src=src_p, dst=dst_p, jobs=jobs,
                    vector=preset.vector_export if preset else None,
                    preset=preset)

    class FakeDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def paths(self):
            return src, tmp_path / "dst", 2

        def output_options(self):
            return {"vector_export": False, "vector_cell": 8,
                    "gif_export": False, "gif_frames": 6, "gif_mode": "both",
                    "export_size": 3000, "export_format": "png",
                    "export_quality": 90}

    monkeypatch.setattr(MW, "BatchDialog", FakeDialog)
    monkeypatch.setattr(window, "run_batch", _fake)
    window.run_batch_dialog()
    assert seen["src"] == src and seen["dst"] == tmp_path / "dst"
    assert seen["jobs"] == 2
    assert seen["vector"] is False  # preset por defecto, sin SVG
    assert seen["preset"].export_size == 3000
    assert seen["preset"].export_format == "png"


def test_batch_handlers(window):
    window._on_batch_progress(1, 2, "a.png")
    assert "1/2" in window.lbl_status.text()
    window._on_batch_finished([{"status": "ok"}, {"status": "skipped"}, {"status": "error"}])
    assert window.btn_batch.isEnabled()
    window._on_batch_error("boom")
    assert window.btn_batch.isEnabled()


def test_run_batch_starts_worker(window, tmp_path: Path, monkeypatch):
    calls: dict = {}

    class FakeSig:
        def __init__(self):
            self.slot = None

        def connect(self, slot):
            self.slot = slot

    class FakeWorker:
        def __init__(self, *a, **k):
            self.progress = FakeSig()
            self.finished = FakeSig()
            self.error = FakeSig()
            calls["created"] = True

        def isRunning(self):
            return False

        def start(self):
            calls["started"] = True
            self.finished.slot([])

    import app.ui.main_window as MW

    monkeypatch.setattr(MW, "BatchWorker", FakeWorker)
    monkeypatch.setattr(MW.QMessageBox, "information", lambda *a, **k: None)
    src = tmp_path / "in"
    dst = tmp_path / "dst"
    src.mkdir()
    window.run_batch(src, dst)
    assert calls.get("started") is True


def test_crop_editor_accept_applies(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import app.ui.crop_editor as CE

    seen: dict = {}

    class FakeDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, *a, **k):
            seen["created"] = True
            self.ratio, self.mode = "4:5", "cover"
            self.fx, self.fy, self.zoom = 20.0, 30.0, 2.0
            self.doc_w, self.doc_h = 1536, 1920
            self.turns, self.image = 0, window.src

        def exec(self):
            return QDialog.DialogCode.Accepted

        def deleteLater(self):
            pass

    monkeypatch.setattr(CE, "CropEditorDialog", FakeDialog)
    window.open_crop_editor()
    assert seen.get("created") is True
    assert (window.crop_fx, window.crop_fy, window.crop_zoom) == (20.0, 30.0, 2.0)
    assert window.cmb_ratio.currentText() == "4:5"
    assert "Crop set" in window.lbl_status.text()


def test_crop_editor_cancel_keeps_values(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import app.ui.crop_editor as CE

    class FakeDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

        def deleteLater(self):
            pass

    monkeypatch.setattr(CE, "CropEditorDialog", FakeDialog)
    before = (window.crop_fx, window.crop_fy, window.crop_zoom)
    window.open_crop_editor()
    assert (window.crop_fx, window.crop_fy, window.crop_zoom) == before
    assert "unchanged" in window.lbl_status.text()


def test_crop_editor_real_dialog(qt_app):
    from PIL import Image as Img
    from PySide6.QtCore import QPointF

    from app.ui.crop_editor import CropEditorDialog, CropView
    from tests.conftest import close_dialog

    src = Img.new("RGB", (400, 300), (10, 20, 30))
    dlg = CropEditorDialog(src, ratio="1:1", mode="cover")
    assert dlg.ratio == "1:1" and dlg.zoom == 1.0
    dlg.view.pan_by(40, 0)
    assert dlg.view.fx != 50.0
    dlg.view.zoom_at(QPointF(300, 300), 2.0)
    assert dlg.zoom == 2.0
    dlg.reset_crop()
    assert (dlg.fx, dlg.fy, dlg.zoom) == (50.0, 50.0, 1.0)
    before = dlg.image.size
    dlg.rotate_cw()
    assert dlg.turns == 1 and dlg.image.size == (before[1], before[0])
    dlg.accept()
    assert dlg.result() == dlg.DialogCode.Accepted
    view = CropView(src, "16:9", "cover", 0, 0, 1.0)
    view.resize(600, 600)
    lay = view._layout()
    assert lay["frame"].width() > 0 and lay["frame"].height() > 0
    close_dialog(dlg)


def test_crop_editor_custom_free_frame(qt_app):
    from PIL import Image as Img

    from app.ui.crop_editor import CropEditorDialog, CropView
    from tests.conftest import close_dialog

    src = Img.new("RGB", (400, 300), (10, 20, 30))
    dlg = CropEditorDialog(src, ratio="custom", mode="cover",
                           canvas_w=1920, canvas_h=800)
    assert dlg.ratio == "custom"
    assert (dlg.doc_w, dlg.doc_h) == (1920, 800)
    assert dlg.spn_w.isEnabled()  # custom: W/H editables
    assert "1920×800" in dlg.lbl_summary.text()
    dlg.spn_w.setValue(1600)  # editar W/H mantiene custom
    assert dlg.ratio == "custom"
    assert (dlg.doc_w, dlg.doc_h) == (1600, 800)
    # Marco libre con el aspecto pedido.
    view = CropView(src, "custom", "cover", 50, 50, 1.0, canvas_w=1600, canvas_h=800)
    view.resize(600, 600)
    lay = view._layout()
    assert abs(lay["frame"].width() / lay["frame"].height() - 2.0) < 0.05
    dlg.cmb_ratio.setCurrentText("1:1")  # volver a preset bloquea W/H
    assert not dlg.spn_w.isEnabled()
    close_dialog(dlg)


def test_crop_zoom_anchor_does_not_snap_back(qt_app):
    # Bucle del zoom: el punto bajo el cursor sobrevive a cada paso.
    from PIL import Image as Img
    from PySide6.QtCore import QPointF

    from app.ui.crop_editor import CropView

    src = Img.new("RGB", (400, 300), (10, 20, 30))
    view = CropView(src, "1:1", "cover", 50, 50, 1.0)
    view.resize(600, 600)
    lay = view._layout()
    frame = lay["frame"]
    pos = QPointF(frame.left() + frame.width() * 0.2,
                  frame.top() + frame.height() * 0.2)

    def anchor():
        lay = view._layout()
        cx = (pos.x() - lay["ox"]) / lay["s"]
        cy = (pos.y() - lay["oy"]) / lay["s"]
        bx, by, bw, bh = view._box
        return ((cx - bx) / bw, (cy - by) / bh)

    before = anchor()
    for _ in range(4):
        view.zoom_at(pos, 1.5)
    after = anchor()
    assert view.zoom > 1.0
    assert abs(after[0] - before[0]) < 0.01
    assert abs(after[1] - before[1]) < 0.01


def test_crop_pan_moves_box_exactly(qt_app):
    from PIL import Image as Img

    from app.ui.crop_editor import CropView

    src = Img.new("RGB", (400, 300), (10, 20, 30))
    view = CropView(src, "1:1", "cover", 50, 50, 2.0)
    before = tuple(view._box)
    view.pan_by(10.0, -5.0)
    after = view._box
    assert after[0] == before[0] + 10.0
    assert after[1] == before[1] - 5.0
    assert (after[2], after[3]) == (before[2], before[3])


def test_crop_drag_moves_frame_with_finger(qt_app):
    # El marco sigue al dedo (la foto está fija): arrastrar a la derecha
    # y abajo desplaza la caja en +x/+y.
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PIL import Image as Img

    from app.ui.crop_editor import CropView

    src = Img.new("RGB", (400, 300), (10, 20, 30))
    view = CropView(src, "1:1", "cover", 50, 50, 2.0)
    view.resize(600, 600)
    before = tuple(view._box)
    view.mousePressEvent(QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, QPointF(100, 100),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier))
    view.mouseMoveEvent(QMouseEvent(
        QMouseEvent.Type.MouseMove, QPointF(160, 140),
        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier))
    view.mouseReleaseEvent(QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease, QPointF(160, 140),
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier))
    after = view._box
    assert after[0] > before[0] and after[1] > before[1]


def test_crop_editor_done_applies_visible_crop(window, qt_app):
    # E2E: gestos en el diálogo -> Done -> win.result cambia de verdad.
    from PIL import Image as Img
    from PySide6.QtCore import QPointF

    from app.services.render_service import render_full
    from app.ui.crop_editor import CropEditorDialog
    from tests.conftest import accept_next_dialog

    src = Img.new("RGB", (400, 300), (10, 20, 30))
    from PIL import ImageDraw as _Draw

    _Draw.Draw(src).rectangle([200, 0, 400, 300], fill=(200, 40, 40))
    window.src = src
    window.refresh()
    before = window.result
    assert before is not None

    def _gestures(dlg):
        dlg.view.resize(600, 600)
        dlg.view.pan_by(80.0, 0.0)
        dlg.view.zoom_at(QPointF(300, 300), 2.0)

    accept_next_dialog(CropEditorDialog, setup=_gestures)
    window.open_crop_editor()
    assert window.crop_zoom == 2.0
    assert (window.crop_fx, window.crop_fy) != (50.0, 50.0)
    assert window.result is not None
    assert window.result.tobytes() != before.tobytes()
    assert window.result.tobytes() == render_full(src, window.current_params()).tobytes()


def test_cover_pixmap_cached_and_invalidated(qt_app):
    # P1: la foto no se reconvierte en cada paint; rotar invalida.
    from PIL import Image as Img

    from app.ui.crop_editor import CropView

    view = CropView(Img.new("RGB", (64, 48), (1, 2, 3)))
    view.resize(300, 300)
    first = view._cover_pixmap()
    view.update()
    view.repaint()
    assert view._cover_pixmap() is first
    view._img = Img.new("RGB", (64, 48), (9, 9, 9))
    assert view._cover_pixmap() is not first


def test_share_export_import(window, tmp_path, isolated_presets, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    target = tmp_path / "shared.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    window.share_preset_export()
    assert target.exists()
    (isolated_presets / "shared.json").write_bytes(target.read_bytes())
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(target), ""))
    window.sld_thr.setValue(100)
    window.share_preset_import()
    assert window.sld_thr.value() == 128
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window.share_preset_import()  # cancel: does nothing
    bad = tmp_path / "bad.json"
    bad.write_text("{no json", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(bad), ""))
    window.share_preset_import()  # invalid: warning, no crash


def test_ops_and_undo(window):
    from app.ops import flip_h

    assert window.history.undo() is None
    window._op_image(flip_h, "flip")
    assert len(window.history) == 1
    window.undo_image()
    assert window.lbl_status.text() == "Undone (Ctrl+Y to redo)"
    window.redo_image()
    assert window.lbl_status.text() == "Redone"
    window.undo_image()
    window.undo_image()
    assert "Nothing to undo" in window.lbl_status.text()
    window.redo_image()
    window.redo_image()
    assert "Nothing to redo" in window.lbl_status.text()
    assert window.result is not None


def test_action_bar_layout(window, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea

    assert window.btn_export.objectName() == "exportBtn"
    assert window.btn_preset_save.minimumWidth() >= 80
    # Export/batch/cancel live outside the scroll: always visible
    assert window.btn_export.parent() is not None
    assert window.btn_cancel.parent() is not None
    assert window.progress.parent() is not None
    assert window.lbl_status.parent() is not None
    scrolls = window.findChildren(QScrollArea)
    assert scrolls, "scroll panel must exist"
    assert scrolls[0].horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff


def test_cancel_button(window):
    window.cancel_batch()
    assert window._batch_cancel == [True]
    assert "Cancelling" in window.lbl_status.text()


def test_crop_editor_programmatic(qt_app):
    """Crop dialog + view math without driving the real mouse."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent, QWheelEvent
    from PIL import Image

    from app.ui.crop_editor import CropEditorDialog, _pil_to_pixmap

    assert _pil_to_pixmap(Image.new("RGB", (8, 8), (1, 2, 3))) is not None
    dlg = CropEditorDialog(Image.new("RGB", (64, 48), (90, 100, 140)))
    try:
        assert dlg.ratio == "1:1" and dlg.mode == "cover"
        assert dlg.fx == 50.0 and dlg.zoom == 1.0
        assert dlg.doc_w > 0 and dlg.doc_h > 0
        dlg.rotate_cw()
        assert dlg.turns == 1
        dlg.reset_crop()
        assert (dlg.fx, dlg.fy, dlg.zoom) == (50.0, 50.0, 1.0)
        dlg._on_ratio("16:9")
        assert dlg.ratio == "16:9"
        dlg._on_wh()
        assert dlg.doc_w >= 64 and dlg.doc_h >= 64
        dlg._on_mode("contain")
        assert dlg.mode == "contain"
        dlg._on_mode("cover")
        assert dlg.mode == "cover"
        dlg._sync_summary()
        assert dlg.lbl_summary.text() != ""
        view = dlg.view
        view.resize(300, 300)
        view.pan_by(5.0, -3.0)
        view.zoom_at(QPointF(150.0, 150.0), 1.5)
        assert 1.0 <= view.zoom <= 4.0
        view.reset_crop()
        assert (view.fx, view.fy, view.zoom) == (50.0, 50.0, 1.0)
        view.mousePressEvent(QMouseEvent(
            QMouseEvent.Type.MouseButtonPress, QPointF(10, 10),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier))
        view.mouseMoveEvent(QMouseEvent(
            QMouseEvent.Type.MouseMove, QPointF(20, 25),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier))
        view.mouseReleaseEvent(QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease, QPointF(20, 25),
            Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier))
        view.mode = "contain"

        def _wheel():
            return QWheelEvent(
                QPointF(150, 150), QPoint(0, 0), QPoint(0, 0), QPoint(0, 120),
                Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase, False)

        view.wheelEvent(_wheel())  # contain: ignored
        view.mode = "cover"
        view.wheelEvent(_wheel())
        view.repaint()  # offscreen paint path
        dlg.accept()
        assert dlg.result() == dlg.DialogCode.Accepted
        bad = CropEditorDialog(Image.new("RGB", (32, 32)), ratio="nope", mode="nope")
        try:
            assert bad.ratio == "1:1" and bad.mode == "cover"
        finally:
            bad.close()
    finally:
        dlg.close()
