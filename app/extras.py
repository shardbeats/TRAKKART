"""Acceleration + video status (pure logic, no Qt).

Both ship inside the bundle. On a dev machine without the packages,
this module answers "what is installed?" and, via Settings → Extras,
pip-installs the missing pieces. Import errors are surfaced verbatim
so the Extras page shows WHY a backend is missing.
"""

from __future__ import annotations

import sys

ACCEL_PACKAGES = ("numba",)
VIDEO_PACKAGES = ("imageio", "imageio-ffmpeg")


def is_frozen() -> bool:
    """True inside the PyInstaller bundle (no pip install possible)."""
    return bool(getattr(sys, "frozen", False))


def accel_status() -> tuple[bool, str]:
    """(available, human detail) for the numba accelerator."""
    try:
        import numba  # noqa: F401
    except ImportError as e:
        return False, f"numpy fallback (numba not installed: {e})"
    except Exception as e:  # noqa: BLE001  (frozen surprises: DLLs, AV interference)
        return False, f"numpy fallback ({type(e).__name__}: {e})"
    try:
        ver = numba.__version__
    except Exception:  # noqa: BLE001
        ver = "unknown version"
    return True, f"numba {ver} (10-50x on large Floyd)"


def video_status() -> tuple[bool, str]:
    """(available, human detail) for MP4 export."""
    try:
        import imageio  # noqa: F401
        import imageio_ffmpeg  # noqa: F401
    except ImportError as e:
        return False, f"MP4 disabled (missing package: {e})"
    except Exception as e:  # noqa: BLE001  (frozen surprises: DLLs, AV interference)
        return False, f"MP4 disabled ({type(e).__name__}: {e})"
    return True, "MP4 available (imageio + ffmpeg)"


def missing_packages(kind: str) -> tuple[str, ...]:
    """Pip packages needed for `kind` ("accel" | "video")."""
    if kind == "accel":
        return ACCEL_PACKAGES
    if kind == "video":
        return VIDEO_PACKAGES
    raise ValueError(f"unknown extra: {kind}")


def pip_install_cmd(packages: tuple[str, ...] | list[str]) -> list[str]:
    """pip command for the current interpreter (dev only, never frozen)."""
    return [sys.executable, "-m", "pip", "install", *packages]


def run_pip_install(packages: tuple[str, ...] | list[str], timeout: int = 600) -> tuple[bool, str]:
    """Blocking pip install. Returns (ok, last log lines). Dialogs run it in a thread."""
    import subprocess

    try:
        proc = subprocess.run(
            pip_install_cmd(tuple(packages)),
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-5:])
    return proc.returncode == 0, tail or "(no output)"


__all__ = ["ACCEL_PACKAGES", "VIDEO_PACKAGES", "accel_status", "is_frozen",
           "missing_packages", "pip_install_cmd", "run_pip_install", "video_status"]
