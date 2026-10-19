"""TRAKKART pre-process — brightness/contrast/saturation (Pillow only)."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageEnhance


@dataclass
class Adjust:
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0

    def validate(self) -> None:
        for name in ("brightness", "contrast", "saturation"):
            v = float(getattr(self, name))
            if not 0.0 <= v <= 3.0:
                raise ValueError(f"{name} out of range 0.0-3.0: {v}")

    def is_identity(self) -> bool:
        return self.brightness == 1.0 and self.contrast == 1.0 and self.saturation == 1.0

    def to_dict(self) -> dict:
        return {"brightness": float(self.brightness), "contrast": float(self.contrast), "saturation": float(self.saturation)}

    @staticmethod
    def from_dict(d: dict | None) -> "Adjust":
        d = d or {}
        a = Adjust(
            brightness=float(d.get("brightness", 1.0)),
            contrast=float(d.get("contrast", 1.0)),
            saturation=float(d.get("saturation", 1.0)),
        )
        a.validate()
        return a


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
    return out
