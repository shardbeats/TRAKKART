"""v1.9 Fase C: color confidence (daltonism, WCAG contrast, Lospec import)."""

import json

from PIL import Image


def _img(w=64, h=64):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 4) % 256, (y * 4) % 256, 140)
    return im


def test_cvd_kinds_and_deterministic():
    from app.color_access import CVD_KINDS, simulate_cvd

    assert set(CVD_KINDS) == {"protan", "deutan", "tritan"}
    for kind in CVD_KINDS:
        a = simulate_cvd(_img(), kind)
        b = simulate_cvd(_img(), kind)
        assert list(a.get_flattened_data()) == list(b.get_flattened_data())
        assert a.size == _img().size and a.mode == "RGB"


def test_cvd_kinds_differ_and_not_identity():
    from app.color_access import simulate_cvd

    outs = [list(simulate_cvd(_img(), k).get_flattened_data())
            for k in ("protan", "deutan", "tritan")]
    assert len({str(o) for o in outs}) == 3  # three distinct simulations
    assert outs[0] != list(_img().get_flattened_data())


def test_cvd_red_anchor_per_kind():
    from app.color_access import simulate_cvd

    red = Image.new("RGB", (4, 4), (255, 0, 0))
    # Viénot-style matrices: red collapses toward yellow-olive (protan/
    # deutan) but stays red under tritan (blue-axis only).
    assert simulate_cvd(red, "protan").getpixel((0, 0)) == (144, 142, 0)
    assert simulate_cvd(red, "deutan").getpixel((0, 0)) == (159, 178, 0)
    assert simulate_cvd(red, "tritan").getpixel((0, 0)) == (242, 0, 0)


def test_cvd_off_and_unknown():
    from app.color_access import simulate_cvd

    import pytest

    for off in ("off", "none", ""):
        out = simulate_cvd(_img(), off)
        assert list(out.get_flattened_data()) == list(_img().get_flattened_data())
        assert out is not _img()  # display copy, doc untouched
    with pytest.raises(ValueError):
        simulate_cvd(_img(), "xray")


def test_contrast_black_white_21_and_same_1():
    from app.color_access import contrast_ratio

    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == 21.0
    assert contrast_ratio((120, 120, 120), (120, 120, 120)) == 1.0
    # Order-independent.
    assert (contrast_ratio((0, 0, 0), (200, 30, 30))
            == contrast_ratio((200, 30, 30), (0, 0, 0)))


def test_accessibility_report_ok_and_low():
    from app.color_access import accessibility_report

    ok = accessibility_report([(0, 0, 0), (255, 255, 255)])
    assert ok["min_ratio"] == 21.0
    assert ok["low_pairs"] == [] and not ok["bw_collapse"]
    assert ok["message"].startswith("contrast ok")
    # Two near-identical darks: low contrast + BW-collapse.
    bad = accessibility_report([(10, 10, 10), (16, 16, 16)])
    assert bad["min_ratio"] < 1.5
    assert len(bad["low_pairs"]) == 1 and bad["bw_collapse"]
    assert "BW-collapse" in bad["message"]
    # Dark gray vs black: low but not collapsed.
    mid = accessibility_report([(0, 0, 0), (80, 80, 80)])
    assert 1.5 <= mid["min_ratio"] < 3.0
    assert len(mid["low_pairs"]) == 1 and not mid["bw_collapse"]


def test_accessibility_report_edge_cases():
    from app.color_access import accessibility_report

    assert accessibility_report([])["message"].startswith("need 2+")
    assert accessibility_report([(1, 2, 3)])["min_ratio"] == 0.0
    # Three inks: only adjacent pairs are checked.
    rep = accessibility_report([(0, 0, 0), (255, 255, 255), (250, 250, 250)])
    assert [p[:2] for p in rep["low_pairs"]] == [(1, 2)]
    assert rep["bw_collapse"]  # white~off-white prints as one gray


