# TRAKKART — Roadmap

> Context for continued development. Single source of truth for state and next steps.

## 1. Vision

TRAKKART = offline dither cover generator for beatmakers, part of the ShardBeats TRAKK family.
Flow: `Image → method + palette + pixel + threshold → preview → bundle → TRAKKOUT`.

Family style: offline-first, portable `.exe` (`data/` next to the exe), PySide6 + Pillow + numpy, MIT with original code (no third-party GPL code).

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

### Unreleased (post-v0.17)
- [x] Named palette library (`palettes/*.json`, editable swatches, dirty "(Custom)" state, random Oklch generator ramp/harmony).
- [x] Pro export: size presets + PNG/JPG/WebP, per-dialog outputs, overwrite policies, quick export with prefs.
- [x] FX packs: GRADE (duotone/posterize/split-tone/fade/glow threshold), TEXTURE (halftone/dust/border/letterbox), GLITCH+ (pixelsort/wave/mosh/grille) in 3 panel groups.
- [x] 7 new engines (shiaufan/filterlite/sierralite/sierra3, ign, checker, hilbert). 23 methods, 35/35 Gherkin.
- [x] GIF overhaul: modes `phase/hue/both/glitch/mix`, 2–24 frames, 2–60 fps, ping-pong, anim at canvas size, shared 128-color palette (no per-frame flicker), deterministic seeded post-fx.
- [x] Video mode: full-canvas animated preview (QThread worker + tokens) with play/pause/scrub, Draft 720p / HD 1080p / Full proxy tiers — export always full-doc. FPS changes retime only (no re-render).
- [x] Single canvas + hold-to-compare (button or Space shows ORIGINAL); export GIF preview removed from the dialog (lives in VIDEO mode).
- [x] Free Custom canvas (Photoshop-style): `Custom` ratio + free W×H (presets refill W/H, typing flips to Custom); `cover/contain/stretch/blur` honor free aspect; old presets migrate via `ratio+export_size`.
- [x] Doc único + anim único: CANVAS owns size, VIDEO owns animation (no duplicated size/GIF controls in dialogs).
- [x] Grille `every=2` crash fixed (mixed bool+list fancy index).
- [x] Refactor: `main_window` 1686→~700 lines (8 controllers + assembly + menus); `FIELDS` preset schema; `BINDINGS` widget table; `RenderSpec` single ~40-param dataclass; unified exporter writer (legacy kept byte-identical). 281 tests, 38/38 Gherkin, gates 5/5.

### v1.0 — Standalone release
TRAKK apps 100% standalone: no TRAKKOUT/TRAKKNAME bridges or shared naming. Each app lives on its own.
- [ ] EN docs + screenshots (before/after, sample GIF) + GitHub release `shardbeats/TRAKKART`.

### v1.1 — Color Pro (done)
Gap: auto-extracted palettes, depth control, lock/shuffle per swatch, Source category.
- [x] Auto-extract palette from image (`app/palette_extract.py`: median-cut numpy-only, N=2..16, deterministic seed) + "From image" button.
- [x] `Source` palette mode: retiene color original como punto de partida editable (no re-mapea a BW/SLIME).
- [x] Depth slider: nº de niveles/steps usados de la paleta (mapeo previo al dither, vive en `RenderSpec` + `FIELDS`).
- [x] Per-swatch lock + shuffle + per-adjust lock/randomize (UI en palette dialog + Adjust row).
- [x] Midtones/highlights adjust (además de brightness/contrast/saturation) en `app/adjust.py` + UI.
- [x] Palette import/export/share `.json`/`.gpl` offline (misma UX que preset share). Gherkin 40/40.

