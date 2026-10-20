# QA — TRAKKART

Verification procedures (TRAKK standard).

## Fast loop (dev)

```
.venv\Scripts\python -m pytest tests -q -p no:cacheprovider --no-cov -m "not slow"
```

## Full suite + coverage

```
.venv\Scripts\python -m pytest tests -q
.venv\Scripts\python -m coverage run -m pytest tests -q
.venv\Scripts\python -m coverage report
.venv\Scripts\python -m coverage html   :: data/quality_html
.venv\Scripts\python -m flake8 app tests tools main.py
```

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
features/export.feature   :: 3 scenarios (palettes, bundle sizes, smoke 500B)
features/presets.feature  :: 2 scenarios (roundtrip, bundled never overwritten)
features/batch.feature    :: 1 scenario (3-image batch)
features/adjust_text.feature :: 2 scenarios (brightness differs, valid metadata)
features/history.feature  :: 1 scenario (export gets logged)
features/canvas.feature   :: 2 scenarios (9:16 export, crop clamp)
features/kernels.feature  :: 5 scenarios (Atkinson, blue-noise, halftone, JJN, numba parity)
features/fx.feature       :: 2 scenarios (scanlines, replace-color)
features/vector.feature   :: 1 scenario (valid SVG with rects)
features/flow.feature     :: 2 scenarios (chromatic aberration, deterministic slice)
features/gif.feature      :: 1 scenario (GIF N frames max 480px)
features/safety.feature   :: 2 scenarios (giant image, huge vector)
```

Total: 30/30. Steps live in `tests/bdd/test_steps_*.py` by domain (scenarios bound per module), shared givens in `tests/bdd/conftest.py`, `ctx` fixture in `tests/conftest.py`.
Current suite: 170 tests (preview worker + valued sliders). Perf tests marked `slow` are excluded with `-m "not slow"` in the fast loop.
`tools/bench.py` is manual (not a gate): B&W 960px ~0.01s, color 960px ~0.02s with numba.
If you add a scenario, update the `gherkin` gate in `tools/quality_metrics.py` and this file.

## Manual GUI checklist (before each release)

1. `run.bat` opens without traceback (offscreen in CI: `QT_QPA_PLATFORM=offscreen`).
2. Open PNG/JPG → original vs dither preview updates when moving threshold/pixel/method/palette/brightness/ratio.
3. Preset saves, reloads and applies sliders.
3b. CANVAS → "Adjust crop..." opens the visual editor (frame + grid, drag pans, wheel zooms, Rotate/Reset/ratio/mode); Done applies, Cancel keeps values.
4. Export dialog generates `<base>.png|jpg|webp` at the chosen long side (default 3000) + optional `*_thumb1080p`, `*_vector.svg`, `*_anim.gif`, `*_metadata.json` in the chosen folder.
4. `*_thumb1080p` opens directly in TRAKKOUT with no odd cropping.
5. `build_exe.py` produces a portable `dist/TRAKKART.exe` that starts on double-click.

## Perf (manual, before release)

- Floyd B&W 3000px < 30s, Floyd color 1080px < 12s (measured in dev with `tools/bench.py` if present).
- If Floyd color gets close to the limit, raise the preset `pixel_size` before touching the algorithm.
