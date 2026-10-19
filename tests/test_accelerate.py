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
