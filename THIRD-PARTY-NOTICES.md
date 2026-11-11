# THIRD-PARTY-NOTICES — TRAKKART

TRAKKART code is MIT (`LICENSE`). The components below keep their
own licenses. They apply when running from source AND inside the
frozen `dist/TRAKKART.exe` / installer.

## Runtime dependencies (pip)

| Component | License | Notes |
|---|---|---|
| PySide6 + Qt (Essentials/Addons) | LGPLv3 | GUI toolkit. Dynamically linked via pip; frozen exe bundles Qt DLLs. Source: https://www.qt.io + https://pypi.org/project/PySide6/ |
| Pillow | HPND (MIT-like) | Image I/O. https://python-pillow.org/ |
| numpy | BSD-3-Clause | Array engine. https://numpy.org/ |
| numba + llvmlite | BSD-2-Clause | Optional JIT accelerator, bit-identical fallback. https://numba.pydata.org/ |
| imageio | BSD-2-Clause | Video/image writer API. https://imageio.readthedocs.io/ |
| imageio-ffmpeg | BSD-2-Clause + bundles FFmpeg | Ships an FFmpeg binary (LGPL build by imageio-ffmpeg). No GPL codecs enabled by TRAKKART. https://github.com/imageio/imageio-ffmpeg |

## Bundled binaries

- **FFmpeg** (via imageio-ffmpeg): LGPLv2.1+. Used only for MP4
  (`libx264`, `yuv420p`, `+faststart`). Binary obtained from the
  imageio-ffmpeg wheel at build time and bundled by PyInstaller.
  FFmpeg source + LGPL text: https://ffmpeg.org/download.html
- **Qt DLLs** (via PySide6): LGPLv3. Relink right: replace the
  `PySide6/*.dll` / `.pyd` next to a source install, or rebuild
  from source with `pip install -r requirements.txt`.

## Build / installer tools (not shipped)

| Component | License |
|---|---|
| PyInstaller | GPLv2 with bootloader exception (build tool only, no runtime copyleft on your code) |
| Inno Setup 6 | Inno Setup license (free, build tool only) |
| pytest / pytest-bdd / pytest-cov / flake8 | MIT (dev only) |

## Compliance checklist for the release

1. Ship `LICENSE` (MIT) + `NOTICE.md` + this file alongside the app
   (installer already copies `LICENSE`; add these two the same way).
2. Keep LGPL texts available: link above + `pip show -f PySide6 imageio-ffmpeg`
   on request. No source modification of Qt/FFmpeg is made by TRAKKART.
3. Do not remove copyright headers from bundled wheels.

Last reviewed: v1.3.0, Python 3.11/3.14, PySide6 6.6–6.12, Pillow 10+,
numpy 1.24+, numba 0.60+, imageio 2.31+, imageio-ffmpeg 0.4.9+.

## JetBrains Mono (OFL-1.1)

Bundled at `app/fonts/JetBrainsMono-Regular.ttf` for the ASCII renderer; license in `app/fonts/OFL.txt`.
