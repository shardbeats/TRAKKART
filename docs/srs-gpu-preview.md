# SRS — GPU preview (C1-GLSL, offscreen dither)

## 1. Goal + pipeline

Give TRAKKART a fluid live preview by running the expensive stage —
ordered/cmyk/edges dither with nearest-palette search — on the GPU,
without changing what the app exports.

`PIL RGB -> CPU grade (canvas/drift/pre/duotone/posterize/adjust/palette)
-> GPU dither -> CPU brand/stack -> PIL RGB` (offscreen GL, same `QLabel`
display path; final export stays CPU numpy).

## 2. Users + non-goals

Users: cover artists iterating on large canvases with palette presets
(SLIME/VAPOR), where the CPU nearest-palette search stalls the sliders.

Non-goals (v1 keeps on CPU on purpose):
- The grade chain (cheap point math): keeping the suite code as the
  single implementation removes a whole class of float32-vs-CPU tie
  bugs (verified during the spike: Pillow blend/mean rounding, Bankers
  ties and FMA fusion all differ by 1 ULP, which dither thresholds and
  nearest-color amplify to full flips).
- ED/hilbert/ascii dither (serial or atlas work; numba/CPU stays).
- No `QOpenGLWidget` live surface (the `QLabel` + compare/wipe/safe-area
  path stays untouched).
- No export/batch/CLI/video path changes (CPU numpy stays byte-identical).
- Post-dither FX stack (4b, future work; CPU today, already fast enough
  at proxy size for v1).

## 3. Direction lock (Step 1, decided)

C1-GLSL offscreen (`moderngl` standalone context -> `QImage` -> existing
preview plumbing). The `TRAKKMOTION`
`src/shaders/{grade,dither,post}.frag.glsl` oracle informed the dither
transcription; transcription rules (all verified by the parity harness):
integer-matrix maps are procedural and bit-exact, float/RNG masks are
baked on CPU to exact LUTs, explicit sampler bindings on every path,
top-first upload convention with flip-on-FBO-sample, normalized `f1`
textures for PIL bytes (integer `u1` sampled as float reads black).
`QOpenGLWidget` rejected for v1 (display-path rewrite, loses overlays).
`wgpu-py`/WGSL kept as a documented future option for web portability.

## 4. Functional requirements

- FR-1 CPU grade chain: unchanged suite code (canvas -> drift -> pre ->
  grade -> adjust -> palette resolve); GPU work starts from its output.
- FR-2 GPU ordered-dither pass: input graded `PIL RGB` + method/threshold/
  pixel/palette/phase/motif; covers all 21 ordered maps + cmyk + edges
  (see `_GPU_MAPS`); `ascii`/ED/hilbert/unknown fall back to CPU.
- FR-3 Post-dither brand + ordered FX stack on CPU (unchanged suite code).
- FR-4 Parity harness (`tests/test_gpu_parity.py`): CPU-vs-GPU over
  synthetic inputs covering every GPU method (BW + named palette),
  drift patterns, pre/post FX tails and the no-GL fallback; gate is
  maxdiff <= 1 LSB everywhere (no Tie tolerance: the new architecture
  removes the float-tie class by construction).
- FR-5 Transparent fallback: no GL context (headless CI, old drivers) or
  unsupported method = CPU preview path, same pixels; status shows the
  backend (`GPU`/`CPU`); zero new failure modes.
- FR-6 Perf target: 640px palette proxy well under the 120ms Live
  budget; measured by the spike (fps vs numpy), not by assertion.
- FR-7 Preview-only wiring: GPU sits behind the viewport proxy path
  (`Live`/`Still`); `Full`, export, batch, CLI and video stay CPU.
- FR-8 Dependency gate: `moderngl` enters `requirements.txt` only with
  this change (spike + parity + size review all green; ~0.1MB added).

## 5. Non-functional

- Offline-first, portable exe, Windows 10/11, no admin, no network.
- Deterministic: same inputs = same pixels across runs and machines
  (no wall-clock in shaders; phase comes from the preset).
- No telemetry, no new data dirs (reuses `data/` + `trakkart.log`).

## 6. UX scope

No visible UI change except the existing status readout gaining a
backend suffix (`Preview ready · 640px · 12ms · GPU` vs `· CPU`).
Empty, error and fallback states reuse current strings plus the FR-5 note.
No new shortcuts, dialogs or prefs.

## 7. Acceptance criteria (per requirement)

- FR-2/4: `pytest tests/test_gpu_parity.py -q` green (25 ordered maps +
  cmyk + edges, BW + palette, drift set, post-FX tail, no-GL fallback).
- FR-5: `QT_QPA_PLATFORM=offscreen` full suite green with and without
  `moderngl` installed (fallback covered both ways).
- FR-6: spike report in `tools/gpu_spike_preview.py` header (fps table
  vs numpy, GPU model); no gate assert, decision input only.
- FR-7: export byte-identity holds (exports never touch the GPU path).
- FR-8: `requirements.txt` diff + exe size note reviewed before merge.

## 8. Milestones

1. SRS accepted (this file) -> 2. afternoon spike (`Bayer + grade` in
   `moderngl`, fps vs numpy + pixel parity) -> 3. full C1 implemented
   behind `supports()` with parity green (this change: 4a grade stays
   CPU, GPU dithers; 4b post-GPU stays future work).
