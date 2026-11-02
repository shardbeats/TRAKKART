# TRAKKART — Roadmap

> Context for continued development. Single source of truth for state and next steps.

## 0. Handoff — continuar en otra sesión (nov-2026)

- Estado: `main` limpio. Último bloque: loop cerrado (`dissolve_loop`),
  holds iguales, MP4 1080p/720p + estima honesta, diálogo vivo vs prefs
  rancias, Length 60s por streaming; docs en CHANGELOG Unreleased + QA
  v1.15 + MANUAL; research sin implementar en §7.7 (modos morph) y §8.
- Verificar al abrir: `git log --oneline -3` y
  `.venv\Scripts\python -m pytest tests -q -p no:cacheprovider --no-cov -m "not slow" -n auto`
  (verde) + `flake8 app tests tools main.py build_exe.py build_installer.py`
  (limpio). Venv: `.venv` local o `C:\venvs\dev` (CENTRAL_VEN). CI usa
  `QT_QPA_PLATFORM=offscreen`; pin `pytest<9.2` por pytest-bdd (ver
  MAINTENANCE.md: no levantar sin upgrade de pytest-bdd).
- Hilos abiertos: (1) Hold slider muerto cuando Length domina — RESUELTO con
  Hold-manda: total = transiciones + holds, Length derivada (readout, no
  spin); `dissolve_length` queda como compat ignorada. (2) Loop default True solo
  afecta con chain en sesión; tests al día. (3) R5+R6 hechos. (4) R1+R2+R3
  hechos (CANVAS_916 + Canvas check + BPM->Hold).
- Siguiente paso recomendado: **R7 (WebP) o R9 (separaciones)** según tiren
  más social o print; o morph F1 (§7.7).

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
- [x] `Source` palette mode: retiene color original como punto de partida editable (no re-mapea a BW/SLIME).
- [x] Depth slider: nº de niveles/steps usados de la paleta (mapeo previo al dither, vive en `RenderSpec` + `FIELDS`).
- [x] Per-swatch lock + shuffle + per-adjust lock/randomize (UI en palette dialog + Adjust row).
- [x] Midtones/highlights adjust (in addition to brightness/contrast/saturation) in `app/adjust.py` + UI.
- [x] Palette import/export/share `.json`/`.gpl` offline (misma UX que preset share). Gherkin 40/40.

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

### v1.6 — Dither-boy particle disperse, solo dispersión (done)
Scope frozen: single-image disperse/reassemble loop (no morph A->B yet).
Style: offline, Pillow+numpy only, deterministic seed, strict 0=off, loop-perfect.
- [x] Fase 1 (done): `app/disintegrate.py` + unit tests (wind vs random, seed determinista, dissolve 0 = identidad).
- [x] Fase 2 (done): `gif_dissolve_frames()` + export GIF/MP4 manual.
- [x] Fase 3 (done): preset fields (`dissolve_*`) + 2 presets bundled (`ASH_WIND`, `DUST_RANDOM`).
- [x] Fase 4 (done): docs (`QA.md`, gates `tools/quality_metrics.py`, `MANUAL.md`) + cierre.
  Note: gates stay at 52 Gherkin (no new scenarios; unit-covered); suite 438 -> 450.

### v1.7 — Morph A->B + UI dissolve (done)
Scope: swap between two images via shared particle cloud + MOTION controls.
- [x] Fase 5 (done): `morph_frames()` + `gif_morph_frames()` + tests.
- [x] Fase 6 (done): UI MOTION (modo dissolve/morph, segunda imagen) + export + docs.
  Modes `dissolve`/`morph` in `GIF_MODES`; `gif_frames(img_b=...)` dispatch;
  preview/export/batch share the path; strict 0=off holds.

### v1.8 — Morph cadena (hasta 6) + página MORPH (done)
Scope: playlist A->B->C... (A = src + hasta 5) con lista Add/Remove/Up/Down;
controles dissolve+morph mudados de MOTION a página MORPH propia.
- [x] Fase 1 (done): `morph_chain_frames()` + `gif_morph_frames(list)` + tests.
- [x] Fase 2 (done): página MORPH + playlist UI (mover controles de MOTION).
  `MORPH` page (panels/morph.py) con dissolve params + lista Add/Remove/Up/Down/Clear (tope 6: A + 5); `win.morph_list` + alias `morph_src` compat.