### v1.2 — Stackable FX (done)
Gap: fixed pipeline `canvas→pre→grade→dither→brand→post`; goal is add-with-`+` and reorder.
- [x] FX stack model: lista ordenada `[{id, enabled}]` en `Preset` + `RenderSpec.fx_stack` (migración: presets viejos → stack equivalente, render idéntico).
- [x] UI: ADD effect (`+` combo), reorder up/down, enable/disable, granular sliders per effect (halo glow, jpeg-glitch, chroma, blur/sharpen as post).
- [x] JPEG Glitch effect (`app/fx_jpeg.py`: recompresión Pillow quality/blocks/chroma-subsampling, numpy-only, determinista con seed).
- [x] Halo glow designed for dither (threshold + screen blend already existed → promoted to a stack effect).
- [x] `render_spec` ejecuta stack en orden (tests de conmutatividad: reorder cambia output). Gherkin 42/42.

### v1.3 — Engines III + print (done: 23→36 + CMYK/vector-pro)
Gap: grow the roster (glitch + special + pattern/ordered extras + CMYK + ASCII + custom Motif builder).
- [x] 13 new engines: granular `bayer32/lines/columns/diag/grid` + glitch-dither `white_noise/blocks/scan_bayer/wave_map` + special `cmyk/ascii/edges` + `motif`. 36 methods.
- [x] ASCII mode (`app/ascii.py`: charset ramp, Pillow-only, animable por `phase`, vector-compatible vía rects).
- [x] Motif: custom pattern builder (`app/motif.py`: 4 bands -> shape/size, 6 shapes, stored in preset as dict). Simple MOTIF panel.
- [x] Vector Pro: black-vector print (`vector_black` + `ink_only`, sin rects de papel) + lossless toggle (force PNG en export/batch) + estimate calibrado (~58B/celda). Embroidery OUT.
- [x] Arrow-stepping (botones + Alt+Left/Right, `step_method` ciclico) + Gherkin 45/45.

### v1.4 — Motion from stills + signal drift (done, trimmed)
Animation always runs over the still image (GIF modes + drift + phase).
Timeline layers and clip import were cut on purpose (Oct 2026 trim):
they added a model + locks + file pipeline far from the core job
(dither stills, make videos OF those stills).
- [x] Video export MP4 (`imageio-ffmpeg` SOLO como extra opcional, `requirements-video.txt`, nunca en base exe; fallback con mensaje claro si falta). Same frame→dither→stack pipeline, shared anti-flicker palette.
- [x] Signal Drift: 9 animated retro-screen noise patterns (`app/drift.py`, seeded, deterministic, works with any method). UI lives in VIDEO (pattern + amount).
- [x] Paste-Up (image/texture overlay with blend + opacity, in-app, e.g. paper grain / riso dust) as `pasteup` FX stack item (neutral when off).
- [x] Gherkin 51/51 (drift determinism + paste-up neutral + motion freeze + backend-missing skips clean).
- [x] Motion legibility pass (post-v1.4, option A+E): mode names + one-line descriptions in UI, `motion_amount` 0–3 (`1.0` = legacy bytes, `0` = freeze), ED-march compat hint with one-click `bayer8` switch, loop-clean march (full matrix period per loop). No engine change besides the march step.

### v1.5 — Iteration UX + content (done)
- [x] Viewport mode selector Full/Live/Still (`app/viewport.py`: 0ms / 120ms-fast-350ms-slow / F5-only + statusbar label + View menu).
- [x] Fast path: core adjusts (brightness/contrast/sat/mid/high) refresh at 120ms in Live; blur/denoise marked "(heavy)" in tooltips + background worker (`is_heavy_preset`).
- [x] In-app tutorial (`Help → Quick tour`, 5 steps, first-run once + `data/samples/` pack generated offline) + batch menu entry verified (File → Batch folder Ctrl+B since v0.2, no duplicate menu).
- [x] App themes (Dark/Light/Handheld green/Pink) via single-source token swap over `theme.qss` + View menu radio. Gherkin 50/50.

## 4. Decisions made (do not reopen without reason)

