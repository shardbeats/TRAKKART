"""Image loading service: filesystem / clipboard / web / drag&drop.

Extraído de MainWindow (que mezclaba UI + IO + red). Funciones puras
testeables sin Qt, salvo qimage_to_pil que vive en ui.qt_image.
"""

from __future__ import annotations

import base64
import io
import urllib.request
from pathlib import Path

from PIL import Image

from app.dnd import is_image_data_url
from app.safety import MAX_BYTES, TooBigError, check_image, check_path


def load_path(path: Path) -> Image.Image:
    """Valida header primero (anti decompression-bomb) y decodifica."""
    check_path(path)
    img = Image.open(path).convert("RGB")
    check_image(img)
    return img


def download_image(url: str, max_bytes: int = MAX_BYTES, timeout: int = 15) -> tuple[Image.Image, int]:
    """Descarga una imagen http(s). Devuelve (PIL, bytes). Valida content-type."""
    req = urllib.request.Request(url, headers={"User-Agent": "TRAKKART/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ctype = (resp.headers.get_content_type() or "").lower()
        if not (ctype.startswith("image/") or "octet-stream" in ctype):
            raise ValueError(f"URL is not an image ({ctype or 'unknown'})")
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise TooBigError(f"download exceeds {max_bytes // 1_000_000}MB")
    img = Image.open(io.BytesIO(data)).convert("RGB")
    check_image(img)
    return img, len(data)


def decode_data_url(url: str) -> tuple[Image.Image, int]:
    """Decodifica data:image/...;base64 sin red. Devuelve (PIL, bytes)."""
    if not is_image_data_url(url):
        raise ValueError("not a data:image")
    _, _, payload = url.partition(",")
    if not payload:
        raise ValueError("empty data URL")
    data = base64.b64decode(payload, validate=True)
    if len(data) > MAX_BYTES:
        raise TooBigError(f"image exceeds {MAX_BYTES // 1_000_000}MB")
    img = Image.open(io.BytesIO(data)).convert("RGB")
    check_image(img)
    return img, len(data)


__all__ = ["load_path", "download_image", "decode_data_url"]
