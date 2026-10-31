# QA — TRAKKART

Verification procedures (TRAKK standard).

## Fast loop (dev)

Venv: central `C:\venvs\dev` if present (override with `CENTRAL_VENV`),
else local `.venv`. The commands below use `.venv`; swap the python path
when using the central one.

```
.venv\Scripts\python -m pytest tests -q -p no:cacheprovider --no-cov -m "not slow" -n auto
```

`-n auto` (pytest-xdist) is the big lever: ~11x faster locally
(6.4 min → ~35 s). Without it, use `-n 4` or nothing.

## Full suite + coverage

```
.venv\Scripts\python -m pytest tests -q -n auto
.venv\Scripts\python -m coverage run -m pytest tests -q -n auto
.venv\Scripts\python -m coverage report
.venv\Scripts\python -m coverage html   :: data/quality_html
.venv\Scripts\python -m flake8 app tests tools main.py build_exe.py build_installer.py
```

## Gates (release)

```
.venv\Scripts\python tools\quality_metrics.py
```

Must pass all 5 gates and write `data/quality_report.json`.
If `coverage` fails, check the HTML report for uncovered lines in `app/`.

## Gherkin

```
features/dither.feature   :: 3 scenarios (B&W Bayer, palette Bayer, dispatch)
features/floyd.feature    :: 1 scenario (B&W Floyd)
features/export.feature   :: 3 scenarios (palettes, main image + thumb, smoke 500B)
features/presets.feature  :: 2 scenarios (roundtrip, bundled never overwritten)
features/batch.feature    :: 1 scenario (3-image batch, 2 PNGs each)
features/adjust_text.feature :: 2 scenarios (brightness differs, valid metadata)
features/history.feature  :: 1 scenario (export gets logged)
features/dnd.feature      :: 2 scenarios (blob is not batch, http download)
features/canvas.feature   :: 3 scenarios (9:16 export, crop clamp, free Custom 1920x800)
features/kernels.feature  :: 7 scenarios (Atkinson, blue-noise, halftone, JJN, numba parity, new kernels, Hilbert)
features/fx.feature       :: 4 scenarios (scanlines, replace-color, duotone, halftone)
features/vector.feature   :: 1 scenario (valid SVG with rects)
features/flow.feature     :: 4 scenarios (chromatic aberration, deterministic slice, pixel sort, mosh modes)
features/gif.feature      :: 3 scenarios (N frames, glitch animates ED, mix ping-pong loop)
features/safety.feature   :: 2 scenarios (giant image, huge vector)
features/color_pro.feature :: 2 scenarios (auto-extract, source/depth)
features/fx_stack.feature :: 2 scenarios (stack order, jpeg neutral)
features/engines3.feature :: 3 scenarios (cmyk/ascii/edges, motif, vector-pro)
features/motion.feature   :: 4 scenarios (drift determinism, paste-up neutral, motion freeze, backend-missing skip)
features/ux.feature       :: 2 scenarios (viewport modes, heavy presets)
```

Total: 52/52. Steps live in `tests/bdd/test_steps_*.py` by domain (scenarios bound per module), shared givens in `tests/bdd/conftest.py`, `ctx` fixture in `tests/conftest.py`.
Current suite: 460 tests (incl. `tests/test_disintegrate.py`: wind vs random, seed, identity, loop, chain up to 6, odd-canvas regression, joints, holds, GIF export/dispatch; `tests/test_ux.py`: morph live pick + playlist). Perf tests marked `slow` are excluded with `-m "not slow"` in the fast loop.
`tools/bench.py` is manual (not a gate): B&W 960px ~0.01s, color 960px ~0.02s with numba.
If you add a scenario, update the `gherkin` gate in `tools/quality_metrics.py` and this file.

