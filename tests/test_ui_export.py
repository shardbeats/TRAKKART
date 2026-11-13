"""Professional export: plan, policies, prefs, dialogs, quick (fixtures in conftest)."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def _img(w=64, h=64):
    from PIL import Image

    return Image.new("RGB", (w, h), (90, 60, 140))


def test_plan_lists_everything(tmp_path: Path):
    from app.exporter import ExportOptions, ExportSelection, plan_export

    opts = ExportOptions(base="mix", selection=ExportSelection(
        image=True, thumb_1080p=True, vector=True, anim=True, metadata=True))
    plan = plan_export(_img(), opts, meta={"ratio": "1:1"}, has_vector=True, has_gif=True,
                       extra={"vector_cells": (10, 10), "gif_frames": 4})
    keys = [k for k, _, _ in plan]
    assert keys == ["image", "thumb_1080p", "vector", "anim", "metadata"]
    names = [f for _, f, _ in plan]
    assert names[0] == "mix.png"  # the image rules: name + extension
    assert all(f.startswith("mix") for f in names)
    assert all(est > 0 for _, _, est in plan)


def test_plan_skips_unavailable():
    from app.exporter import ExportOptions, ExportSelection, plan_export

    opts = ExportOptions(base="b", selection=ExportSelection(vector=True, anim=True))
    keys = [k for k, _, _ in plan_export(_img(), opts, has_vector=False, has_gif=False)]
    assert "vector" not in keys and "anim" not in keys


def test_plan_jpg_uses_extension_and_size():
    from PIL import Image

    from app.exporter import ExportOptions, ExportSelection, plan_export

    img = Image.new("RGB", (400, 200), (9, 9, 9))
    opts = ExportOptions(base="j", size=400, format="jpg", quality=80,
                         selection=ExportSelection(image=True, thumb_1080p=True))
    plan = dict((k, (f, e)) for k, f, e in plan_export(img, opts, meta={"ratio": "2:1"}))
    assert plan["image"][0] == "j.jpg"
    assert plan["thumb_1080p"][0] == "j_thumb1080p.jpg"  # same format
    # the thumb is always 1920x1080


def test_with_options_subset_and_rename(tmp_path: Path):
    from app.exporter import ExportOptions, ExportSelection, export_with_options

    opts = ExportOptions(base="sel", selection=ExportSelection(
        image=True, thumb_1080p=False, metadata=True))
    paths, skipped = export_with_options(_img(), tmp_path, opts, meta={"ratio": "1:1"})
    assert set(paths) == {"image", "metadata"}
    assert paths["image"].suffix == ".png"
    assert skipped == []
    # rename: second time with the same base does not overwrite
    paths2, _ = export_with_options(
        _img(), tmp_path, ExportOptions(base="sel", selection=opts.selection,
                                        overwrite="rename"))
    assert paths2["image"].name == "sel_2.png"
    assert (tmp_path / "sel.png").exists()  # the original stays intact


def test_skip_policy_returns_existing(tmp_path: Path):
    from app.exporter import ExportOptions, ExportSelection, export_with_options

    opts = ExportOptions(base="sk", selection=ExportSelection(
        image=True, thumb_1080p=False, metadata=True),
        overwrite="skip")
    paths, skipped = export_with_options(_img(), tmp_path, opts)
    assert paths and skipped == []
    paths2, skipped2 = export_with_options(_img(), tmp_path, opts)
    assert paths2 == {} and set(skipped2) == {"image", "metadata"}


def test_format_mapping_writes_real_files(tmp_path: Path):
    from PIL import Image

    from app.exporter import ExportOptions, ExportSelection, export_with_options

    img = Image.new("RGB", (64, 64), (90, 60, 140))
    for fmt, ext in (("png", "png"), ("jpg", "jpg"), ("webp", "webp")):
        opts = ExportOptions(base=f"f_{fmt}", format=fmt, quality=80,
                             selection=ExportSelection(image=True))
        paths, _ = export_with_options(img, tmp_path, opts)
        assert paths["image"].suffix == f".{ext}"
        assert paths["image"].stat().st_size > 0
        with Image.open(paths["image"]) as im:
            im.load()  # valid file


def test_invalid_options_rejected():
    import pytest

    from app.exporter import ExportOptions

    with pytest.raises(ValueError):
        ExportOptions(format="bmp")
    with pytest.raises(ValueError):
        ExportOptions(size=10)
    with pytest.raises(ValueError):
        ExportOptions(quality=0)
    with pytest.raises(ValueError):
        ExportOptions(overwrite="maybe")


def test_base_sanitized(tmp_path: Path):
    from app.exporter import export_bundle

    paths = export_bundle(_img(), tmp_path, base="../../evil")
    for p in paths.values():
        assert tmp_path.resolve() in p.resolve().parents
    assert (tmp_path / "evil_cover.png").exists()  # no traversal, no stray runs


def test_prefs_roundtrip_and_corrupt(tmp_path: Path):
    from app.export_prefs import ExportPrefs, load_prefs, save_prefs

    f = tmp_path / "p.json"
    assert load_prefs(f).base == "trakkart_cover"  # no file: defaults
    save_prefs(ExportPrefs(base="mibase", out_dir=str(tmp_path), gif_frames=4), f)
    assert load_prefs(f).base == "mibase"
    assert load_prefs(f).gif_frames == 4
    f.write_text("{roto", encoding="utf-8")
    assert load_prefs(f).base == "trakkart_cover"  # corrupt: defaults


def test_export_dialog_defaults_off_and_persists(window, qt_app, tmp_path):
    # Fresh start: no output checked (the user must pick). Ticked boxes
    # persist through prefs (dialog + quick) including webp/sep/sp404/mp4.
    from app.export_prefs import ExportPrefs, load_prefs, save_prefs
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"}, base="d", out_dir=str(tmp_path))
    try:
        for chk in (dlg.chk_image, dlg.chk_thumb, dlg.chk_vector, dlg.chk_anim,
                    dlg.chk_webp, dlg.chk_sep, dlg.chk_meta, dlg.chk_mp4,
                    dlg.chk_sp404):
            assert chk.isChecked() is False
        assert dlg.btn_export.isEnabled() is False  # nothing to write
        dlg.chk_image.setChecked(True)
        dlg.chk_sp404.setChecked(True)
        assert dlg.btn_export.isEnabled() is True
        gopts = dlg._gif_opts()
        assert gopts["sp404"] is True and gopts["webp"] is False
    finally:
        close_dialog(dlg)
    prefs = ExportPrefs(out_dir=str(tmp_path), image=True, sp404=True,
                        webp=True, sep=True, mp4=True)
    save_prefs(prefs, tmp_path / "p.json")
    back = load_prefs(tmp_path / "p.json")
    assert (back.image, back.webp, back.sep, back.sp404, back.mp4) == (True,) * 5
    assert (back.thumb_1080p, back.vector, back.anim, back.metadata) == (False,) * 4
    fresh = load_prefs(tmp_path / "nope.json")
    assert not any(getattr(fresh, k) for k in
                   ("image", "thumb_1080p", "vector", "anim", "metadata",
                    "webp", "sep", "sp404", "mp4"))


def test_export_dialog_plan_and_options(qt_app):
    from app.exporter import ExportSelection
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"}, base="d",
                       out_dir="/tmp", selection=ExportSelection(vector=True))
    assert dlg.chk_vector.isChecked()  # the dialog is in charge, always enabled
    assert dlg.chk_vector.isEnabled()
    assert dlg.btn_export.isEnabled()
    n0 = dlg.list_files.count()
    assert n0 > 0
    dlg.chk_thumb.setChecked(True)  # defaults are all off: ticking adds a line
    assert dlg.list_files.count() == n0 + 1
    opts, out, gopts = dlg.options()
    assert opts.base == "d" and out == Path("/tmp")
    assert opts.selection.thumb_1080p is True
    assert (gopts["frames"], gopts["mode"]) == (6, "both")
    assert (gopts["fps"], gopts["size"], gopts["pingpong"]) == (8, 3000, False)
    # size + format travel in the options
    dlg2 = ExportDialog(_img(), {"ratio": "1:1"}, size=1920, format="jpg", quality=80)
    o2, _, _ = dlg2.options()
    assert (o2.size, o2.format, o2.quality) == (1920, "jpg", 80)
    close_dialog(dlg2)
    close_dialog(dlg)


def test_export_dialog_size_and_format(qt_app):
    # Single doc: the size comes from CANVAS, the dialog only shows it.
    from app.exporter import ExportSelection, plan_export
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"}, size=1920, format="jpg", quality=80,
                       selection=ExportSelection(image=True))
    assert not hasattr(dlg, "cmb_size") and not hasattr(dlg, "spn_size")
    assert dlg.cmb_format.currentText() == "jpg"
    assert "1920×1920" in dlg.lbl_dims.text()  # ratio 1:1, doc 1920
    opts, _, _ = dlg.options()
    assert (opts.size, opts.format, opts.quality) == (1920, "jpg", 80)
    names = [f for _, f, _ in plan_export(_img(), opts, meta={"ratio": "1:1"})]
    assert names[0].endswith(".jpg")
    close_dialog(dlg)


def test_quick_never_overwrites_repeats_rename(window, qt_app):
    # Neither quick nor the dialog overwrite: repeating creates _2 (even if prefs say overwrite).
    from app.export_prefs import ExportPrefs, save_prefs

    save_prefs(ExportPrefs(out_dir=str(window.out_dir), base="req",
                           image=True, thumb_1080p=False, metadata=False,
                           overwrite="overwrite", src_name="trakkart_cover"),
               window._prefs_path)
    window.refresh()
    window.export(quick=True)
    window.export(quick=True)
    assert (window.out_dir / "req.png").exists()
    assert (window.out_dir / "req_2.png").exists()


def test_dialog_reports_rename_and_keeps_policy_label(qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"}, base="d")
    try:
        assert not hasattr(dlg, "cmb_overwrite")
        assert "name_2" in dlg.lbl_policy.text()
        opts, _, _ = dlg.options()
        assert opts.overwrite == "rename"
    finally:
        close_dialog(dlg)


def _fake_collision_box(choice):
    """Fake QMessageBox: choice is 'overwrite', 'rename' or 'cancel'."""
    over, rename = object(), object()

    class FakeMsg:
        class Icon:
            Warning = 0

        class StandardButton:
            Cancel = 0

        class ButtonRole:
            DestructiveRole = 0
            ActionRole = 1

        def __init__(self, *a, **k):
            pass

        def addButton(self, label, role):
            return over if "Overwrite" in str(label) else rename

        def setDefaultButton(self, b):
            pass

        def exec(self):
            return 0

        def clickedButton(self):
            return {"overwrite": over, "rename": rename}.get(choice)

    return FakeMsg


class _NoBox:
    """QMessageBox that crashes if instantiated (no dialog without a collision)."""

    def __init__(self, *a, **k):
        raise AssertionError("no dialog expected without collision")


def test_resolve_collision_branches(tmp_path, qt_app, monkeypatch):
    import app.ui.export_flow as _ef
    from app.exporter import ExportOptions, ExportSelection

    opts = ExportOptions(base="c", selection=ExportSelection(
        image=True, thumb_1080p=False, vector=False, anim=False, metadata=False))
    # No collision: rename without asking.
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox", _NoBox)
    assert _ef.resolve_collision(None, tmp_path, opts) == "rename"
    (tmp_path / "c.png").write_bytes(b"x")
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox",
                        _fake_collision_box("rename"))
    assert _ef.resolve_collision(None, tmp_path, opts) == "rename"
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox",
                        _fake_collision_box("overwrite"))
    assert _ef.resolve_collision(None, tmp_path, opts) == "overwrite"
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox",
                        _fake_collision_box("cancel"))
    assert _ef.resolve_collision(None, tmp_path, opts) is None


def test_collision_rename_writes_suffixed(window, qt_app, monkeypatch):
    import app.ui.export_flow as _ef
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    (window.out_dir / "dupe.png").write_bytes(b"old")
    monkeypatch.setattr(_ef, "resolve_collision", lambda *a, **k: "rename")
    accept_next_dialog(ExportDialog, lambda dlg: dlg.chk_image.setChecked(True))
    window.src_name = "dupe"
    window.export()
    assert (window.out_dir / "dupe.png").read_bytes() == b"old"
    assert (window.out_dir / "dupe_2.png").exists()


def test_collision_overwrite_replaces(window, qt_app, monkeypatch):
    import app.ui.export_flow as _ef
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    (window.out_dir / "dupe.png").write_bytes(b"old")
    monkeypatch.setattr(_ef, "resolve_collision", lambda *a, **k: "overwrite")
    accept_next_dialog(ExportDialog, lambda dlg: dlg.chk_image.setChecked(True))
    window.src_name = "dupe"
    window.export()
    assert (window.out_dir / "dupe.png").read_bytes() != b"old"
    assert not (window.out_dir / "dupe_2.png").exists()


def test_collision_cancel_aborts(window, qt_app, monkeypatch):
    import app.ui.export_flow as _ef
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    monkeypatch.setattr(_ef, "resolve_collision", lambda *a, **k: None)
    accept_next_dialog(ExportDialog)
    window.src_name = "fresh"
    window.export()
    assert "cancelled" in window.lbl_status.text().lower()
    assert not (window.out_dir / "fresh.png").exists()


def test_plan_warns_about_existing(qt_app, tmp_path):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    (tmp_path / "w.png").write_text("old")
    from app.exporter import ExportSelection

    dlg = ExportDialog(_img(), {"ratio": "1:1"}, base="w", out_dir=str(tmp_path),
                       selection=ExportSelection(image=True))
    try:
        assert "you'll be asked" in dlg.lbl_exists.text()
        dlg.edit_base.setText("free")
        assert dlg.lbl_exists.text() == ""
    finally:
        close_dialog(dlg)


def test_quick_export_headless(window, qt_app):
    from app.export_prefs import ExportPrefs, save_prefs

    save_prefs(ExportPrefs(out_dir=str(window.out_dir), base="quick",
                           image=True, thumb_1080p=False,
                           metadata=True), window._prefs_path)
    window.refresh()
    window.export(quick=True)  # does not ask: repeats prefs
    assert (window.out_dir / "quick.png").exists()
    assert (window.out_dir / "quick_metadata.json").exists()
    assert not (window.out_dir / "quick_thumb1080p.png").exists()


def test_export_dialog_e2e_defaults(window, qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    window.refresh()
    accept_next_dialog(ExportDialog, lambda dlg: dlg.chk_image.setChecked(True))
    window.export()
    assert (window.out_dir / "trakkart_cover.png").exists()
    assert not (window.out_dir / "trakkart_cover_metadata.json").exists()


def test_stale_prefs_yield_fresh_name(window, qt_app):
    # Prefs from another image: the dialog proposes the current src, not the old one.
    from app.export_prefs import ExportPrefs, save_prefs
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    save_prefs(ExportPrefs(out_dir=str(window.out_dir), base="oldname",
                           src_name="otherpic"), window._prefs_path)
    window.src_name = "newpic"
    seen = {}

    def _seen(dlg):
        seen.setdefault("base", dlg.edit_base.text())
        dlg.chk_image.setChecked(True)

    accept_next_dialog(ExportDialog, setup=_seen)
    window.export()
    assert seen.get("base") == "newpic"
    assert (window.out_dir / "newpic.png").exists()
    assert not (window.out_dir / "oldname.png").exists()


def test_quick_with_new_image_opens_dialog(window, qt_app):
    # Quick never silently writes with the stale name: it opens a dialog.
    from app.export_prefs import ExportPrefs, save_prefs
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    save_prefs(ExportPrefs(out_dir=str(window.out_dir), base="oldname",
                           src_name="otherpic"), window._prefs_path)
    window.src_name = "newpic"
    accept_next_dialog(ExportDialog, lambda dlg: dlg.chk_image.setChecked(True))
    window.export(quick=True)
    assert (window.out_dir / "newpic.png").exists()
    assert not (window.out_dir / "oldname.png").exists()


def test_paste_gets_own_name(window, qt_app):
    import re

    from PIL import Image as _Img

    from app.ui.image_flow import load_pil

    load_pil(window, _Img.new("RGB", (32, 32), (9, 9, 9)))
    assert re.fullmatch(r"pasted_\d{8}_\d{6}", window.src_name), window.src_name


def test_video_on_prechecks_anim_in_dialog(window, qt_app):
    # VIDEO preview ON => Animation GIF pre-checked (uncheckable, ~MB visible).
    # Covers both init paths: without prefs (from preset) and with prefs.
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    window.refresh()
    seen = {}

    def _setup(dlg):
        seen.setdefault("off" if "off" not in seen else "on", dlg.chk_anim.isChecked())
        dlg.chk_anim.setChecked(False)  # do not write GIF: only the default matters

    window._video_on = False
    accept_next_dialog(ExportDialog, setup=_setup)
    window.export()
    window._video_on = True
    accept_next_dialog(ExportDialog, setup=_setup)
    window.export()
    assert seen == {"off": False, "on": True}, seen


def _make_fake_box(clicked_name):
    """Fake QMessageBox without modal: clicked_name is 'show' or 'close'."""
    show_btn, close_btn = object(), object()

    class FakeMsg:
        class Icon:
            Information = 0

        class StandardButton:
            Close = 0

        class ButtonRole:
            ActionRole = 0

        _buttons = {"show": show_btn, "close": close_btn}

        def __init__(self, *a, **k):
            pass

        def addButton(self, label, role):
            return self._buttons["show"]

        def exec(self):
            return 0

        def clickedButton(self):
            return self._buttons[clicked_name]

    return FakeMsg


def test_show_exported_opens_folder_only_on_click(tmp_path, qt_app, monkeypatch):
    # The post-export dialog opens the folder only with "Show in folder".
    import app.ui.export_flow as _ef

    opened = {}
    monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl",
                        lambda url: opened.setdefault("url", str(url)))
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox", _make_fake_box("show"))
    _ef.show_exported(None, tmp_path, ["a.png"])
    assert "url" in opened
    opened.clear()
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox", _make_fake_box("close"))
    _ef.show_exported(None, tmp_path, ["a.png"])
    assert opened == {}


def test_mp4_shares_anim_stem(qt_app):
    from app.exporter import MP4_SUFFIX, mp4_name, sanitize_base

    assert mp4_name("shot") == "shot_vid.mp4"
    assert MP4_SUFFIX == "_vid.mp4"
    assert mp4_name(sanitize_base("mi cover!")) == "mi_cover_vid.mp4"


def test_file_name_section_previews_and_resets(qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"}, base="srcname")
    try:
        assert "srcname" in dlg.lbl_basename.text()
        dlg.edit_base.setText("mi cover!")
        assert dlg.lbl_basename.text().endswith("mi_cover")
        dlg.edit_base.setText("otra")
        dlg.btn_name_reset.click()
        assert dlg.edit_base.text() == "srcname"
    finally:
        close_dialog(dlg)


def test_gif_opts_come_from_video(window, qt_app):
    # No duplicates: export does not edit animation, only on/off; the spec is VIDEO's.
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    preset = window.current_params()
    dlg = ExportDialog(window.src, preset.meta(), preset=preset,
                       gif_frames=2, gif_mode="mix", gif_fps=12, gif_pingpong=True)
    for gone in ("spn_gframes", "cmb_gifmode", "spn_gfps", "spn_gsize",
                 "chk_pingpong", "lbl_gifprev"):
        assert not hasattr(dlg, gone)
    assert "mix" in dlg.lbl_gifspec.text() and "VIDEO" in dlg.lbl_gifspec.text()
    opts, _, gopts = dlg.options()
    assert (gopts["frames"], gopts["mode"]) == (2, "mix")
    assert (gopts["fps"], gopts["size"], gopts["pingpong"]) == (12, opts.size, True)
    close_dialog(dlg)


def test_gif_dialog_without_preset(qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"})  # no preset: still no preview
    dlg.chk_anim.setChecked(True)  # does not crash
    assert not hasattr(dlg, "lbl_gifprev")
    close_dialog(dlg)


def test_batch_dialog_validation(tmp_path: Path, qt_app):
    from app.ui.batch_dialog import BatchDialog, count_images
    from tests.conftest import close_dialog

    src = tmp_path / "in"
    src.mkdir()
    assert count_images(src) == 0
    assert count_images(tmp_path / "nope") == 0
    dlg = BatchDialog(in_dir=str(src), out_dir="", jobs=3)
    assert not dlg.btn_run.isEnabled()  # no out or images
    from PIL import Image

    Image.new("RGB", (16, 16)).save(src / "a.png")
    assert count_images(src) == 1
    dlg2 = BatchDialog(in_dir=str(src), out_dir=str(tmp_path / "out"), jobs=9)
    assert dlg2.btn_run.isEnabled()
    assert dlg2.spn_jobs.value() == 8  # clamp 1-8
    dlg2.accept()
    in_p, out_p, jobs = dlg2.paths()
    assert (in_p, jobs) == (src, 8)
    close_dialog(dlg2)
    close_dialog(dlg)


def test_batch_dialog_outputs(qt_app, tmp_path: Path):
    from PIL import Image

    from app.ui.batch_dialog import BatchDialog
    from tests.conftest import close_dialog

    src = tmp_path / "in"
    src.mkdir()
    Image.new("RGB", (32, 32)).save(src / "a.png")
    dlg = BatchDialog(in_dir=str(src), out_dir=str(tmp_path / "o"), jobs=2,
                      vector_export=True, vector_cell=12,
                      gif_export=True, gif_frames=4, gif_mode="hue",
                      canvas_size=(64, 64), doc_w=1920, doc_h=1080,
                      format="webp", quality=75)
    assert dlg.btn_run.isEnabled()
    assert "1920×1080" in dlg.lbl_doc.text()
    assert dlg.output_options() == {"vector_export": True, "vector_cell": 12,
                                    "vector_black": False,
                                    "gif_export": True, "gif_frames": 4,
                                    "gif_mode": "hue", "gif_fps": 8,
                                    "gif_size": 1920, "gif_pingpong": False,
                                    "canvas_w": 1920, "canvas_h": 1080,
                                    "export_size": 1920, "export_format": "webp",
                                    "export_quality": 75,
                                    "seed_mode": "off"}
    for gone in ("spn_gframes", "cmb_gifmode", "spn_gfps", "spn_gsize",
                 "chk_pingpong", "spn_size", "cmb_size"):
        assert not hasattr(dlg, gone)
    assert "cells" in dlg.lbl_vec_est.text()  # estimate with the current canvas
    dlg2 = BatchDialog(in_dir=str(src), out_dir=str(tmp_path / "o"))
    assert dlg2.lbl_vec_est.text() == ""  # no canvas: no estimate
    dlg.accept()
    assert dlg.result() == dlg.DialogCode.Accepted
    close_dialog(dlg)
    close_dialog(dlg2)


def test_batch_sync_honors_memory_vector(window, tmp_path: Path):
    from PIL import Image

    src = tmp_path / "in"
    dst = tmp_path / "dst"
    src.mkdir()
    Image.new("RGB", (32, 32), (9, 9, 9)).save(src / "a.png")
    window._vector_export = True
    window._vector_cell = 8
    results = window.run_batch_sync(src, dst)
    assert results[0]["status"] == "ok"
    assert any(o.endswith("_vector.svg") for o in results[0]["outputs"])


def test_batch_progress_shows_fps_eta(window):
    window._batch_start = __import__("time").time() - 2.0
    window._on_batch_progress(1, 2, "a.png")
    txt = window.lbl_status.text()
    assert "1/2" in txt and "img/s" in txt and "ETA" in txt


def test_export_async_worker_writes_bundle(window, tmp_path, qt_app):
    import time

    from app.exporter import ExportSelection

    window._export_sync = False
    out = tmp_path / "async_out"
    out.mkdir()
    sel = ExportSelection(image=True, thumb_1080p=False, vector=False,
                          anim=False, metadata=True)
    window._run_export(base="async", out_dir=out, selection=sel,
                       gif_opts={"frames": 6, "mode": "both", "fps": 8,
                                 "size": 1200, "pingpong": False},
                       overwrite="rename", size=64, format="png",
                       quality=90, _sync=False)
    assert getattr(window, "_export_worker", None) is not None
    deadline = time.time() + 30.0
    while getattr(window, "_export_worker", None) is not None and time.time() < deadline:
        qt_app.processEvents()
        time.sleep(0.05)
        qt_app.processEvents()
    assert (out / "async.png").exists()
    assert "Exported" in window.lbl_status.text()
