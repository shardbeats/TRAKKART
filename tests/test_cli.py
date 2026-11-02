"""Headless CLI (R10): contract, exit codes, Qt-free dispatch."""

import subprocess
import sys

from PIL import Image


def _img(path, w=96, h=64):
    im = Image.new("RGB", (w, h), (200, 60, 40))
    im.save(path)
    return path


def test_cli_single_ok_and_skipped(tmp_path, capsys):
    from app.cli import run_cli

    src = _img(tmp_path / "cover.png")
    out = tmp_path / "o"
    assert run_cli(["--preset", "SLIME_FS", "--in", str(src), "--out", str(out)]) == 0
    assert (out / "cover.png").exists() and (out / "cover_metadata.json").exists()
    capsys.readouterr()
    assert run_cli(["--preset", "SLIME_FS", "--in", str(src), "--out", str(out)]) == 0
    assert "skipped" in capsys.readouterr().out


def test_cli_folder_and_errors(tmp_path, capsys):
    from app.cli import run_cli

    src = tmp_path / "in_"
    src.mkdir()
    _img(src / "a.png")
    _img(src / "b.jpg")
    (src / "notes.txt").write_text("nope", encoding="utf-8")
    out = tmp_path / "o"
    assert run_cli(["--preset", "SLIME_FS", "--in", str(src), "--out", str(out)]) == 0
    assert (out / "a.png").exists() and (out / "b.png").exists()  # stem + preset format
    assert run_cli(["--preset", "NOPE", "--in", str(src), "--out", str(out)]) == 2
    assert run_cli(["--preset", "SLIME_FS", "--in", str(src / "missing.png"),
                    "--out", str(out)]) == 2
    assert run_cli(["--preset", "SLIME_FS", "--in", str(src / "notes.txt"),
                    "--out", str(out)]) == 2
    assert run_cli(["--preset", "SLIME_FS", "--in", str(src)]) == 2  # --out required


def test_cli_list_presets(capsys):
    from app.cli import run_cli

    assert run_cli(["--list-presets"]) == 0
    assert "SLIME_FS" in capsys.readouterr().out


def test_cli_dispatch_without_qt():
    # Fresh interpreter: --cli must never import PySide6 (fast, display-free).
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    code = ("import sys; sys.argv=['main.py', '--cli', '--list-presets']; "
            "sys.path.insert(0, '.'); import main; rc = main.main(); "
            "assert 'PySide6' not in sys.modules, 'Qt leaked into CLI'; "
            "assert rc == 0")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=str(root))
    assert r.returncode == 0, r.stderr
    assert "SLIME_FS" in r.stdout
