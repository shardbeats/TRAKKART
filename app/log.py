"""File logging: data/trakkart.log (stdlib only, rotating, idempotent).

Tests reset `_INITIALIZED` to point logging at a tmp dir.
"""

from __future__ import annotations

import logging
import re
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "trakkart.log"
_INITIALIZED = False

#: Full text of the most recent error report (None until the first one).
#: powers Help > Copy last error report (paste it with bug reports).
LAST_REPORT: str | None = None

#: Monotonic error-report counter (E0001, E0002, ... per session).
_REPORT_SEQ = 0

_TAG_RE = re.compile(r"^\[(E\d+)\]\s*")


def log_path(data_dir=None) -> Path:
    from app.paths import get_data_dir

    base = Path(data_dir) if data_dir else get_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / LOG_FILENAME


def setup_logging(data_dir=None) -> Path:
    """Attach a rotating file handler to the `trakkart` logger. Idempotent."""
    global _INITIALIZED
    path = log_path(data_dir)
    if _INITIALIZED:
        return path
    handler = RotatingFileHandler(str(path), maxBytes=256 * 1024,
                                  backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("trakkart")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _INITIALIZED = True
    return path


# Human-readable explanations for technical failures. Each entry is
# (needle substrings, message). Matched case-insensitively against
# "ExceptionType: message". Unknown errors fall through to the raw text.
_FRIENDLY = (
    (("truth value of an array",),
     "Render engine hiccup (internal bug: image and preset are safe). "
     "Details logged — please report it with the error code."),
    (("out of memory", "max_gif_pixels", "fail-fast", "memoryerror",
      "transient ram", "transient"),
     "Out of memory: lower Frames/Hold, use a smaller canvas, or pick MP4."),
    (("toobig", "too large", "50mp", "8000px", "decompression bombing"),
     "Image too large: the safety guard refused it (max 8000px / 50MP)."),
    (("videobackendmissing", "no backend", "ffmpeg", "imageio"),
     "Video backend missing (dev installs only; the bundled exe includes it)."),
    (("filenotfounderror", "no such file"),
     "File not found (moved, renamed or deleted?)."),
    (("permissionerror", "permission denied"),
     "Permission denied (write-protected folder?)."),
    (("no space left", "errno 28", "disk full"),
     "Disk full: free space where the export goes."),
    (("unidentifiedimageerror", "cannot identify image"),
     "Not an image, or the file is corrupt."),
)


def friendly_message(exc) -> str:
    """Plain-language explanation for a technical failure.

    Accepts an exception or its text. Unknown errors return the raw
    message (never worse than today).
    """
    if isinstance(exc, BaseException):
        hay = f"{type(exc).__name__}: {exc}".lower()
        raw = str(exc) or type(exc).__name__
    else:
        hay = str(exc).lower()
        raw = str(exc) or "Unknown error"
    for needles, msg in _FRIENDLY:
        if any(n in hay for n in needles):
            return msg
    line = raw.strip().splitlines()
    text = line[-1].strip() if line else raw.strip()
    return text or "Unknown error"


def split_report_tag(msg: str) -> tuple[str | None, str]:
    """Split a "[E0007] ..." worker message into (report id, clean text)."""
    m = _TAG_RE.match(str(msg or ""))
    if not m:
        return None, str(msg or "")
    return m.group(1), str(msg[m.end():])


def format_report(action: str, exc: BaseException,
                  context: dict | None = None) -> tuple[str, str]:
    """Build (report id, full text) for an error. No I/O, no Qt."""
    global _REPORT_SEQ

    _REPORT_SEQ += 1
    rid = f"E{_REPORT_SEQ:04d}"
    try:
        from app import __version__ as _v
    except Exception:  # noqa: BLE001
        _v = "?"
    lines = [
        f"=== TRAKKART ERROR REPORT [{rid}] ===",
        f"when: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"version: {_v}",
        f"action: {action}",
    ]
    for k, v in (context or {}).items():
        lines.append(f"{k}: {v}")
    lines.append(f"error: {type(exc).__name__}: {exc}")
    lines.append("traceback:")
    try:
        lines.extend(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:  # noqa: BLE001
        lines.append("<traceback unavailable>")
    lines.append(f"=== END [{rid}] (Help > Show logs folder for trakkart.log) ===")
    return rid, "\n".join(lines).rstrip() + "\n"


def report_error(action: str, exc: BaseException,
                 context: dict | None = None) -> str:
    """Log a full error report, remember it, return its id ("E0007").

    Thread-safe (plain logging call): worker threads report here so no
    traceback is lost crossing the Qt signal boundary.
    """
    global LAST_REPORT

    rid, text = format_report(action, exc, context)
    try:
        logging.getLogger("trakkart").error("\n" + text)
    except Exception:  # noqa: BLE001
        pass
    LAST_REPORT = text
    return rid


def last_report_text() -> str:
    """Full text of the most recent error report ("" when none yet)."""
    return LAST_REPORT or ""


__all__ = ["LOG_FILENAME", "LAST_REPORT", "friendly_message", "format_report",
           "last_report_text", "log_path", "report_error", "setup_logging",
           "split_report_tag"]
