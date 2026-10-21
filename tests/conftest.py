import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def ctx():
    return {}


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qt_app, tmp_path, monkeypatch):
    from pathlib import Path as _P

    from PySide6.QtWidgets import QMessageBox
    from PIL import Image

    from app.ui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    import app.ui.export_flow as _ef

    monkeypatch.setattr(_ef, "show_exported", lambda *a, **k: None)
    w = MainWindow(out_dir=_P(str(tmp_path)) / "out", db_path=_P(str(tmp_path)) / "h.db",
                   prefs_path=_P(str(tmp_path)) / "prefs.json")
    w.src = Image.new("RGB", (64, 64), (200, 50, 90))
    yield w
    w.store.close()
    w.close()


@pytest.fixture
def isolated_presets(window, tmp_path, monkeypatch):
    import app.presets as P

    d = tmp_path / "presets"
    d.mkdir()
    monkeypatch.setattr(P, "PRESETS_DIR", d)
    P.ensure_bundled(d)
    window.refresh_presets()
    return d


def accept_next_dialog(cls, setup=None):
    """Acepta el próximo diálogo modal de tipo cls (E2E: el diálogo sí se abre).

    `setup(dlg)` opcional para marcar checkboxes antes de aceptar.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    def _close():
        for w in QApplication.topLevelWidgets():
            if isinstance(w, cls):
                try:
                    if setup is not None:
                        setup(w)
                finally:
                    w.accept()  # aceptar siempre: un setup roto no cuelga la suite
                return

    QTimer.singleShot(400, _close)


def close_dialog(dlg):
    """Cierre determinista: evita C++ huérfano que revienta el teardown."""
    from PySide6.QtWidgets import QApplication

    try:
        dlg.close()
    finally:
        dlg.deleteLater()
        QApplication.processEvents()