- 100% original MIT code: public-domain math only, third-party files are never copied.
- Market references never ship: no competitor names, copy, or assets in code, UI, features, or docs (oct-2026 originality pass: Motif/Halo/Signal Drift/Paste-Up).
- No OpenCV / GPU in the core. Numba only as an OPTIONAL accelerator with numpy fallback (the base exe does not include it).
- Pillow + numpy is enough and keeps the `.exe` light. `imageio-ffmpeg` (v1.4 video) is OPT-IN extra only, never in base exe/requirements.
- PySide6 UI (not PyQt6). Preview with `QLabel + QPixmap`, no `QGraphicsScene` in v0.
- Original palettes, not 1:1 GameBoy/C64/NES clones. Auto-extract (v1.1) generates FROM the image, not clones.
- Custom canvas is Photoshop-style: presets fill W/H, typing W/H flips to Custom. No GIMP-style chain toggle (one interaction model only).
- Single canvas + hold-to-compare instead of side-by-side ORIGINAL/DITHER (pro look, less layout).
- Preview proxies (Draft/HD/Full) decouple playback resolution from export: editing stays light on low-end PCs, export is always full-doc. v1.5 exposes Full/Live/Still selector (same workers, user choice).
- Fixed signal chain becomes ordered FX STACK in v1.2, but migration keeps legacy render byte-identical (old presets render same).
- Refactor rule: logic lives in `app/ui/*_controller|flow|assembly` modules + `app/ui/panels/` package (one file per section group, same public names); FX dispatch in `app/fx_dispatch.py`, threshold maps in `app/ordered_maps.py`, binding factories in `app/ui/params_binding.py`. `MainWindow` only orchestrates and keeps the test-facing API.
- Menu/panel order: File (open | export/batch | preset share) / Edit (undo/randomize | clipboard | method step | transforms) / View (refresh/compare | zoom | Viewport | Theme), clipboard lives in Edit, preset share grouped in File. Panel is a 5-page custom accordion (IMAGE/DITHER/COLOR/FX/MOTION) inside the single scroll (plain widgets, no nested scrolls; layout test: 1 `QScrollArea`); widget attribute names unchanged so controllers/presets/tests keep working. `Drop=Batch`/`Jobs` stay in the action bar (batch flow + tests are wired to `win.spn_jobs`/`win.chk_batch_drop`).
- Pro polish: Help → About/Shortcuts, File → Open recent (capped, in prefs JSON), MOTIF box hidden unless method is `motif`, Export dialog pre-checks GIF when VIDEO preview is ON (dialog only, never Quick export), post-export Show in folder, rotating `data/trakkart.log` + crash dialog. `CHANGELOG.md` started.

## 5. Known tech debt

- Tests use `get_flattened_data()` (Pillow ≥10). Downgrading Pillow will break them.
- `floyd_steinberg` color at 3000px is still slow (~45s numpy); with numba <1s. The real flow dithers at source size; video preview defaults to Draft 720p so ED presets stay interactive.
- Multiprocess batch in loose scripts requires the `if __name__ == "__main__"` guard (Windows spawn); without it there is automatic fallback to sequential.
- Legacy `export_bundle()` (cover/small/1080p/metadata) is kept byte-identical for tests + the export-smoke gate; new code uses `export_with_options()`.

## 6. Out of scope (for now)

- Webcam, YouTube upload, BPM/key analysis with torch/librosa, login/cloud.
- Bridges to other apps (TRAKKOUT/TRAKKNAME) and shared naming: each TRAKK app is standalone.
- Video BASE: `imageio-ffmpeg` never ships in base exe/requirements (opt-in `requirements-video.txt` only; MP4 single-export only, batch stays GIF, no clip import by design).
- Explicitly rejected (adds nothing for offline covers): GPU backends (cupy/opencl), preset download from the internet (offline file share instead). Vector export IS in (v0.9, custom rect-only SVG). App themes veto LIFTED and DONE in v1.5 (single-source token variants).
