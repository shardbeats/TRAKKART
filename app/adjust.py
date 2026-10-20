"""TRAKKART pre-process — brightness/contrast/saturation + midtones/highlights (Pillow + numpy)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance


@dataclass
class Adjust:
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    midtones: float = 1.0
    highlights: float = 0.0

    def validate(self) -> None:
        for name, lo, hi in (
            ("brightness", 0.0, 3.0),
            ("contrast", 0.0, 3.0),
            ("saturation", 0.0, 3.0),
            ("midtones", 0.0, 2.0),
            ("highlights", -100.0, 100.0),
        ):
            v = float(getattr(self, name))
            if not lo <= v <= hi:
                raise ValueError(f"{name} out of range {lo:g}-{hi:g}: {v}")

    def is_identity(self) -> bool:
        return (
            self.brightness == 1.0
            and self.contrast == 1.0
            and self.saturation == 1.0
            and self.midtones == 1.0
            and self.highlights == 0.0
        )

    def to_dict(self) -> dict:
        return {
            "brightness": float(self.brightness),
            "contrast": float(self.contrast),
            "saturation": float(self.saturation),
            "midtones": float(self.midtones),
            "highlights": float(self.highlights),
        }

    @staticmethod
    def from_dict(d: dict | None) -> "Adjust":
        d = d or {}
        a = Adjust(
            brightness=float(d.get("brightness", 1.0)),
            contrast=float(d.get("contrast", 1.0)),
            saturation=float(d.get("saturation", 1.0)),
            midtones=float(d.get("midtones", 1.0)),
            highlights=float(d.get("highlights", 0.0)),
        )
        a.validate()
        return a


def apply_mid_high(img: Image.Image, midtones: float = 1.0, highlights: float = 0.0) -> Image.Image:
    """Midtones (gamma around mid gray) + highlights (lift/cut brights).

    midtones 1.0 = neutral; >1 brightens mids, <1 darkens mids.
    highlights -100..100, 0 = neutral; mask ramps 128->255 (smoothstep).
    """
    mid = float(midtones)
    hi = float(highlights)
    if mid == 1.0 and hi == 0.0:
        return img
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    if mid != 1.0:
        gamma = 1.0 / max(mid, 1e-6)
        arr = np.clip(255.0 * np.power(np.clip(arr / 255.0, 0.0, 1.0), gamma), 0.0, 255.0)
    if hi != 0.0:
        lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0
        mask = np.clip((lum - 0.5) / 0.5, 0.0, 1.0)
        mask = mask * mask * (3.0 - 2.0 * mask)  # smoothstep: brights only, no banding
        arr = np.clip(arr + hi * mask[..., None], 0.0, 255.0)
    return Image.fromarray(arr.astype(np.uint8))


def apply_adjust(img: Image.Image, adjust: Adjust | dict | None = None) -> Image.Image:
    """Apply adjustments. No adjustments or identity -> same image."""
    a = adjust if isinstance(adjust, Adjust) else Adjust.from_dict(adjust)
    if a.is_identity():
        return img
    out = img.convert("RGB")
    if a.brightness != 1.0:
        out = ImageEnhance.Brightness(out).enhance(a.brightness)
    if a.contrast != 1.0:
        out = ImageEnhance.Contrast(out).enhance(a.contrast)
    if a.saturation != 1.0:
        out = ImageEnhance.Color(out).enhance(a.saturation)
    out = apply_mid_high(out, float(a.midtones), float(a.highlights))
    return out
