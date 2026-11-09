# QA — TRAKKART

Verification procedures (TRAKK standard).

## Fast loop (dev)

Local `.venv` only. The commands below use `.venv`.

```
.venv\Scripts\python -m pytest tests -q -p no:cacheprovider --no-cov -m "not slow" -n auto
```

`-n auto` (pytest-xdist) is the big lever: ~11x faster locally
(6.4 min → ~35 s). Without it, use `-n 4` or nothing.

### CI rules (test seams)

Two failures that only show up on runners and are easy to reintroduce:

- **No absolute local paths in tests.** Subprocess `cwd`/commands must use the
  repo root (`Path(__file__).resolve().parents[1]`), never a dev path such as
  `D:\...`. A local path makes CI fail with `NotADirectoryError`.
- **Patch stable seams, not moving backends.** UI/debounce tests patch
  `app.ui.preview_controller.render_still` (the single function `refresh()`
  calls). Do not patch `render_service.render_full` or `app.gpu.*`: preview
  routing (CPU ↔ GPU ↔ worker) moves those, the mock counts 0, and CI fails
  while the feature is healthy (CI #148, `test_debounce_coalesces_renders`).
  Count the seam and delegate to the real function.

Quick guard:

```
.venv\Scripts\python -m pytest tests/test_stability.py::test_debounce_coalesces_renders -q
```

## Full suite + coverage

```
.venv\Scripts\python -m pytest tests -q -n auto
.venv\Scripts\python -m pytest tests -q -n auto --cov=app --cov-branch --cov-report=term-missing --cov-report=html:data/quality_html
.venv\Scripts\python -m flake8 app tests tools main.py build_exe.py build_installer.py
```

> `coverage run` misses xdist workers (separate processes) — always go through `pytest-cov` as above.

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
features/morph_modes.feature :: 4 scenarios (burst determinism, stagger-off legacy, blocks ends assembled, elastic loop + fat-dot joints)
features/ux.feature       :: 2 scenarios (viewport modes, heavy presets)
```

Total: 61/61. Steps live in `tests/bdd/test_steps_*.py` by domain (scenarios bound per module), shared givens in `tests/bdd/conftest.py`, `ctx` fixture in `tests/conftest.py`.
Current suite: 572 tests (440 fast + 132 slow; `slow` = whole files with `pytestmark = pytest.mark.slow`, excluded with `-m "not slow"` in the fast loop).
`tools/bench.py` is manual (not a gate): B&W 960px ~0.01s, color 960px ~0.02s with numba.
If you add a scenario, update the `gherkin` gate in `tools/quality_metrics.py` and this file.

## Particle disperse (v1.6, solo dispersion)

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py -q -p no:cacheprovider --no-cov
```

Engine: `app/particles/` (BW dither -> points -> breathe `sin(pi*frac)`, loop-perfect; `app/disintegrate.py` is a shim).
GIF bridge: `app/anim/frames.py::gif_dissolve_frames` (reuses `save_gif` + `video_io.write_mp4`; `app/gif.py` is a shim).
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

## Morph aspect fit + per-image crop (v1.10)

Chain images no longer stretch: each B..F is cover-fit to A's canvas with its
own focus (X/Y 0-100) + zoom (1-4x) — same `crop_cover` semantics as IMAGE.
A honors the preset canvas (ratio/crop/focus/zoom). MORPH page has Crop X/Y/Zoom
sliders bound to the selected chain row; session-only (not in preset).

## Morph timing: holds + per-segment budget (v1.9)

Research: ImageMagick `-set delay "%[fx:(t==0||t==n-1) ? 150 : 8]"` (pause only
assembled ends), ComfyUI `still_image_delay_ms` (default 2500ms per end),
Pillow per-frame `duration=[...]` list.
Here (v1.9–v1.15, sacred Length): `dissolve_hold` seconds per end (MORPH Hold slider 0-3s, default 1.0)
-> duplicated assembled frames (GIF uniform fps + MP4 + preview scrub all work,
no duration-list quirks). Transition budget: morph reserves 2 frames minimum per
segment so every form appears assembled; joints sample `q=j/(nk-1)` (no pop);
holds shrink to fit the 64-frame cap (transitions win). Duration label shows
loop + hold (`= 5.3s loop + 2.0s hold`); hint when a segment gets < 8 frames.

## Sacred Length (editable total, no pad)

Hold-manda stays the engine rule (total = transitions + requested
holds, never padded), but the Length spin is editable again (0.5–60s,
was read-only): it is the sacred total for every MOTION mode.
Particle (dissolve/morph): editing Length solves the Hold needed
(clamped 0–3s, honest short-message when unreachable); dragging Hold
still adds time and Length follows. Rest (phase/hue/both/glitch/mix):
editing Length sets n = Length x FPS (capped at 256f, honest message);
FPS changes keep the seconds and only gain/lose frames (quality).
`dissolve_length` stays in presets for compat but is ignored; no new
preset fields — Length derives from Frames/FPS/Hold. Holds only
shrink against the output cap (256 GIF/preview, 3600 MP4 streaming);
transitions always win. Non-particle MP4 over 256f stays capped
(streaming that path is future work).

## Social delivery (R1+R2, Spotify Canvas shaped)

- R1 recipe `CANVAS_916`: 9:16, export long side 1920 (= 1080x1920),
  dissolve 64f/30fps/Hold 2.7s → 226f = 7.53s closed loop (inside the
  3–8s window, under the ~7.9s rejection reports). Faststart + exact
  dims come from R5+R6 underneath.
- R2 Canvas check (split by data locality): VIDEO duration label warns
  when a 9:16 particle clip lands outside 3–8s; the export dialog warns
  when a 9:16 doc would export MP4 at full-doc size or outside 3–8s.
- R3 beat grid REMOVED (too fiddly): no more ♫ BPM/Bars row, no
  `hold_for_target`. Sacred Length (editable spin) covers every mode
  instead — particle solves Hold, rest derive n = Length x FPS.

## Animated WebP (R7)

```
.venv\Scripts\python -m pytest tests/test_gaps.py::test_save_webp_roundtrip_and_estimate tests/test_gaps.py::test_export_service_webp -q -p no:cacheprovider --no-cov
```

`save_webp()` = `save_gif()` espejo a full color (sin quantize 128);
`estimate_webp` = GIF//3 (hold-aware desde R8). Dialog-only como
MP4 (batch sigue GIF): checkbox + plan + colisiones + `export_full(webp=True)`.
Unit-covered, sin escenarios Gherkin nuevos (gates siguen 52).

## Honest weight (R8)

`estimate_gif(n_trans, w, h, n_hold_forms)` = transitions at full
cost + 1f per still form (Pillow merges identical holds; measured
114f→1f). Migrated: duration label (mirrored ping-pong no longer doubles),
dialog (256f plan once for GIF+WebP) and `_estimate_bytes`
(extra gif_trans/gif_forms, default = old shape for batch).

## Ink separations (R9)

```
.venv\Scripts\python -m pytest tests/test_separations.py -q -p no:cacheprovider --no-cov
```

`app/separations.py`: nearest-color plates (L, black ink on
white, row-chunked) + crosshair-in-circle per corner on every
ink + `effective_palette` (same resolution as the pipeline:
custom > SOURCE extracted > BW > named+depth). Separated from the
exported main ("separate what you see", same size). Dialog-only
(checkbox + plan + collisions); no batch. Unit-covered, Gherkin 52.

## Morph F1: fields × stagger × ease (§7.7)

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py tests/bdd/test_steps_morph.py -q -p no:cacheprovider --no-cov
```

11 fields (`wind/random` legacy + burst/suction/vortex/rain/rise/
wave/ripple/flow/blocks), 5 staggers (off/rank/radial/scan/sweep,
joint-pinned: joints stay assembled under holds), 3 eases
(sine/cubic/linear; elastic/bounce = F2). Legacy triple
wind/off/sine byte-identical (fast path). 3 preset fields with
migration (defaults = legacy). Gherkin 55 (`morph_modes.feature`).
Deviations from research noted in §7.7 (rise+linear in F1, flow
closed-form not baked, blocks 15% peak anchor).

## Morph F2: elastic/bounce + dot-size + preset pack (§7.7)

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py -q -p no:cacheprovider --no-cov -k "f2 or preset_pack or elastic"
```

elastic/bounce cierran el loop (pico ≤1, joints a 0);
`dissolve_dotsize` 1-4 hincha dots con la envolvente (joints a 1px,
slider MORPH); bundled EMBER_RISE (rise/floyd), GRAVITY_DROP
(rain/bayer8), POUR_FAKE (flow+rank+amount 0.5). 4º Gherkin
(elastic loop + fat-dot joints). Gates 56.

## Morph F3: travel/pour A->B (§7.6)

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py -q -p no:cacheprovider --no-cov -k "f3 or travel"
```

`dissolve_travel` 0-1 (default 0 = legacy cloud byte-identical) +
MORPH Travel slider; `match_travel()` seeded-greedy 1:1 (grid +
expanding rings, padded counts, empty-safe fallback); pour mixer =
smootherstep over stagger-shifted q (joints exact, no seam jump),
cloud gated by the ease envelope; strict 0=off hard-cuts even with
travel on; blocks ignores travel. 5º Gherkin (pour ends + seam).
Gates 57.

## Morph F4: color particles (§7.6)

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py -q -p no:cacheprovider --no-cov -k "f4 or tint"
```

`dissolve_tint` 0-1 (default 0 = legacy BW) + MORPH Tint slider;
`sample_colors()` per-dot source hues (travel legs lerp src→dst),
`tint_strength()` = preset x loop envelope (joints land black =
byte-exact stills), `tint_dots()` None at 0 (legacy rasterizer
untouched; all-black equals the L path pixel for pixel);
`render_points(..., colors)` vectorized RGB path (kxk blocks incl.);
strict 0=off gates tint off (frozen stills). 6º Gherkin
(tinted mid + black ends). Gates 58.

## Morph F5: motion trails (§7.6)

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py -q -p no:cacheprovider --no-cov -k "f5 or trail"
```

`dissolve_trail` 0-8 (default 0 = legacy) + MORPH Trail slider;
`trail_decay()` age falloff × envelope (`ghost_entries()` oldest→
newest, joints ghost-free = byte-exact stills); `render_points(...,
trail)` paints ghosts before the core (gray ints / faded hues,
kxk sizes kept); per-leg deque reset, O(K·n) RAM-bounded; strict
0=off skips ghosts. 7º Gherkin (ghosts mid + clean joints).
Gates 59.

## Morph F6: Heckel shade (§7.6)

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py -q -p no:cacheprovider --no-cov -k "f6 or shade"
```

`dissolve_shade` bool (default off = uniform) + MORPH Shade checkbox;
`darkness_map()` per-dot source darkness, `frame_dot_sizes(...,
shade=)` scales 1..dotsize by darkness x envelope (joints stay 1px);
length mismatches fall back to uniform; Dots=1 keeps the legacy None
path; strict 0=off untouched (frozen stills need no sizes). 8º Gherkin
(dark dots bigger + sharp joints). Gates 60.

## Morph F7: palette following

```
.venv\Scripts\python -m pytest tests/test_disintegrate.py -q -p no:cacheprovider --no-cov -k "f7 or ink or paint"
```

`morph_ink()` renders the form's still first (BW dither = legacy,
palette = palette-dithered still, `inked_points()` dark-dot extract +
per-dot ink colors); `dissolve adjust` grades the dots, COLOR palette
prints the inks at full strength (joints = ink stills = holds, no
pop); BW presets keep every byte identical; strict 0=off holds.
9º Gherkin (ink dots + ink ends). Gates 61.

