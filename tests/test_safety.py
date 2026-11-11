"""Safety/stability tests: limits, cancel, prune, debounce."""

import pytest
from PIL import Image

from app.safety import MAX_VECTOR_CELLS, TooBigError, check_image, check_path, check_vector_cells


def _img(w: int = 64, h: int = 64) -> Image.Image:
    return Image.new("RGB", (w, h), (10, 20, 30))


def test_check_image_ok():
    check_image(_img())  # does not raise


def test_check_image_side_limit():
    with pytest.raises(TooBigError):
        check_image(Image.new("RGB", (9000, 10)))


def test_check_image_mp_limit(monkeypatch):
    import app.safety as S

    monkeypatch.setattr(S, "MAX_MP", 0)
    with pytest.raises(TooBigError):
        check_image(_img())


def test_check_path_valid_and_invalid(tmp_path):
    p = tmp_path / "ok.png"
    _img().save(p)
    assert check_path(p) == (64, 64)
    bad = tmp_path / "x.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(ValueError):
        check_path(bad)


def test_check_vector_cells_cap():
    check_vector_cells(100, 100)
    with pytest.raises(TooBigError):
        check_vector_cells(750, 750)
    assert 750 * 750 > MAX_VECTOR_CELLS


def test_vector_bundle_blocks_huge():
    from app.presets import Preset
    from app.vector import vector_bundle

    big = Image.new("RGB", (2000, 2000), (1, 2, 3))
    p = Preset(name="v", vector_cell=4)
    with pytest.raises(TooBigError):
        vector_bundle(big, p)


def test_batch_cancel_before_start(tmp_path):
    from app.batch import batch_process
    from app.presets import Preset

    src = tmp_path / "in"
    src.mkdir()
    _img(32, 32).save(src / "a.png")
    _img(32, 32).save(src / "b.png")
    out = batch_process(src, tmp_path / "o", Preset(name="t"), cancel=[True])
    assert out == []


def test_history_prune(tmp_path):
    import sqlite3

    from app.history import SCHEMA, HistoryStore

    # Seed 500 rows in ONE transaction (fsync-bound disks feel every
    # commit; the point under test is the cap, not 505 slow inserts).
    db = tmp_path / "h.db"
    conn = sqlite3.connect(str(db))
    conn.execute(SCHEMA)
    conn.executemany(
        "INSERT INTO exports (base, preset, params_json, files_json, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [(f"b{i}", "P", "{}", "[]", "2026-01-01T00:00:00+00:00") for i in range(500)],
    )
    conn.commit()
    conn.close()
    s = HistoryStore(db)
    for i in range(5):
        s.log_export(f"c{i}", "P", {}, [])
    assert len(s.list_exports(limit=1000)) == 500
    s.close()
