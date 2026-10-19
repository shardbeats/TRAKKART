"""Perf smoke: Floyd must not degrade (generous thresholds, regressions only)."""

import time

import pytest
from PIL import Image

from app.dither import floyd_steinberg
from app.palettes import get_palette

pytestmark = pytest.mark.slow


def test_floyd_bw_480_under_limit():
    im = Image.new("RGB", (480, 480), (90, 60, 120))
    t = time.time()
    out = floyd_steinberg(im)
    assert out.size == (480, 480)
    assert time.time() - t < 15


def test_floyd_color_320_under_limit():
    im = Image.new("RGB", (320, 320), (90, 60, 120))
    t = time.time()
    out = floyd_steinberg(im, palette=get_palette("SLIME"))
    assert out.size == (320, 320)
    assert time.time() - t < 25
