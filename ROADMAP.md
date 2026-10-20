# TRAKKART — Roadmap

> Context for continued development. Single source of truth for state and next steps.

## 1. Vision

TRAKKART = offline dither cover generator for beatmakers, part of the ShardBeats TRAKK family.
Flow: `Image → method + palette + pixel + threshold → preview → bundle → TRAKKOUT`.

Family style: offline-first, portable `.exe` (`data/` next to the exe), PySide6 + Pillow + numpy, MIT with original code (do not copy GPL from dither-guy / Dither Boy).

## 2. Current state — v0.17.0 (done)

- `app/dither.py`: `ordered_bayer` (4x4/8x8) + `floyd_steinberg` (B&W and palette), `apply_method()`, `pixel_size`, `threshold`. Only numpy + Pillow.
- `app/palettes.py`: `BW / SLIME / VAPOR / EMBER` originals. `get_palette()`, `palette_names()`.
- `app/presets.py`: `Preset` + `save/load/list/delete` + `ensure_bundled()` (never overwrites). 4 bundled: `SLIME_FS`, `VAPOR_BAYER8`, `EMBER_BW`, `CRT_HARD`.
- `app/batch.py`: `batch_process()` with `skip_existing` + `progress_cb`. Exts: png/jpg/jpeg/webp/bmp.
- `app/exporter.py`: export with user size (long side, presets 960–4096) + format (PNG/JPG/WebP) → `<base>.<ext>` + optional 1080p thumb over blur (ready for TRAKKOUT).
- `app/ui/main_window.py`: PySide6, original vs dither preview, combo presets + save, batch with `BatchWorker` + progress bar.
- `app/ui/workers.py`: `BatchWorker(QThread)` with `progress/finished/error` signals.
- `app/pipeline.py`: `render()` + `meta_dict()` — single entry point for UI and batch (adjust → dither → text).
- `app/paths.py`: portable (`TRAKKART_DATA_DIR` / frozen `data/` / `%APPDATA%/TRAKKART`). `app/history.py`: SQLite export history (logged on UI and batch export).
- Vectorized Floyd by rows: B&W 960px 1.5s→0.8s, color 480px 4.0s→0.9s. Custom icon (`tools/make_icon.py` → `icon.ico`, used in window and exe).
- `app/canvas.py`: ratios 1:1/4:3/3:2/4:5/16:9/9:16, crop cover (X/Y focus) / contain, clamp. Export per ratio (long side 3000/960) + 1080p thumb contain over blur.
- `app/kernels.py`: generic ED (floyd/atkinson/burkes/sierra) + ordered bayer16/cross/bluenoise custom and deterministic. 9 methods in `METHODS`.
- `app/fx.py`: pre (blur/sharpen/hue/denoise/smooth) + post (glow/grain/vignette/scanlines) + replace-color + custom palette. Pipeline: canvas→pre→adjust→dither→brand→post→text.
- `app/kernels.py`: generic ED (floyd/atkinson/burkes/sierra/jjn/stucki/stevenson/shiaufan/filterlite/sierralite/sierra3) + Hilbert-ordered diffusion. Ordered: bayer2/4/8/16, halftone, cluster, pattern, checker, ign, cross, bluenoise. 23 methods in `METHODS`.
- `app/vector.py`: grid re-render + RLE + SVG (no post-fx, transparent background, size estimate). Flag in preset + UI checkbox.
- `app/ops.py` (rotate/flip/invert + undo cap 20) + `app/glitch.py` (chromatic aberration + slice shift). Menus, zoom, dnd, clipboard, randomize, preset share via file.
- Quality: 170 tests, 30/30 Gherkin, 5/5 gates PASS (coverage 87.7%, clean flake8).
- Base: `main.py`, `requirements.txt` (PySide6/Pillow/numpy), `start.bat`/`run.bat`, `build_exe.py`, `README.md`, `LICENSE` MIT.

## 3. Roadmap

### v0.2 — Presets + batch (done)
- [x] JSON presets in `presets/` (`save/load/list/delete`): stores method + palette + pixel + threshold + name.
- [x] Bundled presets: `SLIME_FS`, `VAPOR_BAYER8`, `EMBER_BW`, `CRT_HARD` (pixel 3-4 + high threshold).
- [x] Folder batch: `input/*.png|jpg → out/<base>.<ext>` (+ thumb/vector/gif/meta) with the active preset. Progress bar with fps/ETA, skip if exists.
- [x] `QThread` worker for batch (no UI freeze). Custom implementation.
- [x] Tests: JSON preset roundtrip, batch over 3 temp images. Gherkin 10/10, gates 5/5.

