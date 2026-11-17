# TRAKKART — Roadmap

> Context for continued development. Single source of truth for state and next steps.

## 0. Handoff — continue in another session (nov-2026, historical)

- State: `main` at `64e5d0c` (CI fix: portable `cwd` in `test_accelerate`/`test_cli`, no hardcoded local path). Real suite: 572 collected (440 fast + 132 slow, last report: 571 passed / 0 failed) + 61 Gherkin scenarios; `tools/quality_metrics.py` requires 61. Docs synced (README/MAINTENANCE/QA). Last block: closed loop (`dissolve_loop`),
  equal holds, 1080p/720p MP4 + honest estimate, live dialog vs stale
  prefs, 60s Length via streaming; docs in CHANGELOG Unreleased + QA
  v1.15 + MANUAL; unimplemented research in §7.7 (morph modes) and §8.
- Verify on open: `git log --oneline -3` and
  `.venv\Scripts\python -m pytest tests -q -p no:cacheprovider --no-cov -m "not slow" -n auto`
  (green) + `flake8 app tests tools main.py build_exe.py build_installer.py`
  (clean). Venv: local `.venv`. CI uses
  `QT_QPA_PLATFORM=offscreen`; pin `pytest<9.2` for pytest-bdd (see
  MAINTENANCE.md: do not lift without a pytest-bdd upgrade).
- Open threads: (1) dead Hold slider when Length dominates — RESOLVED with
  Hold-manda: total = transitions + holds, derived Length (readout, no
  spin); `dissolve_length` stays as ignored compat. (2) Loop default True only
  matters with an in-session chain; tests current. (3) R5+R6 done. (4) R1+R2+R3
  done (CANVAS_916 + Canvas check + BPM->Hold).
- Recommended next step: **R7 (WebP) or R9 (separations)** depending on
  social vs print pull; or morph F1 (§7.7).

## 1. Vision

TRAKKART = offline cover art studio for beatmakers, part of the ShardBeats TRAKK SUITE.
Flow: `Image → method + palette + pixel + threshold → preview → bundle → TRAKKOUT`.

SUITE style: offline-first, portable `.exe` (`data/` next to the exe), PySide6 + Pillow + numpy, MIT licensed, original code.

## 2. Current state — v0.18.0 (done)

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
- `app/ops.py` (rotate/flip/invert + undo cap 20) + `app/glitch.py` (chromatic aberration, slice shift, pixel sort, wave, datamosh + RGB grille). Menus, zoom, dnd, clipboard, randomize, preset share via file.
- Quality: 375 tests, 51/51 Gherkin, 5/5 gates PASS (coverage 92.1%, clean flake8 on `app` + `tests`).
- Base: `main.py`, `requirements.txt` (PySide6/Pillow/numpy), `start.bat`/`run.bat`, `build_exe.py`, `README.md`, `LICENSE` MIT.
- Session v1.1→v1.5 (done): Color Pro (SOURCE/auto-extract/depth/lock-shuffle/mid-high/` .json`/`.gpl` share); stackable FX (`fx_stack.py` + `fx_jpeg.py`, reorderable `+` UI); 36 engines (`ordered_maps.py`, CMYK/ASCII/edges/Motif, Vector Pro black/lossless, method arrow-stepping); motion from stills (GIF modes + `motion_amount` + loop-clean march + Signal Drift + Paste-Up + MP4 opt-in, timeline layers + clip import trimmed as out-of-scope); Iteration UX (viewport Full/Live/Still, fast/slow debounce, tutorial + samples, 4 themes, batch already in File menu).
- Originality pass (done): Motif/Halo/Signal Drift/Paste-Up renames, zero competitor mentions in code/UI/docs/features; decision logged in §4.
- Bug-hunt fixes (done): panel horizontal clipping (726→440px vs 452px viewport, `hlab`/`tight` helpers + layout audit + `test_layout.py`), eaten video-proxy combo items restored, stale v0.17.0 title → v0.18.0, clip-dialog `load_pil` import, crop-editor W/H setter crash, Windows-drive `classify_drop`, idempotent `set_theme` (startup O(n²) → flat).
- Quality: 375 tests, 51/51 Gherkin, 5/5 gates PASS (coverage 92.1% incl. pragmas only for numba-nopython bodies + env-missing branches, clean flake8 on `app` + `tests`).

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
- [x] SQLite export history (`app/history.py`, SUITE pattern).
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

