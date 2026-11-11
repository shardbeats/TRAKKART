# CHANGELOG — TRAKKART

Release history (newest first). Details live in `git log` and `ROADMAP.md`.

## [1.3.1] - 2026-11-10
### Changed
- Portable is now a one-dir ZIP (`TRAKKART-portable-<version>.zip`): instant startup, no per-launch extraction to `%TMP%`.
- Installer installs the same one-dir build; output moved to `dist-installer/`.
- Removed the one-file build (`build_exe.py`); use `build_portable.py`.

## Unreleased
- Canvas preview redesign: the fixed 520px QLabel is now a fit/zoom/pan
  canvas (`app/ui/preview_canvas.py`). Fit fills the viewport (small images
  up to 3x), 100% is real 1:1 (not 4x), wheel zooms at the cursor, drag pans,
  double-click fits, and a big pixmap can no longer force the window wider
  (minimumSizeHint stays 200x200). The title row shows Fit / %.
- 100% now renders full/document pixels on demand (async for heavy presets;
  document size when the source has enough detail) instead of 1:1 of the
  proxy. The preview proxy is adaptive (640px floor, viewport-sized up to
  1600px, HiDPI aware) and resizing schedules one debounced Live re-render.
- Wipe compare is draggable directly on the canvas (left drag; middle-drag
  pans), keeping the slider in sync. Wipe 100% keeps the framed original
  (no raw-source geometry jump), safe-area guides stay visible during wipe,
  and the aligned original is cached per canvas state (wipe ticks ~28ms on
  a 12MP source, was 75-311ms).
- Crop editor contain/stretch/blur cache their canvas + pixmap: repaints are
  ~1-4ms on a 12MP photo instead of 160-520ms.
- Canvas correctness (bug hunt): `contain` no longer inflates the working
  canvas (a 3000x2000 landscape into 9:16 used to render 3000x5333; it now
  caps at the document long side), `cover` can no longer return a 0-pixel
  side (1px sources + extreme custom ratios), exports validate empty renders
  before writing and build the thumbnail first (no partial bundles), vector
  grids cap at the document size so large sources/`contain` no longer trip
  the cell limit, and changing the ratio inside the crop editor now keeps
  W/H in sync with the main canvas (label/export/metadata agree).