### v0.3 — Pre-dither adjustments + text (done)
- [x] Pre-processing: brightness / contrast / saturation (`app/adjust.py`, Pillow `ImageEnhance`, no OpenCV).
- [x] Text layer: centered title top/bottom (`app/text.py`, safe font with fallback). `Prod. by` + beat name.
- [x] Export includes `metadata.json` in the bundle (method, palette, pixel, threshold, adjust, title, date, version).
- [x] Single `render()` pipeline used by preview, export and batch. Extended presets (compat with v0.2 JSONs).
- [x] Tests: text does not crash without font, valid metadata. Gherkin 12/12, gates 5/5.

### v0.4 — Quality + portable (done)
- [x] Vectorized Floyd by rows (B&W 2x, color 4.4x). API intact, valid output.
- [x] `TRAKKART_DATA_DIR` + portable `data/` + `%APPDATA%/TRAKKART` (`app/paths.py`).
- [x] SQLite export history (`app/history.py`, family pattern).
- [x] Custom icon + `build_exe.py --icon` verified (`dist/TRAKKART.exe` 65.7 MB, windowed one-file). Clean `flake8`.
- [x] QA: manual perf (B&W 3000px ~8s, color 1080px ~5s).

### v0.5 — Canvas and crops (done)
- [x] Preset ratios: 1:1, 4:3, 3:2, 4:5, 16:9 and 9:16, stored in preset (`ratio` + `crop_mode` + focus).
- [x] Crop UI: ratio/mode combo + X/Y focus sliders (cover) / contain with bars.
- [x] Pipeline honors ratio; export per ratio and size (9:16 @3000 → 1688x3000).
- [x] YT thumb 1920x1080 contain over blur for any ratio.
- [x] Exact-dimension tests + clamp + 2 Gherkin scenarios (15/15).

### v0.6 — More dither engines (done, original code)
- [x] Extra error-diffusion: Atkinson, Burkes, Sierra-Lite (`app/kernels.py`, generic row-vectorized engine).
- [x] Extra ordered: 16x16 Bayer (generated by recursion), crosshatch (custom sines), blue-noise (custom RNG with seed, deterministic).
- [x] 9 methods in UI without breaking old presets (bayer4 fallback). Gherkin 17/17.

### v0.7 — Finish: effects and custom palette (done, original code)
- [x] Pre: blur / sharpen (Pillow).
- [x] Post: glow (screen-blend), grain (fixed seed), radial vignette, scanlines every N rows.
- [x] Replace-color: dither white → brand color (UI picker, stored in preset).
- [x] Custom palette in UI (pick N colors, stored inside the preset). Gherkin 19/19.

### v0.8 — Engines II: halftone, cluster and more diffusion (done, original code)
- [x] Ordered: halftone (variable dot), clustered-dot, diagonal pattern, 2x2 bayer (+ existing ones).
- [x] ED: Jarvis-Judice-Ninke, Stucki, Stevenson-Arce (standard tables into the generic engine).
- [x] Pre: hue rotate + denoise/smooth (Pillow, no OpenCV). Gherkin 21/21.

### v0.9 — Vector SVG for logos/merch (done, original code)
- [x] `app/vector.py`: cell-grid re-render WITHOUT post-fx + brand + text, RLE by rows, transparent background.
- [x] Flag in preset (`vector_export`, `vector_cell` 4-16) + UI checkbox with size estimate and >2MB warning.
- [x] Batch includes SVG if the preset asks for it; `metadata.json` logs bytes. Gherkin 22/22.

### v0.10 — Cover flow + glitch pack (done, original code)
- [x] Image ops with undo (rotate left/right, flip H/V, invert), history cap 20.
- [x] Randomize ("Surprise me", Ctrl+R) + zoom (in/out/fit/100%) + drag&drop + clipboard (Ctrl+C/V).
- [x] Glitch pack: chromatic aberration + slice shift (numpy, deterministic).
- [x] Offline preset share: export/import `.json` + File/Edit/View menus. Gherkin 24/24.

### v0.11 — Fast engine (optional, portable-safe) (done)
- [x] Optional numba accelerator with bit-identical parity (`app/accelerate.py`, numpy fallback). Base exe without numba.
- [x] Multiprocess batch (`jobs`, default 1, `freeze_support` in frozen). Jobs spinner in UI.
- [x] `tools/bench.py` (B&W 960px: 0.8s→0.01s; color 960px: ~4.6s→0.02s). Gherkin parity 25/25.

