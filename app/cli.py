"""TRAKKART headless CLI (R10, MIT): presets over files/folders, no UI.

Contract: `--out` is always a directory (`<in-stem>.<ext>` per file,
same bundle as UI batch: image + thumb + metadata, SVG/GIF per preset).
Stateless (no history log): automation must not touch user state.
MP4/WebP/separations stay dialog-only by design.

Exit codes: 0 = all ok/skipped, 1 = any file failed, 2 = usage error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.batch import EXTS


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="TRAKKART --cli",
        description="Offline cover batch without UI (preset over file/folder).")
    ap.add_argument("--preset", default="",
                    help="Preset name (see --list-presets).")
    ap.add_argument("--in", dest="src", default="",
                    help="Input image file or folder.")
    ap.add_argument("--out", dest="dst", default="",
                    help="Output directory (created).")
    ap.add_argument("--list-presets", action="store_true",
                    help="Print available preset names and exit.")
    return ap


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


def _single(src: Path, dst: Path, preset) -> dict:
    """One file through the batch bundle path (safety guard included)."""
    from PIL import Image

    from app.batch import build_extras, options_from_preset, render_single_image
    from app.exporter import bundle_filenames, export_with_options
    from app.safety import check_image

    base = src.stem
    opts = options_from_preset(preset)
    opts.base = base
    outs = [dst / f for f in
            bundle_filenames(opts, has_vector=bool(preset.vector_export),
                             has_gif=bool(preset.gif_export)).values()]
    try:
        img = Image.open(src).convert("RGB")
        check_image(img)  # never OOM on a huge file: becomes an error
    except Exception as e:  # noqa: BLE001
        return {"file": src.name, "status": "error", "error": str(e)}
    if all(o.exists() and o.stat().st_mtime >= src.stat().st_mtime for o in outs):
        return {"file": src.name, "status": "skipped",
                "outputs": [str(o) for o in outs]}
    try:
        res = render_single_image(img, preset)
        svg, frames = build_extras(img, preset)
        paths, _ = export_with_options(res, dst, opts, meta=preset.meta(),
                                       vector_svg=svg, gif_frames=frames,
                                       gif_fps=int(getattr(preset, "gif_fps", 8)))
        return {"file": src.name, "status": "ok",
                "outputs": [str(p) for p in paths.values()]}
    except Exception as e:  # noqa: BLE001
        return {"file": src.name, "status": "error", "error": str(e)}


def run_cli(argv: list[str] | None = None) -> int:
    """Entry point (no Qt import anywhere on this path). Returns exit code."""
    args = build_parser().parse_args(argv)
    # Frozen-safe: seed bundled presets/palettes like MainWindow does, so
    # --cli works on a fresh machine before the GUI ever runs (empty data dir
    # + no repo presets/ inside the bundle).
    from app.paths import get_palettes_dir, get_presets_dir
    from app.palette_library import ensure_bundled_palettes
    from app.presets import ensure_bundled, list_presets, load_preset

    ensure_bundled(get_presets_dir())
    ensure_bundled_palettes(get_palettes_dir())

    if args.list_presets:
        for name in list_presets():
            print(name)
        return 0
    if not args.preset:
        return _fail("--preset is required (or --list-presets)")
    if not args.src:
        return _fail("--in is required")
    if not args.dst:
        return _fail("--out is required")
    try:
        preset = load_preset(args.preset)
    except FileNotFoundError:
        avail = ", ".join(list_presets())
        return _fail(f"preset does not exist: {args.preset} (have: {avail})")
    try:
        preset.validate()
    except ValueError as e:
        return _fail(f"invalid preset {args.preset}: {e}")
    src = Path(args.src)
    dst = Path(args.dst)
    try:
        dst.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return _fail(f"cannot create --out {dst}: {e}")
    if src.is_dir():
        from app.batch import batch_process

        results = batch_process(src, dst, preset, skip_existing=True, jobs=1)
    elif src.is_file():
        if src.suffix.lower() not in EXTS:
            return _fail(f"not an image (need {'/'.join(EXTS)}): {src}")
        results = [_single(src, dst, preset)]
    else:
        return _fail(f"--in not found: {src}")
    ok = sum(1 for r in results if r.get("status") == "ok")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    errors = [(r.get("file", "?"), r.get("error", "?"))
              for r in results if r.get("status") == "error"]
    for r in results:
        if r.get("status") == "ok":
            print(f"ok {r['file']} -> {len(r.get('outputs', []))} file(s)")
        elif r.get("status") == "skipped":
            print(f"skipped {r['file']} (outputs newer)")
    for name, err in errors:
        print(f"error {name}: {err}", file=sys.stderr)
    print(f"{ok} ok, {skipped} skipped, {len(errors)} error(s)")
    return 1 if errors else 0


__all__ = ["build_parser", "run_cli"]
