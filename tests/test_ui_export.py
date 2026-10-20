"""Export profesional: plan, políticas, prefs, diálogos, quick (fixtures en conftest)."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def _img(w=64, h=64):
    from PIL import Image

    return Image.new("RGB", (w, h), (90, 60, 140))


def test_plan_lists_everything(tmp_path: Path):
    from app.exporter import ExportOptions, ExportSelection, plan_export

    opts = ExportOptions(base="mix", selection=ExportSelection(vector=True, anim=True))
    plan = plan_export(_img(), opts, meta={"ratio": "1:1"}, has_vector=True, has_gif=True,
                       extra={"vector_cells": (10, 10), "gif_frames": 4})
    keys = [k for k, _, _ in plan]
    assert keys == ["cover", "small", "thumb_1080p", "vector", "anim", "metadata"]
    assert all(f.startswith("mix") for _, f, _ in plan)
    assert all(est > 0 for _, _, est in plan)


def test_plan_skips_unavailable():
    from app.exporter import ExportOptions, ExportSelection, plan_export

    opts = ExportOptions(base="b", selection=ExportSelection(vector=True, anim=True))
    keys = [k for k, _, _ in plan_export(_img(), opts, has_vector=False, has_gif=False)]
    assert "vector" not in keys and "anim" not in keys


def test_with_options_subset_and_rename(tmp_path: Path):
    from app.exporter import ExportOptions, ExportSelection, export_with_options

    opts = ExportOptions(base="sel", selection=ExportSelection(
        cover=False, small=True, thumb_1080p=False, metadata=True))
    paths, skipped = export_with_options(_img(), tmp_path, opts, meta={"ratio": "1:1"})
    assert set(paths) == {"small", "metadata"}
    assert skipped == []
    # rename: segunda vez con el mismo base no pisa
    paths2, _ = export_with_options(
        _img(), tmp_path, ExportOptions(base="sel", selection=opts.selection,
                                        overwrite="rename"))
    assert paths2["small"].name == "sel_2_small.png"
    assert (tmp_path / "sel_small.png").exists()  # el original intacto


def test_skip_policy_returns_existing(tmp_path: Path):
    from app.exporter import ExportOptions, ExportSelection, export_with_options

    opts = ExportOptions(base="sk", selection=ExportSelection(
        cover=False, small=True, thumb_1080p=False, metadata=True),
        overwrite="skip")
    paths, skipped = export_with_options(_img(), tmp_path, opts)
    assert paths and skipped == []
    paths2, skipped2 = export_with_options(_img(), tmp_path, opts)
    assert paths2 == {} and set(skipped2) == {"small", "metadata"}


def test_base_sanitized(tmp_path: Path):
    from app.exporter import export_bundle

    paths = export_bundle(_img(), tmp_path, base="../../evil")
    for p in paths.values():
        assert tmp_path.resolve() in p.resolve().parents
    assert (tmp_path / "______evil_cover.png").exists()  # 6 chars -> 6 "_"


def test_prefs_roundtrip_and_corrupt(tmp_path: Path):
    from app.export_prefs import ExportPrefs, load_prefs, save_prefs

    f = tmp_path / "p.json"
    assert load_prefs(f).base == "trakkart_cover"  # sin fichero: defaults
    save_prefs(ExportPrefs(base="mibase", out_dir=str(tmp_path), gif_frames=4), f)
    assert load_prefs(f).base == "mibase"
    assert load_prefs(f).gif_frames == 4
    f.write_text("{roto", encoding="utf-8")
    assert load_prefs(f).base == "trakkart_cover"  # roto: defaults


def test_export_dialog_plan_and_options(qt_app):
    from app.exporter import ExportSelection
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"}, base="d",
                       out_dir="/tmp", selection=ExportSelection(vector=True))
    assert dlg.chk_vector.isChecked()  # el diálogo manda, siempre habilitado
    assert dlg.chk_vector.isEnabled()
    assert dlg.btn_export.isEnabled()
    n0 = dlg.list_files.count()
    assert n0 > 0
    dlg.chk_small.setChecked(False)
    assert dlg.list_files.count() == n0 - 1
    opts, out, gframes, gmode = dlg.options()
    assert opts.base == "d" and out == Path("/tmp")
    assert opts.selection.small is False
    assert (gframes, gmode) == (6, "both")
    close_dialog(dlg)


def test_quick_export_headless(window, qt_app):
    from app.export_prefs import ExportPrefs, save_prefs

    save_prefs(ExportPrefs(out_dir=str(window.out_dir), base="quick",
                           cover=True, small=False, thumb_1080p=False,
                           metadata=True), window._prefs_path)
    window.refresh()
    window.export(quick=True)  # no pregunta: repite prefs
    assert (window.out_dir / "quick_cover.png").exists()
    assert (window.out_dir / "quick_metadata.json").exists()
    assert not (window.out_dir / "quick_small.png").exists()


def test_export_dialog_e2e_defaults(window, qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    window.refresh()
    accept_next_dialog(ExportDialog)
    window.export()
    assert (window.out_dir / "trakkart_cover_cover.png").exists()
    assert (window.out_dir / "trakkart_cover_metadata.json").exists()


def test_gif_live_preview_plays(window, qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    preset = window.current_params()
    dlg = ExportDialog(window.src, preset.meta(), preset=preset)
    assert not dlg._gif_timer.isActive()
    assert dlg.lbl_gifprev.text() == "GIF preview off"
    dlg.spn_gframes.setValue(2)
    dlg.cmb_gifmode.setCurrentText("phase")
    dlg.chk_anim.setChecked(True)
    assert dlg._gif_timer.isActive()
    assert (2, "phase") in dlg._gif_cache
    assert len(dlg._gif_cache[(2, "phase")]) == 2
    assert dlg.lbl_gifprev.pixmap() is not None
    assert not dlg.lbl_gifprev.pixmap().isNull()
    first = dlg._gif_idx
    dlg._next_gif_frame()
    assert dlg._gif_idx == (first + 1) % 2
    dlg.spn_gframes.setValue(3)  # cambio invalida cache y regenera
    assert (3, "phase") in dlg._gif_cache
    dlg.chk_anim.setChecked(False)
    assert not dlg._gif_timer.isActive()
    close_dialog(dlg)


def test_gif_preview_without_preset(qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"})  # sin preset: sin preview
    dlg.chk_anim.setChecked(True)  # no revienta
    assert not dlg._gif_timer.isActive()
    assert dlg.lbl_gifprev.text() == "GIF preview off"
    close_dialog(dlg)


def test_batch_dialog_validation(tmp_path: Path, qt_app):
    from app.ui.batch_dialog import BatchDialog, count_images
    from tests.conftest import close_dialog

    src = tmp_path / "in"
    src.mkdir()
    assert count_images(src) == 0
    assert count_images(tmp_path / "nope") == 0
    dlg = BatchDialog(in_dir=str(src), out_dir="", jobs=3)
    assert not dlg.btn_run.isEnabled()  # sin out ni imágenes
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
                      canvas_size=(64, 64))
    assert dlg.btn_run.isEnabled()
    assert dlg.output_options() == {"vector_export": True, "vector_cell": 12,
                                    "gif_export": True, "gif_frames": 4,
                                    "gif_mode": "hue"}
    assert "cells" in dlg.lbl_vec_est.text()  # estimación con el canvas actual
    dlg2 = BatchDialog(in_dir=str(src), out_dir=str(tmp_path / "o"))
    assert dlg2.lbl_vec_est.text() == ""  # sin canvas: sin estimación
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