## Perf round (measured, nov-2026)

| Lever | Before | After | How verified |
|---|---|---|---|
| GIF RAM peak (226f@1080x1920) | ~1.9GB transient (rgb+P lists) | ~0.5GB (incremental quantize) | code read + determinism test |
| Absurd GIF (3000px/424f) | OOM kill (~9GB) | fail-fast MemoryError (`MAX_GIF_PIXELS` 1.2GP) | trip tests (save + builder) |
| Startup (dev import) | 0.86s (numba 47%) | 0.39s (lazy import, compile at 1st ED render) | importtime + fresh-interp test |
| `test_history_prune` | 14–29s (fsync ×1010 commits) | 0.76s (bulk seed + prune-when-needed) | durations |
| MP4 downscale 226f | ~12s bicubic | ~7s bilinear | microbench x5 |
| Median-cut on frame 0 | 2× (waste) | 1× (palette reused, byte-identical) | determinism test |
| `-pix_fmt` duplicate | ffmpeg warning | gone (imageio adds yuv420p; meta asserts it) | immeta check |

Deliberately NOT done: numpy ED paths (dead code in practice —
numba ships in requirements+exe, fallback+parity cover it);
touching batch/proxy/debounce (already right); exe-size audit
(needs a rebuild to measure; UPX rejected for SmartScreen).

