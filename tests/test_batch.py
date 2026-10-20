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
