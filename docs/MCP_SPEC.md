# TRAKKART MCP stdio server — spec (v2.x #9)

Status: ACCEPTED (nov-2026). Implements the last queued v2.x item.

## 1. Goal

Expose the headless CLI surface (`app/cli.py`) to MCP clients
(Coding agents, automation) over **stdio only**. No new render logic:
the server is a thin JSON-RPC skin over `run_cli`'s building blocks
(`load_preset`, `_single`, `list_presets`).

## 2. Transport

- **Newline-delimited JSON-RPC 2.0** over stdin/stdout (one object per
  line, UTF-8). Same framing MCP itself uses on stdio.
- stderr is log-only (human text, never protocol).
- No sockets, no ports, no HTTP, no polling. The process exits on EOF.
- Entry: `python main.py --mcp`. Like `--cli`, it **never imports Qt**
  (fast, display-free, CI-safe).

## 3. No-network guard (hard rule)

- `app/mcp.py` imports only stdlib (`json`, `sys`) + sibling modules
  (`app.cli`, `app.presets`, `app.paths`, `app.palette_library`).
- A pin (`tests/test_mcp.py::test_mcp_no_network_imports`) fails the
  suite if `socket`, `urllib`, `requests`, `http`, `websocket` or
  `httpx` ever appear in `app/mcp.py`.
- Same rule as the CLI for dialog-only extras: **MP4/WebP/APNG stay
  out** — the `render` tool returns the CLI bundle only
  (image + thumb + metadata, SVG/GIF per preset).

## 4. Methods

| Method | Params | Result |
|---|---|---|
| `initialize` | `{protocolVersion, clientInfo?}` | `{protocolVersion, serverInfo: {name: "trakkart", version}, capabilities: {tools: {}}}` |
| `notifications/initialized` | — | no reply (notification) |
| `ping` | — | `{}` |
| `tools/list` | — | `{tools: [{name, description, inputSchema}]}` (3 tools) |
| `tools/call` | `{name, arguments}` | `{content: [{type: "text", text}], isError?}` |

Unknown methods → JSON-RPC `-32601`; bad params → `-32602`;
tool failure → `isError: true` with the message (never a traceback).
Malformed JSON lines → `-32700` and the loop continues.
Any request without `id` is a notification and gets no reply (valid or
notifications like `notifications/initialized`); invalid requests still
return `-32600` with `id: null`.

## 5. Tools

### `list_presets`
- input: `{}`. Output: `{presets: [names...]}` as JSON text.

### `render`
- input: `{preset: str, in: str (image path), out: str (dir, created)}`.
- Behavior: identical to one CLI `_single` run (safety `check_image`
  included; skip-if-newer included).
- Output: `{file, status: ok|skipped|error, outputs: [...], error?}`.

### `estimate`
- input: `{preset: str, width: int, height: int}`.
- Output: the bundle filenames + byte estimate from `plan_export`,
  i.e. the same dimensions/frames the CLI/batch `render` writes
  (preset `gif_size` included, not the dialog's live size override).
  Plan-only, never a promise.

## 6. Non-goals

- No batch-over-folder tool (CLI covers it; one file per call keeps
  the schema small and deterministic).
- No progress notifications, no cancellation (renders are seconds).
- No auth: stdio inherits the caller's OS identity; nothing listens.
