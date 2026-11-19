# Shipping TRAKKART unsigned (Authenticode: decided against)

Decision (owner nov-2026): no code-signing certificate, ever. TRAKKART
ships unsigned; users click through SmartScreen once
(*More info → Run anyway*). This file is the unsigned-release notes,
not a signing plan. The optional `TRAKKART_PFX` hooks in the build
scripts stay as dead-safe no-ops (they only sign when the env vars
exist); nothing depends on them.

Why unsigned is fine here: an unsigned `.exe` triggers Windows
SmartScreen ("Unknown publisher") on first run, but still runs.
Reputation builds over time: identical binaries gain SmartScreen
trust as more users run them (a new filename/version resets it).

## Build

```bat
python build_portable.py --skip-tests
```

Prints `unsigned build` and keeps going.

## Installer

`installer/trakkart.iss` (Inno Setup 6, free) builds
`dist/TRAKKART-Setup-<version>.exe`:

```bat
python build_installer.py
```

It reads the version from `app.__version__`, checks
`dist/portable/TRAKKART/TRAKKART.exe` exists, and calls
`ISCC /DMyVersion=<v> installer/trakkart.iss`.
The exe ships everything (numba + video, ~146MB portable).

## Checklist per release

1. Bump `app/__init__.py` + `pyproject.toml` version.
2. `python build_portable.py` (tests run first).
3. `python build_installer.py`.
4. Smoke test on a clean VM: install, run, export, uninstall.
5. Publish exe + setup + `MANUAL.md` with the CHANGELOG entry and
   this SmartScreen note: "Windows may show SmartScreen on first
   run (unsigned build): click *More info → Run anyway*."
