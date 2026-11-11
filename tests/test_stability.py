"""Stability + security + CPU budgets: anti-hang, anti-leak, anti-bomb.

Guarantees: no thread storms (coalescing), no redundant renders
(debounce), corrupt files never take down the app, batch cancels
cleanly, memory does not grow per render, and safety limits stop
bombs before decoding.
"""

import time

import pytest

pytestmark = pytest.mark.slow


def _rss_mb() -> float:
    """Process RSS in MB (stdlib; Windows via ctypes, rest via resource)."""
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except ImportError:
        pass
    import ctypes

    class _Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    proc = ctypes.windll.kernel32.GetCurrentProcess()
    info = _Counters()
    info.cb = ctypes.sizeof(info)
    if ctypes.windll.psapi.GetProcessMemoryInfo(proc, ctypes.byref(info), info.cb):
        return info.WorkingSetSize / (1024.0 * 1024.0)
    return 0.0


def test_no_thread_storm_on_rapid_refresh(window, qt_app, monkeypatch):
    """5 rapid refreshes with a heavy image → ≤2 workers, no thread storm.

    Deterministic (no wall-clock race): the first worker is held at a gate
    until all 5 refreshes are queued, so 2-5 MUST coalesce into
    _preview_pending instead of spawning extra workers.
    """
    import threading
    import time as _t

    import app.accelerate as A
    import app.ui.preview_worker as PW
    from PIL import Image
    from PySide6.QtCore import QCoreApplication

    monkeypatch.setattr(A, "has_numba", lambda: False)  # force async path
    created: list = []
    Real = PW.PreviewWorker
    gate = threading.Event()

    class Counting(Real):
        def __init__(self, *a, **k):
            created.append(1)
            super().__init__(*a, **k)

    real_work = Real.work

    def gated_work(self):
        gate.wait(60)
        return real_work(self)

    monkeypatch.setattr(PW, "PreviewWorker", Counting)
    monkeypatch.setattr(Real, "work", gated_work)
    window.src = Image.new("RGB", (900, 900), (90, 60, 140))
    window.refresh()  # worker 1 starts, blocks at the gate
    deadline = _t.time() + 60
    while ((window._preview_worker is None or not window._preview_worker.isRunning())
           and _t.time() < deadline):
        QCoreApplication.processEvents()
        _t.sleep(0.01)
    assert window._preview_worker is not None and window._preview_worker.isRunning()
    for _ in range(4):
        window.refresh()  # all coalesce: no new workers while one runs
    gate.set()  # release worker 1; pending spawns exactly one more
    deadline = _t.time() + 60
    while window._preview_worker.isRunning() and _t.time() < deadline:
        QCoreApplication.processEvents()
        _t.sleep(0.05)
    window._preview_worker.wait(10000)
    QCoreApplication.processEvents()
    assert len(created) <= 2, f"thread storm: {len(created)} workers"
    assert window.result is not None


def test_debounce_coalesces_renders(window, qt_app, monkeypatch):
    """20 back-to-back slider changes → a single render (not 20).

    Seam: ``preview_controller.render_still``, the one function the debounce
    calls. Never patch a backend function (``render_service.render_full``,
    ``app.gpu.render_proxy_or_cpu``…): preview routing changes move those,
    the counter stays at 0 and CI fails even though the debounce is fine.
    """
    from PySide6.QtTest import QTest

    from app.ui import preview_controller as PC

    calls: list = []
    real = PC.render_still

    def counting(win):
        calls.append(1)
        return real(win)

    monkeypatch.setattr(PC, "render_still", counting)
    window.viewport_mode = "live"  # debounce only exists in live mode
    for v in range(100, 120):
        window.sld_thr.setValue(v)  # only arms the timer, no event processing
    QTest.qWait(800)  # let the debounce (120-350ms) fire
    assert len(calls) == 1, f"debounce broken: {len(calls)} renders"
    assert window.result is not None


