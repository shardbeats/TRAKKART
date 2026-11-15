"""Social pack (v1.8 Fase B): one-click sizes from the same render.

From the full-doc still, three center-anchored crops (the profile grid
crops 9:16 to a centered 1:1, so the anchor stays centered; subject
outside the middle band gets cut — the dialog says so):
- `{base}_social_yt` 1280x720 (YouTube thumb / 16:9)
- `{base}_social_916` 1080x1920 (Shorts/Reels/TikTok cover / 9:16)
- `{base}_social_11` 1080x1080 (feed square / 1:1)

Same format as the main image (predictable), DPI tags included.
Offline, Pillow only, deterministic. Display/UI never imports this.
"""

from __future__ import annotations

from PIL import Image

#: stem -> ((target_w, target_h)). All center-anchored.
SOCIAL_SIZES: dict[str, tuple[int, int]] = {
    "social_yt": (1280, 720),
    "social_916": (1080, 1920),
    "social_11": (1080, 1080),
}


def social_name(base: str, stem: str, fmt: str) -> str:
    """`{base}_{stem}.{ext}` (ext follows the main format)."""
    return f"{base}_{stem}.{fmt}"


def pack_names(base: str, fmt: str) -> dict[str, str]:
    """{stem: filename} of the whole pack, without writing."""
    return {stem: social_name(base, stem, fmt) for stem in SOCIAL_SIZES}


def center_crop(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Center-anchored cover crop to the exact target aspect."""
    w, h = img.size
    want = tw / max(1, th)
    if w / max(1, h) > want:  # wider: cut sides
        cw, ch = max(1, round(h * want)), h
        x = (w - cw) // 2
        box = (x, 0, x + cw, ch)
    else:  # taller: cut top/bottom
        cw, ch = w, max(1, round(w / want))
        y = (h - ch) // 2
        box = (0, y, cw, y + ch)
    return img.crop(box)


def build_pack(img: Image.Image) -> dict[str, Image.Image]:
    """{stem: resized RGB} from the full-doc render (NEAREST, like export)."""
    rgb = img.convert("RGB")
    out: dict[str, Image.Image] = {}
    for stem, (tw, th) in SOCIAL_SIZES.items():
        out[stem] = center_crop(rgb, tw, th).resize((tw, th), Image.NEAREST)
    return out


def estimate_pack(fmt: str, quality: int) -> int:
    """Rough weight (~) of the three files together."""
    bpp = {"png": 0.35, "jpg": 0.05 + 0.002 * quality,
           "webp": 0.04 + 0.001 * quality}.get(fmt, 0.2)
    px = sum(w * h for w, h in SOCIAL_SIZES.values())
    return int(px * bpp)


__all__ = [
    "SOCIAL_SIZES",
    "build_pack",
    "center_crop",
    "estimate_pack",
    "pack_names",
    "social_name",
]
