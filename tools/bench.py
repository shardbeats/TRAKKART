"""Manual TRAKKART benchmark: numpy vs numba (not a gate, data-driven decisions only)."""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from app.accelerate import has_numba
from app.kernels import run_kernel
from app.palettes import get_palette


def _img(size: int) -> Image.Image:
    im = Image.new("RGB", (size, size), (90, 60, 140))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 5) % 256, (y * 3) % 256, 128)
    return im


def bench(size: int, kernel: str, palette, backend: str) -> float:
    run_kernel(_img(size), kernel, palette, 128.0, backend=backend)  # warmup/compile
    t = time.time()
    run_kernel(_img(size), kernel, palette, 128.0, backend=backend)
    return time.time() - t


def main() -> None:
    pal = get_palette("SLIME")
    print(f"numba available: {has_numba()}")
    for size in (480, 960):
        for kernel in ("floyd", "jjn"):
            row = {"size": size, "kernel": kernel}
            row["numpy_BW"] = round(bench(size, kernel, None, "numpy"), 2)
            row["numpy_color"] = round(bench(size, kernel, pal, "numpy"), 2)
            if has_numba():
                row["numba_BW"] = round(bench(size, kernel, None, "numba"), 2)
                row["numba_color"] = round(bench(size, kernel, pal, "numba"), 2)
            print(row)


if __name__ == "__main__":
    main()