- [x] Fase 3 (done): preview/export wiring + docs + cierre.
  Chain flows through `gif_frames(img_b=list)`; preview (`VideoWorker`),
  export (`export_full`) and batch (dissolve fallback) share the path;
  suite 453 -> 457.

### v1.9 — Morph timing: holds + presupuesto por tramo (done)
Research: ImageMagick end-holds (`t==0||t==n-1 ? 150 : 8`), ComfyUI
`still_image_delay_ms`, Pillow per-frame duration list.
- [x] Fase 1 (done): joints `q=j/(nk-1)` + `hold_start/end` en engine + tests.
- [x] Fase 2 (done): presupuesto (mín 2/tramo, holds caben en 64) + `fps`
  threading + `dissolve_hold` preset + Hold slider + duration con holds + hint <8f.
- [x] Fase 3 (done): suite + docs + cierre. Suite 457 -> 460.

### v1.10 — Morph aspect fit + recorte por imagen (done)
Cadena con aspectos mezclados: cover-fit por imagen con su propio foco/zoom
(mismo crop_cover de IMAGE); A respeta el canvas del preset. MORPH: sliders
Crop X/Y/Zoom por fila + hint. Suite 460 -> 463.

### v1.14 — MORPH visual crop editor (done)
Recorte como IMAGE, no sliders: mismo CropEditorDialog con marco bloqueado
a A (ratio/modo/W/H deshabilitados) + Rotate/Reset; escribe fx/fy/zoom
(giro opcional) en la entrada seleccionada. Suite 465.
Cadena con aspectos mezclados: cover-fit por imagen con su propio foco/zoom
(mismo crop_cover de IMAGE); A respeta el canvas del preset. MORPH: sliders
Crop X/Y/Zoom por fila + hint. Suite 460 -> 463.
### v1.11 — Morph timing: auto-presupuesto al alargar cadena (done)
Research v1.9 confirmada por el uso: con total fijo, añadir imágenes acelera
cada tramo (6f/5 tramos = tramos de 1f que no muestran nada). Regla nueva:
más imágenes = más tiempo.
- Auto-crecer Frames solo hacia arriba al pick/morph-mode: `max(n, tramos*max(8, ~0.8s))`,
  tope 64, avisado en status; al encoger la cadena no se toca nada.
- Hint con f/s por forma cuando un tramo queda bajo 8f o 0.8s.
- Suite 464 -> 465, holds en cada junta, Length hasta 60s.

### v1.12 — Techo de 64 frames: ¿subirlo? (investigación, sin implementar)

Pregunta: el tope actual es 64. ¿Qué costaría 96/128 para animaciones más
largas o más fluidas? Medido en este repo (720p proxy, 3000px doc):

- RAM (frames vivos en lista): 720p = 2.8MB/f → 64f = 177MB, 128f = 354MB.
  Export full-doc 3000px = 27MB/f → 64f = 1.7GB (ya peligroso hoy), 128f = 3.4GB.
- CPU (exe portable SIN numba, peor caso): preview 720p ED ~1-2s/f
  (64f = 1-2 min en hilo, tolerable); export full-doc ED ~10-45s/f
  (64f = 10-48 min; 128f = 20-96 min, inutilizable).
- GIF: estimado 29MB @64f/720p, 59MB @128f; browsers recortan a ~50fps
  reales y sufren >25MB (ya avisamos en UI). MP4 aguanta 60fps sin problema.
- Código: GIF_MAX_FRAMES + ~8 clamps (gif.py, presets, export_prefs,
  dialog_fields, video_controller, params BINDINGS, dialogs) + tests
  que afirman 64 + estimate + spin Length (32s).

