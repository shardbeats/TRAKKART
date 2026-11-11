# TRAKKART

Part of the ShardBeats **TRAKK SUITE**. Offline cover art studio (MIT licensed).

```
Image → canvas (ratio preset or free Custom W×H + cover/contain/stretch/blur)
→ method (36 engines) + palette + pixel + threshold → still/video preview → export
→ main image (canvas W×H + format you choose) + optional 1080p thumb + metadata.json
+ optional vector SVG (logos/merch) + animated GIF (phase/hue/glitch/mix, socials)
```

## Quick start

```
start.bat      :: setup (local .venv) + launch
run.bat        :: launches with the local .venv
py -m pytest tests -q -n auto -m "not slow"   :: fast loop (~35 s with xdist)
```

## Layout

```
main.py                  :: entry point
app/__init__.py          :: single-source version
app/dither.py            :: 11 ordered (incl. checker/ign) + ED + hilbert + cmyk/ascii/edges/motif (36 methods)
app/kernels.py           :: error-diffusion kernels + Hilbert order/diffusion
app/ordered_maps.py      :: ordered threshold maps (bayer/cross/bluenoise/halftone/...)
app/accelerate.py        :: optional numba backend (bit-identical output, falls back to numpy)
app/adjust.py            :: brightness / contrast / saturation / midtones / highlights
app/canvas.py            :: ratios + free Custom W×H + cover/contain/stretch/blur
app/fx.py                :: pre/post fx + replace-color + custom palette
app/fx_dispatch.py       :: stack FX dispatch (one function per effect)
app/fx_stack.py          :: ordered stack model + effect labels
app/fx_jpeg.py           :: JPEG glitch effect (recompress, deterministic)
app/grade.py             :: duotone / posterize / split-tone / fade
app/texture.py           :: halftone / dust / border / letterbox
app/glitch.py            :: chroma / slice / pixelsort / wave / grille (+datamosh compat)
app/mosh.py              :: 7 datamosh flavors + dispatcher (blocks legacy byte-identical)
app/drift.py             :: Signal Drift patterns (seeded pre-dither noise)
app/pasteup.py           :: paper overlay (post-dither stack FX)
app/motif.py             :: custom pattern builder (4 bands -> shape/size)
app/ascii.py             :: ASCII engine (charset ramp, phase-animable)
app/cmyk.py              :: CMYK halftone (print ink, threshold = dot gain)
app/palettes.py          :: original TRAKK palettes (BW/SLIME/VAPOR/EMBER)
app/palette_library.py   :: named palette JSONs (bundled + user) + BW equivalence
app/palette_gen.py       :: random ramp/harmony palettes in Oklch (seedable)
app/palette_extract.py   :: median-cut auto-extract (numpy only)
app/presets.py           :: JSON presets (bundled + user) + declarative FIELDS schema
app/batch.py             :: offline folder batch (sequential/multiprocess + cancel + history)
app/exporter.py          :: canvas-size bundle + plan + _gif/_vid stems + metadata.json
app/export_prefs.py      :: last-config prefs (incl. recent files + src_name guard)
app/names.py             :: filename sanitizers (single home)
app/recent.py            :: recent files (capped, prefs-backed)
app/pipeline.py          :: RenderSpec (single ~40-param dataclass) + render_spec/render
app/render_params.py     :: shared normalizers (delegates to RenderSpec.from_preset)
app/vector.py            :: SVG renderer (gridded re-render + RLE)
app/gif.py               :: shim (R2 split): GIF modes live in app/anim/ (limits/plan/io/frames)
app/anim/                :: limits + plan (budgets) + io (save_gif/webp) + frames (builders)
app/disintegrate.py      :: shim (R2 split): particles live in app/particles/ (modes/fields/color/raster/travel/engine)
app/separations.py       :: RISO/screen spot plates (nearest-color + register marks + effective palette)
app/cli.py               :: headless --cli (no Qt): preset over file/folder, exit 0/1/2
app/video_io.py          :: MP4 backend (imageio-ffmpeg, ships in the bundle)
app/viewport.py          :: Full/Live/Still modes + fast/slow debounce
app/tutorial.py          :: tour steps + offline sample pack
app/paths.py             :: portable data dir (env / frozen data/ / APPDATA)
app/history.py           :: SQLite export history (capped)
app/log.py               :: rotating file log + crash hook source
app/safety.py            :: image/vector size guards (TooBigError)
app/dnd.py               :: drop classifier (image/data/url/folder)
app/ops.py               :: rotate/flip/invert + undo stack
app/services/            :: render / export / image_io services
app/ui/main_window.py    :: thin orchestrator (~900 lines): setup + refresh router + delegation
app/ui/window_assembly.py:: frame, 6-page accordion, action bar, single-canvas preview
app/ui/menus.py          :: File/Edit/View/Help menus
app/ui/panels/           :: accordion builders (IMAGE/DITHER/COLOR/FX/DATAMOSH/MOTION)
app/ui/params_controller.py :: widgets <-> Preset (BINDINGS table + doc/anim readers)
app/ui/params_binding.py :: widget get/set factories
app/ui/video_controller.py  :: animated preview + Draft/HD/Full proxy player + duration label
app/ui/preview_controller.py:: still preview (adaptive proxy 640-1600 / full-doc 100%)
app/ui/preview_canvas.py :: fit/zoom/pan canvas (wheel, drag, 100%, no layout clipping)
app/ui/compare_controller.py:: hold-to-compare (Space/button shows ORIGINAL) + wipe + safe toggle
app/ui/safeareas.py        :: R12 chrome guides 9:16 (display-only paint)
app/ui/watch_flow.py       :: watch folder (debounce + settle + fixed preset, no modals)
app/ui/export_flow.py    :: export dialog orchestration + bundle + history + collision alert
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
app/ui/theme.qss        :: static dark stylesheet (tokens #151617/#F5A623, no switching)
app/ui/widgets.py        :: ValueSlider with reset on double-click
app/ui/workers.py        :: BatchWorker QThread
app/ui/preview_worker.py :: PreviewWorker + VideoWorker (tokens, drops stale renders)
features/*.feature       :: 61 Gherkin acceptance scenarios (pytest-bdd)
tools/quality_metrics.py :: 5 quality gates -> data/quality_report.json
```

## Quality gates

100% tests passing, >=80% branch coverage, Gherkin scenarios green,
export smoke (>500B per PNG), no-leak scan (no personal data).

```
.venv\Scripts\python tools\quality_metrics.py
```
