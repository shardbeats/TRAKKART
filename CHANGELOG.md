# CHANGELOG — TRAKKART

Release history (newest first). Details live in `git log` and `ROADMAP.md`.

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
