"""Vector SVG tests: RLE, grid, background, estimate."""

from PIL import Image

from app.presets import Preset
from app.vector import estimate_bytes, estimate_cells, raster_to_svg, render_cells, vector_bundle


def _img(size: int = 64) -> Image.Image:
    im = Image.new("RGB", (size, size), (200, 50, 90))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, 128)
    return im


def test_estimate_cells():
    assert estimate_cells(960, 960, 8) == (120, 120)
    assert estimate_cells(100, 100, 0) == (100, 100)
    assert estimate_bytes(120, 120) == 120 * 120 * 60


def test_rle_merges_runs():
    flat = Image.new("RGB", (8, 2), (255, 0, 0))
    svg = raster_to_svg(flat, 4)
    assert svg.startswith("<svg")
    assert svg.count("<rect") == 2  # one row = 1 rect
    assert 'fill="#ff0000"' in svg
    assert "crispEdges" in svg


def test_rle_respects_runs():
    im = Image.new("RGB", (4, 1))
    im.putdata([(255, 0, 0), (255, 0, 0), (0, 0, 255), (0, 0, 255)])
    svg = raster_to_svg(im, 10)
    assert svg.count("<rect") == 2
    assert 'width="20"' in svg


def test_background_rect():
    flat = Image.new("RGB", (2, 2), (1, 2, 3))
    svg = raster_to_svg(flat, 4, background=(255, 255, 255))
    assert 'width="100%"' in svg


def test_render_cells_size():
    out = render_cells(_img(), 16, 16, method="bayer4", palette_name="SLIME")
    assert out.size == (16, 16)


def test_vector_bundle_end_to_end(tmp_path):
    from app.exporter import export_bundle

    p = Preset(name="v", method="bayer4", palette="SLIME", vector_export=True, vector_cell=8)
    svg, cols, rows = vector_bundle(_img(), p)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert (cols, rows) == (8, 8)
    paths = export_bundle(_img(), tmp_path, base="vec", meta=p.meta(), vector_svg=svg)
    assert paths["vector"].exists()
    assert paths["vector"].stat().st_size > 100
    import json

    info = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    assert "vector" in info and info["vector"]["bytes"] > 100
    assert info["params"]["vector_export"] is True


def test_vector_large_source_caps_grid_to_document():
    # 3000x4500 -> 9:16 cover used to be 2531x4500 (316x562 cells > cap)
    # even though the exported document is only 1688x3000.
    src = Image.new("RGB", (3000, 4500), (80, 40, 120))
    p = Preset(name="v", ratio="9:16", crop_mode="cover",
               canvas_w=1688, canvas_h=3000, export_size=3000,
               method="bayer4", palette="BW", vector_cell=8, vector_export=True)
    svg, cols, rows = vector_bundle(src, p)
    assert (cols, rows) == (210, 375)  # doc grid, not source scale
    assert cols * rows <= 160_000
    assert svg.startswith("<svg")


def test_capped_canvas_dims_keep_small_sources():
    from app.vector import capped_canvas_dims

    assert capped_canvas_dims(64, 64, 3000, 3000) == (64, 64)
    assert capped_canvas_dims(4000, 7111, 1688, 3000) == (1688, 3000)


def test_vector_invalid_cell_clamped():
    p = Preset(name="v", vector_cell=99)
    p.vector_cell = 99
    import pytest

    with pytest.raises(ValueError):
        p.validate()
