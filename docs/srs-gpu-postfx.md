# SRS — GPU post-FX tail (4b, PROPOSAL, not approved)

Status: draft for owner approval. No code changes until accepted.
Rule from ROADMAP §10: explicit plan approval before any implementation.

## 1. Goal + pipeline

Extend the 4a GPU preview (GPU owns ONLY the dither stage) over the
post-dither tail — brand + ordered FX stack — where it pays, without
changing what the app exports.

Today: `PIL -> CPU grade -> GPU dither -> CPU brand/stack -> PIL`.
Proposed: `PIL -> CPU grade -> GPU dither -> GPU post (subset) ->
PIL`, falling back to the CPU tail whenever the stack contains a
non-GPU effect. Export/batch/CLI/video stay CPU numpy, byte-identical.

## 2. Why it is 4b (measured context)

The post tail at 640px proxy is fast enough for v1 (ROADMAP §10):
point/region ops over ~0.4MP are sub-frame on CPU. 4b only pays on
`Full` doc-size stills (e.g. 3000px) with heavy stacks. It is an
iteration speedup, never a correctness fix.

## 3. Per-effect verdict (20 stack ids, `app/fx_dispatch.py`)

GPU candidates (deterministic, no RNG, no Pillow kernels):
`vignette`, `scanlines`, `grille`, `border`, `letterbox`, `fade`,
`split_tone`, `gradient_map`, `pasteup` (blend math only),
`halftone` (pattern), `slice`/`wave`/`chroma` (rolls; offsets baked
on CPU like the 4a LUTs).

CPU-locked (parity unreachable or pointless in GLSL):
`grain`, `dust` (numpy RNG stream vs GLSL hash — never 1-LSB),
`pixelsort` (serial), `mosh` (RNG + blocks), `jpeg` (Pillow codec),
`post_blur`/`post_sharpen` (Pillow filter kernels), `glow` iff it
blurs (else point-op: re-evaluate in spike).

## 4. Architecture rule (no per-effect ping-pong)

Readback per effect would eat the win. Rule: the tail runs on GPU
only when EVERY enabled stack entry is a GPU candidate; otherwise
the whole tail stays CPU (current code, zero change). One shader
program, one upload, one readback — same shape as 4a.

## 5. Requirements (if approved)

- FR-1 Subset program: brand (`replace_white`) + candidate effects in
  stack order over the dithered image; unknown/disabled ids fall back
  to CPU tail.
- FR-2 All-or-nothing gate: `supports_post(stack)` decides per render;
  mixed stacks take the CPU path silently (status keeps `GPU`/`CPU`
  suffix semantics: suffix reports the dither backend as today).
- FR-3 Parity harness extends `tests/test_gpu_parity.py`: per-candidate
  effect, stacked combos, BW + palette; gate maxdiff <= 1 LSB (same
  transcription rules as 4a: integer math, bankers ties, baked LUTs
  for seeded geometry).
- FR-4 Preview-only wiring (same surfaces as 4a: 640px proxy +
  `Full` stills, CPU fallback, no export/batch/CLI/video change).
- FR-5 Perf gate: `Full` 3000px heavy-stack still under the Live
  120ms budget on the reference machine, measured by spike report
  (no gate assert).

## 6. Acceptance + milestones

1. This SRS accepted (scope table frozen) -> 2. spike (candidate
   subset on one 3000px still: fps vs CPU + parity) -> 3. implement
   behind `supports_post()` with parity green -> 4. MANUAL + QA +
   gates green before merge.

Explicit non-goals: RNG effects on GPU (grain/dust/mosh stay CPU
forever), JPEG/pixelsort/blur-kernel transcription, QOpenGLWidget,
export path changes, new deps (moderngl already reviewed in 4a).
