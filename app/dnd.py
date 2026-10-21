"""Drop classification (pure, no Qt, no disk): what to do with a drop.

Actions: image_data (mime.hasImage, handled elsewhere), http, data, blob,
local (file:// path or no scheme), ignore (empty, weird schemes).
"""

from __future__ import annotations

from urllib.parse import urlsplit


def classify_drop(target: str) -> str:
    s = (target or "").strip()
    if not s:
        return "ignore"
    try:
        scheme = urlsplit(s).scheme.lower()
    except Exception:
        return "ignore"
    if scheme in ("http", "https"):
        return "http"
    if scheme == "data":
        return "data"
    if scheme == "blob":
        return "blob"
    if scheme in ("", "file"):
        return "local"
    if len(scheme) == 1 and scheme.isalpha():
        return "local"  # bare Windows path (C:/...): urlsplit sees drive as scheme
    return "ignore"


def is_image_data_url(target: str) -> bool:
    return (target or "").lower().startswith("data:image/")
