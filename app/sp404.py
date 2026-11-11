"""Roland SP-404MKII image pack (startup logos + screensaver).

Device spec (Roland "Ultimate Guide: Customizing the SP-404MKII"):
OLED 128x64 mono; `.BMP` 1/4/8/24-bit at EXACTLY 128x64 px (anything
else is silently ignored). Fixed names: `startup_1.bmp` +
`startup_2.bmp` (2 max), `screen_saver_1.bmp` .. `screen_saver_16.bmp`
(16 max per project), dropped into
`EXPORT/PROJECT/PROJECT_XX/PICTURE` on an SP-formatted SD card with
UTILITY > SYSTEM > Scrn Saver Type = Custom, then reimported
(SHIFT+PAD 14).

TRAKKART renders the art (BW dither engines are the ideal source for
a 1-bit OLED); this module only frames it to 128x64, thresholds to
1-bit and lays out the fixed names + an install sheet. Pillow-only,
fully offline and deterministic.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

SP_W = 128
SP_H = 64
STARTUP_NAMES = ("startup_1.bmp", "startup_2.bmp")
MAX_SCREENSAVER = 16
README_NAME = "README-SP404.txt"


def screen_saver_name(i: int) -> str:
    """`screen_saver_<1..16>.bmp` (1-based, SP fixed naming)."""
    if not 1 <= int(i) <= MAX_SCREENSAVER:
        raise ValueError(f"screensaver index must be 1-{MAX_SCREENSAVER}: {i!r}")
    return f"screen_saver_{int(i)}.bmp"


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
    big = src.resize((nw, nh), Image.LANCZOS)
    left = max(0, (nw - SP_W) // 2)
    top = max(0, (nh - SP_H) // 2)
    crop = big.crop((left, top, left + SP_W, top + SP_H))
    lum = crop.convert("L")
    thr = max(0, min(255, int(threshold)))
    bw = lum.point(lambda v: 255 if v >= thr else 0, mode="1")
    if invert:
        bw = Image.eval(bw, lambda v: 255 - v)
    return bw


def install_sheet() -> str:
    """Install steps for the pack (mirrors the Roland guide)."""
    return """TRAKKART SP-404MKII image pack
===============================
startup_1.bmp / startup_2.bmp = boot logos (2 max).
screen_saver_1..16.bmp = screensaver slideshow (up to 16 per project).
All files: BMP 1-bit, exactly 128x64 px.

INSTALL
1. On the SP-404MKII, format/select your SD card (SHIFT + PAD 14).
2. UTILITY (SHIFT + PAD 13) > SYSTEM > Scrn Saver Type = Custom.
3. Export the target project to SD: SHIFT + PAD 14 > EXPORT to
   SD-CARD > PROJECT > pick the project pad > ENTER.
4. Power off, move the SD to your computer.
5. Copy these .bmp files into EXPORT / PROJECT / PROJECT_XX / PICTURE
   (replace the stock ones when asked).
6. Back in the SP-404MKII: SHIFT + PAD 14 > IMPORT from SD-CARD >
   PROJECT > pick a project slot (ROLL toggles IMPORT/EXPORT view).
7. Power cycle. Boot shows your logos; idle shows your slideshow.
"""


def write_sp404_pack(images: list[Image.Image], out_dir: str | Path,
                     threshold: int = 128, invert: bool = False) -> dict[str, Path]:
    """Write a ready-to-copy pack: 2 startup + up to 16 screensaver BMPs.

    `images[0:2]` become the boot logos; the rest (cap 16) become the
    slideshow in order. Returns {filename: path}, install sheet included.
    """
    imgs = list(images or [])
    if not imgs:
        raise ValueError("SP-404MKII pack needs at least 1 image")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for name, src in zip(STARTUP_NAMES, imgs[:2]):
        frame = sp404_frame(src, threshold=threshold, invert=invert)
        dest = out / name
        frame.save(str(dest), "BMP")
        result[name] = dest
    for i, src in enumerate(imgs[2:2 + MAX_SCREENSAVER], start=1):
        name = screen_saver_name(i)
        frame = sp404_frame(src, threshold=threshold, invert=invert)
        dest = out / name
        frame.save(str(dest), "BMP")
        result[name] = dest
    sheet = out / README_NAME
    sheet.write_text(install_sheet(), encoding="utf-8")
    result[README_NAME] = sheet
    return result


__all__ = ["SP_W", "SP_H", "STARTUP_NAMES", "MAX_SCREENSAVER",
           "README_NAME", "screen_saver_name", "sp404_frame",
           "install_sheet", "write_sp404_pack"]