def test_parse_hex_txt_roundtrip_and_junk():
    from app.color_access import parse_hex, parse_txt

    name, colors = parse_hex("#FF0000\n00FF00\n#0000FF\n", "t")
    assert (name, colors) == ("t", [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
    assert parse_txt("ff0000\n00ff00\n0000ff\n", "u")[1] == colors
    # Junk lines skipped, dupes dropped, 3-digit expanded.
    _, colors = parse_hex("\n; comment\n#F00\nnot a color\n#F00\n#0000FF\n", "t")
    assert colors == [(255, 0, 0), (0, 0, 255)]
    import pytest

    with pytest.raises(ValueError):
        parse_hex("#FF0000\n", "t")  # single color: nothing to dither with
    with pytest.raises(ValueError):
        parse_hex("no colors here\n", "t")


def test_parse_pal_jasc_and_bad_header():
    from app.color_access import parse_pal

    name, colors = parse_pal(
        "JASC-PAL\n0100\n3\n255 0 0\n0 255 0\n0 0 255\n", "t")
    assert (name, colors) == ("t", [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
    import pytest

    with pytest.raises(ValueError):
        parse_pal("RIFF....PAL data\n", "t")
    with pytest.raises(ValueError):
        parse_pal("JASC-PAL\n0100\n1\n255 0 0\n", "t")


def test_parse_palette_text_dispatch_and_truncate():
    from app.color_access import parse_palette_text

    n, c = parse_palette_text("GIMP Palette\nName: X\n255 0 0\n0 255 0\n", "gpl")
    assert (n, c) == ("X", [(255, 0, 0), (0, 255, 0)])
    n, c = parse_palette_text(
        json.dumps({"name": "J", "colors": [[1, 2, 3], [4, 5, 6]]}), "json")
    assert (n, c) == ("J", [(1, 2, 3), (4, 5, 6)])
    big = "\n".join(f"{i:02X}0000" for i in range(1, 25))
    _, c = parse_palette_text(big, "hex", name="big")
    assert len(c) == 16  # deterministic truncate to engine cap
    import pytest

    with pytest.raises(ValueError):
        parse_palette_text("whatever", "bmp")


def test_parse_palette_path_all_suffixes(tmp_path):
    from app.palette_library import parse_palette_path

    cases = {
        "a.json": json.dumps({"name": "J", "colors": [[1, 2, 3], [200, 200, 200]]}),
        "b.gpl": "GIMP Palette\nName: G\n10 20 30\n200 200 200\n",
        "c.hex": "#0A141E\n#C8C8C8\n",
        "d.txt": "0A141E\nC8C8C8\n",
        "e.pal": "JASC-PAL\n0100\n2\n10 20 30\n200 200 200\n",
    }
    expected = {
        "a.json": [(1, 2, 3), (200, 200, 200)],
        "b.gpl": [(10, 20, 30), (200, 200, 200)],
        "c.hex": [(10, 20, 30), (200, 200, 200)],
        "d.txt": [(10, 20, 30), (200, 200, 200)],
        "e.pal": [(10, 20, 30), (200, 200, 200)],
    }
    for fname, text in cases.items():
        p = tmp_path / fname
        p.write_text(text, encoding="utf-8")
        _, colors = parse_palette_path(p)
        assert colors == expected[fname], fname


def test_curated_pack_size_and_valid():
    from pathlib import Path

    from app.fx import normalize_custom_palette

    files = sorted(Path("palettes").glob("*.json"))
    assert len(files) >= 20  # ~20 dither-friendly ramps ship offline
    for f in files:
        raw = json.loads(f.read_text(encoding="utf-8"))
        colors = raw.get("colors", raw) if isinstance(raw, dict) else raw
        assert normalize_custom_palette([list(c) for c in colors]) is not None, f


def test_curated_ramps_read_dark_to_light():
    from pathlib import Path

    from app.color_access import relative_luminance

    for f in sorted(Path("palettes").glob("*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        colors = raw.get("colors", raw) if isinstance(raw, dict) else raw
        lums = [relative_luminance(c) for c in colors]
        assert lums == sorted(lums), f"{f.stem} should read dark -> light"
