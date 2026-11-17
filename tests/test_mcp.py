"""MCP stdio server (v2.x #9): spec pins over `app/mcp.py`.

Same contract as the headless CLI (no Qt, no network, dialog-only
extras stay out); thin JSON-RPC skin, no new render logic.
"""

import io
import json
import subprocess
import sys

from PIL import Image


def _run(lines: list[str]) -> list[dict]:
    from app.mcp import run_mcp

    out = io.StringIO()
    assert run_mcp(io.StringIO("\n".join(lines) + "\n"), out) == 0
    return [json.loads(line) for line in out.getvalue().strip().split("\n")]


def _call(name: str, args: dict, msg_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
            "params": {"name": name, "arguments": args}}


def _text(reply: dict) -> dict:
    return json.loads(reply["result"]["content"][0]["text"])


def test_mcp_initialize_and_ping():
    replies = _run([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05"}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}),
    ])
    assert len(replies) == 2  # notification gets no reply
    from app import __version__

    assert replies[0]["result"]["serverInfo"] == {"name": "trakkart", "version": __version__}
    assert replies[0]["result"]["capabilities"] == {"tools": {}}
    assert replies[1]["result"] == {}


def test_mcp_tools_list_has_three_tools():
    (reply,) = _run([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})])
    names = [t["name"] for t in reply["result"]["tools"]]
    assert names == ["list_presets", "render", "estimate"]
    for t in reply["result"]["tools"]:
        assert t["inputSchema"]["type"] == "object"


def test_mcp_list_presets_and_estimate(tmp_path):
    replies = _run([
        json.dumps(_call("list_presets", {})),
        json.dumps(_call("estimate", {"preset": "SLIME_FS", "width": 64, "height": 64}, 2)),
    ])
    assert "SLIME_FS" in _text(replies[0])["presets"]
    est = _text(replies[1])
    assert est["preset"] == "SLIME_FS" and est["total"] > 0
    assert all(v["bytes"] >= 0 and v["file"] for v in est["files"].values())


def test_mcp_estimate_and_render_use_the_same_plan(tmp_path, monkeypatch):
    """Estimate mirrors the bundle the CLI render actually writes."""
    import app.presets as P
    from app.presets import Preset, save_preset

    monkeypatch.setattr(P, "PRESETS_DIR", tmp_path)
    save_preset(Preset(name="EST_PLAN", method="bayer4", export_size=64,
                       ratio="1:1", vector_export=True, vector_cell=8,
                       gif_export=True, gif_frames=6, gif_size=480), tmp_path)
    (reply,) = _run([json.dumps(_call(
        "estimate", {"preset": "EST_PLAN", "width": 1000, "height": 500}))])
    est = _text(reply)
    assert est["files"]["image"]["file"] == "cover.png"
    assert est["files"]["image"]["bytes"] == int(64 * 64 * 0.35)  # export_size, not source
    # SVG grid: 1:1 cover caps the 500x500 canvas to the 64px document.
    assert est["files"]["vector"]["bytes"] == 8 * 8 * 60
    # GIF: preset.gif_size (480 long side), not the 1000x500 source.
    assert est["files"]["anim"]["bytes"] == int(480 * 240 * 0.5 * 6)


def test_mcp_notifications_never_get_a_reply():
    replies = _run([
        json.dumps({"jsonrpc": "2.0", "method": "nope"}),
        json.dumps({"jsonrpc": "2.0", "method": "tools/call",
                    "params": {"name": "list_presets", "arguments": {}}}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}),
    ])
    assert [r["id"] for r in replies] == [3]  # only the request answers
    (bad,) = _run([json.dumps({"jsonrpc": "2.0"})])
    assert bad["error"]["code"] == -32600 and bad["id"] is None


def test_mcp_render_roundtrip(tmp_path):
    src = tmp_path / "cover.png"
    Image.new("RGB", (96, 64), (200, 60, 40)).save(src)
    out = tmp_path / "o"
    (reply,) = _run([json.dumps(
        _call("render", {"preset": "SLIME_FS", "in": str(src), "out": str(out)}))])
    res = _text(reply)
    assert res["status"] == "ok" and "isError" not in reply["result"]
    assert any(str(out / p).endswith((".png", ".json", ".svg", ".gif"))
               for p in res["outputs"])
    assert all(__import__("pathlib").Path(p).exists() for p in res["outputs"])


def test_mcp_errors_stay_in_band():
    replies = _run([
        "not json at all",
        json.dumps({"jsonrpc": "2.0", "id": 7, "method": "nope"}),
        json.dumps(_call("render", {"preset": "NOPE", "in": "x", "out": "y"}, 8)),
        json.dumps(_call("mystery", {}, 9)),
        json.dumps({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                    "params": {"name": "estimate",
                               "arguments": {"preset": "SLIME_FS", "width": -1, "height": 0}}}),
    ])
    assert replies[0]["error"]["code"] == -32700  # loop survives bad line
    assert replies[1]["error"]["code"] == -32601
    assert _text(replies[2])["error"] and replies[2]["result"]["isError"] is True
    assert replies[3]["result"]["isError"] is True  # unknown tool, not a crash
    assert replies[4]["result"]["isError"] is True


def test_mcp_no_network_imports():
    # Hard spec guard: stdio only — sockets/HTTP must never land here.
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "app" / "mcp.py").read_text(encoding="utf-8")
    for banned in ("socket", "urllib", "requests", "http", "websocket", "httpx"):
        assert banned not in src, banned


def test_mcp_dispatch_without_qt():
    # Fresh interpreter: --mcp must never import PySide6.
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    probe = ("import sys, json, io; sys.argv=['main.py', '--mcp']; sys.path.insert(0, '.'); "
             "sys.stdin = io.StringIO(json.dumps("
             "{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}}) + chr(10)); "
             "import main; rc = main.main(); "
             "assert 'PySide6' not in sys.modules, 'Qt leaked into MCP'; assert rc == 0")
    r = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                       text=True, cwd=str(root))
    assert r.returncode == 0, r.stderr
    assert '"serverInfo"' in r.stdout
