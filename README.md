# TRAKKART

Part of the ShardBeats **TRAKK** family. Offline dither cover generator (own MIT code, no GPL copied).

```
Image → method (16 engines) + palette + pixel + threshold → preview → bundle
→ cover (long side 3000) + small (960) + 1080p thumb + metadata.json
+ optional vector SVG (logos/merch) + animated GIF (socials)
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
app/canvas.py            :: aspect ratios + crop cover/contain
app/palettes.py          :: original TRAKK palettes (BW/SLIME/VAPOR/EMBER)
app/presets.py           :: JSON presets (bundled + user)
app/batch.py             :: offline folder batch (sequential/multiprocess + cancel + history)
app/exporter.py          :: per-ratio bundle + 1080p thumb + metadata.json (+SVG +GIF)
app/vector.py            :: SVG renderer (gridded re-render + RLE)
app/gif.py               :: animated GIF (Pillow only, no ffmpeg)
app/paths.py             :: portable data dir (env / frozen data/ / APPDATA)
app/history.py           :: SQLite export history (capped)
app/safety.py            :: image/vector size guards (TooBigError)
app/dnd.py               :: drop classifier (image/data/url/folder)
app/ops.py               :: rotate/flip/invert + undo stack
app/ui/main_window.py    :: PySide6 shell (grouped panel, menus, offscreen-tested)
app/ui/preview_worker.py :: background preview worker (tokens, drops stale renders)
app/ui/workers.py        :: batch QThread
app/ui/widgets.py        :: ValueSlider with reset on double-click
app/ui/theme.qss         :: TRAKK family dark theme
features/*.feature       :: 30 Gherkin acceptance scenarios (pytest-bdd)
tools/quality_metrics.py :: 5 quality gates -> data/quality_report.json
```

## Quality gates

100% tests passing, >=80% branch coverage, Gherkin scenarios green,
export smoke (>500B per PNG), no-leak scan (no GPL code, no personal data).

```
.venv\Scripts\python tools\quality_metrics.py
```

## Legal note

Inspired by the *idea* of Dither Boy / dither-guy (GPL-3.0), but implementation
is 100% original. No GPL code is copied.
