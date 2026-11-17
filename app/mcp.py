"""MCP stdio server over the headless CLI (v2.x #9, MIT).

Newline-delimited JSON-RPC 2.0 on stdin/stdout (the framing MCP
itself uses on stdio). Thin skin over `app.cli` building blocks —
no new render logic, no Qt, no network (see `docs/MCP_SPEC.md`;
a pin fails the suite if network imports ever land here).

Entry: `python main.py --mcp`. stdin EOF ends the loop (exit 0).
"""

from __future__ import annotations

import json
import sys

PROTOCOL_VERSION = "2024-11-05"

TOOL_DEFS = [
    {
        "name": "list_presets",
        "description": "List available preset names.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "render",
        "description": "Render one image with a preset (CLI bundle: image + thumb + "
                       "metadata, SVG/GIF per preset). MP4/WebP/APNG stay dialog-only.",
        "inputSchema": {
            "type": "object",
            "required": ["preset", "in", "out"],
            "properties": {
                "preset": {"type": "string"},
                "in": {"type": "string", "description": "Input image path"},
                "out": {"type": "string", "description": "Output directory (created)"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "estimate",
        "description": "Bundle filenames + byte estimates for a preset at WxH "
                       "(plan-only, never a promise).",
        "inputSchema": {
            "type": "object",
            "required": ["preset", "width", "height"],
            "properties": {
                "preset": {"type": "string"},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
    },
]


def _ok(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": code, "message": message}}


def _text(payload: dict, is_error: bool = False) -> dict:
    out = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    if is_error:
        out["isError"] = True
    return out


def _seed() -> None:
    """Frozen-safe seeding, same as run_cli (fresh machine, empty data dir)."""
    from app.paths import get_palettes_dir, get_presets_dir
    from app.palette_library import ensure_bundled_palettes
    from app.presets import ensure_bundled

    ensure_bundled(get_presets_dir())
    ensure_bundled_palettes(get_palettes_dir())


def _tool_call(name: str, args: dict) -> dict:
    from pathlib import Path

    from app.presets import list_presets, load_preset

    _seed()
    if name == "list_presets":
        return _text({"presets": list_presets()})
    if name == "render":
        preset_name = args.get("preset", "")
        src, dst = Path(str(args.get("in", ""))), Path(str(args.get("out", "")))
        if not preset_name or not str(args.get("in", "")) or not str(args.get("out", "")):
            return _text({"error": "preset/in/out are all required"}, is_error=True)
        try:
            preset = load_preset(preset_name)
            preset.validate()
        except (FileNotFoundError, ValueError) as e:
            return _text({"error": str(e)}, is_error=True)
        if not src.is_file():
            return _text({"error": f"input not found: {src}"}, is_error=True)
        try:
            dst.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return _text({"error": f"cannot create out dir {dst}: {e}"}, is_error=True)
        from app.cli import _single

        res = _single(src, dst, preset)
        return _text(res, is_error=res.get("status") == "error")
    if name == "estimate":
        preset_name = args.get("preset", "")
        try:
            w, h = int(args.get("width", 0)), int(args.get("height", 0))
        except (TypeError, ValueError):
            return _text({"error": "width/height must be positive integers"}, is_error=True)
        if not preset_name or w < 1 or h < 1:
            return _text({"error": "preset/width/height are all required"}, is_error=True)
        try:
            preset = load_preset(preset_name)
            preset.validate()
        except (FileNotFoundError, ValueError) as e:
            return _text({"error": str(e)}, is_error=True)
        return _text(_estimate_bundle(preset, w, h))
    return _text({"error": f"unknown tool: {name}"}, is_error=True)


def _estimate_bundle(preset, w: int, h: int) -> dict:
    from app.batch import options_from_preset
    from app.exporter import _estimate_bytes, bundle_filenames

    opts = options_from_preset(preset)
    opts.base = "cover"
    names = bundle_filenames(
        opts, has_vector=bool(preset.vector_export),
        has_gif=bool(preset.gif_export))
    extra = {"gif_frames": int(getattr(preset, "gif_frames", 6)),
             "vector_cells": (0, 0)}
    files = {k: {"file": f, "bytes": _estimate_bytes(
        k, w, h, opts.format, opts.quality, extra)} for k, f in names.items()}
    return {"preset": preset.name, "width": w, "height": h,
            "files": files, "total": sum(f["bytes"] for f in files.values())}


def handle(msg: dict):
    """One JSON-RPC message -> reply dict, or None (notification)."""
    from app import __version__

    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _err(msg.get("id") if isinstance(msg, dict) else None,
                    -32600, "need JSON-RPC 2.0 object")
    method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _ok(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": "trakkart", "version": __version__},
            "capabilities": {"tools": {}}})
    if method == "ping":
        return _ok(msg_id, {})
    if method == "tools/list":
        return _ok(msg_id, {"tools": TOOL_DEFS})
    if method == "tools/call":
        if not isinstance(params, dict) or "name" not in params:
            return _err(msg_id, -32602, "tools/call needs {name, arguments}")
        raw_args = params.get("arguments") or {}
        args = raw_args if isinstance(raw_args, dict) else {}
        return _ok(msg_id, _tool_call(str(params["name"]), args))
    if method is None:
        return _err(msg_id, -32600, "no method")
    return _err(msg_id, -32601, f"unknown method: {method}")


def run_mcp(stdin=None, stdout=None) -> int:
    """Serve JSON-RPC on stdin/stdout until EOF. Returns exit code."""
    inp = stdin or sys.stdin
    out = stdout or sys.stdout
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            out.write(json.dumps(_err(None, -32700, f"parse error: {e}")) + "\n")
            out.flush()
            continue
        try:
            reply = handle(msg)
        except Exception as e:  # noqa: BLE001 — never kill the loop
            reply = _err(msg.get("id") if isinstance(msg, dict) else None,
                         -32603, f"internal: {e}")
        if reply is not None:
            out.write(json.dumps(reply) + "\n")
            out.flush()
    return 0


__all__ = ["PROTOCOL_VERSION", "TOOL_DEFS", "handle", "run_mcp"]
