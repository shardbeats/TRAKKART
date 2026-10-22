"""UI drag & drop: files, folders, urls, clipboard payloads (fixtures in conftest)."""

import pytest

pytestmark = pytest.mark.slow


def _fake_urlopen(data: bytes, ctype: str = "image/png"):
    class FakeHeaders:
        def get_content_type(self):
            return ctype

    class FakeResp:
        headers = FakeHeaders()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return data if n is None or n < 0 else data[:n]

    def _open(req, timeout=None):
        return FakeResp()

    return _open


def test_drop_event_loads(window, tmp_path):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    from PIL import Image as Img

    p = tmp_path / "drop.png"
    Img.new("RGB", (32, 32), (9, 9, 9)).save(p)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p))])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(ev)
    assert "drop.png" in window.lbl_status.text()
    mime2 = QMimeData()
    mime2.setUrls([QUrl.fromLocalFile(str(tmp_path / "x.txt"))])
    ev2 = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime2, Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(ev2)  # invalid extension: does nothing


def test_drag_hover_feedback(window, tmp_path):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    from PIL import Image as Img

    p = tmp_path / "hov.png"
    Img.new("RGB", (32, 32), (9, 9, 9)).save(p)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p))])
    # QDragEnterEvent requires QPoint (not QPointF) in this PySide6 version.
    window.dragEnterEvent(QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert window.lbl_orig.property("dragHover") == "true"
    from PySide6.QtGui import QDragLeaveEvent

    window.dragLeaveEvent(QDragLeaveEvent())
    assert window.lbl_orig.property("dragHover") == "false"
    # leave/drop clear the highlight
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(ev)
    assert window.lbl_orig.property("dragHover") == "false"


def test_drop_folder_needs_toggle_and_confirm(window, tmp_path, monkeypatch):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QMessageBox

    src = tmp_path / "batchin"
    src.mkdir()
    from PIL import Image as Img

    Img.new("RGB", (16, 16), (9, 9, 9)).save(src / "a.png")
    called: dict = {}

    def _run_batch(s, d):
        called["src"] = str(s)

    monkeypatch.setattr(window, "run_batch", _run_batch)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(src))])

    # Toggle OFF: no processing, just a hint
    window.chk_batch_drop.setChecked(False)
    window.dropEvent(QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert called == {}
    assert "Batch" in window.lbl_status.text() or "batch" in window.lbl_status.text()

    # Toggle ON + confirms No: no processing
    window.chk_batch_drop.setChecked(True)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.No)
    window.dropEvent(QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert called == {}
    # Toggle ON + confirms Yes: processes
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.dropEvent(QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert called.get("src") == str(src)


def test_drop_unknown_scheme_hints(window, tmp_path):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    mime = QMimeData()
    mime.setUrls([QUrl("ftp://example.com/a.png")])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(ev)
    assert "Nothing to import" in window.lbl_status.text()


def test_drop_image_data_loads(window):
    from PySide6.QtCore import QMimeData, QPoint, Qt
    from PySide6.QtGui import QDropEvent, QImage

    qimg = QImage(24, 24, QImage.Format_RGB888)
    qimg.fill(0x112233)
    mime = QMimeData()
    mime.setImageData(qimg)
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(ev)
    assert window.src is not None and window.src.size == (24, 24)


def test_drop_http_url_downloads(window, tmp_path, monkeypatch):
    import io
    import urllib.request
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    from PIL import Image as Img

    buf = io.BytesIO()
    Img.new("RGB", (40, 30), (9, 9, 9)).save(buf, format="PNG")
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(buf.getvalue()))
    mime = QMimeData()
    mime.setUrls([QUrl("https://web.whatsapp.com/foto.png")])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(ev)
    assert window.src is not None and window.src.size == (40, 30)


def test_drop_http_url_rejects(monkeypatch, window):
    import urllib.request
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(b"<html>nope</html>", "text/html"))
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a))
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/")])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(ev)
    assert warned and window.src.size == (64, 64)  # current image unchanged


def test_drop_http_url_too_big(monkeypatch, window):
    import io
    import urllib.request
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QMessageBox

    import app.safety as S
    from PIL import Image as Img

    monkeypatch.setattr(S, "MAX_BYTES", 10)  # tiny cap for the test
    buf = io.BytesIO()
    Img.new("RGB", (32, 32)).save(buf, format="PNG")
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(buf.getvalue()))
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a))
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/big.png")])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    before = window.src.size
    window.dropEvent(ev)
    assert warned  # warns, no crash
    assert window.src.size == before