## Polish (R12+R13)

```
.venv\Scripts\python -m pytest tests/test_polish.py -q -p no:cacheprovider --no-cov
```

- R12: 9:16 still previews (sync + async) + crop editor frame show
  250px chrome bands + dashed amber edges (fractions of height, any
  scale); View → Safe areas 9:16 default ON, display-only. Video
  frames excluded (per-frame cost).
- R13: Wipe slider under the preview (ORIGINAL left / result right,
  amber divider, 0 = off); original aligned through the live canvas;
  display-size composite; hold wins while held; video ignores it;
  survives refreshes via the `redisplay` router. Manual: drag wipe on
  a 9:16 cover, toggle safe areas, hold-to-compare still shows pure
  ORIGINAL.

## Headless CLI (R10)

```
python main.py --cli --list-presets
python main.py --cli --preset SLIME_FS --in cover.png --out out
python main.py --cli --preset SLIME_FS --in covers --out out
.venv\Scripts\python -m pytest tests/test_cli.py -q -p no:cacheprovider --no-cov
```

`--out` is always a folder; bundle = batch UI; skip-existing;
safety guard on single; stateless (no history); jobs=1 fixed
(spawn-free in exe). `--cli` dispatches before importing Qt
(fresh-interpreter test asserts it). Exit 0/1/2.

