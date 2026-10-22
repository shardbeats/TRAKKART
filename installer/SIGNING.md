# Signing TRAKKART for Windows (Authenticode)

Why: an unsigned `.exe` triggers Windows SmartScreen ("Unknown publisher").
Users can still run it (More info → Run anyway), but a signature is what
separates "downloaded tool" from "professional product".

## Option A — No certificate (today, free)

1. Build: `python build_exe.py` (prints `unsigned build` and keeps going).
2. Ship `dist/TRAKKART.exe` + a note in the release:
   "Windows may show SmartScreen on first run (unsigned build):
   click *More info → Run anyway*."
3. Reputation builds over time: identical signed-by-nobody binaries gain
   SmartScreen trust as more users run them. New filename/version resets it.

## Option B — OV certificate (recommended when you sell/distribute)

1. Buy an OV code-signing certificate (Sectigo/DigiCert via reseller,
   ~€80-200/year). It arrives on a USB token or as `.pfx`.
2. Install Windows SDK `signtool.exe` (ships with Visual Studio Build Tools).
3. Set env and build:
   ```bat
   set TRAKKART_PFX=C:\certs\trakkart.pfx
   set TRAKKART_PFX_PASSWORD=***
   python build_exe.py
   ```
   The build signs `dist/TRAKKART.exe` automatically (SHA256 + RFC3161
   timestamp so the signature survives certificate expiry).
4. Verify: `signtool verify /pa /v dist\TRAKKART.exe`.

## Option C — EV certificate (SmartScreen reputation from day one)

Same as B, but EV gives immediate SmartScreen trust instead of building
reputation over weeks. Worth it only once downloads are frequent.

## Installer

`installer/trakkart.iss` (Inno Setup 6, free) builds
`dist/TRAKKART-Setup-<version>.exe`:

```bat
python build_installer.py
```

It reads the version from `app.__version__`, checks `dist/TRAKKART.exe`
exists, and calls `ISCC /DMyVersion=<v> installer/trakkart.iss`.
Sign the setup too: `signtool sign ... dist\TRAKKART-Setup-*.exe`.
The exe ships everything (numba + video, ~146MB portable).

## Checklist per release

1. Bump `app/__init__.py` + `pyproject.toml` version.
2. `python build_exe.py` (tests run first; signs if `TRAKKART_PFX` set).
3. `python build_installer.py` (signs the setup too).
4. Smoke test on a clean VM: install, run, export, uninstall.
5. Publish exe + setup + `MANUAL.md` with the CHANGELOG entry.