### v0.12 — Animated GIF for socials (Pillow only, no ffmpeg) (done)
- [x] Frames with Bayer phase offset + hue cycle (`app/gif.py`, phase/hue/both modes), `save_gif` with optimized palette.
- [x] 480px long-side cap, 2-8 frames, flag in preset + UI checkbox. Batch includes it.
- [x] Gherkin 26/26.

### v0.13 — TRAKK family UI (done)
- [x] Custom `app/ui/theme.qss` with family tokens (bg #151617, amber accent #F5A623, Segoe UI).
- [x] Panel reorganized into QGroupBox sections with scroll + header + primary button + statusbar + preview with titles and dims.
- [x] Quick-ops row (rotate/flip/invert/undo/random) instead of hiding them in menus only.

### v0.14 — No text layer (done)
Text layer removed (not pulling its weight): out of pipeline (`app/text.py` deleted), presets (`title/title_position` fields out, old presets with title still load), UI (TEXT section out) and batch/gif/vector.
- [x] `metadata.json` without `title`. Gherkin 26/26, gates 5/5.

### v0.15 — Anti-freeze hardening (done)
Security/stability audit: blocking renders, decompression bomb, giant SVG, batch without cancel, unbounded history.
- [x] Size guard (`app/safety.py`: max 8000px / 50MP, header-first without decoding) in UI and batch.
- [x] 350ms preview debounce (family style): sliders no longer freeze the UI.
- [x] Batch cancel (flag + button) in sequential and multiprocess; fallback to sequential if the pool fails to start.
- [x] Vector cap (160k cells) before rendering + history prune (cap 500). Gherkin 28/28, gates 5/5.
- [x] Layout fix v0.15.1: fixed action bar outside the scroll (export always visible), no horizontal scroll, minimum widths.
- [x] DnD v0.15.2: amber highlight on drag + dropping a folder = direct batch.
- [x] Web drop v0.15.3: drag from the browser (http URLs + image data, e.g. WhatsApp Web) with download capped at 40MB and type validation.

### v0.16 — Safe drop with ON/OFF (done)
Root cause of the WhatsApp bug: `Path("")` == `Path(".")` -> `is_dir()` True + unhandled `blob:` URLs = batch over its own folder with no warning.
- [x] `app/dnd.py`: pure classification (http/data/blob/local/ignore). Strict validation: only existing absolute paths.
- [x] `chk_batch_drop` toggle (default OFF) + confirmation dialog (N files, preset, output) before processing.
- [x] Inline `data:image/...` support + hints for blob:/unknown. Gherkin 30/30.

### v0.17 — Lock-free preview + valued sliders (done)
- [x] `PreviewWorker` (QThread) with tokens: without numba and with a large image, preview renders at 640px on a thread; fast sync otherwise.
- [x] `ValueSlider` with visible value + double-click reset on every slider; export always full-res.
- [x] Gherkin 30/30 (suite 170), gates 5/5.

### v1.0 — Standalone release
TRAKK apps 100% standalone: no TRAKKOUT/TRAKKNAME bridges or shared naming. Each app lives on its own.
- [ ] EN docs + screenshots (before/after, sample GIF) + GitHub release `shardbeats/TRAKKART`.

## 4. Decisions made (do not reopen without reason)

- 100% original MIT code. dither-guy is GPL-3.0: ideas only, never copy files.
- No OpenCV / GPU in the core. Numba only as an OPTIONAL accelerator with numpy fallback (the base exe does not include it).
- Pillow + numpy is enough and keeps the `.exe` light.
- PySide6 UI (not PyQt6). Preview with `QLabel + QPixmap`, no `QGraphicsScene` in v0.
- Original palettes, not 1:1 GameBoy/C64/NES clones.

## 5. Known tech debt

- Tests use `get_flattened_data()` (Pillow ≥10). Downgrading Pillow will break them.
- `floyd_steinberg` color at 3000px is still slow (~45s numpy); with numba <1s. The real flow dithers at source size.
- Multiprocess batch in loose scripts requires the `if __name__ == "__main__"` guard (Windows spawn); without it there is automatic fallback to sequential.

## 6. Out of scope (for now)

- Video (`imageio-ffmpeg`), webcam, YouTube upload, BPM/key analysis with torch/librosa, login/cloud.
- Bridges to other apps (TRAKKOUT/TRAKKNAME) and shared naming: each TRAKK app is standalone.
- Explicitly rejected (seen in Dither Boy / dither-guy, adds nothing): GPU backends (cupy/opencl), video tab, app themes, preset download from GitHub (offline file share instead). Vector export IS in (v0.9, custom rect-only SVG).
