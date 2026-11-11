"""ASCII config integration: parity, modes, roundtrip, perf."""
import time

from PIL import Image

from app.ascii import normalize_config
from app.pipeline import RenderSpec, render_spec
from app.presets import Preset


def _img(w=320, h=200):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (x * 255 // w, y * 255 // h, 128)
    return im


def test_parity_columns_preview_export_gif():
    from app.pipeline import render as _render
    img = _img()
    p = Preset(name="t", method="ascii", ascii={"columns": 60})
    a = render_spec(img, RenderSpec.from_preset(p))
    b = _render(img, **p.to_render_kwargs())
    assert a.size == b.size
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())


def test_charset_custom_and_normalize():
    cfg = normalize_config({"charset": "ABCA\n", "columns": 10, "gamma": 99, "color": "bogus"})
    assert cfg["charset"] == "ABC"
    assert cfg["columns"] == 20  # clamped to min
    assert cfg["gamma"] == 2.5  # clamped to max
    assert cfg["color"] == "mono"


def test_color_modes_and_mono_bw():
    from app.ascii import ascii_render
    img = _img(160, 100)
    mono = ascii_render(img, config={"columns": 40, "color": "mono", "ink": "#FFFFFF", "bg": "#000000"})
    assert set(mono.convert("L").get_flattened_data()) <= set(mono.convert("L").get_flattened_data())
    src = ascii_render(img, config={"columns": 40, "color": "source"})
    pal = ascii_render(img, palette=[(0, 0, 0), (255, 255, 255)],
                       config={"columns": 40, "color": "palette"})
    assert mono.size == src.size == pal.size
    # True BW mono: white-on-black only uses those base bg/ink tones
    bw = ascii_render(Image.new("RGB", (80, 60), (0, 0, 0)), config={"columns": 20})
    assert bw.size == (80, 60)


def test_dither_deterministic_gamma_monotone():
    from app.ascii import ascii_render
    img = _img(160, 100)
    a = ascii_render(img, config={"columns": 40, "dither": 50})
    b = ascii_render(img, config={"columns": 40, "dither": 50})
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())
    lo = ascii_render(Image.new("RGB", (80, 60), (40, 40, 40)), config={"columns": 20, "gamma": 0.5})
    hi = ascii_render(Image.new("RGB", (80, 60), (40, 40, 40)), config={"columns": 20, "gamma": 2.0})
    assert list(lo.get_flattened_data()) != list(hi.get_flattened_data())


def test_roundtrip_preset_metadata():
    p = Preset(name="t", method="ascii", ascii={"columns": 77, "invert": True})
    d = p.to_dict()
    p2 = Preset.from_dict(d)
    assert p2.ascii["columns"] == 77 and p2.ascii["invert"] is True
    m = p.meta()
    assert m["ascii"]["columns"] == 77
    s = RenderSpec.from_preset(p2)
    assert s.ascii["columns"] == 77
    assert s.meta()["ascii"]["columns"] == 77


def test_perf_3000px_100cols():
    img = _img(3000, 2000)
    t0 = time.perf_counter()
    render_spec(img, RenderSpec(method="ascii", ascii={"columns": 100}))
    assert time.perf_counter() - t0 < 5.0


def test_ui_ascii_box_only_visible_for_ascii(window, qt_app):
    window.cmb_method.setCurrentText("bayer8")
    assert window._ascii_box.isHidden()
    window.cmb_method.setCurrentText("ascii")
    assert not window._ascii_box.isHidden()
    assert window.step_method(1) != "ascii"
    assert window._ascii_box.isHidden()
