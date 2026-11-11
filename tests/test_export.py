from pathlib import Path

from app.exporter import export_bundle
from app.palettes import PALETTES, get_palette, palette_names


def _img():
    from PIL import Image

    return Image.new("RGB", (128, 128), (200, 50, 90))


def test_palettes_present():
    assert set(PALETTES.keys()) <= set(palette_names())
    assert "SOURCE" in palette_names()  # v1.1 auto-extract mode
    assert get_palette("BW") is None
    assert len(get_palette("SLIME")) == 4


def test_export_bundle_sizes(tmp_path: Path):
    from PIL import Image

    paths = export_bundle(_img(), tmp_path, base="t")
    assert paths["cover"].exists()
    assert paths["small"].exists()
    assert paths["thumb_1080p"].exists()
    with Image.open(paths["thumb_1080p"]) as im:
        assert im.size == (1920, 1080)
    with Image.open(paths["cover"]) as im:
        assert im.size == (3000, 3000)


def test_export_bundle_invalid_ratio_falls_back(tmp_path: Path):
    from PIL import Image

    paths = export_bundle(_img(), tmp_path, base="x", meta={"ratio": "99:99"})
    with Image.open(paths["cover"]) as im:
        assert im.size == (3000, 3000)


def test_export_bundle_custom_free_dimensions(tmp_path: Path):
    from PIL import Image

    meta = {"ratio": "custom", "canvas": {"w": 1920, "h": 800}}
    paths = export_bundle(_img(), tmp_path, base="c", meta=meta)
    with Image.open(paths["cover"]) as im:
        assert im.size == (1920, 800)
    with Image.open(paths["small"]) as im:
        assert im.size == (960, 400)


def test_empty_canvas_export_writes_nothing(tmp_path: Path):
    import pytest
    from PIL import Image

    from app.exporter import ExportOptions, ExportSelection, export_with_options

    blank = Image.new("RGB", (1, 0))
    opts = ExportOptions(
        base="empty",
        selection=ExportSelection(image=True, thumb_1080p=True,
                                  vector=False, anim=False, metadata=False),
    )
    with pytest.raises(ValueError, match="empty render"):
        export_with_options(blank, tmp_path, opts)
    assert not list(tmp_path.iterdir())  # no partial main file left behind
