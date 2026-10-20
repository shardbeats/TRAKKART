"""TRAKKART JPEG glitch (MIT, clean-room). Pillow-only, deterministic.

Recompresses the dithered image through JPEG bytes (quality driven by
amount) and reloads it: blockiness + chroma-subsampling + ringing, the
classic JPEG-glitch look. No RNG: same input + amount = same output.
"""

from __future__ import annotations

import io

from PIL import Image


def apply_jpeg(img: Image.Image, amount: float = 0.0) -> Image.Image:
    """amount 0-100, 0 = off. Higher = lower quality + stronger subsampling."""
    amt = float(amount or 0.0)
    if amt <= 0:
        return img
    amt = min(100.0, max(0.0, amt))
    # quality 95 -> 8 across the range (amount 100 = heavy blocks).
    quality = int(round(95.0 - amt * 0.87))
    quality = max(5, min(95, quality))
    subsampling = 2 if amt >= 40 else (1 if amt >= 15 else 0)
    base = img.convert("RGB")
    buf = io.BytesIO()
    base.save(buf, format="JPEG", quality=quality, subsampling=subsampling,
              optimize=False, progressive=False)
    buf.seek(0)
    out = Image.open(buf)
    out.load()
    return out.convert("RGB")


__all__ = ["apply_jpeg"]