def test_corrupt_files_never_crash(window, tmp_path):
    before = window.src.copy()
    (tmp_path / "empty.png").write_bytes(b"")
    (tmp_path / "text.png").write_text("not an image", encoding="utf-8")
    (tmp_path / "cut.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    for name in ("empty.png", "text.png", "cut.png", "missing.png"):
        window._load_path(tmp_path / name)  # warns, does not raise
    assert list(window.src.get_flattened_data()) == list(before.get_flattened_data())


def test_export_base_sanitized(window):
    from PIL import Image

    from app.exporter import export_bundle

    res = Image.new("RGB", (32, 32), (1, 2, 3))
    paths = export_bundle(res, window.out_dir, base="../../evil")
    for p in paths.values():
        assert window.out_dir.resolve() in p.resolve().parents
    assert not (window.out_dir.parent / "evil_cover.png").exists()


def test_batch_cancel_midrun(tmp_path):
    from PIL import Image

    from app.batch import batch_process
    from app.presets import Preset

    src = tmp_path / "in"
    dst = tmp_path / "dst"
    src.mkdir()
    for i in range(4):
        Image.new("RGB", (64, 64), (i * 30, 90, 140)).save(src / f"c{i}.png")
    cancel = [False]

    def _cb(done, total, name):
        cancel[0] = True  # cancels after the first file

    t = time.time()
    results = batch_process(src, dst, Preset(name="t"), progress_cb=_cb, cancel=cancel)
    assert time.time() - t < 60
    assert all(r["status"] in ("ok", "skipped", "error") for r in results)
    assert len(results) <= 4


def test_vector_bomb_blocked_in_export(window, qt_app, monkeypatch):
    from PIL import Image
    from PySide6.QtWidgets import QMessageBox

    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    warned: list = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a))
    window.cmb_method.setCurrentText("bayer4")  # fast render, the bomb is in the SVG
    window.src = Image.new("RGB", (1700, 1700), (9, 9, 9))
    window._vector_export = True  # the preset asks for SVG…
    window._vector_cell = 4  # 425x425 = 180k cells > limit
    accept_next_dialog(ExportDialog)
    window.export()  # warns TooBigError, does not crash
    assert warned


def test_oversized_data_url_rejected(monkeypatch):
    import base64

    import app.services.image_io as IO
    from app.safety import TooBigError

    monkeypatch.setattr(IO, "MAX_BYTES", 10)
    url = "data:image/png;base64," + base64.b64encode(b"x" * 100).decode()
    try:
        IO.decode_data_url(url)
        raise AssertionError("should have failed")
    except TooBigError:
        pass


def test_bomb_header_rejected_without_decoding(window, tmp_path):
    from PIL import Image

    Image.new("RGB", (9000, 10), (1, 2, 3)).save(tmp_path / "bomb.png")
    before = window.src.size
    window._load_path(tmp_path / "bomb.png")  # TooBigError from headers, no decoding
    assert window.src.size == before


def test_cpu_budgets():
    from PIL import Image

    from app.dither import ordered
    from app.exporter import export_bundle
    from app.palettes import get_palette

    im = Image.new("RGB", (960, 960), (90, 60, 120))
    t = time.time()
    ordered(im, palette=get_palette("SLIME"), map_name="bayer8")
    assert time.time() - t < 5, "bayer 960px exceeded budget"
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        small = Image.new("RGB", (256, 256), (9, 9, 9))
        t = time.time()
        export_bundle(small, Path(tmp), base="b")
        assert time.time() - t < 15, "export bundle exceeded budget"


def test_rss_does_not_grow_per_render(window):
    from app.services.render_service import render_full

    preset = window.current_params()
    render_full(window.src, preset)  # warm up caches (_BLUE_BASE, crosshatch…)
    base = _rss_mb()
    for _ in range(5):
        render_full(window.src, preset)
    growth = _rss_mb() - base
    assert growth < 100, f"possible render leak: +{growth:.1f}MB"


def test_pil_to_pixmap_empty_never_crashes(qt_app):
    from PIL import Image

    from app.ui.qt_image import pil_to_pixmap

    pix = pil_to_pixmap(Image.new("RGB", (0, 0)))
    assert pix.isNull()


def test_crop_editor_ratio_syncs_canvas_dims(window, qt_app):
    from app.ui.crop_editor import CropEditorDialog
    from tests.conftest import accept_next_dialog

    window.cmb_ratio.setCurrentText("1:1")
    window._on_ratio_preset()
    window.spn_canvas_w.setValue(3000)
    window.spn_canvas_h.setValue(3000)

    def setup(dlg):
        dlg.cmb_ratio.setCurrentText("9:16")
        assert (dlg.doc_w, dlg.doc_h) == (1688, 3000)

    accept_next_dialog(CropEditorDialog, setup)
    window.open_crop_editor()
    p = window.current_params()
    assert (p.ratio, p.canvas_w, p.canvas_h) == ("9:16", 1688, 3000)
    assert (window.spn_canvas_w.value(), window.spn_canvas_h.value()) == (1688, 3000)


def test_zoom_100_renders_document_size(window, qt_app):
    from PIL import Image

    from app.canvas import CUSTOM_LABEL

    window.src = Image.new("RGB", (256, 256), (90, 60, 140))
    window.cmb_ratio.setCurrentText(CUSTOM_LABEL)
    window.spn_canvas_w.setValue(128)
    window.spn_canvas_h.setValue(128)
    window._full_preview = False
    window._zoom_full()
    assert window.result is not None
    assert window.result.size == (128, 128)  # doc, not the proxy/source
    assert window.lbl_res.zoom_text() == "100%"
    assert "100%" in window.lbl_status.text()
    window._zoom_fit()
    assert window._full_preview is False
