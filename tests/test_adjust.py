"""Tests adjust: identidad, cambios reales, validacion."""

import pytest
from PIL import Image

from app.adjust import Adjust, apply_adjust


def _img() -> Image.Image:
    return Image.new("RGB", (32, 32), (100, 120, 140))


def test_identity_returns_same_pixels():
    assert list(apply_adjust(_img(), Adjust()).get_flattened_data()) == list(_img().get_flattened_data())
    assert list(apply_adjust(_img(), None).get_flattened_data()) == list(_img().get_flattened_data())


def test_brightness_changes_output():
    out = apply_adjust(_img(), Adjust(brightness=1.5))
    assert list(out.get_flattened_data()) != list(_img().get_flattened_data())


def test_contrast_and_saturation():
    assert apply_adjust(_img(), {"contrast": 1.4}).size == (32, 32)
    assert apply_adjust(_img(), {"saturation": 0.0}).size == (32, 32)


def test_validation_rejects():
    with pytest.raises(ValueError):
        Adjust(brightness=99).validate()
    with pytest.raises(ValueError):
        Adjust.from_dict({"saturation": -1})


def test_adjust_roundtrip_dict():
    a = Adjust(brightness=1.2, contrast=0.8, saturation=1.5)
    assert Adjust.from_dict(a.to_dict()).to_dict() == a.to_dict()
