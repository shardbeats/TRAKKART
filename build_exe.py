"""Build portable TRAKKART.exe (PyInstaller windowed one-file, all included).

Single flavor since v1: numba acceleration + MP4 video ship inside.
Embeds version metadata + MANUAL/icons, optional Authenticode signing
via env (TRAKKART_PFX path to .pfx, TRAKKART_PFX_PASSWORD,
optional TRAKKART_TIMESTAMP_URL). See installer/SIGNING.md.

Test gate (industry standard: test job blocks the build, but the gate must
stay fast or developers bypass it):
  default          fast gate: pytest -q -n auto -m "not slow" (parallel,
                   excludes slow; ~2-4 min). Requires pytest-xdist
                   (requirements-dev.txt); falls back to serial fast gate.
  --full-tests     full serial suite gate (final release; 30-60+ min).
  --skip-tests     skip gate (only if HEAD was already validated green,
                   e.g. same commit passed full suite in CI/dev).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def app_version() -> str:
    sys.path.insert(0, str(ROOT))
    from app import __version__

    return str(__version__)


def write_version_info(version: str, exe_name: str = "TRAKKART.exe") -> Path:
    """VSVersionInfo so Explorer shows Product/File version (no more 0.0.0.0)."""
    nums = (version.split("-")[0].split(".") + ["0", "0", "0"])[:4]
    major, minor, patch, build = (int(n) if str(n).isdigit() else 0 for n in nums)
    out = ROOT / "build" / "version_info.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(filevers=(%d, %d, %d, %d), prodvers=(%d, %d, %d, %d),\n"
        "    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),\n"
        "  kids=[StringFileInfo([StringTable('040904B0', [\n"
        "    StringStruct('CompanyName', 'ShardBeats'),\n"
        "    StringStruct('FileDescription', 'TRAKKART - offline cover art studio'),\n"
        "    StringStruct('FileVersion', '%s'),\n"
        "    StringStruct('InternalName', '%s'),\n"
        "    StringStruct('LegalCopyright', 'MIT'),\n"
        "    StringStruct('OriginalFilename', '%s'),\n"
        "    StringStruct('ProductName', 'TRAKKART'),\n"
        "    StringStruct('ProductVersion', '%s')])]),\n"
        "  VarFileInfo([VarStruct('Translation', [1033, 1200])])]\n"
        ")\n" % (major, minor, patch, build, major, minor, patch, build, version,
                 exe_name.rsplit(".", 1)[0], exe_name, version),
        encoding="utf-8",
    )
    return out


def maybe_sign(exe: Path) -> None:
    """Sign with signtool if TRAKKART_PFX is set; warn (don't fail) otherwise."""
    pfx = os.environ.get("TRAKKART_PFX", "").strip()
    if not pfx:
        print("[TRAKKART] unsigned build (set TRAKKART_PFX to sign, see installer/SIGNING.md).")
        return
    pwd = os.environ.get("TRAKKART_PFX_PASSWORD", "")
    ts = os.environ.get("TRAKKART_TIMESTAMP_URL", "http://timestamp.digicert.com").strip()
    cmd = ["signtool", "sign", "/fd", "SHA256", "/f", pfx, "/tr", ts, "/td", "SHA256"]
    if pwd:
        cmd += ["/p", pwd]
    cmd.append(str(exe))
    try:
        run(cmd)
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"[TRAKKART] WARNING: signing failed ({e}). Ship unsigned or fix signtool/PFX.")


def _has_xdist(py: str) -> bool:
    """True if the build interpreter can run pytest -n auto."""
    import subprocess

    try:
        r = subprocess.run([py, "-c", "import xdist"],
                           capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    gate = ap.add_mutually_exclusive_group()
    gate.add_argument("--skip-tests", action="store_true",
                      help="skip test gate (only if this HEAD already validated green)")
    gate.add_argument("--full-tests", action="store_true",
                      help="full serial suite gate for final release (slow, 30-60+ min)")
    ap.add_argument("--console", action="store_true")
    args = ap.parse_args()

    py = sys.executable
    if args.full_tests:
        run([py, "-m", "pytest", "tests", "-q"])
    elif not args.skip_tests:
        cmd = [py, "-m", "pytest", "tests", "-q", "-m", "not slow"]
        if _has_xdist(py):
            cmd += ["-n", "auto"]
        else:
            print("[TRAKKART] pytest-xdist missing: fast gate runs serial "
                  "(pip install -r requirements-dev.txt for parallel).")
        run(cmd)
    else:
        print("[TRAKKART] test gate skipped (--skip-tests). "
              "Only safe if this HEAD already passed the suite.")
    run([py, "-m", "pip", "install", "pyinstaller"])
    exe_name = "TRAKKART"
    run([py, "-m", "pip", "install", "-r", "requirements.txt"])
    cmd = [
        py, "-m", "PyInstaller",
        "--noconfirm", "--name", exe_name, "--onefile",
        *(["--console"] if args.console else ["--windowed"]),
        # Everything ships inside (numba + imageio-ffmpeg).
        # copy-metadata: imageio reads its own version via importlib.metadata
        # AT IMPORT TIME; without dist-info the frozen import raises
        # PackageNotFoundError (an ImportError) and has_video() goes False.
        "--copy-metadata", "imageio",
        "--copy-metadata", "imageio-ffmpeg",
        "--copy-metadata", "numba",
        "--copy-metadata", "llvmlite",
        "--version-file", str(write_version_info(app_version(), f"{exe_name}.exe")),
        "main.py",
    ]
    # Bundled at runtime via app.paths.bundle_path (frozen _MEIPASS / dev root).
    for name in ("MANUAL.md", "LICENSE", "NOTICE.md", "THIRD-PARTY-NOTICES.md",
                 "icon.png", "icon.ico", "app/ui/theme.qss"):
        p = ROOT / name
        if p.exists():
            cmd[cmd.index("main.py"):cmd.index("main.py")] = ["--add-data", f"{p}{os.pathsep}."]
    icon = ROOT / "icon.ico"
    if icon.exists():
        cmd[cmd.index("main.py"):cmd.index("main.py")] = ["--icon", str(icon)]
    run(cmd)
    maybe_sign(ROOT / "dist" / f"{exe_name}.exe")
    print(f"[TRAKKART] dist/{exe_name}.exe ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