### v0.13 — TRAKK SUITE UI (done)
- [x] Custom `app/ui/theme.qss` with SUITE tokens (bg #151617, amber accent #F5A623, Segoe UI).
- [x] Panel reorganized into QGroupBox sections with scroll + header + primary button + statusbar + preview with titles and dims.
- [x] Quick-ops row (rotate/flip/invert/undo/random) instead of hiding them in menus only.

### v0.14 — No text layer (done)
Text layer removed (not pulling its weight): out of pipeline (`app/text.py` deleted), presets (`title/title_position` fields out, old presets with title still load), UI (TEXT section out) and batch/gif/vector.
- [x] `metadata.json` without `title`. Gherkin 26/26, gates 5/5.

### v0.15 — Anti-freeze hardening (done)
Security/stability audit: blocking renders, decompression bomb, giant SVG, batch without cancel, unbounded history.
- [x] Size guard (`app/safety.py`: max 8000px / 50MP, header-first without decoding) in UI and batch.
- [x] 350ms preview debounce (SUITE style): sliders no longer freeze the UI.
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

### Unreleased (post-v0.17)
- [x] Named palette library (`palettes/*.json`, editable swatches, dirty "(Custom)" state, random Oklch generator ramp/harmony).
- [x] Pro export: size presets + PNG/JPG/WebP, per-dialog outputs, overwrite policies, quick export with prefs.
- [x] FX packs: GRADE (duotone/posterize/split-tone/fade/glow threshold), TEXTURE (halftone/dust/border/letterbox), GLITCH+ (pixelsort/wave/mosh/grille) in 3 panel groups.
- [x] 7 new engines (shiaufan/filterlite/sierralite/sierra3, ign, checker, hilbert). 23 methods, 35/35 Gherkin.
- [x] GIF overhaul: modes `phase/hue/both/glitch/mix`, 2–24 frames, 2–60 fps, ping-pong, anim at canvas size, shared 128-color palette (no per-frame flicker), deterministic seeded post-fx.
- [x] Video mode: full-canvas animated preview (QThread worker + tokens) with play/pause/scrub, Draft 720p / HD 1080p / Full proxy tiers — export always full-doc. FPS changes retime only (no re-render).
- [x] Single canvas + hold-to-compare (button or Space shows ORIGINAL); export GIF preview removed from the dialog (lives in VIDEO mode).
- [x] Free Custom canvas (editor-style): `Custom` ratio + free W×H (presets refill W/H, typing flips to Custom); `cover/contain/stretch/blur` honor free aspect; old presets migrate via `ratio+export_size`.
- [x] Single doc + single anim: CANVAS owns size, VIDEO owns animation (no duplicated size/GIF controls in dialogs).
- [x] Grille `every=2` crash fixed (mixed bool+list fancy index).
- [x] Refactor: `main_window` 1686→~700 lines (8 controllers + assembly + menus); `FIELDS` preset schema; `BINDINGS` widget table; `RenderSpec` single ~40-param dataclass; unified exporter writer (legacy kept byte-identical). 281 tests, 38/38 Gherkin, gates 5/5.

### v1.0 — Standalone release
TRAKK apps 100% standalone: no TRAKKOUT/TRAKKNAME bridges or shared naming. Each app lives on its own.
- [ ] EN docs + screenshots (before/after, sample GIF) + GitHub release `shardbeats/TRAKKART`.

### v1.1 — Color Pro (done)
Gap: auto-extracted palettes, depth control, lock/shuffle per swatch, Source category.
- [x] Auto-extract palette from image (`app/palette_extract.py`: median-cut numpy-only, N=2..16, deterministic seed) + "From image" button.
- [x] `Source` palette mode: keeps the original color as an editable starting point (no re-map to BW/SLIME).
- [x] Depth slider: number of levels/steps used from the palette (pre-dither mapping, lives in `RenderSpec` + `FIELDS`).
- [x] Per-swatch lock + shuffle + per-adjust lock/randomize (UI en palette dialog + Adjust row).
- [x] Midtones/highlights adjust (in addition to brightness/contrast/saturation) in `app/adjust.py` + UI.
- [x] Palette import/export/share `.json`/`.gpl` offline (same UX as preset share). Gherkin 40/40.

### v1.2 — Stackable FX (done)
Gap: fixed pipeline `canvas→pre→grade→dither→brand→post`; goal is add-with-`+` and reorder.
- [x] FX stack model: ordered list `[{id, enabled}]` in `Preset` + `RenderSpec.fx_stack` (migration: old presets → equivalent stack, identical render).
- [x] UI: ADD effect (`+` combo), reorder up/down, enable/disable, granular sliders per effect (halo glow, jpeg-glitch, chroma, blur/sharpen as post).
- [x] JPEG Glitch effect (`app/fx_jpeg.py`: Pillow recompress quality/blocks/chroma-subsampling, numpy-only, deterministic with seed).
- [x] Halo glow designed for dither (threshold + screen blend already existed → promoted to a stack effect).
- [x] `render_spec` runs the stack in order (commutativity tests: reorder changes output). Gherkin 42/42.

### v1.3 — Engines III + print (done: 23→36 + CMYK/vector-pro)
Gap: grow the roster (glitch + special + pattern/ordered extras + CMYK + ASCII + custom Motif builder).
- [x] 13 new engines: granular `bayer32/lines/columns/diag/grid` + glitch-dither `white_noise/blocks/scan_bayer/wave_map` + special `cmyk/ascii/edges` + `motif`. 36 methods.
- [x] ASCII mode (`app/ascii.py`: charset ramp, Pillow-only, animatable via `phase`, vector-compatible via rects).
- [x] Motif: custom pattern builder (`app/motif.py`: 4 bands -> shape/size, 6 shapes, stored in preset as dict). Simple MOTIF panel.
- [x] Vector Pro: black-vector print (`vector_black` + `ink_only`, no paper rects) + lossless toggle (force PNG on export/batch) + calibrated estimate (~58B/cell). Embroidery OUT.
- [x] Arrow-stepping (buttons + Alt+Left/Right, cyclic `step_method`) + Gherkin 45/45.

### v1.4 — Motion from stills + signal drift (done, trimmed)
Animation always runs over the still image (GIF modes + drift + phase).
Timeline layers and clip import were cut on purpose (Oct 2026 trim):
they added a model + locks + file pipeline far from the core job
(dither stills, make videos OF those stills).
- [x] MP4 video export (`imageio-ffmpeg` ONLY as an opt-in extra at the time — video ships in the base exe/requirements since v1.0; clear fallback message when missing). Same frame→dither→stack pipeline, shared anti-flicker palette.
- [x] Signal Drift: 9 animated retro-screen noise patterns (`app/drift.py`, seeded, deterministic, works with any method). UI lives in VIDEO (pattern + amount).
- [x] Paste-Up (image/texture overlay with blend + opacity, in-app, e.g. paper grain / riso dust) as `pasteup` FX stack item (neutral when off).
- [x] Gherkin 51/51 (drift determinism + paste-up neutral + motion freeze + backend-missing skips clean).
- [x] Motion legibility pass (post-v1.4, option A+E): mode names + one-line descriptions in UI, `motion_amount` 0–3 (`1.0` = legacy bytes, `0` = freeze), ED-march compat hint with one-click `bayer8` switch, loop-clean march (full matrix period per loop). No engine change besides the march step.

### v1.5 — Iteration UX + content (done)
- [x] Viewport mode selector Full/Live/Still (`app/viewport.py`: 0ms / 120ms-fast-350ms-slow / F5-only + statusbar label + View menu).
- [x] Fast path: core adjusts (brightness/contrast/sat/mid/high) refresh at 120ms in Live; blur/denoise marked "(heavy)" in tooltips + background worker (`is_heavy_preset`).
- [x] In-app tutorial (`Help → Quick tour`, 5 steps, first-run once + `data/samples/` pack generated offline) + batch menu entry verified (File → Batch folder Ctrl+B since v0.2, no duplicate menu).
- [x] App themes (Dark/Light/Handheld green/Pink) via single-source token swap over `theme.qss` + View menu radio. Gherkin 50/50.

### v1.6 — Dither-boy particle disperse, dispersion only (done)
Scope frozen: single-image disperse/reassemble loop (no A->B morph yet).
Style: offline, Pillow+numpy only, deterministic seed, strict 0=off, loop-perfect.
- [x] Phase 1 (done): `app/disintegrate.py` + unit tests (wind vs random, deterministic seed, dissolve 0 = identity).
- [x] Phase 2 (done): `gif_dissolve_frames()` + manual GIF/MP4 export.
- [x] Phase 3 (done): preset fields (`dissolve_*`) + 2 bundled presets (`ASH_WIND`, `DUST_RANDOM`).
- [x] Phase 4 (done): docs (`QA.md`, `tools/quality_metrics.py` gates, `MANUAL.md`) + closeout.
  Note: gates stay at 52 Gherkin (no new scenarios; unit-covered); suite 438 -> 450.

### v1.7 — Morph A->B + UI dissolve (done)
Scope: swap between two images via shared particle cloud + MOTION controls.
- [x] Phase 5 (done): `morph_frames()` + `gif_morph_frames()` + tests.
- [x] Phase 6 (done): MOTION UI (dissolve/morph mode, second image) + export + docs.
  Modes `dissolve`/`morph` in `GIF_MODES`; `gif_frames(img_b=...)` dispatch;
  preview/export/batch share the path; strict 0=off holds.

### v1.8 — Morph chain (up to 6) + MORPH page (done)
Scope: A->B->C... playlist (A = src + up to 5) with Add/Remove/Up/Down list;
dissolve+morph controls moved from MOTION to their own MORPH page.
- [x] Phase 1 (done): `morph_chain_frames()` + `gif_morph_frames(list)` + tests.
- [x] Phase 2 (done): MORPH page + playlist UI (moved controls out of MOTION).
  `MORPH` page (panels/morph.py) with dissolve params + Add/Remove/Up/Down/Clear list (cap 6: A + 5); `win.morph_list` + `morph_src` alias compat.
- [x] Phase 3 (done): preview/export wiring + docs + closeout.
  Chain flows through `gif_frames(img_b=list)`; preview (`VideoWorker`),
  export (`export_full`) and batch (dissolve fallback) share the path;
  suite 453 -> 457.

### v1.9 — Morph timing: holds + per-leg budget (done)
Research: ImageMagick end-holds (`t==0||t==n-1 ? 150 : 8`), ComfyUI
`still_image_delay_ms`, Pillow per-frame duration list.
- [x] Phase 1 (done): joints `q=j/(nk-1)` + `hold_start/end` in engine + tests.
- [x] Phase 2 (done): budget (min 2/segment, holds fit in 64) + `fps`
  threading + `dissolve_hold` preset + Hold slider + duration with holds + <8f hint.
- [x] Phase 3 (done): suite + docs + closeout. Suite 457 -> 460.

### v1.10 — Morph aspect fit + per-image crop (done)
Mixed-aspect chain: per-image cover-fit with own focus/zoom
(same IMAGE `crop_cover`); A honors the preset canvas. MORPH: per-row
Crop X/Y/Zoom sliders + hint. Suite 460 -> 463.

### v1.14 — MORPH visual crop editor (done)
Crop like IMAGE, not sliders: same CropEditorDialog with the frame locked
to A (ratio/mode/W/H disabled) + Rotate/Reset; writes fx/fy/zoom
(optional rotation) into the selected entry. Suite 465.
Mixed-aspect chain: per-image cover-fit with own focus/zoom
(same IMAGE `crop_cover`); A honors the preset canvas. MORPH: per-row
Crop X/Y/Zoom sliders + hint. Suite 460 -> 463.
### v1.11 — Morph timing: auto-budget as the chain grows (done)
Confirmed v1.9 research from usage: with a fixed total, adding images speeds
each segment up (6f/5 segments = 1f segments showing nothing). New rule:
more images = more time.
- Auto-grow Frames only upward on pick/morph-mode: `max(n, segments*max(8, ~0.8s))`,
  cap 64, announced in status; shrinking the chain touches nothing.
- Hint with f/s per form when a segment drops under 8f or 0.8s.
- Suite 464 -> 465, holds at every joint, Length to 60s.

### v1.12 — 64-frame cap: raise it? (research, not implemented)

Question: the current cap is 64. What would 96/128 cost for longer
or smoother animations? Measured in this repo (720p proxy, 3000px doc):

- RAM (live frames in list): 720p = 2.8MB/f → 64f = 177MB, 128f = 354MB.
  Full-doc 3000px export = 27MB/f → 64f = 1.7GB (already risky today), 128f = 3.4GB.
- CPU (portable exe WITHOUT numba, worst case): 720p ED preview ~1-2s/f
  (64f = 1-2 min threaded, tolerable); full-doc ED export ~10-45s/f
  (64f = 10-48 min; 128f = 20-96 min, unusable).
- GIF: estimated 29MB @64f/720p, 59MB @128f; browsers cut to ~50fps
  real and struggle past 25MB (we already warn in UI). MP4 holds 60fps fine.
- Code: GIF_MAX_FRAMES + ~8 clamps (gif.py, presets, export_prefs,
  dialog_fields, video_controller, params BINDINGS, dialogs) + tests
  asserting 64 + estimate + Length spin (32s).

Key finding: smoothness = fps, not frames (60fps already allowed). Length =
seconds, not frames. Raising the global cap worsens RAM/export without
adding smoothness by itself. What others do: ComfyUI caps transition_frames
at 60; ImageMagick doesn't cap because it streams to disk (we hold
the whole list in RAM for `save_gif`).

Recommendation (not implemented):
1. Do NOT raise the global cap. GIF stays at 64 (format + RAM + 50fps).
2. Long MP4 via streaming: `write_mp4` takes a generator and renders
   lazily (flat RAM); the limit becomes CPU/time, the user's call with
   a weight warning. Would enable ~128f MP4-only.
3. Cheap length without extra frames: pingpong (doubles effective duration),
   drift loops (repeat motion) and holds (already implemented) — zero RAM.
4. If smoothness is asked for: 30-60fps already exist; teach via Hold/duration UI
   instead of more frames.


### v1.13 — Sacred total duration (done)
Frames/fps stopped ruling: the requested duration was silently clipped
(8s @ 24fps → 2.7s by the 64 cap). New rule: Length (s) is sacred,
frames/fps are quality.
- [x] Phase 1 (done): plan_dissolve (min 2/segment, holds fit in 64, pad
  to total, cap 256) + fps threading in gif/export/batch/video.
- [x] Phase 2 (done): dissolve_length preset + meta/import roundtrip, linked
  Length spin, dissolve/morph-only fps re-render, honest label with
  hold and per-segment hint, 256 cap with warning. Suite 464 -> 465. Follow-up: holds at every inner joint (each form reads), Length 0.5-60s, 256 total cap.

