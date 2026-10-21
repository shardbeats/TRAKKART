"""Build portable TRAKKART.exe (PyInstaller windowed one-file)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--console", action="store_true")
    args = ap.parse_args()

    py = sys.executable
    if not args.skip_tests:
        run([py, "-m", "pytest", "tests", "-q"])
    run([py, "-m", "pip", "install", "pyinstaller"])
    cmd = [
        py, "-m", "PyInstaller",
        "--noconfirm", "--name", "TRAKKART", "--onefile",
        *(["--console"] if args.console else ["--windowed"]),
        # Base exe stays light (ROADMAP §4): numba is an optional accelerator
        # with numpy fallback, imageio-ffmpeg is an opt-in extra. Exclude so
        # a dev .venv with them installed never leaks them into the bundle.
        "--exclude-module", "numba",
        "--exclude-module", "llvmlite",
        "--exclude-module", "imageio",
        "--exclude-module", "imageio_ffmpeg",
        "main.py",
    ]
    icon = ROOT / "icon.ico"
    if icon.exists():
        cmd[cmd.index("main.py"):cmd.index("main.py")] = ["--icon", str(icon)]
    run(cmd)
    print("[TRAKKART] dist/TRAKKART.exe ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
