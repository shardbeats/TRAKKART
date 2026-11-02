"""Accelerator tests: numba/numpy parity, fallback, multiprocessing."""

import numpy as np
import pytest
from PIL import Image

from app import accelerate
from app.accelerate import has_numba
from app.kernels import COEFFS, run_kernel
from app.palettes import get_palette

needs_numba = pytest.mark.skipif(not has_numba(), reason="numba not installed")


def _img(size: int = 48) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 5) % 256, (y * 3) % 256, 128)
    return im


@needs_numba
def test_parity_all_kernels():
    pal = get_palette("VAPOR")
    for k in COEFFS:
        a = np.array(run_kernel(_img(), k, None, 128.0, backend="numpy"))
        b = np.array(run_kernel(_img(), k, None, 128.0, backend="numba"))
        assert np.array_equal(a, b), k
        a = np.array(run_kernel(_img(), k, pal, 128.0, backend="numpy"))
        b = np.array(run_kernel(_img(), k, pal, 128.0, backend="numba"))
        assert np.array_equal(a, b), k


def test_invalid_backend_falls_back_to_auto():
    out = run_kernel(_img(16), "floyd", None, 128.0, backend="nope")
    assert out.size == (16, 16)


def test_numba_missing_raises(monkeypatch):
    monkeypatch.setattr(accelerate, "_NUMBA", False)
    assert accelerate.has_numba() is False
    with pytest.raises(RuntimeError):
        run_kernel(_img(16), "floyd", None, 128.0, backend="numba")


def test_pure_python_fallback_correct(monkeypatch):
    # P1: lazy numba keeps a correct pure-python path (tiny: ms).
    from app import accelerate as acc

    monkeypatch.setattr(acc, "_NUMBA", False)
    acc._compiled.clear()
    dys, dxs, wts = acc.coeffs_to_arrays(COEFFS["floyd"])
    lum = np.array(_img(16).convert("L"), dtype=np.float32)
    out = acc.ed_bw(lum.copy(), dys, dxs, wts, 128.0)
    assert out.shape == (16, 16) and set(np.unique(out)) <= {0, 255}
    pal = np.array(get_palette("SLIME"), dtype=np.float64)
    arr = np.array(_img(16), dtype=np.float32)
    out_c = acc.ed_color(arr.copy(), pal, dys, dxs, wts)
    assert out_c.shape == (16, 16, 3)
    monkeypatch.setattr(acc, "_NUMBA", None)  # re-probe on next use


def test_lazy_import_defers_numba():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    code = ("import sys; import app.accelerate as a; "
            "assert 'numba' not in sys.modules, 'numba imported at accelerate import'; "
            "assert a.has_numba() is True; "
            "assert 'numba' in sys.modules, 'probe must import numba'")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=str(root))
    assert r.returncode == 0, r.stderr


def test_coeffs_arrays_shapes():
    from app.accelerate import coeffs_to_arrays

    dys, dxs, wts = coeffs_to_arrays([(1, -1, 0.5), (0, 1, 0.25)])
    assert dys.tolist() == [1, 0] and dxs.tolist() == [-1, 1]
    assert wts.dtype == np.float64 and dys.dtype == np.int64


@needs_numba
def test_numba_direct_entry_points():
    import numpy as np

    from app import accelerate as acc
    from app.kernels import COEFFS

    dys, dxs, wts = acc.coeffs_to_arrays(COEFFS["floyd"])
    lum = np.array(_img(16).convert("L"), dtype=np.float32)
    out_bw = acc.ed_bw(lum.copy(), dys, dxs, wts, 128.0)
    assert out_bw.shape == (16, 16) and set(np.unique(out_bw)) <= {0, 255}
    pal = np.array(get_palette("SLIME"), dtype=np.float64)
    arr = np.array(_img(16), dtype=np.float32)
    out_c = acc.ed_color(arr.copy(), pal, dys, dxs, wts)
    assert out_c.shape == (16, 16, 3)
    # diffuse_* dispatch through numba explicitly.
    from app.kernels import diffuse_bw, diffuse_color

    a = np.array(diffuse_bw(lum.copy(), COEFFS["floyd"], 128.0, backend="numba"))
    b = np.array(diffuse_bw(lum.copy(), COEFFS["floyd"], 128.0, backend="numpy"))
    assert np.array_equal(a, b)
    c = np.array(diffuse_color(arr.copy(), pal, COEFFS["floyd"], backend="numba"))
    d = np.array(diffuse_color(arr.copy(), pal, COEFFS["floyd"], backend="numpy"))
    assert np.array_equal(c, d)


def test_batch_jobs(tmp_path):
    from app.batch import batch_process
    from app.presets import Preset

    src = tmp_path / "in"
    src.mkdir()
    for i in range(4):
        Image.new("RGB", (32, 32), (i * 40 + 10, 90, 140)).save(src / f"j{i}.png")
    one = batch_process(src, tmp_path / "o1", Preset(name="t", method="bayer4"), jobs=1)
    two = batch_process(src, tmp_path / "o2", Preset(name="t", method="bayer4"), jobs=2)
    assert [r["status"] for r in two] == ["ok"] * 4
    for r1, r2 in zip(one, two):
        assert r1["status"] == r2["status"] == "ok"
        a = np.array(Image.open(r1["outputs"][0]).convert("L"))
        b = np.array(Image.open(r2["outputs"][0]).convert("L"))
        assert np.array_equal(a, b)
