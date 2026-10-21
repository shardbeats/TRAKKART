# CHANGELOG — TRAKKART

Release history (newest first). Details live in `git log` and `ROADMAP.md`.

## Unreleased
- Grouped menus (File/Edit/View/Help with separators; clipboard in Edit).
- Panel as a 5-page accordion: IMAGE / DITHER / COLOR / FX / MOTION.
- VIDEO preview ON pre-checks Animation GIF in the Export dialog.
- Help → About TRAKKART; post-export dialog with Show in folder.
- Help → Keyboard shortcuts; File → Open recent (last 5, in prefs).
- MOTIF section only visible for method `motif`; friendlier empty canvas.
- File logging (`data/trakkart.log`, rotating) + friendly crash dialog.
- Crop editor zoom/pan loop fixed (owned box, exact anchor).
- CHANGELOG started (this file).

## v0.18.0
- Iteration UX: viewport Full/Live/Still, fast/slow debounce, in-app tutorial
  + offline samples, 4 themes, batch in File menu.
- Panel clipping fixes, video-proxy combo restore, layout audit tests.
- 375 tests, 51 Gherkin scenarios, 5/5 gates (coverage 92.1%).

## v0.17.0
- Lock-free threaded preview + ValueSlider on every slider.

## v0.16.0 — v0.15.0
- Safe drop classification with ON/OFF batch-drop toggle.
- Anti-freeze hardening: size guards, 350ms debounce, batch cancel,
  vector cap, history prune, action bar outside the scroll.

## v0.14.0 — v0.11.0
- Text layer removed. Numba optional accelerator (bit-identical).
- Multiprocess batch, animated GIF (Pillow only), TRAKK family theme.

## v0.10.0 — v0.7.0
- Image ops + undo, randomize, zoom, drag&drop, clipboard, glitch pack.
- Vector SVG export. Halftone/cluster/diffusion engines. Pre/post FX.

## v0.6.0 — v0.2.0
- Canvas ratios + crop, portable data dir, SQLite history, custom icon.
- Adjustments (brightness/contrast/saturation), JSON presets, folder batch.

## v0.1.0
- Initial modular app: ordered + Floyd-Steinberg dither, 4 original
  palettes, PySide6 preview, canvas-size export + 1080p thumb + metadata.
