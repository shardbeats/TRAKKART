# TRAKKART

Part of the ShardBeats **TRAKK** family. Offline dither cover generator (own MIT code, no GPL copied).

```
Image → canvas (ratio preset or free Custom W×H + cover/contain/stretch/blur)
→ method (36 engines) + palette + pixel + threshold → still/video preview → export
→ main image (canvas W×H + format you choose) + optional 1080p thumb + metadata.json
+ optional vector SVG (logos/merch) + animated GIF (phase/hue/glitch/mix, socials)
```

## Quick start

```
start.bat      :: creates .venv, installs deps, launches
run.bat        :: launches with existing .venv
py -m pytest tests -q
```

## Layout

```
main.py                  :: entry point
app/__init__.py          :: single-source version
app/dither.py            :: ordered dither (bayer/cross/bluenoise/halftone/cluster/pattern)
app/kernels.py           :: error-diffusion kernels (floyd/atkinson/burkes/sierra/jjn/stucki/stevenson)
app/accelerate.py        :: optional numba backend (bit-identical output, falls back to numpy)
app/adjust.py            :: brightness / contrast / saturation
app/fx.py                :: pre/post fx (blur, sharpen, hue, denoise, smooth, glow, grain, vignette, scanlines)
app/glitch.py            :: chromatic aberration + slice shift
app/canvas.py            :: ratios + free Custom W×H + cover/contain/stretch/blur
app/palettes.py          :: original TRAKK palettes (BW/SLIME/VAPOR/EMBER)
app/presets.py           :: JSON presets (bundled + user) + declarative FIELDS schema
app/batch.py             :: offline folder batch (sequential/multiprocess + cancel + history)
app/exporter.py          :: canvas-size bundle + 1080p thumb + metadata.json (+SVG +GIF)
app/render_params.py     :: shared normalizers (scan/slice/grille/posterize/halftone)
app/pipeline.py          :: RenderSpec (single ~40-param dataclass) + render_spec/render
app/vector.py            :: SVG renderer (gridded re-render + RLE)
app/gif.py               :: animated GIF modes (phase/hue/both/glitch/mix, Pillow only)
app/paths.py             :: portable data dir (env / frozen data/ / APPDATA)
app/history.py           :: SQLite export history (capped)
app/safety.py            :: image/vector size guards (TooBigError)
app/dnd.py               :: drop classifier (image/data/url/folder)
app/ops.py               :: rotate/flip/invert + undo stack
app/ui/main_window.py    :: thin orchestrator (~700 lines): setup + refresh router + delegation
app/ui/window_assembly.py:: frame, panel groups, action bar, single-canvas preview
app/ui/menus.py          :: File/Edit/View menus
app/ui/params_controller.py :: widgets <-> Preset (BINDINGS table + doc/anim readers)
app/ui/video_controller.py  :: animated preview + Draft/HD/Full proxy player
app/ui/preview_controller.py:: still preview (sync render or background thread)
app/ui/compare_controller.py:: hold-to-compare (Space or button shows ORIGINAL)
app/ui/export_flow.py    :: export dialog orchestration + bundle + history
app/ui/batch_flow.py     :: batch dialog + worker + progress/ETA
app/ui/image_flow.py     :: open/drop/clipboard/zoom/ops/crop editor
app/ui/color_actions.py  :: brand/duotone/border + custom palette strip/library
app/ui/preview_worker.py :: PreviewWorker + VideoWorker (tokens, drops stale renders)
app/ui/workers.py        :: batch QThread
app/ui/widgets.py        :: ValueSlider with reset on double-click
app/ui/theme.qss         :: TRAKK family dark theme
features/*.feature       :: 51 Gherkin acceptance scenarios (pytest-bdd)
tools/quality_metrics.py :: 5 quality gates -> data/quality_report.json
```

## Quality gates

100% tests passing, >=80% branch coverage, Gherkin scenarios green,
export smoke (>500B per PNG), no-leak scan (no GPL code, no personal data).

```
.venv\Scripts\python tools\quality_metrics.py
```

## Legal note

100% original implementation (MIT, clean-room): algorithms reimplemented
from public-domain math. No third-party GPL code is used or copied.
