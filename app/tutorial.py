"""TRAKKART in-app tutorial + sample pack (MIT, clean-room).

No network, no binaries: samples are generated with Pillow at runtime
into data/samples/, and the "seen" flag is a marker file next to them.
All pure/testable; Qt lives only in app/ui/tutorial_dialog.py.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

MARKER = ".tutorial_seen"
SAMPLES_DIRNAME = "samples"

STEPS: tuple[tuple[str, str], ...] = (
    ("Open",
     "File → Open image (Ctrl+O), drag&drop onto the window, or paste "
     "from the clipboard (Ctrl+V). Folders can be dropped for batch."),
    ("Method",
     "Pick 1 of 36 dither engines (◀ ▶ steps through them). Ordered maps "
     "march with phase; error-diffusion stays put. Hover Compare (Space) "
     "to hold the original."),
    ("Color",
     "SOURCE auto-extracts the palette from your image, Depth limits "
     "shades, and the dice + locks remix swatches without losing a good one."),
    ("Animate",
     "VIDEO mode previews the full canvas. Layers sweep any of 10 props "
     "across frames, Signal Drift adds retro-screen noise, and GIF/MP4 "
     "export at canvas size."),
    ("Export",
     "Export… (Ctrl+Shift+S) writes the canvas-size bundle; Quick export "
     "(Ctrl+S) repeats the last setup. SVG vectors are resolution-free."),
)


def samples_dir(data_dir: str | Path | None = None) -> Path:
    from app.paths import get_data_dir

    base = Path(data_dir) if data_dir else get_data_dir()
    d = base / SAMPLES_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def marker_path(data_dir: str | Path | None = None) -> Path:
    return samples_dir(data_dir) / MARKER


def first_run_needed(data_dir: str | Path | None = None) -> bool:
    return not marker_path(data_dir).exists()


def mark_seen(data_dir: str | Path | None = None) -> Path:
    p = marker_path(data_dir)
    p.write_text("seen", encoding="utf-8")
    return p


def _gradient(size: int = 512) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            v = int(x / (size - 1) * 255)
            px[x, y] = (v, v // 2, 255 - v)
    return im


def _checker(size: int = 512, cells: int = 8) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    step = size // cells
    for y in range(size):
        for x in range(size):
            on = ((x // step) + (y // step)) % 2 == 0
            px[x, y] = (235, 235, 235) if on else (20, 20, 24)
    return im


def _portrait(size: int = 512) -> Image.Image:
    im = Image.new("RGB", (size, size), (24, 18, 30))
    d = ImageDraw.Draw(im)
    d.ellipse([size * 0.3, size * 0.12, size * 0.7, size * 0.55], fill=(216, 178, 150))
    d.rectangle([size * 0.2, size * 0.62, size * 0.8, size], fill=(88, 40, 140))
    d.ellipse([size * 0.38, size * 0.28, size * 0.46, size * 0.36], fill=(20, 12, 16))
    d.ellipse([size * 0.54, size * 0.28, size * 0.62, size * 0.36], fill=(20, 12, 16))
    return im


def ensure_samples(data_dir: str | Path | None = None) -> list[Path]:
    """Generate the sample pack if missing. Returns the 3 sample paths."""
    d = samples_dir(data_dir)
    out = []
    for name, make in (("gradient", _gradient), ("checker", _checker), ("portrait", _portrait)):
        p = d / f"{name}.png"
        if not p.exists():
            make().save(str(p), "PNG")
        out.append(p)
    return out


__all__ = [
    "STEPS",
    "ensure_samples",
    "first_run_needed",
    "mark_seen",
    "marker_path",
    "samples_dir",
]
