"""v1.8 Fase C: preset-pack share + batch bundle-as-ZIP."""

import json
import zipfile

from PIL import Image


def _preset_dir(d, name="Mine", palette="BW", custom=None):
    from app.presets import Preset, save_preset

    kw = {"name": name, "palette": palette}
    if custom is not None:
        kw["custom_palette"] = custom
    return save_preset(Preset(**kw), d)


def test_pack_roundtrip_with_palette(tmp_path):
    from app.pack import export_pack, import_pack
    from app.presets import load_preset

    src_p, src_a = tmp_path / "p", tmp_path / "a"
    (src_a).mkdir()
    _preset_dir(src_p, "Mine", palette="BW")
    (src_a / "Custom9.json").write_text(json.dumps(
        {"name": "Custom9", "colors": [[10, 20, 30], [200, 210, 220]]}),
        encoding="utf-8")
    out = export_pack(["Mine"], src_p, src_a, tmp_path / "pack.zip")
    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = sorted(zf.namelist())
    assert names == ["pack.json", "palettes/Custom9.json", "presets/Mine.json"]

    dst_p, dst_a = tmp_path / "q", tmp_path / "b"
    rep = import_pack(out, dst_p, dst_a)
    assert rep == {"presets_imported": ["Mine"], "presets_skipped": [],
                   "palettes_imported": ["Custom9"], "palettes_skipped": []}
    assert load_preset("Mine", dst_p).palette == "BW"
    # second import skips existing, imports nothing
    rep2 = import_pack(out, dst_p, dst_a)
    assert rep2["presets_imported"] == [] and rep2["presets_skipped"] == ["Mine"]
    assert rep2["palettes_skipped"] == ["Custom9"]


def test_pack_rejects_traversal_and_invalid(tmp_path):
    import pytest

    from app.pack import export_pack, import_pack

    src_p = tmp_path / "p"
    _preset_dir(src_p, "Mine")
    with pytest.raises(ValueError):
        export_pack([], src_p, tmp_path / "a", tmp_path / "e.zip")
    with pytest.raises(FileNotFoundError):
        export_pack(["Nope"], src_p, tmp_path / "a", tmp_path / "e.zip")
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../evil.json", "{}")
    with pytest.raises(ValueError):
        import_pack(evil, tmp_path / "q", tmp_path / "b")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("presets/X.json", json.dumps({"name": "X", "method": "nope"}))
    with pytest.raises(ValueError):
        import_pack(bad, tmp_path / "q2", tmp_path / "b2")


def test_pack_builtin_palette_needs_no_file(tmp_path):
    from app.pack import export_pack

    src_p = tmp_path / "p"
    _preset_dir(src_p, "Mine", palette="VAPOR")
    out = export_pack(["Mine"], src_p, tmp_path / "a", tmp_path / "pack.zip")
    with zipfile.ZipFile(out) as zf:
        names = sorted(zf.namelist())
    assert names == ["pack.json", "presets/Mine.json"]


def test_bundle_zip_roundtrip_and_empty(tmp_path):
    import pytest

    from app.pack import bundle_zip

    d = tmp_path / "out"
    d.mkdir()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(d / "a.jpg", "JPEG", quality=90)
    (d / "b.txt").write_text("hi", encoding="utf-8")
    dest = bundle_zip(d)
    assert dest.is_file() and dest.name == "out_bundle.zip"
    with zipfile.ZipFile(dest) as zf:
        assert sorted(zf.namelist()) == ["a.jpg", "b.txt"]
    with pytest.raises(ValueError):
        bundle_zip(tmp_path / "missing")
    e = tmp_path / "e2"
    e.mkdir()
    with pytest.raises(ValueError):
        bundle_zip(e)