Hallazgo clave: fluidez = fps, no frames (60fps ya permitido). Largo =
segundos, no frames. Subir el techo global empeora RAM/export sin dar
fluidez por sí solo. Lo que otros hacen: ComfyUI capa transition_frames
en 60; ImageMagick no capa porque escribe a disco en streaming (nosotros
retenemos la lista entera en RAM para `save_gif`).

Recomendación (no implementada):
1. NO subir el techo global. GIF se queda en 64 (formato + RAM + 50fps).
2. MP4 largo por streaming: `write_mp4` acepta generador y renderiza
   perezoso (RAM plana); el límite pasa a ser CPU/tiempo, decisión del
   usuario con aviso de peso. Habilitaría hasta ~128f solo-MP4.
3. Largo barato sin frames extra: pingpong (duplica duración efectiva),
   drift loops (repite movimiento) y holds (ya implementados) — cero RAM.
4. Si se pide suavidad: 30-60fps ya existen; educar vía Hold/duration UI
   en vez de más frames.


### v1.13 — Duración total sagrada (done)
Frames/fps dejaban de mandar: la duración pedida se recortaba en silencio
(8s @ 24fps → 2.7s por el tope 64). Regla nueva: Length (s) es sagrado,
frames/fps son calidad.
- [x] Fase 1 (done): plan_dissolve (mín 2/tramo, holds caben en 64, pad
  hasta el total, tope 256) + fps threading en gif/export/batch/video.
- [x] Fase 2 (done): dissolve_length preset + meta/import roundtrip, spin
  Length ligado, fps re-render solo en dissolve/morph, label honesto con
  hold y hint por tramo, cap 256 con aviso. Suite 464 -> 465. Follow-up: holds en cada junta interior (cada forma se lee), Length 0.5-60s, cap total 256.

