# docs/screenshots — TRAKKART

User-facing captures referenced by `README.md`. All four ship with the repo:

| File | What it shows | Size hint |
|---|---|---|
| `main-window.png` | Full app window (SLIME_FS on a generated cover) | ≤1600px wide |
| `dither-panel.png` | Method cycling / pixel / threshold controls | ≤1200px wide |
| `export-dialog.png` | Export dialog with plan + format/size row | ≤1200px wide |
| `anim-preview.gif` | Genuine product GIF (March + Hue, 8f) | ≤5 MB, ≤800px wide |

Regenerate: `python tools/capture_readme_shots.py`. It uses an isolated
data dir (`TRAKKART_DATA_DIR`, temp by default, overridable via
`TRAKKART_SHOT_DIR`), a generated sample image (no licensed assets) and a
neutral `out/` folder, so no personal paths leak into the shots.