## Watch folder (R11)

```
.venv\Scripts\python -m pytest tests/test_watch.py -q -p no:cacheprovider --no-cov
```

File → Watch folder… (checkable): input/output + fixed preset by
name (reloaded each cycle: edit it and it applies). QFileSystemWatcher
+ 2s debounce + 3s settle (never bakes partial copies) +
idempotent skip-existing + BatchWorker jobs=1 + stateless (no
history) + zero modals (status only). Stop: same menu, close app,
or deleted preset. Unit-covered with synchronous worker stub (no
event-loop waits), Gherkin 52.

## Morph loop + equal holds + honest MP4 (v1.15)

- Loop (MORPH "Loop (last → first)", default ON, `dissolve_loop` preset):
  last form morphs back into A through one cloud; opening and closing
  frames are byte-identical A; A's hold share splits across both ends.
  With loop closed, ping-pong is skipped (already seamless).
- Holds are shared equally across forms (≤1f apart);
  `hold_joint` accepts a per-joint list end-to-end. (Length pad removed
  since Hold-manda: total = transitions + holds.)
- MP4 size (Export dialog): Canvas/1080p/720p, default 1080p (stills stay
  full-doc). Estimate is content-aware (noisy transitions vs duplicated
  holds, calibrated with x264); hints above ~100MB, warning above ~400MB.
- Export dialog animation spec always follows the live VIDEO section;
  stale prefs can no longer smuggle a morph mode into a mix export.

## Manual GUI checklist (before each release)

1. `run.bat` opens without traceback (offscreen in CI: `QT_QPA_PLATFORM=offscreen`).
2. Open PNG/JPG → single-canvas preview updates when moving threshold/pixel/method/palette/brightness/ratio. Hold "Hold to compare" (or Space) shows ORIGINAL; release returns to result. CUSTOM PALETTE loads named palettes as editable swatches (dirty shows "(Custom)"); 🎲 generates harmonious ramps.
2b. VIDEO mode: animated preview plays (Draft 720p default); switching to Full (doc) re-renders bigger; FPS change does NOT re-render (only retimes).
3. Preset saves, reloads and applies sliders (incl. grade/texture/glitch + canvas W/H + anim).
3b. CANVAS → ratio presets fill W/H; typing W/H flips Ratio to Custom. "Adjust crop..." opens the visual editor (frame + grid, drag pans, wheel zooms, Rotate/Reset/ratio/mode incl. Custom with free frame); Done applies, Cancel keeps values.
4. Export dialog generates `<base>.png|jpg|webp` at the canvas W×H + optional `*_thumb1080p`, `*_vector.svg`, `*_gif.gif`, `*_vid.mp4`, `*_metadata.json` in the chosen folder (no size spin: size comes from CANVAS). MP4 defaults to 1080p (selector: Canvas/1080p/720p); the animation line shows the live VIDEO mode + honest `~MB` estimate.
4. `*_thumb1080p` opens directly in TRAKKOUT with no odd cropping.
5. `build_exe.py` produces a portable `dist/TRAKKART.exe` that starts on double-click.
5b. Release extras: `build_installer.py` builds the Inno Setup installer (needs `dist/TRAKKART.exe` + ISCC); session smoke = open image → close → reopen restores it; Edit → Redo (Ctrl+Y) after Undo; Settings Export…/Import… round-trips the JSON; Settings → Extras shows accel/MP4 state (all included in the exe); F1 opens MANUAL.md; Help → Show logs folder reveals data dir.

## Perf (manual, before release)

- Floyd B&W 3000px < 30s, Floyd color 1080px < 12s (measured in dev with `tools/bench.py` if present).
- If Floyd color gets close to the limit, raise the preset `pixel_size` before touching the algorithm.
- Video preview: 6 mix frames at Draft 720p < 1s; Full-doc render may take seconds on ED presets (background thread, debounced) — expected, not a freeze.
- GIF exports at canvas size: check the `~MB` plan estimate in the export dialog before writing 12f 3000px+ GIFs.
