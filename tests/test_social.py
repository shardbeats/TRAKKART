"""v1.8 Fase B: social pack + Apple Motion + text safe-areas."""

from PIL import Image


def _img(w=64, h=64, color=(10, 20, 30)):
    return Image.new("RGB", (w, h), color)


def test_pack_stems_sizes_and_names():
    from app.social import SOCIAL_SIZES, build_pack, estimate_pack, pack_names

    assert set(SOCIAL_SIZES) == {"social_yt", "social_916", "social_11"}
    names = pack_names("cover", "jpg")
    assert names == {
        "social_yt": "cover_social_yt.jpg",
        "social_916": "cover_social_916.jpg",
        "social_11": "cover_social_11.jpg",
    }
    pack = build_pack(_img(3000, 3000, (200, 100, 50)))
    assert pack["social_yt"].size == (1280, 720)
    assert pack["social_916"].size == (1080, 1920)
    assert pack["social_11"].size == (1080, 1080)
    assert estimate_pack("jpg", 90) > 0


def test_anchor_is_centered():
    from app.social import build_pack

    # left half red, right half blue: a centered crop keeps both sides.
    img = Image.new("RGB", (3000, 3000), (255, 0, 0))
    img.paste(Image.new("RGB", (1500, 3000), (0, 0, 255)), (1500, 0))
    pack = build_pack(img)
    tall = pack["social_916"]
    assert tall.getpixel((10, 960))[0] > 200  # left edge still red
    assert tall.getpixel((1069, 960))[2] > 200  # right edge still blue
    wide = pack["social_yt"]
    assert wide.getpixel((100, 10))[0] > 200  # red side survives
    assert wide.getpixel((1180, 709))[2] > 200  # blue side survives
    sq = pack["social_11"]
    assert sq.getpixel((10, 540))[0] > 200 and sq.getpixel((1069, 540))[2] > 200


def test_apple_motion_presets(tmp_path):
    from app.canvas import doc_dimensions
    from app.presets import ensure_bundled, load_preset

    ensure_bundled(tmp_path)
    m = load_preset("APPLE_MOTION", tmp_path)
    m.validate()
    assert (m.ratio, m.export_size) == ("1:1", 4000)
    assert doc_dimensions(m.ratio, m.export_size, m.canvas_w, m.canvas_h) == (4000, 4000)
    assert (m.gif_mode, m.gif_frames, m.gif_fps) == ("dissolve", 64, 24)
    assert bool(m.dissolve_loop) is True
    t = load_preset("APPLE_MOTION_TALL", tmp_path)
    t.validate()
    assert (t.ratio, t.export_size) == ("3:4", 3000)
    assert doc_dimensions(t.ratio, t.export_size, t.canvas_w, t.canvas_h) == (2250, 3000)
    assert bool(t.dissolve_loop) is True


def test_grid_and_title_rows():
    from app.ui.safeareas import band_rows, grid11_rows, title_rows

    assert grid11_rows(1920) == (420, 1500)  # centered 1080 square
    top, bottom = band_rows(1920)
    assert (top, bottom) == (250, 250)
    ttop = title_rows(1920, "top")
    tbot = title_rows(1920, "bottom")
    assert ttop[0] >= top and tbot[1] <= 1920 - bottom  # inside chrome-free zone
    assert ttop[1] <= tbot[0]  # bands do not overlap
    assert title_rows(1920, "TOP") == ttop  # case-insensitive


def test_export_service_writes_social_pack(tmp_path):
    from app.presets import Preset
    from app.services.export_service import export_full

    preset = Preset(name="t")
    paths, _skipped = export_full(
        _img(), preset, tmp_path, base="c", size=128,
        social=True, format="jpg",
        gif_frames=2, gif_mode="both",
    )
    assert len([k for k in paths if k.startswith("social_")]) == 3
    from PIL import Image as _I

    for stem, dims in (("social_yt", (1280, 720)),
                       ("social_916", (1080, 1920)),
                       ("social_11", (1080, 1080))):
        p = paths[f"social_{stem}"]
        assert p.is_file()
        with _I.open(p) as im:
            assert im.size == dims


def test_export_full_social_skip_and_rename(tmp_path):
    from app.presets import Preset
    from app.services.export_service import export_full

    preset = Preset(name="t")
    kw = {"size": 64, "social": True, "format": "jpg",
          "gif_frames": 2, "gif_mode": "both"}
    paths1, _ = export_full(_img(), preset, tmp_path, base="c", **kw)
    assert len([k for k in paths1 if k.startswith("social_")]) == 3
    _p2, skipped = export_full(_img(), preset, tmp_path, base="c",
                               overwrite="skip", **kw)
    assert any(str(s).startswith("social_") for s in skipped)


def test_prefs_carry_social(tmp_path):
    from app.export_prefs import ExportPrefs, load_prefs, save_prefs

    prefs = ExportPrefs(social=True)
    save_prefs(prefs, tmp_path / "p.json")
    assert load_prefs(tmp_path / "p.json").social is True
