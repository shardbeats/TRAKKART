# SRS — GPU preview (C1-GLSL, offscreen)

## 1. Goal + pipeline

Give TRAKKART a fluid live preview by running the pixel-parallel stages
on the GPU, without changing what the app exports.

`PIL RGB -> grade pass -> ordered-dither pass -> post pass -> PIL RGB`
(offscreen GL, same `QLabel` display path; final export stays CPU numpy).

## 2. Users + non-goals

Users: cover artists iterating on large canvases with ED or heavy FX,
where the 640px CPU proxy still stalls the sliders.

Non-goals (v1 will NOT):
- No compute shaders for ED/particles (serial by physics; numba stays).
- No `QOpenGLWidget` live surface (the `QLabel` + compare/wipe/safe-area
  path stays untouched).
- No export/batch/CLI/vector path changes (CPU numpy stays byte-identical).
- No ASCII on GPU (glyph atlas work; CPU fallback covers it).
- No new runtime deps in `requirements.txt` until the spike is green
  (the spike installs `moderngl` locally only).
- No web repackaging (that is a separate track).

## 3. Direction lock (Step 1, decided)

C1-GLSL offscreen (`moderngl` standalone context -> `QImage` -> existing
preview plumbing). Reasons: the `TRAKKMOTION`
`src/shaders/{grade,dither,post}.frag.glsl` oracle already implements
all three passes (transcription is mechanical); no UI rewrite; CPU
fallback is a same-signature call. `QOpenGLWidget` rejected for v1
(display-path rewrite, loses overlays). `wgpu-py`/WGSL kept as a
documented future option for web portability, not v1 (no oracle, native
lib shipping, younger Windows support).

Known gaps at transcription time: oracle is WebGL2 GLSL ES 1.00
(`texture2D`, `gl_FragColor`); desktop GL needs 330 core (`texture`,
`out vec4`). The per-stage `floor()` quantization and bankers rounding
must survive the port or parity fails.

## 4. Functional requirements

- FR-1 GPU grade pass: input `PIL RGB` + adjust/duotone/posterize/
  split-tone/fade params; behavior = `app/adjust.py` + `app/grade.py`
  semantics; output `PIL RGB`, same size; error path = any GL failure
  falls back to the CPU functions with a status note, never a crash.
- FR-2 GPU ordered-dither pass: input graded `PIL RGB` + method/threshold/
  pixel/palette/phase; behavior = all oracle maps (bayer family,
  lines/columns/diag/grid/checker, halftone/cluster/pattern, ign/cross,
  bluenoise/white-noise/blocks/scan-bayer/wave-map/motif, cmyk, edges);
  output dithered `PIL RGB`; `ascii` and unknown methods fall back to CPU.
- FR-3 GPU post pass: input dithered `PIL RGB` + ordered FX stack +
  brand color; behavior = stack order drives the output (reorder visibly
  changes it), border grows the canvas host-side; output `PIL RGB`.
- FR-4 Parity harness: `numpy-vs-GPU` comparison over bundled samples
  and palette/method matrix; pass = max abs diff <= 1 LSB on >= 99.9% of
  pixels, with pinned deviations documented (contrast pivot 0.5 vs image
  mean, hue YIQ vs HSV, hash RNG vs `numpy default_rng`).
- FR-5 Transparent fallback: no GL context (headless CI, old drivers) =
  CPU preview with a one-line status note; zero new failure modes.
- FR-6 Perf target: full three-pass 640px proxy <= 100 ms on integrated
  graphics; measured by the spike (fps vs numpy), not by assertion.
- FR-7 Preview-only wiring: GPU sits behind the viewport proxy path
  (`Live`/`Still`); `Full`, export, batch, CLI and video stay CPU.
- FR-8 Dependency gate: `moderngl` enters `requirements.txt` / the exe
  only after spike + parity + size review; the spike lives in
  `tools/gpu_spike_preview.py` (manual, not a quality gate).

## 5. Non-functional

- Offline-first, portable exe, Windows 10/11, no admin, no network.
- Deterministic: no wall-clock inside shaders (phase comes from the
  frame index); same inputs = same pixels across runs and machines.
- No telemetry, no new data dirs (reuses `data/` + `trakkart.log`).

## 6. UX scope

No visible UI change in v1 except the existing status readout gaining a
backend suffix (`Preview ready · 640px · 12ms · GPU` vs `· CPU`).
Empty, error and fallback states reuse current strings plus the FR-5 note.
No new shortcuts, dialogs or prefs.

## 7. Acceptance criteria (per requirement)

- FR-1/2/3: `tools/gpu_spike_preview.py --check` renders the three
  passes on `data/samples/*` without traceback; manual eyeball vs CPU.
- FR-4: `pytest tests/test_gpu_parity.py -q` green (new file, added with
  the wiring step, not the spike); gate stays 61 Gherkin (no new
  scenarios for pixel parity).
- FR-5: `QT_QPA_PLATFORM=offscreen` full suite green with and without
  `moderngl` installed (fallback covered both ways).
- FR-6: spike report in the file header (fps table vs numpy, GPU model);
  no gate assert, decision input only.
- FR-7: export byte-identity test — same preset exports identical bytes
  with the GPU preview on and off.
- FR-8: `requirements.txt` diff + exe size note reviewed before merge.

## 8. Milestones

1. SRS accepted (this file) -> 2. afternoon spike (`Bayer + grade` in
   `moderngl`, minimal PySide6 window, fps vs numpy + parity) ->
   3. full C1 decision only with spike + parity green and explicit
   approval. Never implement the full C1 without step 3.