### v1.15 — Closed loop + equal holds + honest MP4 + live dialog (done)
- Loop: `dissolve_loop` (preset, default True) + MORPH "Loop (last → first)" checkbox; closing leg with A's exact still/coords (byte-identical joint); holds: equal share per form with A split across open/close; ping-pong skipped when the loop is closed; budget/hints count the extra leg.
- MP4: streaming to 60s (3600f, O(1) RAM), MP4 size Canvas/1080p/720p (default 1080p, stills full-doc), content-aware estimate (trans 0.43 / hold 0.011 B/px, x264-calibrated) + >100/400MB warnings.
- R5+R6: `mp4_dims` always even + `macro_block_size=2` (exact 1080x1920, 721→720) + `-movflags +faststart` in both writers.
- Hold-manda: total = transitions + holds (no Length pad); Length becomes a derived readout (read-only spin); `dissolve_length` stays as ignored compat; holds only yield to the cap (transitions rule).
- Equal holds: the Length pad splits across every form (≤1f apart) instead of all going to the last; `hold_joint` takes a per-joint list end to end.
- Export: animation spec always comes from the live VIDEO section; stale prefs can no longer smuggle a morph mode into a mix export; session chain only feeds dissolve/morph (export + preview).
- New tests: loop opens/closes on A, hold shares, MP4 estimate, live dialog vs stale prefs, per-mode gate (+7).

### vNext — SP-404MKII image export (done in v1.5.0, spec kept for reference)
Goal: make TRAKKART the fastest way to put custom art on a Roland
SP-404MKII (startup logo + screensaver). Source: Roland's official
"Ultimate Guide: Customizing the SP-404MKII" (articles.roland.com).
- Device spec: OLED 128x64 mono. `.BMP` 1/4/8/24-bit, EXACT 128x64 px
  (anything else is silently ignored). Names are fixed: `startup_1.bmp`
  + `startup_2.bmp` (2 max), `screen_saver_1.bmp` … `screen_saver_16.bmp`
  (16 max per project).
- Install path (user-side, no code): SD formatted on-device, UTILITY >
  SYSTEM > Scrn Saver Type = Custom, export project to SD
  (SHIFT+PAD 14), copy BMPs to `EXPORT/PROJECT/PROJECT_XX/PICTURE`,
  reimport project. White-on-black reads like the stock images.
- Fit: TRAKKART Custom canvas already allows 128x64 (MIN_DIM 64);
  BW dither engines are the ideal source for a 1-bit OLED. Gap is only
  BMP export: `exporter.py` writes png/jpg/webp today (reads BMP fine).
- Plan: (1) `bmp` 1-bit writer (`app/sp404.py`: cover-fit + luminance
  cut, no re-dither, optional invert); (2) locked `128x64 SP-404` canvas
  button (2:1) for WYSIWYG framing + View "SP-404 OLED preview" toggle
  (display-only 1-bit, threshold = DITHER slider); (3) export-dialog
  checkbox writing one `{base}_sp404.bmp` (user renames/organizes);
  (4) tests (1-bit 128x64 BMP, dialog, preview, service) + hardware QA
  by owner (copy > import > watch).
  Shipped in v1.5.0 as a single `{base}_sp404.bmp` (no multi-file pack
  per owner request); live OLED preview + canvas button included.
- Out of scope: the SP-404MKII desktop-app background/slideshow (takes
  plain PNGs, already exportable today).

### v1.7 — True AVC datamosh + segment timeline (done)
Inspiration: browser datamosh editors that work at codec level (single
keyframe + dropped/repeated P-frames = real motion bleed). TRAKKART's
mosh is pixel-procedural on stills; this adds the real codec technique
as a new engine, offline, behind the existing opt-in `imageio-ffmpeg`
extra (per §4: never in the base exe).
- Phase A — codec-flavored modes in `app/mosh.py` (done, house style):
  `bleed` (directional echo blend), `hold` (frozen P-frame bands) and
  `tear` (macroblock band rolls) join the 7 legacy flavors with the same
  rules: `(img, amount, seed, size)`, strict 0=off, deterministic, Pillow
  + numpy only. `MOSH_MODES` drives the DATAMOSH combo, the FX stack
  entry and GIF mix, so the new modes animate and stack with zero extra
  plumbing; old presets keep rendering byte-identical (unknown modes
  still fall back to `blocks`). The single-keyframe re-encode stays a
  future MP4-writer option behind the Phase C encoder select, not an
  effect.
- Phase B — segment timeline (done): morph legs are `Segment{name, leg,
  start, end, repeat}` in `app/anim/plan.py` (`plan_segments` windows from
  the exact `leg_transitions` split, repeat >= 1); `iter_morph_chain` /
  `morph_chain_frames` take `repeats` (deterministic recompute, O(1) RAM,
  all-1 byte-identical incl. the loop leg); entries carry `repeat`
  (session-only, like fx/fy/zoom); MORPH page has a per-leg Repeat ×1-8
  spin; `planned_total` counts repeats in total + Length readout;
  preview/GIF/MP4 inherit via chain entries. Pinned by
  `tests/test_segments.py`.
