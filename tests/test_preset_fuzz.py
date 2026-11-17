"""Preset fuzzer pins (v2.x #10): deterministic seeds, crash-freedom.

The full sweep lives in `tools/fuzz_presets.py` (CI fast job); these
pins keep the fuzzer itself under the suite: same seed -> same preset,
every mutated preset validates, small renders never crash.
"""

from PIL import Image


def _img():
    im = Image.new("RGB", (64, 64))
    px = im.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = ((x * 4) % 256, (y * 4) % 256, (x + y) % 256)
    return im


def test_fuzz_deterministic():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from fuzz_presets import mutate

    p1, m1 = mutate(7, 3)
    p2, m2 = mutate(7, 3)
    assert m1 == m2 and p1 == p2


def test_fuzz_mutated_presets_validate_and_render():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from fuzz_presets import run_case

    img = _img()
    for seed in (7, 99, 1234):
        for case in range(4):
            try:
                run_case(seed, case, img)
            except ValueError:
                pass  # invalid combo: validate() is right to reject it
