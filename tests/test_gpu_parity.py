"""FR-4 parity harness: GPU proxy vs CPU pipeline (skips without GL).

Strict: every covered combo must match within 1 LSB. Combos outside the
v1 gate (ED family, pre kernels, post stack) assert supports() is False
instead of matching pixels.
"""

import numpy as np
import pytest
from PIL import Image, ImageFilter

from app import gpu


def _images() -> dict[str, Image.Image]:
    rng = np.random.default_rng(0x60)
    w, h = 128, 96
    xs = np.tile(np.linspace(0, 255, w, dtype=np.float32), (h, 1))
    ys = np.tile(np.linspace(0, 255, h, dtype=np.float32)[:, None], (1, w))
    grad = np.stack([xs, ys, 255.0 - xs], axis=-1).astype(np.uint8)
    noise = rng.integers(0, 256, (h, w, 3)).astype(np.uint8)
    photo = np.asarray(Image.fromarray(noise).filter(ImageFilter.GaussianBlur(radius=2)))
    flat = np.full((h, w, 3), 128, dtype=np.uint8)
    return {"gradient": Image.fromarray(grad),
            "photo": Image.fromarray(photo),
            "flat": Image.fromarray(flat)}


def _kwargs(method: str = "bayer8", **over) -> dict:
    from app.presets import Preset
    from app.render_params import preset_to_render_kwargs

    base = {"name": "t", "method": method, "palette": "BW", "pixel_size": 1,
            "threshold": 128, "brightness": 1.2, "contrast": 1.3,
            "saturation": 1.4, "midtones": 1.1, "highlights": 20.0,
            "duotone_dark": "#123456", "duotone_light": "#F5A623",
            "duotone_mid": 50.0, "posterize": 4}
    base.update(over)
    return preset_to_render_kwargs(Preset(**{k: v for k, v in base.items()
                                             if k in Preset.__dataclass_fields__}))


def _needs_gl():
    try:
        ok = gpu.available()
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        pytest.skip("no GL context")
    return True


def _check(img: Image.Image, kwargs: dict) -> None:
    from app.pipeline import render

    assert gpu.supports(kwargs) is True
    got = gpu.render_proxy_kwargs(img, kwargs)
    ref = render(img, **kwargs)
    assert got.size == ref.size
    d = np.abs(np.asarray(got).astype(int) - np.asarray(ref).astype(int))
    assert d.max() <= 1, f"maxdiff {d.max()} for {kwargs.get('method')}"


def test_supports_gate_needs_no_gl():
    # The gate is method-only: every pre/post effect runs on CPU either
    # way, so only the dither engine decides. ED/hilbert/ascii stay on CPU.
    assert gpu.supports(_kwargs("bayer8")) is True
    assert gpu.supports(_kwargs("cmyk")) is True
    assert gpu.supports(_kwargs("floyd")) is False
    assert gpu.supports(_kwargs("hilbert")) is False
    assert gpu.supports(_kwargs("ascii")) is False
    assert gpu.supports(_kwargs("bayer8", grain=10.0)) is True
    assert gpu.supports(_kwargs("bayer8", pre_blur=2.0)) is True
    assert gpu.supports(_kwargs("bayer8", drift_pattern="snow", drift_amount=30.0)) is True
    assert gpu.supports(_kwargs("bayer8", pixelsort=100)) is True
    assert gpu.supports(_kwargs("bayer8", jpeg=50.0)) is True


def test_fallback_without_gl(monkeypatch):
    from app.presets import Preset

    monkeypatch.setattr(gpu, "available", lambda: False)
    img = _images()["flat"]
    out, backend = gpu.render_proxy_or_cpu(img, Preset(name="t", method="bayer8"))
    assert backend == "CPU" and out is not None
    out2, backend2 = gpu.render_kwargs_or_cpu(img, _kwargs("bayer8"))
    assert backend2 == "CPU" and out2 is not None


def test_fallback_on_gl_error(monkeypatch):
    """A mid-render GL failure falls back to the CPU proxy, never raises."""
    from app.presets import Preset

    def _boom(*a, **k):
        raise RuntimeError("no GL today")

    monkeypatch.setattr(gpu, "render_proxy_kwargs", _boom)
    img = _images()["flat"]
    out, backend = gpu.render_proxy_or_cpu(img, Preset(name="t", method="bayer8"))
    assert backend == "CPU" and out is not None
    out2, backend2 = gpu.render_kwargs_or_cpu(img, _kwargs("bayer8"))
    assert backend2 == "CPU" and out2 is not None


def test_method_matrix_bw():
    _needs_gl()
    imgs = _images()
    for method in sorted(gpu._GPU_MAPS):
        _check(imgs["gradient"], _kwargs(method))


def test_palette_path_and_posterize_off():
    _needs_gl()
    imgs = _images()
    for method in ("bayer8", "bluenoise", "cmyk", "edges"):
        _check(imgs["photo"], _kwargs(method, palette="SLIME", posterize=0))
    _check(imgs["flat"], _kwargs("bayer4", threshold=200, pixel_size=2))
    _check(imgs["photo"], _kwargs("cluster", palette="SOURCE", posterize=0))


def test_drift_patterns():
    _needs_gl()
    from app.drift import DRIFT_PATTERNS

    img = _images()["photo"]
    for pattern in DRIFT_PATTERNS:
        _check(img, _kwargs("bayer8", drift_pattern=pattern, drift_amount=30.0,
                            drift_position=50.0))


def test_post_fx_tail_matches_cpu():
    """Post-dither FX stay on CPU: the tail must match render() exactly."""
    _needs_gl()
    img = _images()["photo"]
    _check(img, _kwargs("bayer8", grain=25.0, vignette=30.0, scanlines=4,
                        glow_radius=8.0, glow_intensity=40.0,
                        halftone=6, dust=30.0, wave=5,
                        replace_color="#123456"))
    _check(img, _kwargs("bluenoise", posterize=0, pre_blur=1.0,
                        split_tone=40.0, fade=20.0, halftone_shape="lines"))