- Phase C — export hygiene (done): "Reprocess" guard + libx264-only MP4.
  `app/anim/fingerprint.py`: `clip_fingerprint()` over source thumb +
  preset meta + chain signature + anim spec; VIDEO shows a ⚠ badge +
  one-click Rebuild when `win._video_frames` predate current inputs
  (export itself always re-renders fresh, so MP4s can't go stale).
  MP4 uses the bundled software H.264 encoder only (no hardware
  probing, no selector): one path that works on every machine.
  Pinned by `tests/test_export_hygiene.py`.
- Phase D — docs + gates (done): MANUAL section "Datamosh, segments and
  export hygiene" (10 flavors, Repeat, ⚠ Rebuild, encoder select) + README
  flavor count; QA section with the targeted v1.7 command and the portable
  release checklist. `tests/test_v17_release.py` pins file-level preset
  roundtrip (new fields + old presets byte-identical), repeat determinism
  and frame counts (GIF + streamed paths), and the no-extra path
  (`has_video` False, software-only encoders, clean `VideoBackendMissing`,
  stills/GIF unaffected). Portable rebuilt and smoke-tested offscreen.
- Out of scope: WebCodecs/MediaRecorder (browser stack), BPM-synced cuts.

### v1.8 — Delivery: distro + social + motion presets (planned)

Goal: the export a beatmaker actually ships (distributor-valid, social
sizes, Apple motion) + sharing presets as packs. No engine changes.
- Phase A — distributor-ready: DONE (nov-2026). `DISTRO_3000` bundled
  preset (1:1, 3000px, JPG q90) + `app/distro.py` validator (session +
  file, honest hints in the dialog) + TIFF still extra (LZW,
  resolution tags) + DPI plumbed (dialog spin 72–600, tags on
  JPG/PNG/TIFF + separations + metadata, prefs persist).
  Pinned by `tests/test_distro.py` (validator cases, TIFF roundtrip,
  DPI tags, preset recipe).
- Phase B — social + motion: DONE (nov-2026). One-click Social pack
  from the same render (`{base}_social_yt/_916/_11`: 1280×720 +
  1080×1920 center-anchored + 1080×1080, same format, grid-crop note);
  `APPLE_MOTION` presets (1:1 4000px + 3:4 2250×3000 tall, dissolve
  loop, first frame = still, loop-perfect by construction; new `3:4`
  ratio); text safe-area helpers (title top/bottom bands + 1:1 grid
  rows, display-only, `paint_text_guides`).
  Pinned by `tests/test_social.py` (pack stems, sizes, anchor math,
  preset recipes, safe-area rows). Utility verified on a real render
  (subject preserved in all three sizes) — kept.
- Phase C — preset-pack share: export/import zip (presets + palettes,
  offline file, no network); batch "bundle as ZIP" (stdlib zipfile,
  same helper as the v2.0 frame ZIP); keep single-JSON share intact.
  DONE (nov-2026): File → Export/Import pack (`app/pack.py`, whole
  library + palette library as one offline `.zip` with manifest;
  import validates, never overwrites, rejects traversal). Batch
  "Bundle as ZIP" checkbox (output folder → `<output>_bundle.zip`).
  Pinned by `tests/test_pack.py` + UI roundtrip in
  `tests/test_ui_presets.py`. Utility verified on a real batch — kept.
- Phase D — docs + gates: DONE (nov-2026). MANUAL covers distro
  checklist, social pack, motion presets, TIFF/DPI, batch ZIP and
  packs; full gate green (pytest `not slow` + flake8, EXIT=0).
- Out of scope: tap-tempo/BPM (rejected, owner nov-2026), AV1, auto-update.

### v1.9 — Engine + print + color (planned)

Goal: three named dithering additions, real print-shop flow, color
confidence. Reopens R14 narrowly (see §4): the frozen test updates to
the new exact list, nothing else in the roster moves.
- Phase A — engines: DONE (nov-2026). `ostromoukhov`
  (variable-coefficient ED, error scaled by gray level, clean
  midtones), `dizzy` (IGN threshold modulation, blue-noise-like),
  serpentine toggle for all ED kernels (per-row direction flip, no
  streaks); same rules (0=off, deterministic, numpy+Pillow, bit-exact
  numba parity). Preset field + RenderSpec + metadata + DITHER
  checkbox (ED-only); combo/stack/GIF/batch inherit via
  `apply_method`. Roster 36 → 38. Pinned by `tests/test_dither.py`
  (frozen-list update + per-engine determinism + parity) + UI
  roundtrip in `tests/test_ui_presets.py`.
- Phase B — print-shop: DONE (nov-2026). RISO trap (1px expand for
  misregistration, `sep_trap` export option + prefs, overprint);
  300 DPI separations (export DPI threads into the CMYK LPI calc);
  mirror-wrap third framing (`fit_mirror`, np.pad reflect: bleed
  without smear, beside stretch/blur, `mirror` in CROP_MODES);
  CMYK rosette presets (standard byte-identical / alt / single);
  LPI control tied to DPI (`cmyk_lpi`, cell = dpi/lpi clamp 2–64,
  0 = legacy 8px). Pinned by `tests/test_print.py` (+ trap in
  `tests/test_separations.py`, mirror in `tests/test_canvas.py`,
  UI roundtrip in `tests/test_ui_presets.py`).
- Phase C — color confidence: DONE (nov-2026). Daltonism preview
  (protan/deutan/tritan matrices in `app/color_access.py`, display-only
  like safe areas: View → Daltonism preview, wipe included); palette
  accessibility check (WCAG 2.1 contrast between adjacent inks, ✓/⚠
  low <3:1/BW-collapse <1.5:1 hint on the COLOR strip); Lospec offline
  import (.hex/.txt one-#RRGGBB-per-line + JASC .pal + unified
  `parse_palette_path`, Import accepts .json/.gpl/.hex/.txt/.pal,
  >16 truncates to 16) + curated pack (16 original dark→light ramps
  in `palettes/`, 21 total, all valid + luminance-ordered; NIGHT's 2nd
  ink retuned out of a 1.45:1 collapse). Pinned by new
  `tests/test_color_access.py` (13 tests: anchors, determinism,
  WCAG, reports, all parsers, pack) + Gherkin `color_pro.feature` +1
  (daltonism deterministic).
- Phase D — docs + gates: DONE (nov-2026). MANUAL covers print flow
  (DPI/LPI, trap, rosettes, mirror), daltonism, WCAG contrast and
  Lospec (+ ostromoukhov/dizzy in the DITHER row); QA.md current
  (65/65 scenarios, 738-suite split, gherkin gate at 65, flake8 line
  without the gone `build_exe.py`); one stale v1.8C test caught by
  the gates (`bundle_zip` in `test_batch_dialog_outputs`); 5/5 gates
  PASS + clean flake8. v1.9 closed; next is v2.0 (clip import).
- Out of scope: NeuQuant/Wu re-quantization, blue-noise mask assets,
  JXL (extra dep weight), APNG (candidate v2.x).

### v2.0 — Clip import + timeline (planned, major)

Reverses the "no clip import" rule (owner nov-2026, see §4): stills stay
the core product, but a short clip becomes a first-class *input* that
the existing still pipeline dithers frame by frame. Preview is visual
only (no audio playback in-app); sound joins at MP4 export.
- Phase A — import + timeline: DONE (nov-2026). Open MP4/GIF/WebP clip
  (`app/clip.py`, video extra con `VideoBackendMissing` limpio);
  session-only clip store (cap 120f, 720p proxy); timeline editor
  (MOTION → Clip: info + trim spins + scrub) con preview visual
  fuente (sin audio, sin dither aún). Pinned por `tests/test_clip.py`.
- Phase B — dither: DONE (nov-2026). `dither_clip` /
  `iter_dither_clip` (receta viva por frame, seed = base + índice,
  flicker documentado; reusa `render_spec` + writers GIF/MP4);
  preview ditherizado conmutado en el timeline (caché por receta).
- Phase C — export wiring: DONE (nov-2026). Silent GIF, frame ZIP
  (PNG sequence via stdlib), MP4 with a chosen soundtrack (user
  picks an audio file; ffmpeg mux `-c:v copy -c:a aac -shortest`;
  silent MP4 when no track chosen); preview scrub + Length math
  inherited (FPS spin = trim duration); batch stays stills-only.
  Pinned by `tests/test_clip.py` (zip/mux with-without track).
- Phase D — docs + gates: DONE (nov-2026). MANUAL clip flow
  (MOTION row + Clip section: session input, timeline, dithered
  preview, GIF/ZIP/MP4 + optional soundtrack);
  `tests/test_clip.py` (import caps, determinism, mux with/without
  track, missing-extra) + `features/clip.feature` +2 (dither
  determinism, inclusive trim); QA.md current (67/67, 750-suite
  split, gherkin gate at 67); one stale trim-guard test updated to
  the reversed rule (`test_ux.py`: clip widgets exist, no layer
  model); 5/5 gates PASS + clean flake8. v2.0 closed.
- Out of scope: webcam, audio analysis/BPM, audio trimming/fades,
  in-app audio playback, clips in batch, >120f, 4K clip edit.

### v2.1 — Stabilize (in progress: bug hunt done nov-2026)

No new features until the tree is compact and hunted:
- [x] Bug-hunt test pass (nov-2026): reproduced the reported hard crash
  (`0xC0000409`, no traceback) — a live `QThread` reference was
  dropped by `new_project`, `preview.on_done/on_error` and
  `closeEvent`. Fixed with `app/ui/thread_safe.py` (retire/hold/stop).
  Also fixed: New project now closes the session clip; clip cache
  invalidated on reopen; `nframes=inf` no longer clears the 120f cap
  notice; mux cuts at video length (`apad`+`-shortest` hangs) and
  keeps the silent MP4 on failure; `has_video()` checks the ffmpeg
  binary. Real 2GB clip: import 3.5s → 0.5s after the ffmpeg-side
  scaling, 120f dither 1.05s (~9ms/frame), GIF/ZIP/MP4 valid; clip
  exports now rename instead of overwriting.
  Pins: `tests/test_v21_bughunt.py` (+28) + `tests/test_clip.py` (+3:
  in-point GIF/MP4, VFR normalization) + `tests/test_ui_export.py` (+3:
  clip Export section) + `tests/test_ux.py` (+2: MOTION XOR, clip
  follows still Crop) + `tests/test_ui_render.py` (+1: W×H link;
  suite 792 = 647 fast + 145 slow; Gherkin 68).
- [x] Online research + measurement (nov-2026): proxy downscale moved
  inside ffmpeg (`size=`/`-s` on the reader) instead of decoding native
  frames and resizing in Python: **4K 452MB 12.9s → 1.2s (11x)**, 2GB
  5.4s → 0.5s, 1080p 3.3s → 1.1s, same 720x405 proxy and 120f cap.
  Verified on this build (ffmpeg 7.1): `-ss` before `-i` is
  frame-accurate (frame 10 of 30, gray exact), autorotate already fixes
  phone display-matrix videos (no action needed), `nframes=inf` is
  normal (never call `count_frames`, it decodes the whole file).
- [x] Compact: weight audit (base exe stays light, no OpenCV/GPU in
  core), dead-code sweep, docs sync (ROADMAP/CHANGELOG/MANUAL/QA).
  Findings nov-2026: no cv2/torch/pyav imports anywhere; `moderngl`
  dropped from `requirements.txt` (spike-only + lazy `app/gpu.py`
  fallback — never in the bundle); stale `build_exe.py` references
  fixed to `build_portable.py` (QA + SIGNING); all other hits are
  historical notes. `app/gpu.py` stays (live optional preview path).
- [x] Gates green (5/5 + flake8) before any v2.x candidate starts:
  last run 100% pass (776/778, 2 skipped), coverage 84.9%, Gherkin 68,
  export smoke, no-leak + clean flake8.

Keep/cut from the hunt: kept every fix above (all reproduced, all
pinned); cut nothing. Deferred: clip import/export still run on the GUI
thread, but with ffmpeg-side scaling the 4K import is ~1.2s and the
worker is no longer urgent.

### Candidates v2.x (planned queue, ordered, not scheduled)

House rules for every candidate: offline, Pillow+numpy (+ffmpeg only
where video already uses it), deterministic (seed = base + index
pattern), MP4 stays libx264-only, batch stays stills-only unless the
item says otherwise. Each lands in A/B/C/D phases (engine → UI →
export → docs+gates) with pinned tests, MANUAL + QA.md updates, and
5/5 gates + flake8 before commit. A real-render utility check decides
keep/cut.
1. [x] Clip in-point seek on import (`-ss`) — SHIPPED nov-2026.
   `import_clip(..., start_s)` + "Start at (s)" control next to Open
   clip: `input_params=["-ss", t]` (verified frame-accurate on our
   ffmpeg 7.1) and `im.seek(frame)` for GIF/WebP; clamp to the source
   duration and fail clean past the end. `info` gains `start_s` +
   `source_duration` and `truncated` stays honest (frames left before
   OR after the window). Still session-only, ≤120f, 720p proxy,
   deterministic, no network. Pins: unit (GIF skip, MP4 `-ss`, clamps)
   + Gherkin +1 (68). Real 1080p/38MB: `start=10s` ~1.0s, pixels differ.
2. [x] VFR/timebase normalization on import — SHIPPED nov-2026.
   The MP4 reader always gets `-vf fps=N` (N = rounded source fps,
   clamped 2–60): passthrough on CFR (verified byte-identical), honest
   CFR on VFR (synthetic 30-real-frame file went 57 → 29 reads ≈
   duration × N). `info` fps is the effective rate. Pins: unit (VFR +
   CFR-untouched). No UI change (automatic), no new Gherkin (gate 68).
3. Timeline param envelopes (keyframes/curves/LFO, deterministic).
   Builds on the v2.0 timeline + sacred-Length math: per-clip curves
   for preset params (e.g. motion amount, drift, grain) instead of
   flat values. Session-only curves (like chain crops/repeats), never
   in presets. Pins: `tests/test_envelopes.py` + Gherkin +2.
   DONE (nov-2026): `app/envelopes.py` (flat/ramp/LFO/keys, loop-perfect,
   clamped, `envelopes_signature`) threads through still motion
   (`gif_frames(..., envelopes)`: motion/drift/grain per frame) and clip
   dither (`iter/dither_clip(..., envelopes)`: drift+grain; motion is
   still-motion only). MOTION → Details → Envelopes UI (Off/Flat/Ramp/LFO
   per param, session-only, preset meta untouched); preview fingerprint
   includes the signature (stale ⚠ on curve change); still + clip exports
   re-render with the session curves; batch stays flat.
4. Multi-stop gradient-map FX (DitherEffect survey, mechanics only).
   New GRADE effect: N ink stops over luminance (duotone with more
   stops), post-dither stack item, strict 0=off. Pins: unit + Gherkin +1.
   DONE (nov-2026): `app/grade.py::gradient_stops` (piecewise-linear
   over luminance, <2 valid stops = identity, junk never raises) +
   `GRADIENT_RAMPS` (Ember/Abyss/Acid/Bone); preset/spec/meta carry
   `gradient_stops` (`grade.gradient_map` in JSON); FX STACK id
   `gradient_map` after `fade` (legacy presets byte-identical, off by
   default); GRADE combo + honest label (named ramp, custom N stops,
   or off); pins `tests/test_gradient_map.py` (8) + Gherkin +1
   (fx_stack.feature). Suite 850 (700 fast + 150 slow). Gherkin 77/77.
5. Temporal CRT/VHS motion modes. New GIF modes (scanline roll,
   tracking wobble, chroma bleed over time) reusing the march/hue
   engine; ED-frozen rule respected (post-fx animation only).
   Pins: determinism + Gherkin +1.
   DONE (nov-2026): GIF mode `crt` ("CRT drift") in `gif_frames`:
   phase march (ordered; frozen on ED) + per-frame scanline roll
   (`fx.scanlines_roll`, loop-perfect, 0 == static), traveling-band
   tracking wobble (`glitch.tracking_wobble`, slice knobs), chroma
   bleed (sin envelope), wave reuse; no hue/sheen/mosh. Strict 0=off
   (FX 0 on ordered == phase output), motion 0 freezes. UI: combo
   auto-lists it; ED hint covers `crt`. Pins: `tests/test_crt.py` (7)
   + Gherkin +1 (motion.feature). Suite 857 (707 fast + 150 slow).
   Gherkin 78/78.
6. SVG color-region export (one layer per ink). Vector Pro extension:
   rect runs grouped per palette ink (display + separation reuse).
   Pins: layer count + byte checks.
   DONE (nov-2026): `raster_to_svg` emits one `<g id="ink-RRGGBB">`
   layer per ink (first-appearance order, group fill, rects inherit —
   no per-rect fill); row RLE unchanged so rect counts match legacy
   (`<rect` totals identical, bytes smaller). Black-vector stays one
   `ink-000000` layer (paper skipped); optional bg rect stays outside
   layers. Pins: `tests/test_svg_layers.py` (6) + Gherkin +1
   (vector.feature 2 escenarios). Suite 863 (713 fast + 150 slow).
   Gherkin 79/79.
7. Cross-dissolve frame interpolation (numpy-only motion smoothing).
   Optional smoothing between clip/dissolve frames; strict 0=off,
   default off (flicker stays the aesthetic). Pins: 0=identity,
   determinism, cap behavior.
8. Animated APNG (Pillow-native). Same frames as the GIF path, full
   color like WebP; dialog-only extra. Pins: roundtrip + size note.
9. MCP stdio server over the headless CLI. New surface: needs its own
   spec (commands, schemas, no-network guard) before any code; last
   in the queue for that reason.
10. Infra/quality (ongoing, cheapest first): preset fuzzer in CI;
   SSIM-based weight estimator (replaces the B/px constants only if
   it wins); precomputed blue-noise masks (only if measured faster
   than IGN); NeuQuant/Wu quantization (only if it beats median-cut
   on covers); tile renderer for 8000px exports; JPEG XL stills
   (plugin weight first — likely cut).
    PyAV backend evaluation (imageio-ffmpeg's own README recommends
    it, but after ffmpeg-side scaling our 120f proxy import is
    0.5–1.2s; the bundled-FFmpeg weight must be measured first —
    likely cut).
Ops (not code): code-signing cert to end SmartScreen warnings on the Setup.

## 4. Decisions made (do not reopen without reason)

- Original MIT-licensed code based on public-domain math.
- Market references never ship: no competitor names, copy, or assets in code, UI, features, or docs (oct-2026 originality pass: Motif/Halo/Signal Drift/Paste-Up).
- No OpenCV / GPU in the core. Numba only as an OPTIONAL accelerator with numpy fallback (the base exe does not include it).
- Pillow + numpy is enough and keeps the `.exe` light. `imageio-ffmpeg` (v1.4 video) is OPT-IN extra only, never in base exe/requirements.
- PySide6 UI (not PyQt6). Preview with `QLabel + QPixmap`, no `QGraphicsScene` in v0.
- Original palettes, not 1:1 GameBoy/C64/NES clones. Auto-extract (v1.1) generates FROM the image, not clones.
- Custom canvas is editor-style: presets fill W/H, typing W/H flips to Custom. No chained toggle (one interaction model only).
- Single canvas + hold-to-compare instead of side-by-side ORIGINAL/DITHER (pro look, less layout).
- Preview proxies (Draft/HD/Full) decouple playback resolution from export: editing stays light on low-end PCs, export is always full-doc. v1.5 exposes Full/Live/Still selector (same workers, user choice).
- Fixed signal chain becomes ordered FX STACK in v1.2, but migration keeps legacy render byte-identical (old presets render same).
- Refactor rule: logic lives in `app/ui/*_controller|flow|assembly` modules + `app/ui/panels/` package (one file per section group, same public names); FX dispatch in `app/fx_dispatch.py`, threshold maps in `app/ordered_maps.py`, binding factories in `app/ui/params_binding.py`. `MainWindow` only orchestrates and keeps the test-facing API.
- Menu/panel order: File (open | export/batch | preset share) / Edit (undo/randomize | clipboard | method step | transforms) / View (refresh/compare | zoom | Viewport | Theme), clipboard lives in Edit, preset share grouped in File. Panel is a 5-page custom accordion (IMAGE/DITHER/COLOR/FX/MOTION) inside the single scroll (plain widgets, no nested scrolls; layout test: 1 `QScrollArea`); widget attribute names unchanged so controllers/presets/tests keep working. `Drop=Batch`/`Jobs` stay in the action bar (batch flow + tests are wired to `win.spn_jobs`/`win.chk_batch_drop`).
- Pro polish: Help → About/Shortcuts, File → Open recent (capped, in prefs JSON), MOTIF box hidden unless method is `motif`, Export dialog pre-checks GIF when VIDEO preview is ON (dialog only, never Quick export), post-export Show in folder, rotating `data/trakkart.log` + crash dialog. `CHANGELOG.md` started.
- Crop editor owns its box: pan/zoom mutate it directly (anchor round-trips exactly, no snap-back loop); frame follows the finger (static photo); zoom anchor clamped when the cursor sits over the black bars. `crop_box_for` only reseeds on ratio/mode/canvas/rotate/reset. fx/fy position the zoomed box directly (corners/edges reachable, no forced recenter); `crop_cover` delegates so dialog and pipeline never disagree.
- Datamosh module: `app/mosh.py` owns 10 flavors (blocks legacy byte-identical; bleed/hold/tear since v1.7); `mosh_mode`/`mosh_seed`/`mosh_size` preset fields (old presets default `blocks`/0/100); dedicated DATAMOSH accordion page (params live there, order stays in FX STACK); stack entry + GIF mix dispatch by mode. 683 tests, 62/62 Gherkin, 5/5 gates.
- Export naming: `{base}_anim.mp4` (same stem as GIF); hardened sanitizer (no `__`, no edge junk); File name section with live preview + Reset; dialogs `deleteLater` on close (no hidden-window hoard).
- Stale export names: prefs carry `src_name`; new image → fresh default (quick falls back to dialog, never silently reuses); `load_pil` stamps `pasted_YYYYMMDD_HHMMSS`. 402 tests, 5/5 gates.
- Collision policy: single export (dialog + quick) always renames (`name_2`, …); skip/overwrite removed from the dialog (engine + batch keep all modes). 404 tests, 5/5 gates.
- Collision alert (`resolve_collision`): lists clashing files, Overwrite / Rename-as-`base_2` / Cancel with safe default; ⚠ hint in the plan; quick stays silent-rename; dialogs `deleteLater` + visible-first accept (no modal flake in CI). 409 tests, 5/5 gates.
- MOTION duration readout (driver spin removed: request-vs-reality split confused; label never lies). Animation suffixes `_gif.gif` + `_vid.mp4`. FPS combo sorted inserts (no stray 8).
- Refactor P1+M2: cached crop pixmap + `app/names.py` sanitizer home. 414 tests, 5/5 gates.
- R14 engine freeze REOPENED narrowly (owner nov-2026, research-backed):
  +`ostromoukhov` +`dizzy` + serpentine ED toggle in v1.9 (exact-list test
  updates to the new list; the rest of the roster stays frozen).
- Clip import rule REVERSED (owner nov-2026): stills stay the core
  product, but short clips become a first-class input in v2.0
  (session-only, ≤120f, timeline editor + visual-only preview, batch
  stays stills; MP4 export muxes a user-chosen soundtrack, GIF/ZIP
  stay silent). The old "no clip import by design" is void.
- Tap-tempo/pulse-sync REJECTED (owner nov-2026): same fiddly family as
  the removed BPM grid; Length stays Frames/FPS/Hold.
- Clip import decodes 8-bit RGB only (no HDR/10-bit tone mapping): HDR
  sources are downconverted by ffmpeg, so washed colors are expected.
  Detect HDR/10-bit and warn if it ever matters; tonemapping is out of
  scope for the same reason MP4 stays libx264-only (keep one simple,
  predictable path).
- Clip mux rule: cut at the video duration (`-t`, from a header probe);
  never use `-af apad -shortest` with `-c:v copy` (hangs ffmpeg), and
  never re-encode the video. A failed mux keeps the silent MP4.
- Clip UX rule (nov-2026, user request): the panel is watch-only (Play
  + trim + scrub, canvas always dithered); all clip export lives in
  the Export window (dialog base + first-free names, clip-only without
  a still, quick export stays stills-only). The render core is shared,
  never duplicated per surface.
- Clip framing rule (nov-2026, user request, option B): no per-clip
  crop — the clip cover-fits the still canvas through IMAGE → Crop
  (mode/focus/zoom). Preview and export share the pixels by
  construction (both go through the preset spec).
- MOTION single-line rule (nov-2026, user request): Source radios
  (Animate still XOR Clip footage), one box visible, one canvas writer;
  Timing + proxy collapsed under Details (stale Rebuild stays out).
  Canvas titles always `MOTION · …` with the origin in parens.
- MP4 stays software `libx264`-only (HW selector tried and reverted
  pre-release: fake detection, quality mapping, streaming fallback bug).
- v2.x queue ordered (owner nov-2026): stabilize (compact + bug-hunt)
  first, then envelopes → gradient-maps → CRT/VHS → SVG regions →
  cross-dissolve → APNG → MCP, infra cheapest-first; each candidate
  keep/cut by real-render utility check, gates green before commit.
- Clip in-point seek (`-ss`) added at the head of the v2.x queue
  (nov-2026): cheap, closes the v2.0 "first 120 frames only" gap, and
  long videos become usable without a new engine. VFR normalization
  follows, then envelopes.
- Video research (nov-2026): proxy scaling belongs in ffmpeg, not
  Python (4K import 11x faster); never call `count_frames` (decodes
  the whole file) — `nframes=inf` is normal; `-ss` before `-i` is
  frame-accurate on modern ffmpeg; autorotate already handles phone
  display-matrix videos; VFR sources duplicate frames on the native
  imageio pass (pending item); PyAV stays deferred by bundle weight.
- QThread rule (v2.1): never release the last reference to a running
  worker — Qt fast-fails the process (`0xC0000409`, no traceback).
  All worker handoff goes through `app/ui/thread_safe.py`
  (`retire`/`drop`/`stop`); `closeEvent` waits bounded and orphans a
  stuck render. `new_project` cancels preview + clip + video token.

## 5. Known tech debt

- Tests use `get_flattened_data()` (Pillow ≥10). Downgrading Pillow will break them.
- `floyd_steinberg` color at 3000px is still slow (~45s numpy); with numba <1s. The real flow dithers at source size; video preview defaults to Draft 720p so ED presets stay interactive.
- Multiprocess batch in loose scripts requires the `if __name__ == "__main__"` guard (Windows spawn); without it there is automatic fallback to sequential.
- Legacy `export_bundle()` (cover/small/1080p/metadata) is kept byte-identical for tests + the export-smoke gate; new code uses `export_with_options()`.

## 6. Out of scope (for now)

- Webcam, YouTube upload, BPM/key analysis with torch/librosa, tap-tempo, login/cloud.
- Bridges to other apps (TRAKKOUT/TRAKKNAME) and shared naming: each TRAKK app is standalone.
- Video BASE: `imageio-ffmpeg` ships in the base exe/requirements since v1.0 (historical opt-in `requirements-video.txt` era over). MP4 single-export only (software `libx264`, no HW probing), batch stays GIF.
- Explicitly rejected (adds nothing for offline covers): GPU backends (cupy/opencl), preset download from the internet (offline file share instead). Vector export IS in (v0.9, custom rect-only SVG). App themes veto LIFTED and DONE in v1.5 (single-source token variants).

## 7. MORPH engine — dither-boy particle system (reference)

Single source of truth for how dissolve/morph works, what it is good for
beyond the 2 bundled presets, and where it goes next. Researched against
ImageMagick -morph/-set delay, ComfyUI morph nodes, TesseraUI pour,
typexperiments (Morph/Explode/Pour/Wave), dither_app (Pace/Scatter + gravity
profiles), GodUI/halftone-fx (color dots), Heckel halftone shading.

### 7.1 Pipeline (5 stages, all offline, Pillow + numpy only)

1. Fit: A honors the preset canvas (ratio/crop/focus/zoom via to_canvas);
   B..F cover-fit to A with per-image fx/fy/zoom (same crop_cover as IMAGE,
   no stretch, no bars). Chain cap: A + 5 (MAX_MORPH_IMAGES = 6).
2. Dither: one BW pass per image (Bayer/Floyd family, app/dither.py,
   palette=None). Active set = black dots (MAX_POINTS cap with stride).
3. Move: disperse_positions = origin + (wind + seeded turbulence) * env,
   env = sin(pi*frac), frac = (progress*loops) % 1. Loop-perfect by
   construction (frac 0 == 1); deterministic (default_rng(seed + frame)).
4. Rasterize: 1px dots on white canvas, clipped, vectorized (no per-dot loop).
5. Assemble: GIF via shared 128-color palette (no flicker), MP4 via
   imageio-ffmpeg. Holds = duplicated assembled ends (uniform fps, no
   per-frame duration quirks; preview scrub walks them like any frame).

Files: app/disintegrate.py (engine), app/gif.py (gif_dissolve_frames /
gif_morph_frames / gif_frames dispatch), presets dissolve_* (+ ASH_WIND,
DUST_RANDOM), MORPH page (panels/morph.py, win.morph_list + morph_src alias).

Invariants (do not break): strict 0=off (amount 0 = still / hard cut),
64-frame cap (transitions win over holds), min 2 frames per segment (every
form appears at least assembled), joints meet assembled (q=j/(nk-1)).

### 7.2 Parameters

- dissolve_amount 0-2 (0 = off): disperse strength. Still reads first.
- dissolve_seed 0-999999 (53596): same seed = same particles.
- dissolve_mode wind | random: directional + turbulence vs all directions.
- dissolve_speed 0.25-4.0 (1): traversals per clip.
- dissolve_wind_x/y -500..500 px (120, -40): displacement at full disperse.
- dissolve_hold 0-3s (1.0): still pause per form (assembled duplicates, shared equally across all forms). Every tick adds time: total = transitions + holds.
- dissolve_length: legacy request, IGNORED since Hold-manda (kept for preset compat); Length is sacred since v1.3: the UI spin is editable and solves Hold (particle) or n = Length x fps (rest).
- dissolve_loop true (default): closed loop, last form morphs back into A; A's share split across both loop ends; ping-pong ignored when closed.
- Chain: playlist order = play order; per-image Crop X/Y 0-100 + Zoom 1-4x
  (session-only, covers B..F; A comes from the canvas).

### 7.3 Current presets (2)

- ASH_WIND (bayer8/BW/3px, wind 140,-50): lateral ash drift, general covers.
- DUST_RANDOM (floyd/BW/2px, random): grain-storm rebuild, dark covers.

### 7.4 Proposed preset pack (works today, no engine change)

- EMBER_RISE: wind (0,-160) upward drift, floyd/BW, for fiery covers.
- GRAVITY_DROP: wind (0,+160) falling ash, bayer8/BW.
- POUR_FAKE: wind down + low amount (0.5) + tight seed — approximates a pour
  until true destination matching lands (see 7.6).
- TEXT_CARD: any mode with a pasted title card as B (manual path of the
  kinetic-typography use below; in-app text render is future work).
- VJ_LOOP: dissolve, speed 2.0, holds 0.5, pingpong on — seamless club loop.

### 7.5 Uses beyond the 2 presets (researched)

- Logo stings / cover intros: dithered logo assembles from dust
  (Componentry Dithered Logo pattern; Framer Dither Reveal waves).
- Kinetic typography: beat titles / track intros that explode and reassemble
  (typexperiments Morph/Explode/Pour; Word Morph physics; Letter Cascade).
- VJ loops / hero backgrounds: living halftone + ripple backdrops
  (halftone-fx live component; Dither Reveal cursor flashlight).
- Beat-synced drops: amount/speed ridden by a beat grid (dither_app Pulse
  double-beat; our motion_amount already scales intensity) — natural fit
  for a beatmaker audience.
- Social stickers / GIF reactions: 2-6f micro-morphs (cheap at 64px).
- E-ink / RISO print aesthetic transitions; split-flap arrivals-board
  (per-dot flip = stagger variant, see 7.6).
- Interactive preview: cursor repel scatter/reassemble in the canvas
  (text-practice.js, Particle Typography, Particle Image cursor field).

### 7.6 Improvement roadmap (researched, not scheduled)

Short term (engine-only, no UI migration):
- Easing select: Cubic / Elastic / Bounce / Quad / Linear envelope instead
  of fixed sin (typexperiments easing panel).
- Per-particle stagger: delay by distance-from-center or seed rank, so the
  cloud pours in waves instead of breathing all at once (typexperiments
  stagger; ComfyUI transition_frames granularity).
- Gravity + bounce modes: Drizzle / Cascade / Flutter / Collapse profiles
  (dither_app) map directly onto wind + a floor bounce.

Mid term (visible leap, needs UI + tests):
- Palette following (F7, done): morph animates the graded still —
  IMAGE adjust grades the dots, COLOR palette prints the inks at full
  strength (joints = ink stills = holds, no pop); BW presets keep every
  byte identical. Grade/FX/texture stay still-only (post-dither FX on
  particles needs its own renderer). Gherkin 61.
- Destination matching (pour, not scatter): nearest-neighbor / angle-paired
  assignment A->B so dots TRAVEL to their target instead of cloud-reform
  (TesseraUI pour; typexperiments glyph mapping). Keep seeded-greedy for
  determinism. Biggest single visual upgrade on this list.
  Done F3: `match_travel()` seeded-greedy grid matching + `travel_positions()`
  smootherstep pour (`dissolve_travel` 0-1, default 1 = pour, 0 = legacy; MORPH slider;
  joints exact; blocks exempt). Gherkin 57.
- Color particles: tint each dot with its source pixel/palette color
  (GodUI color=source; halftone-fx multicolor). Huge for SLIME/VAPOR covers;
  watch export size + readability gates.
  Done F4: `dissolve_tint` 0-1 + `sample_colors()` per-dot hues
  (travel legs lerp src→dst), envelope-gated so joints land black
  (byte-exact); tint=0 legacy BW; 0=off freezes tint. Gherkin 58.
- Dot-size attenuation by envelope/luminance (Heckel halftone shading)
  instead of fixed 1px dots.
  Done F6: `dissolve_shade` bool + `darkness_map()` per-dot darkness,
  `frame_dot_sizes(shade=)` 1..dotsize x darkness x envelope (joints 1px;
  off/Dots=1 = legacy). Gherkin 60.
- Trails / motion-blur accumulation (Word Morph trails; Particle Image).
  Done F5: `dissolve_trail` 0-8 + per-leg position deque + envelope-gated
  ghosts (BW gray / tinted hues, joints ghost-free, 0 = legacy). Gherkin 59.
- Canvas-relative particle density (done nov-2026): `point_cap()` in
  `app/particles/modes.py` replaces the fixed 120k cap (1200px reference,
  900k hard ceiling), so Full/doc morph keeps the same dots per image area
  as the preview. Measured 1:1 ink density 9.0% @1600 vs 9.3% @3000 (old:
  5.2% vs 1.6%) — this was the real "color/form lost at real size", not
  tint. Exports <=1200px stay byte-identical.

Long term (new surfaces):
- Interactive cursor repel in the preview canvas via Qt mouse events
  (Componentry magnetic field; Particle Typography springs).
- Beat-grid sync: amount/speed keyed to BPM markers.
- Animated WebP export (smaller than GIF; Pillow supports per-frame
  duration lists too) + PNG-sequence zip (dither_app ships both).
  --> Promoted with concrete spec in §8 R7 (nov-2026 research).
- In-app text-to-image source so TEXT_CARD presets need no paste step.

### 7.7 New morph modes: fields × stagger × ease (researched nov-2026)

Today only `wind` + `random` exist (`disperse_positions`, `app/disintegrate.py`).
Survey: force taxonomies (Gravity/Wind/Turbulence/Vortex/Attractor/
Spring), burst with speed variance (many slow, few fast),
smooth noise flow-fields (bake-then-play), map-driven staggered
release (graph/axis/rank), ripple/wave/pulse over dot-grids, per-cell
block dissolve. All of it fits our design (closed field × periodic
envelope, no integration: that's why we're loop-perfect and deterministic;
velocity/drag simulation does NOT enter: it would break the loop).

Design rule (no combinatorial explosion, FX-stack philosophy): three
orthogonal axes instead of N loose modes. Same vectorized O(n) cost, same
RAM (MAX_POINTS), same invariants (seeded, frac%1 loop-perfect).

- DIRECTION (offset field, extended `dissolve_mode`; wind/random intact):
  `burst` (radial-out from center, rank-based speed 0.3+rank to avoid a
  mechanical ring), `suction` (radial-in: converges; ideal logo-stings §7.5),
  `vortex` (tangential + slight outward pull, angle by position),
  `rain` (fall with frac² + fold floor-bounce: periodic),
  `rise` (upward: makes the proposed EMBER_RISE preset §7.4 real),
  `wave` (traveling sine in x, loop-locked phase),
  `ripple` (concentric rings from center, radial sine),
  `flow` (smooth seeded value-noise field, FIXED per clip like the
  current turbulence: bake once O(HxW), lookup per frame; organic drift),
  `blocks` (per-cell block dissolve in pixel_size with rank order: no
  cloud, block pops; the cheapest and most dither-native).
- STAGGER (`dissolve_stagger`: off | rank | radial | scan | sweep):
  per-particle delay pinned to the joint `frac_i=(frac+delay_i·sin(π·frac))%1`
  (pure shift would break joint assembly and holds would pop;
  pinned: zero shift at both joints, full mid-loop waves, loop intact
  via %1). `rank` uses the Bayer map from `ordered_maps.py`
  (matrix order = dither signature); `radial` = center-out wave on
  gather; `scan` = top-down rows; `sweep` = left-right reassembly
  (converge-to-shape). Deterministic, no extra RNG.
- EASE (`dissolve_ease`: sine | cubic | linear in F1; elastic | bounce in F2):
  envelope shape instead of fixed sin; sine = legacy byte-identical;
  cubic = sin³ (sharp attack, long dwell); linear = constant-speed tent.
  rain/rise fold their drop inside the field and the envelope
  gates it (ease always rules, no control lies).
- Preset/UI/migration: 3 fields (extended oneof `mode` + `stagger` +
  `ease`, defaults wind/off/sine = legacy byte-identical renders);
  MORPH: extended mode combo + 2 combos; plan counts the same (stagger
  doesn't change counts, only which particle moves when).
- Tests: determinism (same seed = same pixels) + loop-perfect
  (frac 0 == 1 per mode/stagger/ease) + pinned assembled joint per
  stagger + legacy byte-identical by default + 2-3 Gherkin scenarios
  (deterministic burst, neutral rank with stagger off, blocks on # forms).
  Done F1: `features/morph_modes.feature` (3) + unit in
  `tests/test_disintegrate.py` (11 modes × 5 staggers × 3 eases in loop,
  blocks 9/64 anchor, fallback) + MORPH combos (11/5/3). Gates 55.
  Done F2: elastic/bounce + `dissolve_dotsize` 1-4 (joints at 1px) +
  EMBER_RISE/GRAVITY_DROP/POUR_FAKE pack + 4th Gherkin. Gates 56.
- Phases: F1 = fields (burst/suction/vortex/rain/rise/wave/ripple/flow/blocks;
  rise enters by symmetry with rain, 3 lines) + stagger (rank/radial/scan/sweep)
  + ease sine/cubic/linear (linear enters for neutrality, 1 line);
  rain/rise fold their drop (frac² + bounce) INSIDE the field and the envelope
  gates it (ease does rule); blocks pops per pixel_size cell with a
  15%-dense anchor (no anchor flashes white at peak: measured); stagger pinned
  to the joint (pure shift broke holds). F2 = elastic/
  bounce + dot-size coupling (§7.6) + preset pack (EMBER_RISE,
  GRAVITY_DROP with rain, POUR Fake with flow + rank stagger).
  Done F2: elastic = sine·(0.65+0.35cos) peak ~0.88, bounce =
  sine·(0.55+0.45|sin|) peak 1.0; dotsize 1-4 with joints at 1px
  (MORPH slider + BINDINGS); 3-preset bundle.
- Out: integrated physics (velocity springs/drag), hover/explode
  interactivity in export (only makes sense in preview; see §7.6
  long-term), new formats here (that's §8 R7).

## 8. Research backlog (web, nov-2026) — candidates, not scheduled

External survey (official specs + Pillow/imageio docs) crossed with
measurements in this repo. Only offline, Pillow/numpy/imageio work that fits
TRAKK = dithered stills + videos OF those stills.
Verified today in code: (1) imageio rescales MP4 to multiples of 16
(1080x1920 comes out as 1088x1920: breaks the exact 9:16 Canvas demands);
(2) Pillow already collapses identical GIF holds (measured: 114f -> 1f, 171B).
(3) Codec-level datamosh (supermosh.github.io, surveyed nov-2026):
single-keyframe x264 (`-g high -bf 0`) + dropped/repeated P-frames at
segment cuts = real motion bleed, distinct from our pixel-procedural
mosh. Portable subset scheduled as v1.7 (AVC engine + segment
timeline + reprocess guard + encoder select); browser stack
(WebCodecs/MediaRecorder) rejected, presets/live-preview already
ahead here.

### 8.1 Social delivery (top fit, low cost)

Sources: Spotify Canvas guidelines (MP4 or JPG, 9:16, 720-1080px, 3-8s);
sep/oct-2026 spec guides (Reels/Stories/TikTok/Shorts = 1080x1920 9:16;
YT thumb 1280x720 16:9; square 1080x1080; 4:5 1080x1350; safe areas with
~250px top/bottom chrome).

- [x] R1 — Canvas recipe preset: 9:16 + 1080x1920 + 24/30fps + Length 7.5s
  (H.264 + faststart). At exactly 8.000 there are rejection reports: aim
  ≤7.9s. Our 3 modes already map 1:1 to the Spotify taxonomy
  (Continuous=loop, Rebound=ping-pong, Hard Cut=loop off). Cost S.
  Done (Hold-manda era): `CANVAS_916` bundled (9:16, export 1920,
  dissolve 64f/30fps/Hold 2.7 → 226f = 7.53s, loop) + R5/R6 (dims exactas,
  faststart) debajo.
- [x] R2 — "Canvas check": with 9:16 ratio and (Length outside 3-8s or MP4 size
  outside 720p/1080p), hint in the duration label. Cost S.
  Done split by data locality: duration label warns on duration
  (9:16 ratio + actual outside 3-8s); export dialog warns on size
  (9:16 + mp4_size Canvas or actual outside 3-8s).
- [x] R3 — BPM -> Length: BPM + bars inputs -> Length = bars*240/BPM
  (120BPM/2 bars = 4s; 140BPM/4 bars = 6.86s). The loop doesn't start
  on the downbeat (Spotify loops on its own clock) but the inner pulse matches
  the track. Cost S, total beatmaker fit.
  Done (Hold-manda era): `hold_for_target()` solves Hold for the target
  (capped 3.0s, honest fits); VIDEO adds ♫ BPM/Bars row + Set Hold.
  REMOVED (nov-2026, post-v1.2.0): too fiddly, Length stays derived
  (Frames/FPS/Hold direct). Row + `apply_bpm()` + `hold_for_target()`
  deleted; no preset fields involved (Hold is and stays the preset).
- [x] R4 — Social recipe presets (bundled JSON): YT thumb 1280x720, square
  1080x1080, portrait 4:5 1080x1350, master 9:16 1080x1920 (one master covers
  Reels/Stories/TikTok/Shorts). Cost S.
  Done: `YT_THUMB` (16:9/1280), `SQUARE_11` (1:1/1080),
  `PORTRAIT_45` (4:5/1350); master = `CANVAS_916` (R1).

### 8.2 Format/codec (measured, low cost)

- [x] R5 — macro_block_size=2 + even-guard on mp4_dims (BUG verified today:
  1080x1920 -> 1088x1920, 404x720 -> 416x720; H.264/yuv420p only requires
  multiples of 2). Without this no MP4 is Canvas-valid. Cost XS, do now.
  Done: `mp4_dims` rounds down to even + `macro_block_size=2` in
  `write_mp4`/`write_mp4_iter`; 1080x1920 ships exact, 721x721 -> 720x720.
- [x] R6 — faststart (`-movflags +faststart`) on write_mp4/write_mp4_iter:
  progressive playback on web/stores, ~zero cost. Do with R5.
  Done: in both writers; test asserts moov before mdat.
- [x] R7 — Animated WebP export (promotes §7.6): Pillow save_all + duration
  (int or list) + loop=0 + minimize_size, no new deps, ~1/3 of the GIF at
  equal quality and full color; every browser plays it. New
  `save_webp()` mirroring save_gif + checkbox in dialog + bundle
  `*_anim.webp`. Cost S/M.
  Done: `save_webp()` (full color, minimize_size, quality 80) +
  `estimate_webp` (GIF//3) + `{base}_anim.webp` via `webp_name()` +
  "Animation WebP" checkbox in dialog (plan + collisions) + `webp=True`
  in `export_full` (reuses GIF frames; dialog-only like MP4,
  batch stays GIF).
- [x] R8 — GIF estimate v2 (hold-collapse aware): the current estimate
  (frames*w*h//2) lies 100-1000x on clips with holds because Pillow
  merges identical frames. Estimate transitions at full cost + 1f
  per still form. Cost S.
  Done: `estimate_gif(n_trans, w, h, n_hold_forms=0)` (+ `estimate_webp`
  mirror); video_controller migrates (label, ping-pong no longer doubles),
  GIF+WebP dialog (256f plan once) and `_estimate_bytes` (extra
  gif_trans/gif_forms, default = old shape). Measured real 480p:
  12.7x→3.8x over, same safe direction.

### 8.3 Print (pairs with Vector Pro)

- [x] R9 — Ink separations (RISO/screen print): one PNG per palette
  color (spot separations) + registration marks. Real print-shop
  flow, no OpenCV. Cost M.
  Done: `app/separations.py` (nearest-color plates L + crosshair-in-circle
  per corner + `effective_palette` mirror of the pipeline + `plate_count`
  without render); `{base}_sep_{NN}_{RRGGBB}.png` via `export_full(sep=True)`
  (dialog-only); dialog with checkbox + plan + collisions (exact post-accept
  glob). Pairs with the Vector Pro black-ink flow.

### 8.4 Workflow/automation

- [x] R10 — Headless CLI (`TRAKKART.exe --cli --preset X --in ... --out ...`):
  labels shipping 20 singles/month thank you for it; UI and engine are already
  service-separated. Cost M.
  Done: `app/cli.py` (`run_cli` → exit 0/1/2, `--list-presets`, file +
  folder via batch bundle, skip-existing, safety guard, stateless without
  history); `main.py` dispatches `--cli` before importing Qt (verified
  without PySide6 in a fresh interpreter); MP4/WebP/seps stay dialog-only;
  MANUAL with a section.
- [x] R11 — Watch-folder (watched folder -> auto-batch with fixed preset).
  Cost M. Cheap alternative: "re-batch last folder" in 1 click (S).
  Done: `app/ui/watch_flow.py` (QFileSystemWatcher + 2s debounce +
  skip-existing idempotente + 3s settle anti-copias-parciales + preset
  fixed by NAME reloaded per cycle + jobs=1 + stateless without history
  + zero modals) + `WatchDialog` + File → Watch folder... (checkable).
  The cheap alternative wasn't needed (same cost covers the case).

### 8.5 UX/engine polish (only with spare cycles)

- [x] R12 — 9:16 safe-area guides (IG/TikTok/Shorts chrome top/bottom bands)
  in crop editor + preview. Cost S/M.
  Done: `app/ui/safeareas.py` (250/1920 bands as fraction + Qt overlay,
  display-only); still preview (sync + async) + crop editor (9:16 frame);
  View → Safe areas 9:16 (default ON). Video frames excluded
  (per-frame cost, documented).
- [x] R13 — Wipe compare (before/after slider) besides hold-to-compare.
  Cost S.
  Done: Wipe slider under the preview (ORIGINAL left / result right,
  amber divider, 0 = off); original aligned via live canvas;
  display-size composite; hold wins while held; video
  ignores it; survives refreshes (`redisplay` router).
- [x] R14 — Freeze the 36-engine roster: more diffusions (Ostromoukhov
  et al.) add <5% visible value for covers and each engine is test/preset
  surface forever. Proposed decision.
  Done (decision adopted): frozen roster with a test asserting the exact
  list (`test_engine_roster_frozen_r14`); adding an engine requires a
  deliberate decision (list + docs). NOTE: the PARTICLE roster (11 F1/F2
  fields) is out of this freeze (live axis).

### 8.6 Explicitly rejected (do not reopen without reason)

- AV1/new codecs: H.264 is the universal Canvas/social codec; AV1
  encoding is slow and nothing requires it. Pillow+numpy+imageio suffice.
- Cloud AI, accounts, uploads, login, auto-update/store: they break
  offline-first and §6. In-app text layer: already removed in v0.14.

### Recommended (next)

1. R5+R6 DONE + Hold-manda DONE + R1+R2+R3 DONE → 2. R7 (WebP) or
   R9 (separations) by social vs print pull → 3. morph F1 (§7.7).
2. New tracks below (§9 pro polish + §10 GPU preview) run after the
   above; §9 ships first (small, no arch change), §10 needs explicit
   plan approval before any implementation.

## 9. Professional polish — visual UI + preview fluency (done)

Goal: feel modern without a rewrite. Two micro-packs, each mergeable
separately, pytest green after each step, one clean commit per pack.
No arch change, no new deps, offline-first intact.

### 9.1 Preview fluency (done)

- Background: `preview_controller.render_still` uses `render_full` sync
  except `should_render_async` (no-numba + >480px). A large image + an
  ED method (`floyd` family) freezes sliders even with numba.
  `is_heavy_preset` only covers `pre_blur/denoise/smooth`, not the method.
- Plan: (1) preview at 640px via `render_preview_small` (already
  compensates `pixel_size`/radius FX) except in Full mode; (2) extend
  heavy/async detection to the ED family + `hilbert` + canvas >1MP so
  those go to the worker with token stale-drop; (3) status readout
  (`Preview 640px · 180ms`) + Wait cursor while a worker is alive
  (Export stays enabled: it re-renders independently, blocking it
  would only hurt).
- Verify: manual drag on a 3000px `floyd` preset stays responsive;
  fast suite green (`-m "not slow"`); no new Gherkin unless the readout
  needs one scenario.

### 9.2 Visual UI micro-polish (done)

- Empty-state rich-text placeholder (`NO IMAGE` + drop guidance);
  `theme.qss` focus/disabled states (buttons, inputs, sliders,
  checkboxes); `pil_to_pixmap` BICUBIC + HiDPI backing
  (`devicePixelRatio`, no-op at 1x).
- Verify: `test_empty_state_placeholder`, QSS selector + pixmap tests;
  fast suite + flake8 green.

## 10. GPU preview — C1-GLSL offscreen dither (4a done, 4b future)

Context (do not reopen without reason): replicating TRAKKART on another
stack was evaluated and rejected; staying on Qt/PySide6 with GPU for
pixel-parallel work is the best ROI. Physical rule: per-pixel work goes
to fragment shaders (ordered dither, duotone, posterize, post FX);
serial work stays on CPU (ED Floyd-Steinberg with numba, JPEG,
pixelsort, numpy particles). Honest dual arch: GPU for iteration,
numpy CPU for the final render, switchable. Rejected: compute shaders
for ED/particles (high cost, dubious ROI), native Rust GUI rewrite,
repackaging everything for web (separate track). Hybrid option to keep
in mind: portable WGSL kernels (`wgpu-py` today, web tomorrow).

Architecture correction (nov-2026, learned from the spike): the grade
chain stays on CPU (cheap point ops; keeping the suite code as the
single implementation kills a whole class of float32-vs-CPU tie bugs
that dither thresholds amplify). The GPU owns ONLY the dither stage
(the actual bottleneck: nearest-palette search). See
`docs/srs-gpu-preview.md` for the accepted shape.

Reference (read-only, do not edit there): the `TRAKKMOTION`
`src/shaders/{grade,dither,post}.frag.glsl` oracle plus its fixtures
served as the transcription reference.

- Step 1 — direction lock: DONE. C1-GLSL offscreen.
- Step 2 — SRS: DONE (`docs/srs-gpu-preview.md`, FR-1..8).
- Step 3 — spike: DONE (`tools/gpu_spike_preview.py`, manual).
- Step 4a — GPU dither + parity + wiring: DONE. `app/gpu.py` +
  `app/gpu_shaders.py` (dither only) + `tests/test_gpu_parity.py`
  (25 ordered maps + cmyk + edges, BW + named palettes, drift set,
  post-FX tail, no-GL fallback; gate maxdiff <= 1 LSB, all green).
   Wired behind the 640px proxy (`Live`/`Still`) plus doc-size `Full`
   stills (`render_full_kwargs`, display-only) with CPU fallback and
   a `GPU`/`CPU` status suffix; `moderngl` in `requirements.txt`
   (+~0.1MB to the exe, reviewed). Export/batch/CLI/video stay
   untouched (CPU).
- Step 4b — GPU post-FX: NOT started (future work; post runs on CPU
  today, fast enough at proxy size for v1).
