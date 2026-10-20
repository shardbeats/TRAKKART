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
    assert keys == ["image", "thumb_1080p", "vector", "anim", "metadata"]
    names = [f for _, f, _ in plan]
    assert names[0] == "mix.png"  # la imagen manda: nombre + extensión
    assert all(f.startswith("mix") for f in names)
    assert all(est > 0 for _, _, est in plan)


def test_plan_skips_unavailable():
    from app.exporter import ExportOptions, ExportSelection, plan_export

    opts = ExportOptions(base="b", selection=ExportSelection(vector=True, anim=True))
    keys = [k for k, _, _ in plan_export(_img(), opts, has_vector=False, has_gif=False)]
    assert "vector" not in keys and "anim" not in keys


def test_plan_jpg_uses_extension_and_size():
    from PIL import Image

    from app.exporter import ExportOptions, plan_export

    img = Image.new("RGB", (400, 200), (9, 9, 9))
    opts = ExportOptions(base="j", size=400, format="jpg", quality=80)
    plan = dict((k, (f, e)) for k, f, e in plan_export(img, opts, meta={"ratio": "2:1"}))
    assert plan["image"][0] == "j.jpg"
    assert plan["thumb_1080p"][0] == "j_thumb1080p.jpg"  # mismo formato
    # el thumb siempre es 1920x1080


def test_with_options_subset_and_rename(tmp_path: Path):
    from app.exporter import ExportOptions, ExportSelection, export_with_options

    opts = ExportOptions(base="sel", selection=ExportSelection(
        image=True, thumb_1080p=False, metadata=True))
    paths, skipped = export_with_options(_img(), tmp_path, opts, meta={"ratio": "1:1"})
    assert set(paths) == {"image", "metadata"}
    assert paths["image"].suffix == ".png"
    assert skipped == []
    # rename: segunda vez con el mismo base no pisa
    paths2, _ = export_with_options(
        _img(), tmp_path, ExportOptions(base="sel", selection=opts.selection,
                                        overwrite="rename"))
    assert paths2["image"].name == "sel_2.png"
    assert (tmp_path / "sel.png").exists()  # el original intacto


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

    from app.exporter import ExportOptions, export_with_options

    img = Image.new("RGB", (64, 64), (90, 60, 140))
    for fmt, ext in (("png", "png"), ("jpg", "jpg"), ("webp", "webp")):
        opts = ExportOptions(base=f"f_{fmt}", format=fmt, quality=80)
        paths, _ = export_with_options(img, tmp_path, opts)
        assert paths["image"].suffix == f".{ext}"
        assert paths["image"].stat().st_size > 0
        with Image.open(paths["image"]) as im:
            im.load()  # fichero válido


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
    dlg.chk_thumb.setChecked(False)
    assert dlg.list_files.count() == n0 - 1
    opts, out, gopts = dlg.options()
    assert opts.base == "d" and out == Path("/tmp")
    assert opts.selection.thumb_1080p is False
    assert (gopts["frames"], gopts["mode"]) == (6, "both")
    assert (gopts["fps"], gopts["size"], gopts["pingpong"]) == (8, 3000, False)
    # tamaño + formato viajan en las opciones
    dlg2 = ExportDialog(_img(), {"ratio": "1:1"}, size=1920, format="jpg", quality=80)
    o2, _, _ = dlg2.options()
    assert (o2.size, o2.format, o2.quality) == (1920, "jpg", 80)
    close_dialog(dlg2)
    close_dialog(dlg)


def test_export_dialog_size_and_format(qt_app):
    # Doc único: el tamaño viene de CANVAS, el diálogo solo lo muestra.
    from app.exporter import plan_export
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import close_dialog

    dlg = ExportDialog(_img(), {"ratio": "1:1"}, size=1920, format="jpg", quality=80)
    assert not hasattr(dlg, "cmb_size") and not hasattr(dlg, "spn_size")
    assert dlg.cmb_format.currentText() == "jpg"
    assert "1920×1920" in dlg.lbl_dims.text()  # ratio 1:1, doc 1920
    opts, _, _ = dlg.options()
    assert (opts.size, opts.format, opts.quality) == (1920, "jpg", 80)
    names = [f for _, f, _ in plan_export(_img(), opts, meta={"ratio": "1:1"})]
    assert names[0].endswith(".jpg")
    close_dialog(dlg)


def test_quick_export_headless(window, qt_app):
    from app.export_prefs import ExportPrefs, save_prefs

    save_prefs(ExportPrefs(out_dir=str(window.out_dir), base="quick",
                           image=True, thumb_1080p=False,
                           metadata=True), window._prefs_path)
    window.refresh()
    window.export(quick=True)  # no pregunta: repite prefs
    assert (window.out_dir / "quick.png").exists()
    assert (window.out_dir / "quick_metadata.json").exists()
    assert not (window.out_dir / "quick_thumb1080p.png").exists()


def test_export_dialog_e2e_defaults(window, qt_app):
    from app.ui.export_dialog import ExportDialog
    from tests.conftest import accept_next_dialog

    window.refresh()
    accept_next_dialog(ExportDialog)
    window.export()
    assert (window.out_dir / "trakkart_cover.png").exists()
    assert (window.out_dir / "trakkart_cover_metadata.json").exists()


def test_gif_opts_come_from_video(window, qt_app):
    # Sin duplicados: el export no edita animación, solo on/off; la spec es la de VIDEO.
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

    dlg = ExportDialog(_img(), {"ratio": "1:1"})  # sin preset: sin preview igual
    dlg.chk_anim.setChecked(True)  # no revienta
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
                      canvas_size=(64, 64), size=1920, format="webp", quality=75)
    assert dlg.btn_run.isEnabled()
    assert dlg.output_options() == {"vector_export": True, "vector_cell": 12,
                                    "gif_export": True, "gif_frames": 4,
                                    "gif_mode": "hue", "gif_fps": 8,
                                    "gif_size": 1920, "gif_pingpong": False,
                                    "export_size": 1920, "export_format": "webp",
                                    "export_quality": 75}
    for gone in ("spn_gframes", "cmb_gifmode", "spn_gfps", "spn_gsize",
                 "chk_pingpong", "spn_size", "cmb_size"):
        assert not hasattr(dlg, gone)
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
