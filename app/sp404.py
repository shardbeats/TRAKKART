"""Roland SP-404MKII still export (startup logo / screensaver source).

Device spec (Roland "Ultimate Guide: Customizing the SP-404MKII"):
OLED 128x64 mono; `.BMP` 1/4/8/24-bit at EXACTLY 128x64 px (anything
else is silently ignored). Fixed device names: `startup_1.bmp` +
`startup_2.bmp`, `screen_saver_1.bmp` .. `screen_saver_16.bmp`, dropped
into `EXPORT/PROJECT/PROJECT_XX/PICTURE` on an SP-formatted SD card
with UTILITY > SYSTEM > Scrn Saver Type = Custom, then reimported
(SHIFT+PAD 14).

TRAKKART exports one 128x64 1-bit BMP of the current still
(`{base}_sp404.bmp`); the user renames/organizes it on the device
names by hand. The still render is already-dithered art, so only a
luminance cut is applied (no second dither): the dot pattern is
preserved exactly. Pillow-only, fully offline and deterministic.
"""

from __future__ import annotations

from PIL import Image

SP_W = 128
SP_H = 64


def sp404_frame(img: Image.Image, threshold: int = 128,
                invert: bool = False) -> Image.Image:
    """Cover-fit any image to the 128x64 OLED and threshold to 1-bit.

    The input is expected to be already-dithered TRAKKART art, so no
    second dither is applied: a plain luminance cut preserves the dot
    pattern exactly. `invert` flips to white-on-black (stock look).
    """
    if img.width < 1 or img.height < 1:
        raise ValueError("cannot frame an empty image for SP-404MKII")
    src = img.convert("RGB")
    scale = max(SP_W / src.width, SP_H / src.height)
    nw, nh = max(1, round(src.width * scale)), max(1, round(src.height * scale))
    # NEAREST: dither dots stay crisp (no blur) when scaling to the OLED.
    big = src.resize((nw, nh), Image.NEAREST)
    left = max(0, (nw - SP_W) // 2)
    top = max(0, (nh - SP_H) // 2)
    crop = big.crop((left, top, left + SP_W, top + SP_H))
    lum = crop.convert("L")
    thr = max(0, min(255, int(threshold)))
    bw = lum.point(lambda v: 255 if v >= thr else 0, mode="1")
    if invert:
        bw = Image.eval(bw, lambda v: 255 - v)
    return bw


def install_hint() -> str:
    """One-paragraph install reminder (mirrors the Roland guide)."""
    return ("SP-404MKII: rename this file to startup_1/2.bmp or "
            "screen_saver_N.bmp (1-16), copy into EXPORT / PROJECT / "
            "PROJECT_XX / PICTURE on an SP-formatted SD (UTILITY > SYSTEM "
            "> Scrn Saver Type = Custom), reimport the project "
            "(SHIFT + PAD 14), power cycle.")


__all__ = ["SP_W", "SP_H", "sp404_frame", "install_hint"]