- CI fix (#148): `test_debounce_coalesces_renders` mocked
  `render_service.render_full`, but previews have rendered through `app.gpu.*`
  since `5ea3e58`, so the counter stayed at 0. The test now patches the stable
  `preview_controller.render_still` seam and delegates to the real render.
  `QA.md`/`MAINTENANCE.md` document the rule (and the no-hardcoded-local-paths
  rule from `64e5d0c`) so it does not come back.

## v1.3.0 — 2026-11-03
- CI fix: subprocess tests used a hardcoded local `cwd` (`<repo>`) and failed on runners with `NotADirectoryError`; both now use the repo root (`Path(__file__).parents[1]`).
- Docs synced to reality: 572 tests (440 fast + 132 slow) + 61 Gherkin scenarios + 13 bundled presets (`README.md`, `MAINTENANCE.md`, `QA.md`, `ROADMAP.md` handoff); numba ships in the bundle with numpy fallback (was documented as optional).
- Correctness (R4): `normalize_stack` warns on unknown effect ids instead of dropping them silently; preview compensates pixel-unit FX (`glow_radius/border/scanlines/grille/halftone/letterbox`) by the downscale factor; `RenderSpec.meta()` now includes grade/texture/drift/paste/motif blocks.
- No more GUI freezes: preview slots no longer `wait(5000)` on the worker (token + `deleteLater`, re-queue on pending); single export runs on an `ExportWorker` thread with snapshotted inputs (tests keep the sync path via `win._export_sync`).
- R2 split (zero logic change, byte-identical, shims keep every import working): `app/disintegrate.py` (1252 → 33 lines) is now `app/particles/` (modes/fields/color/raster/travel/engine); `app/gif.py` (935 → 48 lines) is now `app/anim/` (limits/plan/io/frames). Shared `_resolve_anim_spec()` helper removes the duplicated preset→spec prologue in the 4 particle builders.
- Removed BPM beat grid (too fiddly): no more ♫ BPM/Bars row + Set Hold in VIDEO, no `apply_bpm()`/`hold_for_target()`.
- Fixed morph crash with travel/tint on multi-leg chains (closed loop or 2+ chain images): per-frame color temps shadowed the frame budget (`base`) and legs after the first blew up with "truth value of an array is ambiguous". Pinned by a regression test (plus a 1024-combo sweep).
- Error reporting you can actually use: every failure logs a numbered report (`[E0007]`: action + params + full traceback) to `trakkart.log`; workers report in-thread so nothing is lost crossing threads; the UI shows a plain-language hint + code instead of raw tracebacks; Help → Copy last error report copies the full report for bug reports.
- Sacred Length (editable total, all modes): the VIDEO Length spin is editable again (0.5–60s) — particle modes solve the Hold needed to reach it (clamped 0–3s, honest short-message), other modes set n = Length x FPS (Frames combo shows the derived total, capped at 256f); FPS changes keep the seconds and only gain/lose frames; Hold-manda (no pad) stays the engine rule; no new preset fields (`dissolve_length` stays ignored compat). Non-particle GIF/MP4 lists cap at 256f.
- Customizable keyboard shortcuts: single registry (`app/shortcuts.py`) drives menus, method-step keys and hold-to-compare — no more hardcoded strings drifting from the reference table. Help → Keyboard shortcuts is now an editor (click a cell, press keys; Esc cancels, Del clears, conflicts refused naming the other action, Reset defaults). Bindings persist in `shortcuts.json` (portable data dir, travels with your data). Previous/Next method now show Alt+Left/Right in the menu itself.

## v1.2.0 — 2026-11-02
- Morph F3 travel/pour (§7.6): `dissolve_travel` 0-1 preset field + MORPH Travel slider; non-blocks legs pour src→dst through seeded-greedy 1:1 matching (uneven counts padded, empties fall back to legacy); leg joints stay byte-exact, stagger shifts the pour, ease gates the cloud; travel=0 keeps the legacy cloud path byte-identical; strict 0=off still hard-cuts. Gherkin 57.
- Morph F4 color particles (§7.6): `dissolve_tint` 0-1 preset field + MORPH Tint slider; dots carry their source colors mid-flight (travel legs lerp src→dst hues), gated by the loop envelope so joints land black = byte-exact stills; tint=0 keeps the legacy BW path byte-identical; strict 0=off freezes tint too; blocks tints its pops. Gherkin 58.
- Morph F5 motion trails (§7.6): `dissolve_trail` 0-8 preset field + MORPH Trail slider; past dots linger as fading ghosts (BW gray / tinted hues), strength = decay(age) x loop envelope so joints stay ghost-free = byte-exact stills; trail=0 keeps the legacy path byte-identical; strict 0=off skips ghosts; works in dissolve, morph legs, travel and blocks. Gherkin 59.
- Morph F6 Heckel shade (§7.6): `dissolve_shade` bool preset field + MORPH Shade checkbox; dot size scales with source darkness (dark→full `dissolve_dotsize`, light→1px), envelope-gated so joints stay 1px; shade off or Dots=1 keeps the legacy path byte-identical; works in dissolve, morph legs, travel and blocks. Gherkin 60.
- Morph F7 palette following: morph animates the graded still — IMAGE adjust (brightness/contrast/saturation/mid/highlights) grades the dots, COLOR palette prints the inks (chromatic palettes render full-strength dots, joints = ink stills = holds, no pop); BW/SLIME-less presets keep the legacy path byte-identical; strict 0=off holds; works with travel/tint/trail/shade/blocks. Gherkin 61.

## v1.1.0 — 2026-11-02
- MP4 Canvas-exacto (R5): `mp4_dims` siempre par + `macro_block_size=2` en
  ambos writers — 1080x1920 sale 1080x1920 (era 1088x1920), 404x720 intacto,
  721x721 -> 720x720.
- MP4 faststart (R6): `-movflags +faststart` en `write_mp4`/`write_mp4_iter`
  (moov antes que mdat, playback progresivo).
- Morph loop closure: new `dissolve_loop` preset field + MORPH "Loop (last → first)" checkbox (default ON); the last form morphs back into the first (byte-identical joint), A's hold split across both loop ends; ping-pong skipped when the loop is closed.
- Equal holds: Length pad shared across every form (≤1 frame apart) instead of all-to-last; per-joint hold lists end-to-end (engine + GIF + streaming + labels).
- Honest MP4 weight: MP4 size selector (Canvas/1080p/720p, default 1080p; stills stay full-doc) + content-aware estimate (transitions ~0.43 B/px, holds ~0.011 B/px, calibrated) + heavy-file hints.
- Export dialog fix: animation spec always comes from the live VIDEO section, never stale prefs (morph leaked into mix exports); session chain gated by mode in export + preview.
- Length 0.5–60s via MP4 streaming (up to 3600f, O(1) RAM); GIF/preview stay capped at 256f with honest labels.
- Hold-manda: clip total = transitions + holds (no Length pad); Length is now a derived readout (read-only spin); `dissolve_length` kept as ignored compat; holds only yield to the frame cap.
- Canvas delivery (R1+R2+R3): bundled `CANVAS_916` (9:16 1080x1920, dissolve 64f/30fps/Hold 2.7 = 7.53s loop); Canvas check hints (duration label for 3–8s, export dialog for 720p/1080p); ♫ BPM/Bars row solves Hold for the beat grid (`hold_for_target`).
- Social recipes (R4): bundled `YT_THUMB` (16:9 1280x720), `SQUARE_11` (1:1 1080x1080), `PORTRAIT_45` (4:5 1080x1350); master = `CANVAS_916`.
- Animated WebP (R7): `save_webp()` mirrors the GIF frames (full color, ~1/3 weight) to `{base}_anim.webp`; dialog checkbox with plan + collision cover; dialog-only like MP4.
- Honest GIF/WebP weight (R8): hold-collapse-aware estimates (transitions full cost + 1 frame per still form; measured 12.7x→3.8x over on real 480p dither).
- Ink separations (R9): one PNG per palette ink + corner registration marks (`{base}_sep_{NN}_{RRGGBB}.png`, dialog-only, pairs with Vector Pro black-ink).
- Headless CLI (R10): `TRAKKART.exe --cli --preset X --in ... --out ...` (file/folder, batch bundle, skip-existing, exit 0/1/2, Qt-free; MP4/WebP/seps stay dialog-only).
- Watch folder (R11): File → Watch folder auto-batches arrivals with a fixed preset (2s debounce, 3s settle, skip-existing, sequential, stateless, no modals).
- Morph F1 (§7.7): 11 particle fields (burst/suction/vortex/rain/rise/wave/ripple/flow/blocks) × 5 staggers (joint-pinned) × 3 eases; legacy wind/off/sine byte-identical; MORPH combos; Gherkin 55.
- Morph F2 (§7.7): elastic/bounce eases + dot-size swell (`dissolve_dotsize` 1-4, joints at 1px) + bundled EMBER_RISE/GRAVITY_DROP/POUR_FAKE; Gherkin 56.
- Engine roster frozen at 36 (R14 decision, exact-list test; particle fields are a separate axis).
- Perf round (measured): streaming `save_gif` (peak ~-70%, byte-identical) + GIF RAM budget guard (`MAX_GIF_PIXELS`, fail-fast MemoryError); lazy numba import (startup 0.86→0.39s, parity intact); history prune-when-needed + fast prune test (29→0.8s); bilinear MP4 downscale (~5s per long export); dropped duplicate `-pix_fmt` (warning-only).
- Polish (R12+R13): 9:16 safe-area chrome guides (still preview + crop editor, View toggle, display-only) + wipe compare slider (ORIGINAL/result divider, aligned canvas, survives refreshes).

## v1.0.1
- New icon: 05_bayer_dots (TRAKK SUITE dark + amber).
- Fixed flaky thread-storm test (pending guard + slot release in preview controller).
- Build gate: fast parallel `-n auto -m "not slow"` by default, `--full-tests` for release.
- Copy cleanup: no GPL/clean-room disclaimers, no competitor names; MANUAL fully in English.
- MANUAL.md bundled in English.

## v1.0.0
- First stable: single flavor with numba + MP4 bundled, portable + installer.
- Minimal identity: window title and header without taglines.
- Test speed: pytest-xdist in dev deps; fast loop is now `-n auto`
  (~11x: 6.4 min → ~35 s locally). CI split: fast suite + lint per push,
  full suite nightly + on demand. CI actions bumped off deprecated Node 20.
- CI fixes: MP4 export test skips without the video extra (was a hard
  VideoBackendMissing on runners without imageio); thread-storm test is now
  deterministic (gate-held worker instead of a wall-clock race).
- Single flavor v1: numba + MP4 always bundled (light/full split removed;
  `requirements-video.txt` merged into `requirements.txt`; Extras group is
  now status-only in the exe).
- Settings → Extras: accel/MP4 state with 1-click pip install on dev (threaded);
  frozen exe points to TRAKKART-full.exe. MP4 tooltip updated.
- Portable user data: presets/palettes now live in `data/` (seeded from
  bundled, user edits shadow them); frozen-safe, test seams preserved.
- Release build: exe embeds version metadata; bundled MANUAL.md + icon;
  optional Authenticode signing via `TRAKKART_PFX` (`installer/SIGNING.md`).
- Installer: `installer/trakkart.iss` (Inno Setup 6, EN/ES) + builder
  `build_installer.py` (version from `app.__version__`, signs the setup too).
- User manual: `MANUAL.md` (ES) bundled with the app; Help → User manual (F1).
- Session restore: reopens last image + preset on startup (opt-out in
  Settings); Help → Show logs folder (prefs/db/`trakkart.log`).
- Undo/redo: 20-level `ImageHistory` with redo branch; Edit → Redo (Ctrl+Y).
- Settings backup: Export…/Import… of the full `.json` (validated import).
- Prefs hardened: every numeric/enum clamped (`normalize_prefs`); writable
  output resolution (`resolve_out_dir`); shared dialog builders
  (`app/ui/dialog_fields.py`), Settings split into `settings_flow` + builders.
- Grouped menus (File/Edit/View/Help with separators; clipboard in Edit).
- Panel as a 5-page accordion: IMAGE / DITHER / COLOR / FX / MOTION.
- VIDEO preview ON pre-checks Animation GIF in the Export dialog.
- Help → About TRAKKART; post-export dialog with Show in folder.
- Help → Keyboard shortcuts; File → Open recent (last 5, in prefs).
- Refactor P1+M2: CropView caches its pixmap across paints (invalidated by
  identity on rotate); filename sanitizers unified in `app/names.py`
  (byte-identical outputs).
- MOTIF section only visible for method `motif`; friendlier empty canvas.
- File logging (`data/trakkart.log`, rotating) + friendly crash dialog.
- Crop editor zoom/pan loop fixed (owned box, exact anchor, frame follows
  finger, anchor clamped over black bars, free corner/edge positioning).
- Datamosh module (`app/mosh.py`): 7 flavors (blocks legacy byte-identical +
  smear/ghost/rows/chroma/crush/speckle), `mosh_mode`/`mosh_seed`/`mosh_size`
  preset fields, dedicated DATAMOSH page (mode/amount/size/seed+dice),
  same envelope in GIF mix.
- Export naming: MP4 shares the GIF stem (`*_anim.mp4`, was `*_clip.mp4`);
  sanitizer collapses/trims (`mi cover!` → `mi_cover`); dedicated File name
  section (live preview + Reset); accepted dialogs no longer hoard hidden
  windows (fixes E2E modal flake).
- MOTION duration readout: live `= Xs loop` label from frames ÷ fps (no
  driver spin: three linked controls disagreed; readout never lies). No new
  preset fields.
- Animation suffixes: `{base}_gif.gif` + `{base}_vid.mp4` (lowercase pair;
  legacy `_anim.gif` writer untouched for compat).
- FPS combo: preset default 8 is a first-class entry; custom values insert
  sorted instead of dangling at the end.
- `build_exe.py` excludes numba/llvmlite/imageio (base exe stays light per
  policy); `dist/TRAKKART.exe` rebuilt (66MB) + offscreen smoke green.
- Stale export names fixed: prefs remember their image (`src_name`); a new
  image gets a fresh default (dialog opens instead of silent quick reuse);
  pasted/dropped/downloaded pixels get `pasted_YYYYMMDD_HHMMSS`.
- Collision policy fixed to rename: existing files are never replaced nor
  skipped (repeats save as `name_2`, `name_3`); batch keeps its own policy.
- Collision alert: post-Accept modal lists clashing files (Overwrite / Rename
  as `base_2` / Cancel, safe default Rename); plan shows a ⚠ hint; quick stays
  silent-rename. Test seam hardened (visible-dialog accept, no modal in CI).
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
- Multiprocess batch, animated GIF (Pillow only), TRAKK SUITE theme.

## v0.10.0 — v0.7.0
- Image ops + undo, randomize, zoom, drag&drop, clipboard, glitch pack.
- Vector SVG export. Halftone/cluster/diffusion engines. Pre/post FX.

## v0.6.0 — v0.2.0
- Canvas ratios + crop, portable data dir, SQLite history, custom icon.
- Adjustments (brightness/contrast/saturation), JSON presets, folder batch.

## v0.1.0
- Initial modular app: ordered + Floyd-Steinberg dither, 4 original
  palettes, PySide6 preview, canvas-size export + 1080p thumb + metadata.
