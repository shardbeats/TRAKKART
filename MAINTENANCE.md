# MAINTENANCE — TRAKKART

## Versioning

Single source: `app/__init__.py` (`__version__`). `pyproject.toml` and `build_exe.py` read it.
Manual bump per release (0.1.0 → 0.2.0 ...).

## Dependencies

- Runtime: `requirements.txt` (PySide6, Pillow, numpy, numba, imageio-ffmpeg). No OpenCV/GPU. Numba ships in the bundle; numpy fallback stays for safety (`has_numba()` probe, parity tested).
- Dev: `requirements-dev.txt` (pytest, pytest-bdd, pytest-cov, coverage).
- Install dev: `.venv\Scripts\python -m pip install -r requirements-dev.txt`

## CI pins (known incident 2026-10-30)

- `requirements-dev.txt` pins `pytest>=8.0,<9.2` on purpose.
- Incident: scheduled `CI` runs `41036412295` (2026-10-30), `40852105381` (2026-10-29),
  `40664875487` (2026-10-28) failed in both `fast` and `full` jobs with:
  `AttributeError: 'FixtureManager' object has no attribute '_arg2fixturedefs'`
  at `pytest_bdd/scenario.py:65` in `find_fixturedefs_for_step`.
- Root cause: upstream `pytest 9.2.0` removed/renamed the private `_arg2fixturedefs`
  API used by `pytest-bdd 9.0.0`. Last green scheduled run `40476374579` (2026-10-27)
  used `pytest 9.1.1 + pytest-bdd 9.0.0`. Not an app regression.
- Fix commit: `fix(ci): pin pytest below 9.2 for pytest-bdd compat`.
  Verified by push run `41093063744` (`fast` green in 3m27s, installs `pytest 9.1.1`).
- To lift the pin: upgrade `pytest-bdd` to a release that supports `pytest>=9.2`,
  then remove the `<9.2` upper bound and watch one `schedule` + one `workflow_dispatch` run.

## CI test seams (known incident 2026-11-08)

- `CI` #148 (`6d0b95c`) failed only in `full` on
  `tests/test_stability.py::test_debounce_coalesces_renders` with
  `AssertionError: debounce roto: 0 renders`.
- Root cause: stale mock. Since `5ea3e58` the still preview renders through
  `app.gpu.render_proxy_or_cpu` / `render_full_or_cpu`, but the test patched
  `app.services.render_service.render_full`, so the counter never moved.
  The debounce itself was healthy.
- Fix: patch `app.ui.preview_controller.render_still` (the seam `refresh()`
  calls) and delegate to the real function. Never patch a specific render
  backend (`render_service.render_full`, `app.gpu.*`): preview routing can
  move it under you.
- Tests never hardcode absolute local paths. Subprocess `cwd` is
  `Path(__file__).resolve().parents[1]` (see `64e5d0c`); a dev path fails CI
  with `NotADirectoryError`.

## Layout