## Particle disperse (v1.6, solo dispersion)

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py -q -p no:cacheprovider --no-cov
```

Engine: `app/disintegrate.py` (BW dither -> points -> breathe `sin(pi*frac)`, loop-perfect).
GIF bridge: `app/gif.py::gif_dissolve_frames` (reuses `save_gif` + `video_io.write_mp4`).
Presets: `ASH_WIND` (wind) + `DUST_RANDOM` (random) via `dissolve_*` fields.

## Morph A->B + dissolve UI (v1.7)

MOTION modes `dissolve` (one image loop) + `morph` (A->B through one cloud).
Second image: `Morph image...` button in MOTION (session-only, `win.morph_src`).
Without B, `morph` falls back to a dissolve of A (hint in `lbl_compat`).
`gif_frames(..., img_b=...)` dispatches both; preview (`VideoWorker`), export
(`export_full(morph_src=...)`) and batch share the path. Strict 0=off holds.

## Morph chain + MORPH page (v1.8)

`morph_chain_frames([A,B,C...])` splits frames per segment (cap 6 total: A + 5);
`gif_morph_frames`/`gif_frames(img_b=list)` accept lists. Batch without chain
images falls back to dissolve.
MORPH accordion page owns dissolve params + playlist (Add/Remove/Up/Down/Clear,
`win.morph_list` + `morph_src` alias); MOTION keeps Mode/Frames/FPS/Length.
Morph needs chain images (hint); live preview auto-enables video on pick, and
the video bar scrubs A->B->... without exporting.

## Morph timing: holds + per-segment budget (v1.9)

Research: ImageMagick `-set delay "%[fx:(t==0||t==n-1) ? 150 : 8]"` (pause only
assembled ends), ComfyUI `still_image_delay_ms` (default 2500ms per end),
Pillow per-frame `duration=[...]` list.
Here: `dissolve_hold` seconds per end (MORPH Hold slider 0-3s, default 1.0)
-> duplicated assembled frames (GIF uniform fps + MP4 + preview scrub all work,
no duration-list quirks). Transition budget: morph reserves 2 frames minimum per
segment so every form appears assembled; joints sample `q=j/(nk-1)` (no pop);
holds shrink to fit the 64-frame cap (transitions win). Duration label shows
loop + hold (`= 5.3s loop + 2.0s hold`); hint when a segment gets < 8 frames.

## Manual GUI checklist (before each release)

1. `run.bat` opens without traceback (offscreen in CI: `QT_QPA_PLATFORM=offscreen`).
2. Open PNG/JPG → single-canvas preview updates when moving threshold/pixel/method/palette/brightness/ratio. Hold "Hold to compare" (or Space) shows ORIGINAL; release returns to result. CUSTOM PALETTE loads named palettes as editable swatches (dirty shows "(Custom)"); 🎲 generates harmonious ramps.
2b. VIDEO mode: animated preview plays (Draft 720p default); switching to Full (doc) re-renders bigger; FPS change does NOT re-render (only retimes).
3. Preset saves, reloads and applies sliders (incl. grade/texture/glitch + canvas W/H + anim).
3b. CANVAS → ratio presets fill W/H; typing W/H flips Ratio to Custom. "Adjust crop..." opens the visual editor (frame + grid, drag pans, wheel zooms, Rotate/Reset/ratio/mode incl. Custom with free frame); Done applies, Cancel keeps values.
4. Export dialog generates `<base>.png|jpg|webp` at the canvas W×H + optional `*_thumb1080p`, `*_vector.svg`, `*_gif.gif`, `*_vid.mp4`, `*_metadata.json` in the chosen folder (no size spin: size comes from CANVAS).
4. `*_thumb1080p` opens directly in TRAKKOUT with no odd cropping.
5. `build_exe.py` produces a portable `dist/TRAKKART.exe` that starts on double-click.
5b. Release extras: `build_installer.py` builds the Inno Setup installer (needs `dist/TRAKKART.exe` + ISCC); session smoke = open image → close → reopen restores it; Edit → Redo (Ctrl+Y) after Undo; Settings Export…/Import… round-trips the JSON; Settings → Extras shows accel/MP4 state (all included in the exe); F1 opens MANUAL.md; Help → Show logs folder reveals data dir.

## Perf (manual, before release)

- Floyd B&W 3000px < 30s, Floyd color 1080px < 12s (measured in dev with `tools/bench.py` if present).
- If Floyd color gets close to the limit, raise the preset `pixel_size` before touching the algorithm.
- Video preview: 6 mix frames at Draft 720p < 1s; Full-doc render may take seconds on ED presets (background thread, debounced) — expected, not a freeze.
- GIF exports at canvas size: check the `~MB` plan estimate in the export dialog before writing 12f 3000px+ GIFs.
