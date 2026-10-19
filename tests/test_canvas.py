"""Canvas tests: exact ratios, clamp, contain, fallbacks."""

from PIL import Image

from app.canvas import CROP_MODES, canvas_size_for, fit_contain, ratio_names, to_canvas


def _img(w: int = 400, h: int = 300) -> Image.Image:
    return Image.new("RGB", (w, h), (80, 40, 120))


def test_all_ratios_exact():
    assert set(ratio_names()) == {"1:1", "4:3", "3:2", "4:5", "16:9", "9:16"}
    assert canvas_size_for("1:1", 3000) == (3000, 3000)
    assert canvas_size_for("16:9", 3000) == (3000, 1688)
    w, h = canvas_size_for("9:16", 3000)
    assert (w, h) == (1688, 3000)
    assert canvas_size_for("4:5", 960) == (768, 960)


def test_cover_center_and_focus():
    out = to_canvas(_img(), ratio="1:1")
    assert out.size == (300, 300)
    out = to_canvas(_img(), ratio="16:9", fx=0, fy=0)
    assert out.size == (400, 225)


def test_cover_clamp_out_of_range():
    out = to_canvas(_img(), ratio="9:16", fx=999, fy=-99)
    assert out.size == (169, 300)  # 300*9/16 rounded
    assert out.size[0] > 0 and out.size[1] > 0


def test_fit_contain_square_passthrough():
    from PIL import Image

    sq = Image.new("RGB", (100, 100), (1, 2, 3))
    out = fit_contain(sq, "1:1")
    assert out.size == (100, 100)
    assert list(out.get_flattened_data()) == list(sq.get_flattened_data())


def test_contain_pads_without_cropping():
    out = fit_contain(_img(), "1:1")
    assert out.size == (400, 400)
    out = to_canvas(_img(), ratio="9:16", mode="contain")
    assert out.size == (400, 711)


def test_invalid_ratio_and_mode_fallback():
    assert to_canvas(_img(), ratio="99:99").size == (300, 300)
    assert to_canvas(_img(), ratio="1:1", mode="weird").size == (300, 300)
    assert set(CROP_MODES) == {"cover", "contain"}


def test_crop_zoom_one_matches_classic():
    a = to_canvas(_img(), ratio="9:16", fx=20, fy=80, zoom=1.0)
    b = to_canvas(_img(), ratio="9:16", fx=20, fy=80)
    assert a.size == b.size
    assert list(a.get_flattened_data()) == list(b.get_flattened_data())


def test_crop_zoom_tighter_same_ratio():
    out = to_canvas(_img(), ratio="1:1", zoom=2.0)
    assert out.size == (150, 150)
    assert out.size[0] / out.size[1] == 1.0


def test_crop_box_for_mirrors_crop_cover():
    from app.canvas import crop_box_for

    box = crop_box_for(400, 300, "1:1", 50, 50, 2.0)
    out = to_canvas(_img(), ratio="1:1", zoom=2.0)
    assert (box[2], box[3]) == out.size
    bx, by, bw, bh = box
    assert 0 <= bx <= 400 - bw and 0 <= by <= 300 - bh
