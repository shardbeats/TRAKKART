"""Ink separations (R9): spot plates + registration marks + export hook."""

import numpy as np
from PIL import Image


def _img(w=64, h=64):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 5) % 256, (y * 7) % 256, 140)
    return im


def test_plates_nearest_disjoint_covering():
    from app.separations import separation_plates

    im = Image.new("RGB", (64, 64), (255, 0, 0))
    px = im.load()
    for y in range(64):
        for x in range(32, 64):
            px[x, y] = (0, 0, 255)
    plates = separation_plates(im, [(255, 0, 0), (0, 0, 255)])
    assert [h for h, _ in plates] == ["FF0000", "0000FF"]
    assert all(p.size == (64, 64) and p.mode == "L" for _, p in plates)
    a = np.asarray(plates[0][1])
    b = np.asarray(plates[1][1])
    assert (a[:, :32] == 0).all() and (a[:, 32:] == 255).all()
    assert ((a == 0) | (b == 0)).all()  # every pixel prints on exactly one plate
    assert ((a == 0) & (b == 0)).sum() == 0


def test_plates_deterministic_and_marked(tmp_path):
    from app.separations import add_registration_marks, separation_plates, write_separations

    plates = separation_plates(_img(), [(0, 0, 0), (255, 255, 255)])
    p1 = write_separations(_img(), [(0, 0, 0), (255, 255, 255)], tmp_path / "a", base="m")
    p2 = write_separations(_img(), [(0, 0, 0), (255, 255, 255)], tmp_path / "b", base="m")
    assert [p.name for p in p1] == ["m_sep_01_000000.png", "m_sep_02_FFFFFF.png"]
    assert p1[0].read_bytes() == p2[0].read_bytes()
    for _, plate in plates:
        marked = add_registration_marks(plate.copy())
        assert marked.size == plate.size
        m = min(marked.size)
        inset = max(4, m // 25)
        corner = np.asarray(marked)[inset - 2:inset + 3, inset - 2:inset + 3]
        assert (corner == 0).any()  # registration ink lands near every corner


def test_effective_palette_and_count():
    from app.presets import Preset
    from app.separations import effective_palette, plate_count

    assert effective_palette(Preset(name="t", palette="BW")) == [(0, 0, 0), (255, 255, 255)]
    assert plate_count(Preset(name="t", palette="BW")) == 2
    slime = effective_palette(Preset(name="t", palette="SLIME"))
    assert len(slime) == 4 and plate_count(Preset(name="t", palette="SLIME")) == 4
    custom = [[10, 0, 0], [0, 20, 0], [0, 0, 30]]
    assert effective_palette(Preset(name="t", custom_palette=custom)) == [(10, 0, 0), (0, 20, 0), (0, 0, 30)]
    assert plate_count(Preset(name="t", custom_palette=custom)) == 3
    src = effective_palette(Preset(name="t", palette="SOURCE"), _img())
    assert len(src) == 6  # extracted default depth
    assert plate_count(Preset(name="t", palette="SOURCE")) == 6
    from app.separations import estimate_sep, sep_name

    assert sep_name("beat", 0, "FF0000") == "beat_sep_01_FF0000.png"
    assert estimate_sep(1080, 1920, 4) == 1080 * 1920 * 4 // 8


def test_trap_expands_ink_by_one_pixel():
    import numpy as np

    from app.separations import separation_plates

    bg = Image.new("RGB", (32, 32), (0, 0, 255))
    bg.paste(Image.new("RGB", (8, 8), (255, 0, 0)), (12, 12))
    cols = [(255, 0, 0), (0, 0, 255)]
    plain = np.asarray(separation_plates(bg, cols)[0][1])
    trapped = np.asarray(separation_plates(bg, cols, trap_px=1)[0][1])
    assert int((plain == 0).sum()) == 64
    assert int((trapped == 0).sum()) == 100  # 8x8 -> 10x10
    # Blue plate shrinks where red overprints (trap overlaps, no white gap):
    # blue dilates into the red square's border ring (28px), so both
    # inks cover the ring (overprint hides misregistration).
    blue = np.asarray(separation_plates(bg, cols, trap_px=1)[1][1])
    assert int((blue == 0).sum()) == 32 * 32 - 64 + 28
    overlap = int(((trapped == 0) & (blue == 0)).sum())
    assert overlap == 100 - 64 + 28  # red ring + blue ring share ink
    # trap_px clamps to 4 and stays deterministic.
    big = separation_plates(bg, cols, trap_px=99)[0][1]
    ref = separation_plates(bg, cols, trap_px=4)[0][1]
    assert list(big.get_flattened_data()) == list(ref.get_flattened_data())


def test_export_full_separations_with_trap(tmp_path):
    from app.exporter import ExportSelection
    from app.presets import Preset
    from app.services.export_service import export_full
    from PIL import Image as _I

    preset = Preset(name="t", method="bayer4", palette="BW", export_size=64)
    sel = ExportSelection(
        image=True, thumb_1080p=False, vector=False, anim=False, metadata=False)
    _, _ = export_full(_img(64, 64), preset, tmp_path / "a", base="m",
                       selection=sel, sep=True)
    paths, skipped = export_full(
        _img(64, 64), preset, tmp_path / "b", base="m",
        selection=sel, sep=True, sep_trap=True)
    assert skipped == []
    for p in paths.values():
        if "_sep_" not in str(p):
            continue
        with _I.open(p) as im:
            assert im.size == (64, 64)
    assert any("_sep_" in str(p) for p in paths.values())


def test_export_full_separations(tmp_path):
    from app.exporter import ExportSelection
    from app.presets import Preset
    from app.services.export_service import export_full

    preset = Preset(name="t", method="bayer4", palette="SLIME", export_size=64)
    sel = ExportSelection(
        image=True, thumb_1080p=False, vector=False, anim=False, metadata=False)
    paths, skipped = export_full(
        _img(64, 64), preset, tmp_path / "os", base="m",
        selection=sel, sep=True)
    seps = sorted(str(p) for p in paths.values() if "_sep_" in str(p))
    assert len(seps) == 4
    assert all(p.endswith(".png") for p in seps)
    assert skipped == []


def test_export_dialog_sep_checkbox(window, qt_app, tmp_path):
    from app.presets import Preset
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    window.src = _img(64, 64)
    preset = Preset(name="t", method="bayer4", palette="SLIME", export_size=64)
    dlg = ExportDialog(window.src, preset.meta(), base="m", out_dir=str(tmp_path),
                       preset=preset, gif_frames=2)
    try:
        assert dlg.chk_sep.isChecked() is False
        assert dlg._gif_opts()["sep"] is False
        dlg.chk_sep.setChecked(True)
        assert dlg._gif_opts()["sep"] is True
        assert any("_sep_" in dlg.list_files.item(i).text()
                   for i in range(dlg.list_files.count()))
        assert dlg.chk_trap.isChecked() is False
        assert dlg._gif_opts()["sep_trap"] is False
        dlg.chk_trap.setChecked(True)
        assert dlg._gif_opts()["sep_trap"] is True
        assert any("trap" in dlg.list_files.item(i).text()
                   for i in range(dlg.list_files.count()))
    finally:
        close_dialog(dlg)