### v1.15 — Loop cerrado + holds iguales + MP4 honesto + diálogo vivo (done)
- Loop: `dissolve_loop` (preset, default True) + checkbox MORPH "Loop (last → first)"; pierna de cierre con still/coords exactos de A (joint byte-idéntico); holds: reparto igual por forma con A partida en apertura/cierre; ping-pong se omite con loop cerrado; presupuesto/budget/hints cuentan la pierna extra.
- MP4: streaming hasta 60s (3600f, O(1) RAM), tamaño MP4 Canvas/1080p/720p (default 1080p, stills full-doc), estima por contenido (trans 0.43 / hold 0.011 B/px, calibrada con x264) + avisos >100/400MB.
- R5+R6: `mp4_dims` siempre par + `macro_block_size=2` (1080x1920 exacto, 721→720) + `-movflags +faststart` en ambos writers.
- Hold-manda: total = transiciones + holds (sin pad a Length); Length pasa a readout derivado (spin read-only); `dissolve_length` queda como compat ignorada; holds solo ceden ante el cap (transiciones mandan).
- Holds iguales: el pad de Length se reparte entre todas las formas (≤1f de diferencia) en vez de ir todo a la última; `hold_joint` acepta lista por tramo de punta a punta.
- Export: spec animada siempre del preset vivo (las prefs rancias ya no hacen bypass: morph se colaba en exports mix); chain de sesión solo alimenta dissolve/morph (export + preview).
- Tests nuevos: loop abre/cierra en A, reparto de holds, estima MP4, diálogo vivo vs prefs rancias, gate por modo (+7).

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
- Datamosh module: `app/mosh.py` owns 7 flavors (blocks legacy byte-identical); `mosh_mode`/`mosh_seed`/`mosh_size` preset fields (old presets default `blocks`/0/100); dedicated DATAMOSH accordion page (params live there, order stays in FX STACK); stack entry + GIF mix dispatch by mode. 397 tests, 52/52 Gherkin, 5/5 gates.
- Export naming: `{base}_anim.mp4` (same stem as GIF); hardened sanitizer (no `__`, no edge junk); File name section with live preview + Reset; dialogs `deleteLater` on close (no hidden-window hoard).
- Stale export names: prefs carry `src_name`; new image → fresh default (quick falls back to dialog, never silently reuses); `load_pil` stamps `pasted_YYYYMMDD_HHMMSS`. 402 tests, 5/5 gates.
- Collision policy: single export (dialog + quick) always renames (`name_2`, …); skip/overwrite removed from the dialog (engine + batch keep all modes). 404 tests, 5/5 gates.
- Collision alert (`resolve_collision`): lists clashing files, Overwrite / Rename-as-`base_2` / Cancel with safe default; ⚠ hint in the plan; quick stays silent-rename; dialogs `deleteLater` + visible-first accept (no modal flake in CI). 409 tests, 5/5 gates.
- MOTION duration readout (driver spin removed: request-vs-reality split confused; label never lies). Animation suffixes `_gif.gif` + `_vid.mp4`. FPS combo sorted inserts (no stray 8).
- Refactor P1+M2: cached crop pixmap + `app/names.py` sanitizer home. 414 tests, 5/5 gates.

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
- dissolve_length: legacy request, IGNORED since Hold-manda (kept for preset compat); Length is derived = total / fps, shown as readout.
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
- Destination matching (pour, not scatter): nearest-neighbor / angle-paired
  assignment A->B so dots TRAVEL to their target instead of cloud-reform
  (TesseraUI pour; typexperiments glyph mapping). Keep seeded-greedy for
  determinism. Biggest single visual upgrade on this list.
  Done F3: `match_travel()` seeded-greedy grid matching + `travel_positions()`
  smootherstep pour (`dissolve_travel` 0-1, default 0 = legacy; MORPH slider;
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

Long term (new surfaces):
- Interactive cursor repel in the preview canvas via Qt mouse events
  (Componentry magnetic field; Particle Typography springs).
- Beat-grid sync: amount/speed keyed to BPM markers.
- Animated WebP export (smaller than GIF; Pillow supports per-frame
  duration lists too) + PNG-sequence zip (dither_app ships both).
  --> Promoted with concrete spec in §8 R7 (nov-2026 research).
- In-app text-to-image source so TEXT_CARD presets need no paste step.

### 7.7 New morph modes: fields × stagger × ease (researched nov-2026)

Hoy solo hay `wind` + `random` (`disperse_positions`, `app/disintegrate.py`).
Sondeo: taxonomías de forces (Gravity/Wind/Turbulence/Vortex/Attractor/
Spring), burst con varianza de velocidad (muchas lentas, pocas rápidas),
flow-fields de ruido suave (bake-then-play), release escalonado por mapa
(graph/axis/rank), ripple/wave/pulse sobre dot-grids, block dissolve por
celdas. Todo es expresable en nuestro diseño (campo cerrado × envolvente
periódica, sin integración: por eso somos loop-perfect y deterministas;
la simulación con velocidades/drag NO entra: rompería el loop).

Regla de diseño (no explosión combinatoria, filosofía FX stack): tres ejes
ortogonales en vez of N modos sueltos. Mismo coste O(n) vectorizado, misma
RAM (MAX_POINTS), mismos invariantes (seeded, frac%1 loop-perfect).

- DIRECTION (campo de offset, `dissolve_mode` extendido; wind/random intactos):
  `burst` (radial-out desde centro, speed por rank 0.3+rank para no hacer
  anillo mecánico), `suction` (radial-in: converge; ideal logo-stings §7.5),
  `vortex` (tangencial + leve pull outward, ángulo por posición),
  `rain` (caída con frac² + floor-bounce por plegado: periódico),
  `rise` (subida: hace real el preset propuesto EMBER_RISE §7.4),
  `wave` (seno viajero en x, fase lockeada al loop),
  `ripple` (anillos concéntricos desde centro, seno radial),
  `flow` (campo de value-noise suave con seed, FIJO por clip como la
  turbulencia actual: bake once O(HxW), lookup por frame; organic drift),
  `blocks` (block dissolve por celdas pixel_size con orden por rank: sin
  nube, pop por bloques; el más barato y el más dither-nativo).
- STAGGER (`dissolve_stagger`: off | rank | radial | scan | sweep):
  delay por partícula con pin al joint `frac_i=(frac+delay_i·sin(π·frac))%1`
  (shift puro rompería el ensamblado del joint y los holds harían pop;
  pineado: cero shift en ambos joints, olas llenas mid-loop, loop intacto
  por el %1). `rank` usa el mapa Bayer de `ordered_maps.py`
  (orden de matriz = firma dither); `radial` = ola centro-fuera en el
  gather; `scan` = filas top-down; `sweep` = reensamblado left-right
  (converge-to-shape). Determinista, sin RNG extra.
- EASE (`dissolve_ease`: sine | cubic | linear en F1; elastic | bounce en F2):
  forma de la envolvente en vez del sin fijo; sine = legacy byte-identical;
  cubic = sin³ (ataque marcado, dwell largo); linear = tent a velocidad
  constante. rain/rise pliegan su drop dentro del field y la envolvente
  lo puerta (el ease siempre manda, ningún control miente).
- Preset/UI/migración: 3 fields (`mode` oneof extendido + `stagger` +
  `ease`, defaults wind/off/sine = renders legacy byte-identical);
  MORPH: combo de modo extendido + 2 combos; plan cuenta igual (el stagger
  no cambia conteos, solo reparte qué partícula se mueve cuándo).
- Tests: determinismo (same seed = same pixels) + loop-perfect
  (frac 0 == 1 por modo/stagger/ease) + joint ensamblado pineado por
  stagger + legacy byte-identical por defecto + 2-3 escenarios Gherkin
  (burst determinista, rank neutral con stagger off, blocks en # formas).
  Done F1: `features/morph_modes.feature` (3) + unit en
  `tests/test_disintegrate.py` (11 modos × 5 staggers × 3 eases en loop,
  ancla blocks 9/64, fallback) + combos MORPH (11/5/3). Gates 55.
  Done F2: elastic/bounce + `dissolve_dotsize` 1-4 (joints a 1px) +
  pack EMBER_RISE/GRAVITY_DROP/POUR_FAKE + 4º Gherkin. Gates 56.
- Fases: F1 = fields (burst/suction/vortex/rain/rise/wave/ripple/flow/blocks;
  rise entra por simetría con rain, 3 líneas) + stagger (rank/radial/scan/sweep)
  + ease sine/cubic/linear (linear entra por neutralidad, 1 línea);
  rain/rise pliegan su drop (frac² + bounce) DENTRO del field y la envolvente
  lo puerta (el ease sí manda); blocks popea por celdas pixel_size con ancla
  del 15% denso (sin ancla flashea blanco a pico: medido); stagger pineado
   al joint (shift puro rompía holds). F2 = elastic/
   bounce + acople con dot-size (§7.6) + preset pack (EMBER_RISE,
   GRAVITY_DROP con rain, POUR Fake con flow + stagger rank).
   Done F2: elastic = sine·(0.65+0.35cos) pico ~0.88, bounce =
   sine·(0.55+0.45|sin|) pico 1.0; dotsize 1-4 con joints a 1px
   (slider MORPH + BINDINGS); pack de 3 bundled.
- No entra: física integrada (springs/drag con velocidad), interactividad
  hover/explode en export (solo tendría sentido en preview; ver §7.6
  long-term), nuevos formatos aquí (eso es §8 R7).

## 8. Research backlog (web, nov-2026) — candidates, not scheduled

Sondeo externo (specs oficiales + docs de Pillow/imageio) cruzado con
mediciones en este repo. Solo entra lo offline, Pillow/numpy/imageio y
coherente con TRAKK = stills dither + videos DE esos stills.
Verificado hoy en código: (1) imageio reescala el MP4 a múltiplos de 16
(1080x1920 sale como 1088x1920: rompe el 9:16 exacto que exige Canvas);
(2) Pillow ya colapsa holds idénticos del GIF (medido: 114f -> 1f, 171B).

### 8.1 Delivery social (encaje máximo, coste bajo)

Fuentes: Spotify Canvas guidelines (MP4 o JPG, 9:16, 720-1080px, 3-8s);
guías de specs sep/oct-2026 (Reels/Stories/TikTok/Shorts = 1080x1920 9:16;
YT thumb 1280x720 16:9; square 1080x1080; 4:5 1080x1350; safe areas con
chrome arriba/abajo ~250px).

- [x] R1 — Canvas recipe preset: 9:16 + 1080x1920 + 24/30fps + Length 7.5s
  (H.264 + faststart). A 8.000 exactos hay reportes de rechazo: apuntar
  ≤7.9s. Nuestros 3 modos ya mapean 1:1 con la taxonomía Spotify
  (Continuous=loop, Rebound=ping-pong, Hard Cut=loop off). Coste S.
  Done (Hold-manda era): `CANVAS_916` bundled (9:16, export 1920,
  dissolve 64f/30fps/Hold 2.7 → 226f = 7.53s, loop) + R5/R6 (dims exactas,
  faststart) debajo.
- [x] R2 — "Canvas check": si ratio 9:16 y (Length fuera de 3-8s o MP4 size
  fuera de 720p/1080p), hint en el duration label. Coste S.
  Done repartido por localidad de datos: duration label avisa duración
  (ratio 9:16 + actual fuera de 3-8s); export dialog avisa tamaño
  (9:16 + mp4_size Canvas o actual fuera de 3-8s).
- [x] R3 — BPM -> Length: inputs BPM + compases -> Length = bars*240/BPM
  (120BPM/2 compases = 4s; 140BPM/4 compases = 6.86s). El loop no arranca
  en downbeat (Spotify loopea por su reloj) pero el pulso interno coincide
  con el tema. Coste S, encaje total con beatmakers.
  Done (Hold-manda era): `hold_for_target()` resuelve Hold para el target
  (capped 3.0s, fits honesto); VIDEO suma fila ♫ BPM/Bars + Set Hold.
- [x] R4 — Social recipe presets (bundled JSON): YT thumb 1280x720, square
  1080x1080, portrait 4:5 1080x1350, master 9:16 1080x1920 (un master cubre
  Reels/Stories/TikTok/Shorts). Coste S.
  Done: `YT_THUMB` (16:9/1280), `SQUARE_11` (1:1/1080),
  `PORTRAIT_45` (4:5/1350); master = `CANVAS_916` (R1).

### 8.2 Formato/codec (medido, coste bajo)

- [x] R5 — macro_block_size=2 + even-guard en mp4_dims (BUG verificado hoy:
  1080x1920 -> 1088x1920, 404x720 -> 416x720; H.264/yuv420p solo exige
  múltiplos de 2). Sin esto ningún MP4 es Canvas-válido. Coste XS, hacerlo ya.
  Done: `mp4_dims` redondea a par hacia abajo + `macro_block_size=2` en
  `write_mp4`/`write_mp4_iter`; 1080x1920 sale exacto, 721x721 -> 720x720.
- [x] R6 — faststart (`-movflags +faststart`) en write_mp4/write_mp4_iter:
  playback progresivo en web/stores, coste ~cero. Hacer con R5.
  Done: en ambos writers; test afirma moov antes que mdat.
- [x] R7 — Animated WebP export (promueve §7.6): Pillow save_all + duration
  (int o lista) + loop=0 + minimize_size, sin deps nuevas, ~1/3 del GIF a
  igual calidad y full color; todos los browsers lo reproducen. Nuevo
  `save_webp()` espejo de save_gif + checkbox en diálogo + bundle
  `*_anim.webp`. Coste S/M.
  Done: `save_webp()` (full color, minimize_size, quality 80) +
  `estimate_webp` (GIF//3) + `{base}_anim.webp` vía `webp_name()` +
  checkbox "Animation WebP" en diálogo (plan + colisiones) + `webp=True`
  en `export_full` (reusa los frames del GIF; dialog-only como MP4,
  batch sigue GIF).
- [x] R8 — GIF estimate v2 (hold-collapse aware): la estima actual
  (frames*w*h//2) miente 100-1000x en clips con holds porque Pillow
  fusiona frames idénticos. Estimar transiciones a coste completo + 1f
  por forma quieta. Coste S.
  Done: `estimate_gif(n_trans, w, h, n_hold_forms=0)` (+ `estimate_webp`
  espejo); migran video_controller (label, ping-pong ya no duplica),
  diálogo GIF+WebP (plan 256f una vez) y `_estimate_bytes` (extra
  gif_trans/gif_forms, default = forma vieja). Medido 480p real:
  12.7x→3.8x over, misma dirección segura.

### 8.3 Print (encaja con Vector Pro)

- [x] R9 — Separaciones por tinta (RISO/serigrafía): un PNG por color de
  paleta (spot separations) + marcas de registro. Flujo real de
  print-shops, sin OpenCV. Coste M.
  Done: `app/separations.py` (nearest-color plates L + crosshair-in-circle
  por esquina + `effective_palette` espejo del pipeline + `plate_count`
  sin render); `{base}_sep_{NN}_{RRGGBB}.png` vía `export_full(sep=True)`
  (dialog-only); diálogo con checkbox + plan + colisiones (glob exacto
  post-accept). Pareja del flujo Vector Pro black-ink.

### 8.4 Workflow/automatización

- [x] R10 — CLI headless (`TRAKKART.exe --cli --preset X --in ... --out ...`):
  sellos con 20 singles/mes lo agradecen; UI y engine ya están separados
  por servicios. Coste M.
  Done: `app/cli.py` (`run_cli` → exit 0/1/2, `--list-presets`, file +
  folder vía batch bundle, skip-existing, safety guard, stateless sin
  history); `main.py` despacha `--cli` antes de importar Qt (verificado
  sin PySide6 en intérprete fresco); MP4/WebP/seps quedan dialog-only;
  MANUAL con sección.
- [x] R11 — Watch-folder (carpeta vigilada -> auto-batch con preset fijo).
  Coste M. Alternativa barata: "re-batch last folder" en 1 click (S).
  Done: `app/ui/watch_flow.py` (QFileSystemWatcher + 2s debounce +
  skip-existing idempotente + 3s settle anti-copias-parciales + preset
  fijo por NOMBRE recargado por ciclo + jobs=1 + stateless sin history
  + cero modales) + `WatchDialog` + File → Watch folder... (checkable).
  La alternativa barata no hizo falta (el mismo coste cubre el caso).

### 8.5 Polish UX/motor (solo si sobra ciclo)

- [x] R12 — Safe-area guides 9:16 (franjas top/bottom de chrome
  IG/TikTok/Shorts) en crop editor + preview. Coste S/M.
  Done: `app/ui/safeareas.py` (bandas 250/1920 como fracción + overlay
  Qt, display-only); preview still (sync + async) + crop editor (frame
  9:16); View → Safe areas 9:16 (default ON). Video frames excluidos
  (coste por frame, documentado).
- [x] R13 — Wipe compare (slider antes/después) además de hold-to-compare.
  Coste S.
  Done: slider Wipe bajo el preview (ORIGINAL izq / result der,
  divisor ámbar, 0 = off); original alineado vía canvas vivo;
  composita a tamaño display; hold manda mientras se pulsa; video lo
  ignora; sobrevive refreshes (router `redisplay`).
- [x] R14 — Congelar roster de motores en 36: más difusiones (Ostromoukhov
  y cía) aportan <5% visible para covers y cada motor es superficie de
  test/preset para siempre. Decisión propuesta.
  Done (decisión adoptada): roster congelado con test que afirma la lista
  exacta (`test_engine_roster_frozen_r14`); añadir un motor exige decisión
  consciente (lista + docs). NOTA: el roster de PARTÍCULAS (11 fields F1/F2)
  no entra en este freeze (eje vivo).

### 8.6 Rechazado explícito (no reabrir sin motivo)

- AV1/codecs nuevos: H.264 es el codec universal de Canvas/socials; AV1
  encode es lento y nada lo exige. Pillow+numpy+imageio bastan.
- IA en nube, cuentas, uploads, login, auto-update/store: rompen
  offline-first y el §6. Text layer in-app: ya se quitó en v0.14.

### Recomendado (siguiente)

1. R5+R6 HECHO + Hold-manda HECHO + R1+R2+R3 HECHO → 2. R7 (WebP) o
   R9 (separaciones) según tiren más social o print → 3. morph F1 (§7.7).
