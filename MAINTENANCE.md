# MAINTENANCE — TRAKKART

## Versioning

Single source: `app/__init__.py` (`__version__`). `pyproject.toml` and `build_exe.py` read it.
Manual bump per release (0.1.0 → 0.2.0 ...).

## Dependencies

- Runtime: `requirements.txt` (PySide6, Pillow, numpy). No OpenCV/GPU. Numba only as an optional accelerator (`pip install numba`), with automatic fallback.
- Dev: `requirements-dev.txt` (pytest, pytest-bdd, pytest-cov, coverage).
- Install dev: `.venv\Scripts\python -m pip install -r requirements-dev.txt`

## Layout

```
main.py                  :: entry
app/__init__.py          :: version
app/dither.py            :: 9 ordered + ED via kernels (16 methods)
app/kernels.py           :: COEFFS (7 kernels) + diffuse_* (numpy/numba backend)
app/accelerate.py        :: optional njit + fallback (bit-identical parity)
app/canvas.py            :: ratios + crop cover/contain
app/adjust.py            :: brightness/contrast/saturation
app/fx.py                :: pre (hue/denoise/smooth) + post + replace + custom
app/pipeline.py          :: render() + meta_dict() (canvas/pre/adjust/dither/brand/post/glitch, no text since v0.14)
app/palettes.py          :: original palettes
app/presets.py           :: JSON presets (bundled + user, no title since v0.14)
app/batch.py             :: sequential/multiprocess batch (fallback + cancel) + history
app/ui/main_window.py    :: PySide6 (sections + menus + safe drop with toggle)
app/ui/crop_editor.py    :: CropEditorDialog (visual crop: frame + grid + drag + zoom)
app/dnd.py               :: drop classification (http/data/blob/local/ignore)
app/safety.py            :: size/vector guards (TooBigError)
app/exporter.py          :: per-ratio bundle + 1080p thumb + metadata.json (+SVG)
app/vector.py            :: grid re-render + RLE + SVG
app/gif.py               :: phase/hue frames + save_gif (max 480px)
app/ops.py               :: rotate/flip/invert + undo cap 20
app/glitch.py            :: chromatic aberration + slice shift
app/paths.py             :: portable data (env/frozen/APPDATA)
app/history.py           :: SQLite export history
app/ui/main_window.py    :: PySide6 (QGroupBox sections + menus + preview + statusbar)
app/ui/theme.qss         :: TRAKK family theme (tokens #151617/#F5A623)
app/ui/theme.py          :: load_stylesheet() with fallback
app/ui/workers.py        :: BatchWorker QThread (jobs + cancel)
app/ui/preview_worker.py :: PreviewWorker QThread (tokens, 640px preview)
app/ui/widgets.py        :: ValueSlider (value + double-click reset)
presets/*.json           :: 4 bundled (never overwritten)
features/*.feature       :: 30 Gherkin scenarios
tests/                   :: unit + bdd/ (pytest-bdd por dominio)
tools/quality_metrics.py :: gates → data/quality_report.json
```

## Do not commit

`data/` (includes `quality_report.json`, `coverage.json`, `quality_html/`), `out/`, `*.db`, `dist/`, `build/`, `.venv/`, `.pytest_cache/`.

## Distribution

Portable: `py build_exe.py` → `dist\TRAKKART.exe` (windowed one-file).
No installer shipped. The app is offline, no admin rights needed.
