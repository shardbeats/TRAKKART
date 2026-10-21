"""Batch tests: 3 temp images, skip_existing, errors."""

from pathlib import Path

from PIL import Image

from app.batch import batch_process
from app.presets import Preset


def _make_inputs(d: Path, n: int = 3) -> None:
    for i in range(n):
        Image.new("RGB", (48, 48), (30 * i + 40, 90, 140)).save(d / f"beat{i}.png")


def test_batch_three_images(tmp_path: Path):
    src = tmp_path / "in"
    dst = tmp_path / "out"
    src.mkdir()
    _make_inputs(src)
    seen: list[tuple[int, int, str]] = []
    results = batch_process(src, dst, Preset(name="t", method="bayer4", palette="SLIME"), progress_cb=lambda a, b, c: seen.append((a, b, c)))
    assert len(results) == 3
    assert all(r["status"] == "ok" for r in results)
    assert len(seen) == 3 and seen[-1][0] == 3
    for r in results:
        for o in r["outputs"]:
            assert Path(o).exists()


def test_batch_skip_existing(tmp_path: Path):
    src = tmp_path / "in"
    dst = tmp_path / "out"
    src.mkdir()
    _make_inputs(src, 1)
    preset = Preset(name="t", method="bayer4", palette="BW")
    batch_process(src, dst, preset)
    again = batch_process(src, dst, preset)
    assert again[0]["status"] == "skipped"


def test_batch_bad_input_dir(tmp_path: Path):
    import pytest

    with pytest.raises(NotADirectoryError):
        batch_process(tmp_path / "nodir", tmp_path / "o", Preset(name="t"))


def test_batch_with_vector(tmp_path: Path):
    src = tmp_path / "in"
    dst = tmp_path / "out"
    src.mkdir()
    _make_inputs(src, 1)
    preset = Preset(name="t", method="bayer4", palette="BW", vector_export=True, vector_cell=8)
    results = batch_process(src, dst, preset)
    assert results[0]["status"] == "ok"
    assert any(o.endswith("_vector.svg") for o in results[0]["outputs"])
    again = batch_process(src, dst, preset)
    assert again[0]["status"] == "skipped"


def test_batch_with_gif(tmp_path: Path):
    src = tmp_path / "in"
    dst = tmp_path / "out"
    src.mkdir()
    _make_inputs(src, 1)
    preset = Preset(name="t", method="bayer4", palette="BW", gif_export=True, gif_frames=2)
    results = batch_process(src, dst, preset)
    assert results[0]["status"] == "ok"
    assert any(o.endswith("_anim.gif") for o in results[0]["outputs"])
    again = batch_process(src, dst, preset)
    assert again[0]["status"] == "skipped"


def test_batch_skips_bad_file(tmp_path: Path):
    src = tmp_path / "in"
    dst = tmp_path / "out"
    src.mkdir()
    (src / "fake.png").write_bytes(b"this is not an image")
    Image.new("RGB", (32, 32), (10, 20, 30)).save(src / "ok.png")
    results = batch_process(src, dst, Preset(name="t", method="bayer4", palette="BW"))
    by_name = {r["file"]: r["status"] for r in results}
    assert by_name["fake.png"] == "error"
    assert by_name["ok.png"] == "ok"


def test_batch_jpg_small(tmp_path: Path):
    src = tmp_path / "in"
    dst = tmp_path / "dst"
    src.mkdir()
    _make_inputs(src, 1)
    preset = Preset(name="t", method="bayer4", palette="BW",
                    export_format="jpg", export_quality=80, export_size=64)
    results = batch_process(src, dst, preset)
    assert results[0]["status"] == "ok"
    assert any(o.endswith(".jpg") and Path(o).exists() for o in results[0]["outputs"])
    again = batch_process(src, dst, preset)
    assert again[0]["status"] == "skipped"


def test_batch_unit_helpers(tmp_path: Path):
    import json

    from app.batch import _outputs_for, _render_one, _sort_results, build_extras, options_from_preset, render_single_image

    preset = Preset(name="t", method="bayer4", palette="SLIME", vector_export=True,
                    gif_export=True, gif_frames=2, export_format="png", export_size=64)
    opts = options_from_preset(preset)
    assert opts.selection.vector is True and opts.selection.anim is True
    outs = _outputs_for(tmp_path, "b", preset)
    assert any(str(o).endswith((".png", ".jpg")) for o in outs)
    img = Image.new("RGB", (48, 48), (90, 100, 140))
    assert render_single_image(img, preset).size == (48, 48)
    svg, frames = build_extras(img, preset)
    assert svg is not None and svg.startswith("<svg")
    assert frames is not None and len(frames) == 2
    plain = Preset(name="t", method="bayer4", palette="BW")
    assert build_extras(img, plain) == (None, None)
    # _render_one error path (bad file) returns an error dict, never raises.
    bad = _render_one((str(tmp_path / "nope.png"), str(tmp_path), "b",
                       json.dumps(plain.to_dict())))
    assert bad["status"] == "error"
    # cancel flag aborts before processing anything.
    src = tmp_path / "in2"
    src.mkdir()
    _make_inputs(src, 2)
    results = batch_process(src, tmp_path / "o2", Preset(name="t", method="bayer4"),
                            cancel=[True])
    assert results == []
    by_name = [{"file": "b.png", "status": "ok"}, {"file": "a.png", "status": "ok"}]
    files = [tmp_path / "b.png", tmp_path / "a.png"]
    _sort_results(by_name, files)  # in place, like input order
    assert [r["file"] for r in by_name] == ["b.png", "a.png"]
