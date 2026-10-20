"""Offline batch: input folder -> one bundle per file with a preset.

Skip if outputs exist and are newer than the source.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image

from app.exporter import ExportOptions, ExportSelection, bundle_filenames, export_with_options
from app.presets import Preset
from app.vector import vector_bundle

__all__ = ["EXTS", "batch_process", "render_single_image", "build_extras"]

EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def options_from_preset(preset: Preset) -> ExportOptions:
    """Bundle batch: imagen+thumb+meta siempre, SVG/GIF según preset."""
    return ExportOptions(
        base="batch",
        selection=ExportSelection(
            image=True, thumb_1080p=True,
            vector=bool(preset.vector_export), anim=bool(preset.gif_export),
            metadata=True,
        ),
        overwrite="overwrite",
        size=int(preset.export_size), format=str(preset.export_format),
        quality=int(preset.export_quality),
    )


def _outputs_for(out_dir: Path, base: str, preset) -> list[Path]:
    opts = options_from_preset(preset)
    opts.base = base
    return [out_dir / f for f in
            bundle_filenames(opts, has_vector=bool(preset.vector_export),
                             has_gif=bool(preset.gif_export)).values()]


def render_single_image(img: Image.Image, preset: Preset) -> Image.Image:
    """Un solo render (secuencial o multiproceso usan lo mismo)."""
    from app.pipeline import render_preset

    return render_preset(img, preset)


def build_extras(img: Image.Image, preset: Preset) -> tuple[str | None, list | None]:
    """SVG + frames GIF opcionales según preset. Retorna (svg, frames)."""
    svg = None
    if preset.vector_export:
        svg, _, _ = vector_bundle(img, preset)
    frames = None
    if preset.gif_export:
        from app.gif import gif_frames

        frames = gif_frames(img, preset, frames=int(preset.gif_frames), mode=preset.gif_mode,
                            max_side=int(getattr(preset, "gif_size", 480)),
                            pingpong=bool(getattr(preset, "gif_pingpong", False)))
    return svg, frames


def _render_one(args: tuple) -> dict:
    """Top-level worker (multiprocess): (path_str, out_str, base, preset_dict)."""
    import json as _json

    from PIL import Image as _Image

    from app.exporter import export_with_options as _export_with_options
    from app.presets import Preset as _Preset
    from app.safety import check_image as _check_image

    path_str, out_str, base, preset_dict = args
    try:
        p = _Preset.from_dict(_json.loads(preset_dict))
        img = _Image.open(path_str).convert("RGB")
        _check_image(img)  # never OOM on a huge file: becomes an error
        res = render_single_image(img, p)
        svg, frames = build_extras(img, p)
        opts = options_from_preset(p)
        opts.base = base
        paths, _ = _export_with_options(res, out_str, opts, meta=p.meta(),
                                        vector_svg=svg, gif_frames=frames,
                                        gif_fps=int(getattr(p, "gif_fps", 8)))
        return {"file": Path(path_str).name, "status": "ok",
                "outputs": [str(x) for x in paths.values()]}
    except Exception as e:  # noqa: BLE001
        return {"file": Path(path_str).name, "status": "error", "error": str(e)}


def batch_process(
    input_dir: str | Path,
    out_dir: str | Path,
    preset: Preset,
    skip_existing: bool = True,
    progress_cb: Callable[[int, int, str], None] | None = None,
    store=None,
    jobs: int = 1,
    cancel: list | None = None,
) -> list[dict]:
    """Process every image in input_dir. jobs>1 uses multiprocessing.
    cancel=[True] stops between files (Cancel button)."""
    import json as _json
    from concurrent.futures import ProcessPoolExecutor

    preset.validate()
    src = Path(input_dir)
    dst = Path(out_dir)
    if not src.is_dir():
        raise NotADirectoryError(f"input is not a folder: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() in EXTS)
    total = len(files)
    results: list[dict] = []

    def _log(base: str, r: dict) -> None:
        if store is not None and r["status"] == "ok":
            try:
                store.log_export(base, preset.name, preset.meta(), r.get("outputs", []))
            except Exception:
                pass

    pending: list[tuple] = []
    for f in files:
        base = f.stem
        outs = _outputs_for(dst, base, preset)
        if cancel and cancel[0]:
            break
        if skip_existing and all(o.exists() and o.stat().st_mtime >= f.stat().st_mtime for o in outs):
            results.append({"file": f.name, "status": "skipped", "outputs": [str(o) for o in outs]})
            if progress_cb:
                progress_cb(len(results), total, f.name)
            continue
        pending.append((str(f), str(dst), base, _json.dumps(preset.to_dict(), ensure_ascii=False)))

    if jobs and int(jobs) > 1 and pending:
        pool_ok = False
        try:
            from concurrent.futures import as_completed

            with ProcessPoolExecutor(max_workers=int(jobs)) as ex:
                futs = {}
                for item in pending:
                    if cancel and cancel[0]:
                        break
                    futs[ex.submit(_render_one, item)] = item[0]
                for fut in as_completed(futs):
                    if cancel and cancel[0]:
                        for g in futs:
                            g.cancel()
                        break
                    r = fut.result()
                    results.append(r)
                    _log(Path(r["file"]).stem, r)
                    if progress_cb:
                        progress_cb(len(results), total, r["file"])
            pool_ok = True
        except (RuntimeError, OSError):
            # No __main__ guard (scripts) or no resources: fall back to sequential.
            pass
        if pool_ok or (cancel and cancel[0]):
            _sort_results(results, files)
            return results

    for path_str, _, base, _ in pending:
        if cancel and cancel[0]:
            break
        f = src / Path(path_str).name
        try:
            img = Image.open(f).convert("RGB")
            res = render_single_image(img, preset)
            svg, frames = build_extras(img, preset)
            opts = options_from_preset(preset)
            opts.base = base
            paths, _ = export_with_options(res, dst, opts, meta=preset.meta(),
                                           vector_svg=svg, gif_frames=frames,
                                           gif_fps=int(getattr(preset, "gif_fps", 8)))
            results.append({"file": f.name, "status": "ok", "outputs": [str(p) for p in paths.values()]})
            _log(base, results[-1])
        except Exception as e:  # noqa: BLE001
            results.append({"file": f.name, "status": "error", "error": str(e)})
        if progress_cb:
            progress_cb(len(results), total, f.name)
    return results


def _sort_results(results: list[dict], files: list[Path]) -> None:
    """Sort results like files (the pool does not guarantee order)."""
    order = {f.name: i for i, f in enumerate(files)}
    results.sort(key=lambda r: order.get(r.get("file", ""), 0))
