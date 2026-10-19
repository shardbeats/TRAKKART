"""Generate TRAKKART's own icon.png + icon.ico (SLIME dither on black)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from app.dither import ordered_bayer


def main() -> None:
    base = Image.new("RGB", (256, 256), (10, 18, 12))
    px = base.load()
    for y in range(256):  # slime -> black diagonal
        for x in range(256):
            v = int((x + y) / 510 * 255)
            px[x, y] = (10 + v // 3, 18 + v // 2, 12 + v // 4)
    icon = ordered_bayer(base, palette=[(10, 18, 12), (46, 92, 52), (126, 178, 78), (222, 238, 178)], matrix="4x4")
    icon.save(ROOT / "icon.png", "PNG")
    icon.save(ROOT / "icon.ico", "ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon.png + icon.ico ready")


if __name__ == "__main__":
    main()
