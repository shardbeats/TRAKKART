# MAINTENANCE — TRAKKART

## Versioning

Single source: `app/__init__.py` (`__version__`). `pyproject.toml` and `build_exe.py` read it.
Manual bump per release (0.1.0 → 0.2.0 ...).

## Dependencies

- Runtime: `requirements.txt` (PySide6, Pillow, numpy). No OpenCV/GPU. Numba only as an optional accelerator (`pip install numba`), with automatic fallback.
- Dev: `requirements-dev.txt` (pytest, pytest-bdd, pytest-cov, coverage).
- Install dev: `<venv>\Scripts\python -m pip install -r requirements-dev.txt`
  (`<venv>` = central `C:\venvs\dev` or local `.venv`).

## Layout

```
main.py                  :: entry
app/__init__.py          :: version
app/dither.py            :: 11 ordered (incl. checker/ign) + ED + hilbert + cmyk/ascii/edges/motif (36 methods)
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
app/gif.py               :: GIF modes phase/hue/both/glitch/mix (2-24f, 2-60fps, Pillow only)
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
app/ui/compare_controller.py:: hold-to-compare (Space/button)
app/ui/export_flow.py    :: export dialog orchestration + collision alert + history
app/ui/export_dialog.py  :: File name section + plan + policy note
app/ui/settings_dialog.py :: Settings (default output, export defaults, jobs/drop/viewport)
app/ui/settings_flow.py   :: Settings orchestration (dialog + save + apply, win delegates)
app/ui/session_flow.py    :: session restore (last image + preset, silent + opt-out)
app/extras.py             :: accel/MP4 detection + pip install (dev; frozen → full build)
app/ui/dialog_fields.py   :: shared dialog builders (format/quality, jobs, folder row, gif-spec)
app/ui/batch_flow.py     :: batch dialog + worker + progress/ETA
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
presets/*.json           :: 4 bundled (never overwritten)
features/*.feature       :: 52 Gherkin scenarios
tests/                   :: unit + bdd/ (pytest-bdd por dominio)
tools/quality_metrics.py :: gates → data/quality_report.json
```

## Do not commit

`data/` (includes `quality_report.json`, `coverage.json`, `quality_html/`), `out/`, `*.db`, `dist/`, `build/`, `.venv/`, `.pytest_cache/`.

## Distribution

Portable: `py build_exe.py` → `dist\TRAKKART.exe` (windowed one-file).
No installer shipped. The app is offline, no admin rights needed.
