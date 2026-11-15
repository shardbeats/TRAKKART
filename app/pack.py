"""Preset-pack share (v1.8 Fase C): offline zip of presets + palettes.

A pack is a plain zip (stdlib only, no network) with:
- `presets/<name>.json` — preset files (validated on import)
- `palettes/<name>.json` — palette files referenced by the presets
- `pack.json` — manifest {app, version, presets, palettes}

Single-JSON share stays intact; the pack is the multi-preset bundle
(sell/share a look pack). Import never overwrites: existing names are
skipped and reported. Zip traversal (`..`, absolute paths, foreign
top-level dirs) is rejected.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

PACK_MANIFEST = "pack.json"


def _safe_name(name: str) -> str:
    from app.names import safe_stem

    return safe_stem(name, "", keep=("-", "_"), fill="_")


def export_pack(preset_names: list[str], presets_dir: str | Path,
                palettes_dir: str | Path, out_zip: str | Path,
                palette_names: list[str] | None = None) -> Path:
    """Pack named presets + palettes. Returns the zip path.

    palette_names None = the whole palette library (a look pack ships
    its swatches); explicit list = only those files. Builtin palette
    names need no file (the app already has them).
    """
    from app import __version__
    from app.presets import load_preset

    pdir, adir = Path(presets_dir), Path(palettes_dir)
    out = Path(out_zip)
    if not list(preset_names):
        raise ValueError("pack needs at least one preset")
    presets: dict[str, dict] = {}
    for name in preset_names:
        p = load_preset(str(name), pdir)  # validates existence
        p.validate()
        presets[p.name] = p.to_dict()
    palettes: dict[str, dict] = {}
    adir_files = {p.stem: p for p in adir.glob("*.json")} if adir.is_dir() else {}
    wanted = list(palette_names) if palette_names is not None else sorted(adir_files)
    for ref in wanted:
        cand = adir_files.get(_safe_name(str(ref)))
        if cand is None or ref in palettes:
            continue
        try:
            palettes[str(ref)] = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    manifest = {"app": "TRAKKART", "version": __version__,
                "presets": sorted(presets), "palettes": sorted(palettes)}
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(PACK_MANIFEST, json.dumps(manifest, indent=2))
        for name in sorted(presets):
            zf.writestr(f"presets/{_safe_name(name)}.json",
                        json.dumps(presets[name], indent=2))
        for name in sorted(palettes):
            zf.writestr(f"palettes/{_safe_name(name)}.json",
                        json.dumps(palettes[name], indent=2))
    return out


def _check_member(name: str) -> str | None:
    """Safe relative member path (presets|palettes|manifest only), else None."""
    if not name or name.startswith("/") or name.startswith("\\"):
        return None
    parts = name.replace("\\", "/").split("/")
    if ".." in parts or "" in parts[:-1]:
        return None
    if len(parts) == 1 and parts[0] == PACK_MANIFEST:
        return name
    if len(parts) == 2 and parts[0] in ("presets", "palettes") \
            and parts[1].endswith(".json"):
        return name
    return None


def import_pack(zip_path: str | Path, presets_dir: str | Path,
                palettes_dir: str | Path) -> dict[str, list[str]]:
    """Merge a pack (skip existing, validate all). Returns the report."""
    from app.fx import normalize_custom_palette
    from app.presets import Preset, save_preset

    report = {"presets_imported": [], "presets_skipped": [],
              "palettes_imported": [], "palettes_skipped": []}
    pdir, adir = Path(presets_dir), Path(palettes_dir)
    pdir.mkdir(parents=True, exist_ok=True)
    adir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = [(_check_member(i.filename), i) for i in zf.infolist()]
        if any(m is None for m, _ in members):
            bad = sorted({i.filename for m, i in members if m is None})
            raise ValueError(f"unsafe pack members: {bad[:4]}")
        for _, info in members:
            if info.filename == PACK_MANIFEST:
                continue
            raw = json.loads(zf.read(info.filename).decode("utf-8"))
            if info.filename.startswith("presets/"):
                p = Preset.from_dict(raw)
                p.validate()
                dest = pdir / f"{_safe_name(p.name)}.json"
                if dest.exists():
                    report["presets_skipped"].append(p.name)
                else:
                    save_preset(p, pdir)
                    report["presets_imported"].append(p.name)
            else:
                colors = raw.get("colors", raw) if isinstance(raw, dict) else raw
                valid = normalize_custom_palette(colors)
                if valid is None:
                    raise ValueError(f"invalid palette: {info.filename}")
                name = raw.get("name", Path(info.filename).stem) \
                    if isinstance(raw, dict) else Path(info.filename).stem
                dest = adir / f"{_safe_name(str(name))}.json"
                if dest.exists():
                    report["palettes_skipped"].append(str(name))
                else:
                    dest.write_text(json.dumps(
                        {"name": str(name), "colors": [list(c) for c in valid]},
                        indent=2), encoding="utf-8")
                    report["palettes_imported"].append(str(name))
    return report


def bundle_zip(out_dir: str | Path, zip_path: str | Path | None = None) -> Path:
    """Zip every file in a folder (flat, stdlib). Used by batch + v2.0 frames."""
    from app.names import safe_stem

    out = Path(out_dir)
    if not out.is_dir():
        raise ValueError(f"not a folder: {out_dir}")
    files = sorted(f for f in out.iterdir() if f.is_file())
    if not files:
        raise ValueError("nothing to bundle")
    dest = Path(zip_path) if zip_path else out.parent / f"{safe_stem(out.name)}_bundle.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    return dest


__all__ = ["PACK_MANIFEST", "bundle_zip", "export_pack", "import_pack"]
