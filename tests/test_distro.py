"""v1.8 Fase A: distributor delivery (DISTRO_3000 + validator + TIFF + DPI)."""

import json

from PIL import Image


def _img(w=64, h=64, color=(10, 20, 30)):
    return Image.new("RGB", (w, h), color)


def test_distro_preset_is_symmetric_and_valid(tmp_path):
    from app.canvas import doc_dimensions
    from app.presets import ensure_bundled, load_preset

    ensure_bundled(tmp_path)
    p = load_preset("DISTRO_3000", tmp_path)
    p.validate()
    assert (p.ratio, p.export_size) == ("1:1", 3000)
    assert (p.export_format, p.export_quality) == ("jpg", 90)
    assert doc_dimensions(p.ratio, p.export_size, p.canvas_w, p.canvas_h) == (3000, 3000)


def test_validate_session_ready():
    from app.distro import distro_summary, validate_session

    checks = validate_session(3000, 3000, "jpg", 3000, 3000, 90)
    assert all(c.ok for c in checks)
    ok, _summary = distro_summary(checks)
    assert ok


def test_validate_session_flags_each_problem():
    from app.distro import validate_session

    def codes(**kw):
        args = {"doc_w": 3000, "doc_h": 3000, "fmt": "jpg",
                "src_w": 3000, "src_h": 3000, "quality": 90}
        args.update(kw)
        return {c.code for c in validate_session(**args) if not c.ok}

    assert codes(doc_h=2000) == {"square"}
    assert codes(doc_w=1080, doc_h=1080) == {"size"}
    assert codes(fmt="png") == {"format"}
    assert codes(quality=70) == {"quality"}
    assert codes(src_w=1000, src_h=800) == {"upscale"}
    # hints are honest (mention the actual numbers)
    from app.distro import validate_session as vs

    bad = [c for c in vs(3000, 2000, "png", 500, 500, 70) if not c.ok]
    assert len(bad) >= 4
    assert all(c.hint for c in bad)


def test_validate_file_roundtrip(tmp_path):
    from app.distro import distro_summary, validate_file

    good = tmp_path / "cover.jpg"
    _img(3000, 3000).save(str(good), "JPEG", quality=90)
    checks = validate_file(good)
    ok, _summary = distro_summary(checks)
    assert ok

    bad = tmp_path / "small.png"
    _img(800, 600).save(str(bad), "PNG")
    codes = {c.code for c in validate_file(bad) if not c.ok}
    assert {"square", "size", "format"} <= codes

    missing = validate_file(tmp_path / "nope.jpg")
    assert missing and not missing[0].ok and missing[0].code == "readable"


def test_validate_file_mode_must_be_rgb(tmp_path):
    from app.distro import validate_file

    gray = tmp_path / "g.jpg"
    Image.new("L", (3000, 3000), 128).save(str(gray), "JPEG", quality=90)
    codes = {c.code for c in validate_file(gray) if not c.ok}
    assert "mode" in codes


def test_tiff_still_roundtrip_with_tags(tmp_path):
    from app.exporter import save_tiff_still

    out = tmp_path / "print.tif"
    save_tiff_still(_img(128, 128), out, dpi=300)
    with Image.open(out) as im:
        im.load()
        assert im.size == (128, 128) and im.mode == "RGB"
        assert im.info.get("compression") == "tiff_lzw"
        assert tuple(im.info.get("dpi", (0, 0))) == (300, 300)


def test_export_options_dpi_validation_and_metadata(tmp_path):
    import pytest

    from app.exporter import ExportOptions, ExportSelection, export_with_options

    assert ExportOptions().dpi == 300
    with pytest.raises(ValueError):
        ExportOptions(dpi=50)
    with pytest.raises(ValueError):
        ExportOptions(dpi=601)
    sel = ExportSelection(image=True, metadata=True)
    opts = ExportOptions(format="jpg", quality=90, dpi=300, size=128, selection=sel)
    paths, _sk = export_with_options(_img(), tmp_path, opts, meta={"ratio": "1:1"})
    with Image.open(paths["image"]) as im:
        assert tuple(im.info.get("dpi", (0, 0))) == (300, 300)
    meta2 = json.loads((tmp_path / "trakkart_cover_metadata.json").read_text(
        encoding="utf-8"))
    assert meta2["export"]["dpi"] == 300


def test_separation_plates_carry_dpi(tmp_path):
    from app.separations import write_separations

    paths = write_separations(_img(64, 64), [(0, 0, 0), (255, 255, 255)],
                              tmp_path, "s", dpi=300)
    assert len(paths) == 2
    with Image.open(paths[0]) as im:
        # PNG stores DPI as float pixels/meter: 300000/0.0254 rounds.
        got = im.info.get("dpi", (0, 0))
        assert all(abs(d - 300) < 0.01 for d in got)


def test_export_service_writes_tiff_extra(tmp_path):
    from app.presets import Preset
    from app.services.export_service import export_full

    preset = Preset(name="t")
    paths, _skipped = export_full(
        _img(), preset, tmp_path, base="c", size=128,
        tiff=True, dpi=300,
        gif_frames=2, gif_mode="both",
    )
    assert paths["tiff"].is_file() and paths["tiff"].suffix == ".tif"
    with Image.open(paths["tiff"]) as im:
        im.load()
        assert tuple(im.info.get("dpi", (0, 0))) == (300, 300)
        assert im.size[0] == im.size[1]


def test_prefs_carry_tiff_and_dpi(tmp_path):
    from app.export_prefs import ExportPrefs, load_prefs, normalize_prefs, save_prefs

    prefs = ExportPrefs(tiff=True, dpi=150)
    save_prefs(prefs, tmp_path / "p.json")
    back = load_prefs(tmp_path / "p.json")
    assert back.tiff is True and back.dpi == 150
    weird = ExportPrefs(dpi=50)
    normalize_prefs(weird)
    assert weird.dpi == 72
