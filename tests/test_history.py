"""History + portable paths tests."""

from pathlib import Path

from app.history import HistoryStore
from app.paths import get_data_dir, get_db_path, get_out_dir


def test_history_roundtrip(tmp_path: Path):
    s = HistoryStore(tmp_path / "h.db")
    rid = s.log_export("beat1", "SLIME_FS", {"method": "floyd"}, ["a.png", "b.png"])
    assert rid == 1
    rows = s.list_exports()
    assert len(rows) == 1
    assert rows[0]["base"] == "beat1"
    assert rows[0]["preset"] == "SLIME_FS"
    assert "floyd" in rows[0]["params_json"]
    s.close()


def test_history_limit(tmp_path: Path):
    s = HistoryStore(tmp_path / "h.db")
    for i in range(3):
        s.log_export(f"b{i}", "P", {}, [])
    assert len(s.list_exports(limit=2)) == 2
    s.close()


def test_paths_override_env(tmp_path: Path, monkeypatch):
    import os

    monkeypatch.setenv("TRAKKART_DATA_DIR", str(tmp_path / "custom"))
    assert get_data_dir() == tmp_path / "custom"
    assert get_db_path().name == "trakkart.db"
    assert get_out_dir().name == "out"
    assert os.path.isdir(tmp_path / "custom" / "out")


def test_batch_logs_history(tmp_path: Path):
    from PIL import Image

    from app.batch import batch_process
    from app.presets import Preset

    src = tmp_path / "in"
    dst = tmp_path / "out"
    src.mkdir()
    Image.new("RGB", (32, 32), (9, 9, 9)).save(src / "a.png")
    s = HistoryStore(tmp_path / "h.db")
    batch_process(src, dst, Preset(name="SLIME_FS", method="bayer4"), store=s)
    assert len(s.list_exports()) == 1
    s.close()
