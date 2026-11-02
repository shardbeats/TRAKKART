# CHANGELOG — TRAKKART

Release history (newest first). Details live in `git log` and `ROADMAP.md`.

## Unreleased
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
