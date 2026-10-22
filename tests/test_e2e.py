"""E2E journeys: real user flows on the offscreen app, end to end.

No mocks of the app itself (only file dialogs): open → tweak → export,
shortcuts, threaded batch, GIF+SVG, preset persistence across restarts.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def _trigger(window, shortcut: str) -> bool:
    from PySide6.QtGui import QAction

    for act in window.findChildren(QAction):
        if act.shortcut().toString() == shortcut:
            act.trigger()
            return True
    return False


def test_e2e_tweak_export(window, qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    window.cmb_method.setCurrentText("bayer8")
    window._on_palette_preset_changed("VAPOR")
    window.sld_thr.setValue(160)
    window.spn_pixel.setValue(3)
    window.sld_bri.setValue(120)
    window.refresh()
    assert window.result is not None
    accept_next_dialog(ExportDialog)
    window.export()
    out = window.out_dir
    assert (out / "trakkart_cover.png").exists()
    assert (out / "trakkart_cover_thumb1080p.png").exists()
    meta = (out / "trakkart_cover_metadata.json")
    assert meta.exists()
    import json

    info = json.loads(meta.read_text(encoding="utf-8"))
    assert info["params"]["method"] == "bayer8"
    assert info["params"]["threshold"] == 160
    assert info["params"]["pixel_size"] == 3


def test_e2e_shortcuts(window, tmp_path: Path, monkeypatch):
    from PIL import Image
    from PySide6.QtWidgets import QFileDialog

    # Ctrl+O with a real file (dialog mocked, load path real)
    p = tmp_path / "shot.png"
    Image.new("RGB", (48, 48), (1, 2, 3)).save(p)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(p), ""))
    assert _trigger(window, "Ctrl+O")
    assert window.src is not None and window.src.size == (48, 48)
    assert window.src_name == "shot"  # default base = source name
    # Ctrl+S is Quick export: with seeded prefs it does not ask
    from app.export_prefs import ExportPrefs, save_prefs

    save_prefs(ExportPrefs(out_dir=str(window.out_dir), base="shot"), window._prefs_path)
    # Ctrl+R randomizes, Ctrl+Z undoes an op, Ctrl+S exports
    assert _trigger(window, "Ctrl+R")
    assert window.result is not None
    before = window.src.copy()
    from app.ops import flip_h

    window._op_image(flip_h, "flip")
    assert _trigger(window, "Ctrl+Z")
    assert window.lbl_status.text() == "Undone (Ctrl+Y to redo)"
    assert list(window.src.get_flattened_data()) == list(before.get_flattened_data())
    assert _trigger(window, "Ctrl+Y")
    assert window.lbl_status.text() == "Redone"
    assert _trigger(window, "Ctrl+S")
    assert (window.out_dir / "shot.png").exists()


def test_e2e_batch_threaded(window, tmp_path: Path):
    from PIL import Image
    from PySide6.QtCore import QEventLoop, QTimer

    from app.ui.workers import BatchWorker

    src = tmp_path / "in"
    dst = tmp_path / "dst"
    src.mkdir()
    for i in range(3):
        Image.new("RGB", (32, 32), (i * 40, 90, 140)).save(src / f"e{i}.png")
    got: dict = {}
    loop = QEventLoop()
    w = BatchWorker(src, dst, window.current_params(), jobs=1)
    w.finished.connect(lambda r: (got.update(results=r), loop.quit()))
    w.error.connect(lambda m: (got.update(error=m), loop.quit()))
    QTimer.singleShot(60000, loop.quit)
    w.start()
    loop.exec()
    w.wait(5000)
    assert "error" not in got, got.get("error")
    assert len(got["results"]) == 3
    assert all(r["status"] == "ok" for r in got["results"])


def test_e2e_gif_svg_export(window, qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    def _on(dlg):
        dlg.chk_vector.setChecked(True)
        dlg.chk_anim.setChecked(True)

    window._vector_cell = 8
    window.refresh()
    accept_next_dialog(ExportDialog, _on)
    window.export()
    out = window.out_dir
    assert (out / "trakkart_cover_vector.svg").exists()
    assert (out / "trakkart_cover_gif.gif").exists()


def test_e2e_preset_survives_restart(window, tmp_path: Path, monkeypatch):
    import app.presets as P
    from app.presets import save_preset
    from app.ui.main_window import MainWindow

    d = tmp_path / "presets"
    d.mkdir()
    monkeypatch.setattr(P, "PRESETS_DIR", d)
    P.ensure_bundled(d)
    window.refresh_presets()
    window.spn_pixel.setValue(4)
    window.sld_thr.setValue(160)
    p = window.current_params()
    p.name = "E2EStyle"
    save_preset(p)
    assert (d / "E2EStyle.json").exists()
    # "restart": brand-new window over the same presets dir
    w2 = MainWindow(out_dir=tmp_path / "o2", db_path=tmp_path / "h2.db")
    try:
        from PIL import Image

        w2.src = Image.new("RGB", (32, 32), (5, 5, 5))
        w2._apply_preset("E2EStyle")
        assert w2.spn_pixel.value() == 4
        assert w2.sld_thr.value() == 160
        w2.refresh()
        assert w2.result is not None
    finally:
        w2.store.close()
        w2.close()


def test_e2e_ui_kwargs_match_preset(window):
    """UI kwargs and Preset.to_render_kwargs() must never drift apart."""
    from app.pipeline import render

    kwargs_ui = window._render_kwargs()
    kwargs_preset = window.current_params().to_render_kwargs()
    assert kwargs_ui == kwargs_preset
    a = render(window.src, **kwargs_ui)
    b = render(window.src, **kwargs_preset)
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())


def test_e2e_drop_to_export(window, tmp_path: Path, qt_app):
    from PIL import Image
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    p = tmp_path / "journey.png"
    Image.new("RGB", (40, 40), (9, 9, 9)).save(p)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p))])
    window.dropEvent(QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert window.src is not None and window.src.size == (40, 40)
    assert window.src_name == "journey"  # default base = source name
    window.refresh()
    accept_next_dialog(ExportDialog)
    window.export()
    assert (window.out_dir / "journey.png").exists()
