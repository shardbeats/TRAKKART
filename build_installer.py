"""Build the TRAKKART installer (Inno Setup), separately from the portable exe.

Portable:  python build_exe.py [--full]
Installer: python build_installer.py [--full]   (needs dist/*.exe + ISCC)

Reads the version from app.__version__ and signs the setup when TRAKKART_PFX
is set (same vars as build_exe.py, see installer/SIGNING.md).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _which_in(candidate: str) -> str | None:
    return candidate if Path(candidate).is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true",
                    help="package dist/TRAKKART-full.exe instead of the light exe")
    ap.add_argument("--skip-sign", action="store_true",
                    help="do not sign the setup even if TRAKKART_PFX is set")
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    from app import __version__

    exe_name = "TRAKKART-full.exe" if args.full else "TRAKKART.exe"
    suffix = "-full" if args.full else ""
    exe = ROOT / "dist" / exe_name
    if not exe.is_file():
        flavor = "--full " if args.full else ""
        print(f"[installer] missing {exe} — run `python build_exe.py {flavor}--skip-tests` first.")
        return 2
    iss = ROOT / "installer" / "trakkart.iss"
    iscc = (
        shutil.which("ISCC")
        or shutil.which("iscc")
        # Default Inno Setup 6 locations (not always on PATH).
        or _which_in(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
        or _which_in(r"C:\Program Files\Inno Setup 6\ISCC.exe")
    )
    defines = [f"/DMyVersion={__version__}", f"/DMySuffix={suffix}", f"/DMyExe={exe_name}"]
    if iscc is None:
        print("[installer] ISCC not found (install Inno Setup 6).")
        print(f"[installer] then run: ISCC {' '.join(defines)} {iss}")
        return 3
    print("+", iscc, *defines, str(iss))
    subprocess.check_call([iscc, *defines, str(iss)])
    setup = ROOT / "dist" / f"TRAKKART-Setup{suffix}-{__version__}.exe"
    if not setup.is_file():
        print("[installer] done (setup not found?).")
        return 0
    print(f"[installer] {setup.name} ready.")
    if not args.skip_sign:
        from build_exe import maybe_sign

        maybe_sign(setup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
