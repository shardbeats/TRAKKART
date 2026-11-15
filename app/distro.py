"""Distributor delivery check (v1.8 Fase A): DISTRO_3000 readiness.

What stores ask for (DistroKid/TuneCore/Spotify, surveyed nov-2026):
square artwork, 3000x3000 px, JPG, RGB. DPI only matters for print.

Two entry points, both offline and Pillow-only:
- `validate_session(...)`: the live document (doc dims + chosen format +
  source size for the upscale-blur hint). Shown as honest hints in the
  export dialog; nothing is blocked.
- `validate_file(path)`: an already-written file on disk.

Checks are data (`DistroCheck` list): the dialog renders them, tests pin
them. No UI import here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

#: The distributor square both presets and validators target.
DISTRO_LONG_SIDE = 3000

#: Below this quality a JPG shows banding on flat dither fields.
DISTRO_MIN_QUALITY = 85


@dataclass(frozen=True)
class DistroCheck:
    """One rule: ok + machine code + human hint (empty hint when ok)."""

    ok: bool
    code: str
    hint: str = ""


def _square_checks(w: int, h: int) -> list[DistroCheck]:
    out: list[DistroCheck] = []
    if w == h and w > 0:
        out.append(DistroCheck(True, "square"))
    else:
        out.append(DistroCheck(False, "square",
                               f"Not square ({w}x{h}): distributors want 1:1."))
    long_side = max(int(w), int(h))
    if long_side == DISTRO_LONG_SIDE:
        out.append(DistroCheck(True, "size"))
    elif long_side >= DISTRO_LONG_SIDE:
        out.append(DistroCheck(False, "size",
                               f"{long_side}px: over {DISTRO_LONG_SIDE}px, "
                               "some distributors reject it (downscale)."))
    elif long_side >= 1000:
        out.append(DistroCheck(False, "size",
                               f"{long_side}px: under {DISTRO_LONG_SIDE}px, "
                               "upscale or re-render at 3000."))
    else:
        out.append(DistroCheck(False, "size",
                               f"{long_side}px: far under {DISTRO_LONG_SIDE}px "
                               "(1000px is the bare minimum)."))
    return out


def validate_session(doc_w: int, doc_h: int, fmt: str,
                     src_w: int = 0, src_h: int = 0,
                     quality: int = 90) -> list[DistroCheck]:
    """Live-document readiness (does not touch disk)."""
    out = _square_checks(int(doc_w), int(doc_h))
    if str(fmt).lower() == "jpg":
        out.append(DistroCheck(True, "format"))
    else:
        out.append(DistroCheck(False, "format",
                               f"Format is {str(fmt).upper()}: ship JPG "
                               "(RGB, high quality)."))
    try:
        if int(quality) >= DISTRO_MIN_QUALITY:
            out.append(DistroCheck(True, "quality"))
        else:
            out.append(DistroCheck(False, "quality",
                                   f"Quality {int(quality)}: below "
                                   f"{DISTRO_MIN_QUALITY} banding shows."))
    except (TypeError, ValueError):
        out.append(DistroCheck(False, "quality", "Quality unreadable."))
    try:
        src_long = max(int(src_w), int(src_h))
    except (TypeError, ValueError):
        src_long = 0
    doc_long = max(int(doc_w), int(doc_h))
    if src_long > 0 and doc_long > src_long:
        factor = doc_long / max(1, src_long)
        out.append(DistroCheck(False, "upscale",
                               f"Upscaled {factor:.1f}x from source "
                               f"({src_long}px): soft at full size."))
    else:
        out.append(DistroCheck(True, "upscale"))
    return out


def validate_file(path: str | Path) -> list[DistroCheck]:
    """Readiness of a file already on disk."""
    p = Path(path)
    try:
        with Image.open(p) as im:
            im.load()
            w, h = im.size
            mode, fmt = str(im.mode), str(im.format or "").upper()
    except Exception:  # noqa: BLE001
        return [DistroCheck(False, "readable",
                            f"Cannot open {p.name} as an image.")]
    out = _square_checks(w, h)
    if fmt in ("JPEG", "JPG"):
        out.append(DistroCheck(True, "format"))
    else:
        out.append(DistroCheck(False, "format",
                               f"{p.suffix or 'file'} ({fmt or 'unknown'}): "
                               "ship JPG."))
    if mode == "RGB":
        out.append(DistroCheck(True, "mode"))
    else:
        out.append(DistroCheck(False, "mode",
                               f"Mode is {mode}: ship RGB (not {mode})."))
    return out


def distro_summary(checks: list[DistroCheck]) -> tuple[bool, str]:
    """(all_ok, one-line honest summary) for dialogs and logs."""
    bad = [c for c in checks if not c.ok]
    if not bad:
        return True, "Distro ready: 3000x3000 square JPG."
    first = bad[0].hint or bad[0].code
    rest = len(bad) - 1
    extra = f" (+{rest} more)" if rest else ""
    return False, f"Distro: {first}{extra}"


__all__ = [
    "DISTRO_LONG_SIDE",
    "DISTRO_MIN_QUALITY",
    "DistroCheck",
    "distro_summary",
    "validate_file",
    "validate_session",
]
