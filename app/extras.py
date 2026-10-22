"""Acceleration + video status (pure logic, no Qt).

The shipped bundle includes both (numba + imageio-ffmpeg). On a dev
machine without them this module answers "what is installed?" and,
via Settings → Extras, pip-installs the missing pieces.
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
        from app.accelerate import has_numba

        if has_numba():
            try:
                import numba

                return True, f"numba {numba.__version__} (10-50x on large Floyd)"
            except ImportError:
                return True, "numba (unknown version)"
    except ImportError:
        pass
    return False, "numpy fallback (slower on large Floyd)"


def video_status() -> tuple[bool, str]:
    """(available, human detail) for MP4 export."""
    try:
        from app.video_io import has_video

        if has_video():
            return True, "MP4 available (imageio + ffmpeg)"
    except ImportError:
        pass
    return False, "MP4 disabled (extra not installed)"


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