```
main.py                  :: entry
app/__init__.py          :: version
app/cli.py               :: headless --cli (no Qt): preset over file/folder, exit 0/1/2
app/dither.py :: 11 ordered (incl. checker/ign) + ED + hilbert + cmyk/ascii/edges/motif (36 methods)
app/gpu.py :: offscreen GPU dither backend (moderngl): supports() gate + render_proxy_kwargs (CPU grade, GPU ordered/cmyk/edges dither, CPU brand/stack) + render_full_kwargs (doc-size Full stills, display-only) + CPU fallback
app/gpu_shaders.py :: VERT_330 + DITHER_330 (procedural ordered maps + baked-mask LUTs + cmyk/edges + nearest-palette)
app/kernels.py           :: COEFFS (11 kernels) + diffuse_* (numpy/numba) + Hilbert order/diffusion
app/ordered_maps.py      :: ordered threshold maps
app/accelerate.py        :: optional njit + fallback (bit-identical parity)
app/canvas.py            :: ratios + free Custom WxH + cover/contain/stretch/blur (crop_box_for delegates)
app/adjust.py            :: brightness/contrast/saturation/midtones/highlights
app/fx.py                :: pre (hue/denoise/smooth) + post + replace + custom
app/fx_dispatch.py       :: stack FX dispatch (one function per effect)
app/fx_stack.py          :: ordered stack model + effect labels
app/fx_jpeg.py           :: JPEG glitch effect (recompress, deterministic)
app/grade.py             :: duotone/posterize/split-tone/fade (pre/post dither)
app/texture.py           :: halftone/dust/border/letterbox (post-dither)
app/glitch.py            :: chroma/slice + pixelsort/wave/grille (+datamosh compat)
app/mosh.py              :: 7 datamosh flavors + dispatcher (blocks legacy byte-identical)
app/drift.py             :: Signal Drift patterns (seeded pre-dither noise)
app/pasteup.py           :: paper overlay (post-dither stack FX)
app/motif.py             :: custom pattern builder (4 bands)
app/ascii.py             :: ASCII engine (charset ramp, phase-animable)
app/cmyk.py              :: CMYK halftone (print ink)
app/pipeline.py          :: RenderSpec + render_spec/render + meta_dict (no text since v0.14)
app/render_params.py     :: shared normalizers (delegates to RenderSpec.from_preset)
app/palettes.py          :: original palettes
app/palette_library.py   :: named palette JSONs (bundled + user) + BW equivalence
app/palette_gen.py       :: random ramp/harmony palettes in Oklch (seedable)
app/palette_extract.py   :: median-cut auto-extract (numpy only)
app/presets.py           :: FIELDS schema + JSON presets (bundled + user, no title since v0.14)
app/batch.py             :: sequential/multiprocess batch (fallback + cancel) + history
app/exporter.py          :: export canvas WxH + plan + _gif/_vid stems + sanitize_base
app/export_prefs.py      :: last-config prefs (recent + src_name guard, always-rename)
app/names.py             :: filename sanitizers (single home)
app/recent.py            :: recent files (capped, prefs-backed)
app/vector.py            :: grid re-render + RLE + SVG
app/gif.py               :: shim (R2 split): GIF modes live in app/anim/ (limits/plan/io/frames)
app/anim/                :: limits (caps) + plan (budgets/estimates) + io (save_gif/webp) + frames (builders)
app/disintegrate.py      :: shim (R2 split): particle engine lives in app/particles/ (see below)
app/particles/           :: modes + fields (stagger/ease/offset) + color (dots/inks/tint)
                            + raster (sizes/trail/paint) + travel (match/pour/disperse) + engine (iterators)
app/separations.py       :: RISO/screen spot plates (nearest-color + register marks + effective palette)
app/video_io.py          :: MP4 backend (imageio-ffmpeg, ships in the bundle)
app/viewport.py          :: Full/Live/Still modes + fast/slow debounce
app/tutorial.py          :: tour steps + offline sample pack
app/paths.py             :: portable data (env/frozen/APPDATA)
app/history.py           :: SQLite export history
app/log.py               :: rotating file log
app/dnd.py               :: drop classification (http/data/blob/local/ignore)
app/safety.py            :: size/vector guards (TooBigError)
app/ops.py               :: rotate/flip/invert + undo cap 20
app/services/            :: render / export / image_io services
app/ui/main_window.py    :: thin orchestrator: setup + refresh router + delegation (~900 lines)
app/ui/window_assembly.py:: frame + 6-page accordion + action bar + single-canvas preview
app/ui/menus.py          :: File/Edit/View/Help menus
app/ui/panels/           :: accordion builders (IMAGE/DITHER/COLOR/FX/DATAMOSH/MOTION)
app/ui/params_controller.py :: widgets<->Preset (BINDINGS table + doc/anim readers)
app/ui/params_binding.py :: widget get/set factories
app/ui/video_controller.py  :: animated preview + Draft/HD/Full proxy + duration label
app/ui/preview_controller.py:: still preview (sync or background thread)
app/ui/compare_controller.py:: hold-to-compare (Space/button) + wipe + safe toggle
app/ui/safeareas.py          :: R12 chrome guides 9:16 (display-only paint)
app/ui/export_flow.py    :: export dialog orchestration + collision alert + history
app/ui/export_dialog.py  :: File name section + plan + policy note
app/ui/settings_dialog.py :: Settings (default output, export defaults, jobs/drop/viewport)
app/ui/settings_flow.py   :: Settings orchestration (dialog + save + apply, win delegates)
app/ui/session_flow.py    :: session restore (last image + preset, silent + opt-out)
app/extras.py             :: accel/MP4 detection + pip install (dev; frozen → full build)
app/ui/dialog_fields.py   :: shared dialog builders (format/quality, jobs, folder row, gif-spec)
app/ui/batch_flow.py     :: batch dialog + worker + progress/ETA
app/ui/watch_flow.py     :: watch folder (debounce + settle + fixed preset, no modals)
app/ui/image_flow.py     :: open/drop/clipboard/zoom/ops/crop editor
app/ui/color_actions.py  :: brand/duotone/border + custom palette strip/library
app/ui/crop_editor.py    :: CropEditorDialog (visual crop, owned box, cached paint)
app/ui/palette_dialog.py :: palette editor (swatches, locks, shuffle)
app/ui/about_dialog.py   :: About (version, MIT, offline note)
app/ui/shortcuts_dialog.py :: shortcut reference table
app/ui/fx_stack_controller.py :: stack list sync (reorder/enable/add)
app/ui/theme.qss         :: static dark stylesheet (tokens #151617/#F5A623, no switching)
app/ui/workers.py        :: BatchWorker QThread (jobs + cancel)
app/ui/preview_worker.py :: PreviewWorker + VideoWorker (tokens, stale drops)
app/ui/widgets.py        :: ValueSlider (value + double-click reset)
presets/*.json           :: 13 bundled (never overwritten)
features/*.feature       :: 61 Gherkin scenarios
tests/                   :: unit + bdd/ (pytest-bdd por dominio)
tools/quality_metrics.py :: gates → data/quality_report.json
tools/gpu_spike_preview.py :: manual GPU spike (Bayer+grade parity/bench/show, not a gate)
```

## Do not commit

`data/` (includes `quality_report.json`, `coverage.json`, `quality_html/`), `out/`, `*.db`, `dist/`, `build/`, `.venv/`, `.pytest_cache/`.

## Distribution

Portable: `py build_exe.py` → `dist\TRAKKART.exe` (windowed one-file).
Installer: `py build_installer.py` → `dist\TRAKKART-Setup-<version>.exe` (Inno Setup 6).
The app is offline, no admin rights needed.
