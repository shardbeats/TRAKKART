"""Preset fuzzer (v2.x #10, cheapest first): seeded random presets -> render.

Walks the declarative `FIELDS` schema in `app.presets` (ranges, oneofs
with live registries, bools, hex) so new fields are fuzzed for free.
Stacks/palettes ride along untouched from the base preset.

Contract: deterministic — same (seed, case) always renders the same
preset. A crash prints the seed + mutated fields as repro JSON and
exits 1. Renders are capped at 128px (the dither/FX params under test
are resolution-independent; size paths have their own pins).

Usage: `python tools/fuzz_presets.py --cases 120 --seed 7`
CI runs a short pass in the fast job; nightly can raise --cases.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Render-only caps (keep the fuzz fast; size paths have their own pins).
# Concrete 128 canvas: valid under every ratio (custom included).
_RENDER_CAPS = {"export_size": 128, "gif_size": 128, "canvas_w": 128,
                "canvas_h": 128, "gif_frames": 4, "gif_export": False,
                "vector_export": False}

_SKIP_FIELDS = {"name", "custom_palette", "fx_stack", "motif", "ascii",
                "gradient_stops"}  # structured blobs: own tests, not scalars


def mutate(seed: int, case: int, n_mutations: int = 8):
    """Deterministic mutated preset + {field: value} repro dict."""
    from app.presets import FIELDS, list_presets, load_preset

    rng = random.Random(seed * 1_000_003 + case * 7919)
    names = list_presets()
    base = load_preset(rng.choice(names))
    current = {f.name: getattr(base, f.name, None) for f in FIELDS}
    mutated: dict = {}
    # Always cross method x palette (the core of every render).
    methods = _oneof("method")
    palettes = _oneof("palette")
    if methods:
        mutated["method"] = rng.choice(methods)
    if palettes:
        mutated["palette"] = rng.choice(palettes)
    pool = [f for f in FIELDS if f.name not in _SKIP_FIELDS
            and f.name not in mutated and getattr(base, f.name, None) is not None]
    for spec in rng.sample(pool, min(n_mutations, len(pool))):
        v = _sample(spec, rng)
        if v is not None:
            mutated[spec.name] = v
    from app.presets import Preset

    preset = Preset(**{**current, **mutated})
    preset.validate()
    return preset, mutated


def _oneof(field_name: str) -> tuple:
    from app.presets import FIELDS

    for spec in FIELDS:
        if spec.name == field_name and spec.rule and spec.rule[0] == "oneof":
            try:
                return tuple(spec._oneof_values())
            except Exception:  # noqa: BLE001 — registry import issue: skip
                return ()
    return ()


def _sample(spec, rng: random.Random):
    kind = spec.kind
    rule = spec.rule or ()
    try:
        if kind == "bool":
            return bool(rng.getrandbits(1))
        if not rule:
            return None
        if rule[0] in ("range", "range0"):
            _, lo, hi = rule
            v = rng.uniform(lo, hi)
            if rule[0] == "range0" and rng.random() < 0.2:
                v = 0
            return int(round(v)) if kind == "int" else float(v)
        if rule[0] == "oneof":
            return rng.choice(list(spec._oneof_values()))
        if rule[0] in ("hex", "hexreq"):
            return "#%06X" % rng.getrandbits(24)
    except Exception:  # noqa: BLE001 — never let sampling itself fail
        return None
    return None


def run_case(seed: int, case: int, img, preset=None):
    import dataclasses

    from app.batch import render_single_image

    if preset is None:
        preset, mutated = mutate(seed, case)
    else:
        mutated = {}
    preset = dataclasses.replace(preset, **{k: v for k, v in _RENDER_CAPS.items()
                                            if k in preset.__dataclass_fields__})
    t0 = time.perf_counter()
    out = render_single_image(img, preset)
    dt = time.perf_counter() - t0
    assert out.size[0] > 0 and out.size[1] > 0
    return mutated, dt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seeded preset fuzz (crash-freedom).")
    ap.add_argument("--cases", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)
    from PIL import Image

    img = Image.new("RGB", (64, 64))
    px = img.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = ((x * 4) % 256, (y * 4) % 256, (x + y) % 256)
    t0 = time.perf_counter()
    worst = 0.0
    skipped = 0
    for case in range(max(1, args.cases)):
        try:
            preset, _ = mutate(args.seed, case)
        except ValueError:
            # Sampled an invalid combo (e.g. ratio=custom over a 0x0
            # canvas): validate() is right to reject it — skip, not FAIL.
            skipped += 1
            continue
        try:
            _, dt = run_case(args.seed, case, img, preset)
        except Exception as e:  # noqa: BLE001
            _, mutated = mutate(args.seed, case)
            print(f"fuzz FAIL seed={args.seed} case={case}: {type(e).__name__}: {e}")
            print("repro: " + json.dumps({"seed": args.seed, "case": case,
                                          "mutated": {k: str(v) for k, v in mutated.items()}}))
            return 1
        worst = max(worst, dt)
    total = time.perf_counter() - t0
    print(f"fuzz: {args.cases - skipped} ok, {skipped} invalid-combo skips "
          f"(seed={args.seed}, {total:.1f}s total, worst case {worst:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
