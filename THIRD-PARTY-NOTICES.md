# THIRD-PARTY-NOTICES — TRAKKART

TRAKKART code is MIT (`LICENSE`). The components below keep their own
licenses. They apply when running from source AND inside the frozen
portable folder / installer.

## Runtime dependencies (pip)

| Component | License | Notes |
|---|---|---|
| PySide6 + Qt (Essentials/Addons) | LGPLv3 | GUI toolkit. Dynamically linked via pip; frozen exe bundles Qt DLLs. Source: https://www.qt.io + https://pypi.org/project/PySide6/ |
| Pillow | HPND (MIT-like) | Image I/O. https://python-pillow.org/ |
| numpy | BSD-3-Clause | Array engine. https://numpy.org/ |
| numba + llvmlite | BSD-2-Clause | Optional JIT accelerator, bit-identical fallback. https://numba.pydata.org/ |
| imageio | BSD-2-Clause | Video/image writer API. https://imageio.readthedocs.io/ |
| imageio-ffmpeg | BSD-2-Clause (Python wrapper) | The wrapper is BSD-2; the FFmpeg executable it ships is **GPLv3** (see below). https://github.com/imageio/imageio-ffmpeg |
| FFmpeg (bundled executable) | **GPLv3** | MP4 decode/encode binary. See “FFmpeg GPLv3” below. https://ffmpeg.org/ |

## Bundled binaries

- **FFmpeg** (via imageio-ffmpeg): **GPLv3, not LGPL.** The imageio-ffmpeg
  wheels pin third-party builds that enable GPL parts:
  Windows uses gyan.dev “essentials”
  (`--enable-gpl --enable-version3 --enable-libx264 --enable-libx265`),
  Linux/macOS use BtbN GPL builds. The pinned sources are public in
  `imageio-ffmpeg/tools/ffmpeg-sources.json`.
  GPL components in the binary include libx264, libx265 and libxvid;
  LGPL/permissive parts include libaom, libvpx, libopus, libwebp and zimg.
  TRAKKART runs `ffmpeg.exe` as a **separate process** (subprocess/pipe)
  for MP4 export; no FFmpeg library is linked into the MIT Python code.
  The GPL applies to the distributed FFmpeg binary and its corresponding
  source, not to TRAKKART's own MIT source. This is the project's reading
  of the licenses, not legal advice.
- **Qt DLLs** (via PySide6): LGPLv3. Relink right: replace the
  `PySide6/*.dll` / `.pyd` next to a source install, or rebuild
  from source with `pip install -r requirements.txt`.

## FFmpeg GPLv3 — what every release must ship

`build_portable.py` writes `FFMPEG-BUILD-INFO.txt` next to the exe with
the exact binary name, SHA-256, `ffmpeg -version` output (including the
`configuration:` line) and source links. Keep it in the ZIP/installer.

1. **License text:** ship `licenses/GPL-3.0.txt` (FFmpeg) and
   `licenses/LGPL-3.0.txt` (Qt) with the app.
2. **Build record:** ship `FFMPEG-BUILD-INFO.txt` (generated at build
   time; never hand-edited).
3. **Corresponding source:** keep the upstream source for the exact
   FFmpeg version (https://ffmpeg.org/releases/) plus the external GPL
   libraries (x264: https://code.videolan.org/videolan/x264,
   x265: https://bitbucket.org/multicoreware/x265_git) and the build
   provider's files (gyan.dev Windows builds, BtbN FFmpeg-Builds)
   available for as long as the release is distributed.
4. **Written offer:** the release notes state that the corresponding
   source for the bundled GPLv3 FFmpeg is available on request through
   the project repository (https://github.com/shardbeats/TRAKKART),
   valid for at least three years from the release date.
5. **No extra restrictions:** do not add terms on the FFmpeg binary or
   source beyond GPLv3.
6. **About box:** names the bundled FFmpeg as GPLv3 (Help → About).
7. **Future video import:** if PyAV is adopted, its PyPI wheels also
   bundle GPL FFmpeg libraries (x264/x265); audit them the same way
   before shipping.

## Build / installer tools (not shipped)

| Component | License |
|---|---|
| PyInstaller | GPLv2 with bootloader exception (build tool only, no runtime copyleft on your code) |
| Inno Setup 6 | Inno Setup license (free, build tool only) |
| pytest / pytest-bdd / pytest-cov / flake8 | MIT (dev only) |

## Compliance checklist for the release

1. Ship `LICENSE` (MIT) + `NOTICE.md` + this file + `licenses/GPL-3.0.txt`
   + `licenses/LGPL-3.0.txt` + `FFMPEG-BUILD-INFO.txt` alongside the app.
   `build_portable.py` copies/bundles all of them.
2. Keep the source links above alive and publish the written offer in the
   release notes (FFmpeg GPLv3).
3. Keep the LGPLv3 relink right for Qt (dynamic DLLs) and make the Qt
   license text available; `pip show -f PySide6` on request.
4. Do not remove copyright headers from bundled wheels/binaries.

Last reviewed: nov-2026, Python 3.11/3.14, PySide6 6.6–6.12, Pillow 10+,
numpy 1.24+, numba 0.60+, imageio 2.31+, imageio-ffmpeg 0.4.9+.

## JetBrains Mono (OFL-1.1)

Bundled at `app/fonts/JetBrainsMono-Regular.ttf` for the ASCII renderer; license in `app/fonts/OFL.txt`.
