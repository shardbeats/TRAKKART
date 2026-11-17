"""Pins for v2.x #6: SVG color-region export (one layer per ink).

Rect runs grouped per palette ink (<g id="ink-RRGGBB">), display +
separation reuse. Rect count unchanged (row RLE), layers == inks.
Deterministic, offline, Pillow only.
"""

from __future__ import annotations

from PIL import Image


def _two_colors():
    im = Image.new("RGB", (16, 16))
    px = im.load()
    for y in range(16):
        for x in range(16):
            px[x, y] = (255, 0, 0) if x < 8 else (0, 0, 255)
    return im


def test_two_inks_two_layers_rect_count_kept():
    from app.vector import raster_to_svg

    svg = raster_to_svg(_two_colors(), 8)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert svg.count("<rect") == 32  # 16 rows x 2 runs (RLE unchanged)
    assert svg.count("<g ") == 2
    assert 'id="ink-FF0000"' in svg and 'id="ink-0000FF"' in svg


def test_rects_inherit_group_fill():
    from app.vector import raster_to_svg

    svg = raster_to_svg(_two_colors(), 8)
    assert svg.count('fill="#ff0000"') == 1  # group fill, not per-rect
    assert svg.count('fill="#0000ff"') == 1
    body = svg.split(">", 1)[1]
    assert body.count("<rect") == 32
    # layer order = first appearance (red row-start first)
    assert svg.index('id="ink-FF0000"') < svg.index('id="ink-0000FF"')


def test_ink_only_single_black_layer():
    from app.vector import raster_to_svg

    im = Image.new("RGB", (8, 4), (255, 255, 255))
    px = im.load()
    for y in range(4):
        for x in range(4):
            px[x, y] = (0, 0, 0)
    svg = raster_to_svg(im, 8, ink_only=True)
    assert "#000000" in svg
    assert svg.count("<rect") == 4  # ink only, no paper
    assert svg.count("<g ") == 1
    assert 'id="ink-000000"' in svg
    full = raster_to_svg(im, 8, ink_only=False)
    assert full.count("<rect") == 8
    assert full.count("<g ") == 2


def test_layered_deterministic_and_byte_sane():
    from app.vector import estimate_bytes, raster_to_svg

    a = raster_to_svg(_two_colors(), 8)
    b = raster_to_svg(_two_colors(), 8)
    assert a == b
    raw = len(a.encode("utf-8"))
    assert 0 < raw < estimate_bytes(16, 16)  # RLE + shared fills beat ~60B/cell
    # grouped shares fills: strictly smaller than one fill per rect
    assert raw < a.count("<rect") * 60


def test_background_stays_outside_layers():
    from app.vector import raster_to_svg

    svg = raster_to_svg(_two_colors(), 8, background=(255, 255, 255))
    assert svg.count("<rect") == 33  # bg full-bleed + 32 runs
    assert svg.index('width="100%"') < svg.index("<g ")


def test_vector_bundle_layers_integration():
    from app.presets import Preset
    from app.vector import vector_bundle

    im = Image.new("RGB", (64, 64), (255, 255, 255))
    px = im.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = (0, 0, 0) if x < 32 else (255, 255, 255)
    p = Preset(name="t", method="bayer4", palette="BW", vector_cell=8)
    svg, cols, rows = vector_bundle(im, p)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 1 <= svg.count("<g ") <= 2
    assert svg.count("<rect") >= 1
    assert cols >= 1 and rows >= 1
