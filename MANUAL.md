# TRAKKART — User manual

Offline cover-art generator with dithering. 100% local: nothing is uploaded,
nothing is tracked. Your data lives on your machine (the app's data folder).

## Installation

- **Installer:** run `TRAKKART-Setup-<version>.exe` (Start menu shortcut +
  bundled manual).
- **Portable:** copy `TRAKKART.exe` anywhere and run it.
- **First launch:** Windows SmartScreen may warn if the build is unsigned:
  *More info → Run anyway*.
- **Requirements:** 64-bit Windows 10/11. No internet, no Python install.
  Video (MP4) and acceleration ship inside — no extra download.

## Quick start (5 steps)

1. **Open an image:** File → Open (Ctrl+O), drag it onto the window, or
   paste it (Ctrl+V). Folders work too (see Batch).
2. **Pick a method:** the ◀ ▶ buttons cycle through 36 dithering engines.
3. **Adjust color:** SOURCE extracts the palette from your image, Depth limits
   tones, the dice (🎲) reshuffle without losing the good stuff (locks 🔒).
4. **Animate (optional):** the VIDEO panel previews; GIF exports at
   document size, MP4 defaults to 1080p (MP4 size: Canvas/1080p/720p in the Export dialog).
5. **Export:** Export… (Ctrl+Shift+S) or Quick export (Ctrl+S), which repeats
   your last setup. SVG for logos, JSON for metadata.

## Panels

| Panel | What it does |
|---|---|
| IMAGE | open, rotate, flip, invert, visual crop, CANVAS size |
| DITHER | preset, method, pixel, motif, ascii (charset, columns 20-300, gamma, color mono/source/palette, ink/bg, invert, dither; pixel_size ignored) |
| COLOR | adjustments, duotone/brand, custom strip, palette library |
| FX | pre/grade/texture/glitch + reorderable effect stack |
| DATAMOSH | mosh flavors + amount + seed |
| MORPH | particle chain (Add/Remove/Up/Down) + "Loop (last → first)" for a seamless loop |
| MOTION | video preview + Signal Drift |

**Viewport** (View): Full = instant render; Live = debounced (fast
120ms / heavy 350ms); Still = manual only (F5). For slow machines or
huge canvases use Still.

## Exporting
- **File name:** base for all files (weird characters → `_`).
- **Folder:** destination; Settings default.
- **Format/Quality/Size:** the document CANVAS dictates size.
- **Include:** main image, 1080p thumb, vector SVG, GIF, MP4, JSON.
  MP4 has its own size (Canvas/1080p/720p, default 1080p); the dialog
  shows a weight estimate and warns on heavy files. The animation
  always follows the live VIDEO section.
- **Collision:** nothing is ever lost — if the name exists it suggests
  `name_2`, `name_3`… (or Overwrite if you choose).
- **Quick export** repeats the last setup without asking. If you switch
  images, it asks again (never reuses the previous name).

## Batch (folders)

File → Batch folder (Ctrl+B): pick input/output, Jobs 1-8
(1 = safe sequential, more = multiprocessing), format and outputs per
operation. With `Drop=Batch` on, dropping a folder asks directly
whether to process it.

**Watch folder:** File → Watch folder… picks a folder to watch, an
output and a fixed preset. New/changed files process automatically
(only those; 3s settle delay). Uncheck the menu entry to stop.

## Command line (no UI)

Same engine, no window — for labels batching many singles:

```
TRAKKART.exe --cli --list-presets
TRAKKART.exe --cli --preset SLIME_FS --in cover.png --out out\
TRAKKART.exe --cli --preset SLIME_FS --in covers\ --out out\
```

`--out` is always a folder. Same bundle as Batch (image + thumb +
metadata, SVG/GIF per preset). MP4/WebP/separations stay dialog-only.
Exit 0 = done, 1 = some file failed, 2 = usage error.

## Presets & Settings

- **Presets:** the combo saves the current recipe (Save…), Export/Import
  shares `.json` offline.
- **File → Settings (Ctrl+,):** default output folder, format/
  quality/size and default outputs, jobs, Drop=Batch, startup
  viewport, recent recipes and data folder.
- **Backup:** in Settings, Export…/Import… save or restore the whole
  config `.json`.
- **Session:** by default it reopens your last image and preset on launch
  (disable in Settings).

## Acceleration & video (included)

The `.exe` ships everything: numba acceleration (10-50x on large Floyd)
and MP4. Nothing to install, nothing to pick.

- Running from source: `pip install -r requirements.txt` already
  includes acceleration + video.
- In the `.exe`, the Extras group is informational only: everything ships
  inside.

## Editing the image

- **Undo/Redo:** Edit → Undo (Ctrl+Z) / Redo (Ctrl+Y), 20 levels.
- **Compare:** hold Space or *Hold to compare* to see the ORIGINAL.
- **Zoom:** Ctrl+= / Ctrl+- / Ctrl+0 (fit) / Ctrl+1 (100%). The canvas
  fits to the available area by default; wheel zooms at the cursor and
  dragging pans when the image is larger than the view. The zoom badge in
  the preview title row is clickable: Fit <-> 100%. 100% renders the
  full preview on demand (document size when the source has enough detail;
  async when the preset is heavy), so you see real pixels instead of an
  upscaled proxy.
- **Canvas size:** the Document panel shows W×H and the megapixels. Above
  36 MP the label turns amber (`⚠ 64 MP`): a soft warning about render time
  and RAM, never a block. Tiny sources (64px or less) keep hard edges in
  stretch/blur instead of blending into mush.

## Main shortcuts

| Action | Shortcut |
|---|---|
| Open / Export / Quick export | Ctrl+O / Ctrl+Shift+S / Ctrl+S |
| Batch | Ctrl+B |
| Undo / Redo | Ctrl+Z / Ctrl+Y |
| Surprise me | Ctrl+R |
| Copy result / Paste | Ctrl+C / Ctrl+V |
| Refresh / Previous-next method | F5 / Alt+Left / Alt+Right |
| Manual | F1 |

Full list: Help → Keyboard shortcuts.

**Custom shortcuts:** open Help → Keyboard shortcuts, click any
shortcut cell and press the new keys (Esc cancels, Del clears).
Conflicts are refused with a message naming the other action;
*Reset defaults* restores everything. Bindings live in
`shortcuts.json` next to the other portable data, so they travel
with your `data` folder.

## Privacy & data

- Zero network: TRAKKART makes no connections (unless you drop an
  image URL, at your own request).
- Zero tracking: no telemetry, no accounts.
- Where everything is: Help → Show logs folder (prefs, database,
  `trakkart.log`). Your presets and palettes live in `data/presets` and
  `data/palettes`: copy the data folder and they travel with you to another
  machine. Deleting that folder factory-resets the app.

## Common issues

- **App won't open an image:** unsupported format (use PNG/JPG/WebP/
  BMP) or giant image (8000px limit / see the exact message).
- **It's slow:** switch to the Still viewport or lower the CANVAS size.
- **MP4 disabled (source runs only):** `pip install -r requirements.txt` then restart.
- **Something broke:** every failure writes a numbered report
  (`[E0007]`: what you did + full technical detail) to `trakkart.log`,
  and the app shows a plain-language hint plus that code instead of
  the raw error. Help → *Copy last error report* copies the whole
  report — paste it when reporting the bug (Help → *Show logs folder*
  reveals the file; Help → *About* shows the exact version).
