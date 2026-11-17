"""Pins for v2.x #4: multi-stop gradient-map FX (GRADE, post-dither stack).

Off (fewer than 2 valid stops) is identity; N stops interpolate
piecewise-linear over luminance; legacy presets render byte-identical.
"""

from __future__ import annotations

from PIL import Image


def _img():
    im = Image.new("RGB", (48, 48))
    px = im.load()
    for y in range(48):
        for x in range(48):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    return im


def _flat(im):
    return list(im.get_flattened_data())


def test_off_is_identity():
    from app.grade import gradient_stops

    im = _img()
    for stops in (None, [], [(50.0, "#FF0000")], [(10.0, "junk"), (20.0, "")],
                  "not-a-list"):
        assert gradient_stops(im, stops) is im


def test_deterministic():
    from app.grade import gradient_stops

    im = _img()
    stops = [(0.0, "#000000"), (45.0, "#7A1F00"), (100.0, "#FFE9C4")]
    assert _flat(gradient_stops(im, stops)) == _flat(gradient_stops(im, stops))


def test_two_stop_bw_matches_luminance():
    from app.grade import gradient_stops

    stops = [(0.0, "#000000"), (100.0, "#FFFFFF")]
    black = gradient_stops(Image.new("RGB", (4, 4), (0, 0, 0)), stops)
    white = gradient_stops(Image.new("RGB", (4, 4), (255, 255, 255)), stops)
    mid = gradient_stops(Image.new("RGB", (4, 4), (128, 128, 128)), stops)
    assert black.load()[0, 0] == (0, 0, 0)
    assert white.load()[0, 0] == (255, 255, 255)
    assert all(abs(v - 128) <= 2 for v in mid.load()[0, 0])


def test_mid_stop_hits_its_ink():
    from app.grade import gradient_stops

    stops = [(0.0, "#000000"), (50.0, "#FF0000"), (100.0, "#FFFFFF")]
    mid = gradient_stops(Image.new("RGB", (4, 4), (128, 128, 128)), stops)
    r, g, b = mid.load()[0, 0]
    assert abs(r - 255) <= 3 and g <= 3 and b <= 3


def test_normalize_sorts_clamps_and_dedups():
    from app.grade import normalize_stops

    pts = normalize_stops([(80.0, "#FFFFFF"), (-5.0, "#000000"),
                           (80.0, "#FF0000"), (50.0, "junk"), (None, None)])
    assert pts == [(0.0, (0, 0, 0)), (80.0, (255, 0, 0))]
    assert normalize_stops(None) == []


def test_legacy_preset_renders_byte_identical():
    from app.pipeline import RenderSpec, render_spec

    im = _img()
    base = dict(method="bayer4", palette_name="SLIME", grain=20.0, vignette=30.0)
    assert _flat(render_spec(im, RenderSpec(**base))) == _flat(
        render_spec(im, RenderSpec(**base, gradient_stops=None)))


def test_stack_on_changes_output_and_order_matters():
    from app.pipeline import RenderSpec, render_spec

    im = _img()
    stops = [(0.0, "#000000"), (50.0, "#E8641B"), (100.0, "#FFE9C4")]
    off = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME",
                                     gradient_stops=None))
    on = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME",
                                    gradient_stops=stops))
    assert _flat(on) != _flat(off)
    a = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME",
                                   gradient_stops=stops, grain=40.0,
                                   fx_stack=[{"id": "gradient_map", "enabled": True},
                                             {"id": "grain", "enabled": True}]))
    b = render_spec(im, RenderSpec(method="bayer4", palette_name="SLIME",
                                   gradient_stops=stops, grain=40.0,
                                   fx_stack=[{"id": "grain", "enabled": True},
                                             {"id": "gradient_map", "enabled": True}]))
    assert _flat(a) != _flat(b)


def test_preset_roundtrip_keeps_stops():
    from app.presets import Preset

    stops = [[0.0, "#000000"], [50.0, "#E8641B"], [100.0, "#FFE9C4"]]
    p = Preset(name="g", gradient_stops=stops)
    p.validate()
    q = Preset.from_dict(p.to_dict())
    assert q.gradient_stops == stops
    assert q.meta()["grade"]["gradient_map"] == stops
