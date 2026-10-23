"""Generate TRAKKART's own icon.png + icon.ico (05_bayer_dots, TRAKK SUITE).

Dark rounded square #151617 + amber border #F5A623 + 4x4 Bayer dots.
Regenerable: py tools/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
S = 256
DARK = (21, 22, 23, 255)
AMBER = (245, 166, 35, 255)
WHITE = (235, 235, 235, 255)


def render(size: int = 256) -> Image.Image:
    sc = size / 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(56 * sc)
    border = max(1, int(round(8 * sc)))
    d.rounded_rectangle([4 * sc, 4 * sc, size - 5 * sc, size - 5 * sc],
                        radius=radius, fill=DARK, outline=None)
    d.rounded_rectangle([4 * sc, 4 * sc, size - 5 * sc, size - 5 * sc],
                        radius=radius, fill=None, outline=AMBER, width=border)
    sizes = [[14, 7, 10, 5], [5, 11, 4, 9], [12, 6, 14, 7], [4, 9, 5, 11]]
    gap = 38 * sc
    cx, cy = 128 * sc, 133 * sc
    for gy in range(4):
        for gx in range(4):
            r = sizes[gy][gx] * sc
            x = cx + (gx - 1.5) * gap
            y = cy + (gy - 1.5) * gap
            col = AMBER if (gx + gy) % 2 == 0 else WHITE
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    return img


def main() -> None:
    icon = render(256)
    icon.save(ROOT / "icon.png", "PNG")
    icon.save(ROOT / "icon.ico", "ICO",
              sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon.png + icon.ico ready (05_bayer_dots)")


if __name__ == "__main__":
    main()
