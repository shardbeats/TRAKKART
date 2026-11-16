# TRAKKART — User manual

Offline cover-art generator with dithering. 100% local: nothing is uploaded,
nothing is tracked. Your data lives on your machine (the app's data folder).

Words used in this manual: a **still** is one static dithered image (the main
product); an **animation** (GIF/MP4) is a loop built from stills. The
**Viewport** `Still` mode is the manual-refresh still-image preview.

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
2. **Pick a method:** the ◀ ▶ buttons cycle through 38 dithering engines.
3. **Adjust color:** SOURCE extracts the palette from your image, Depth limits
   tones, the dice (🎲) reshuffle without losing the good stuff (locks 🔒).
4. **Animate (optional):** the VIDEO panel previews; GIF exports at
   document size, MP4 defaults to 1080p (MP4 size: Canvas/1080p/720p in the Export dialog).
5. **Export:** Export… (Ctrl+Shift+S) or Quick export (Ctrl+S), which repeats
   your last setup. SVG for logos, JSON for metadata.

## Panels

| Panel | What it does |
|---|---|
| IMAGE | open, rotate, flip, invert, visual crop, CANVAS size ("SP-404 128×64" button for the Roland OLED canvas), framing: cover / contain / stretch / blur / mirror (mirror wraps edges outward for print bleed) |
| DITHER | preset, method (incl. `ostromoukhov` variable-coefficient ED for clean midtones + `dizzy` IGN blue-noise-like threshold), serpentine (ED scan alternates per row, less streaks), rosette + LPI (CMYK print: screen assignment + ruling at export DPI), pixel, motif, ascii (charset, columns 20-300, gamma, color mono/source/palette, ink/bg, invert, dither; pixel_size ignored) |
| COLOR | adjustments, duotone/brand, custom strip, palette library, daltonism preview (View menu), WCAG contrast hints, Lospec offline import |
| FX | pre/grade/texture/glitch + reorderable effect stack |
| DATAMOSH | 10 mosh flavors (incl. codec-style bleed/hold/tear) + amount + size + seed |
| MORPH | particle chain (Add/Remove/Up/Down) + per-leg Repeat ×1-8 + "Loop (last → first)" for a seamless loop. Dissolve controls: Field, Stagger, Ease, Dots, Travel, Path, Match (smooth/hilbert/radial/morton), Dots shape (square/round), Tint (fades as dots disperse), Trail, Amount, Speed, Wind, Seed, Hold, Shade |
| MOTION | video preview + Signal Drift + clip import (short footage as input, session-only) + ⚠ Rebuild when the preview is stale |

**Viewport** (View): Full = instant render; Live = debounced (fast
120ms / heavy 350ms); Still = manual only (F5). For slow machines or
huge canvases use Still. "SP-404 OLED preview" shows the still as the
128×64 1-bit device image (display-only; DITHER threshold tunes it).

## Datamosh, segments and export hygiene (v1.7)

- **Datamosh:** 10 flavors share one control row. Seven are classic pixel
  damage (`blocks`, `smear`, `ghost`, `rows`, `chroma`, `crush`,
  `speckle`); three are codec-flavored: `bleed` (directional echo),
  `hold` (frozen P-frame bands) and `tear` (macroblock band rolls).
  Amount 0 = off; Seed re-rolls the damage deterministically (same seed =
  same result, so exports replay); Size scales the feature. They animate
  in VIDEO and stack in FX STACK like the classic ones, and old presets
  keep rendering identically.
- **Repeat per leg (MORPH):** each playlist row has a Repeat ×1-8 spin.
  Replaying a leg does not re-pick images; Length and the loop readout
  count repeats. Repeat is session-only (like Crop X/Y/Zoom): saving a
  preset keeps the recipe, not the temporary playlist.
- **⚠ Rebuild (VIDEO):** if you change the image, preset or chain after
  the preview was generated, the VIDEO bar shows a ⚠ badge. Click
  Rebuild to refresh it. Exports always re-render fresh, so a stale
  preview can never produce a stale MP4.
- **Encoder:** MP4 always uses software H.264 (`libx264`, bundled).
  No hardware options, no probing: one encoder that works everywhere.

## Clip import (v2.0)

- **Input:** File → Open clip (MP4/GIF/WebP, ≤120 frames, 720p proxy,
  session-only — never saved into presets, batch stays stills-only).
  Without the video backend the dialog explains the install instead
  of failing.
- **Timeline (MOTION → Clip):** info line (file, fps, trim, `=` length),
  Trim spins pick the inclusive `[start, end]` range, the slider
  scrubs the source proxy (visual only, no audio in-app).
- **Dithered preview:** tick "Dithered preview" to scrub frames through
  the live preset recipe (seed = base + frame index, so grain/dust
  flicker per frame — that is the look; untick for the clean proxy).
  Changing the preset re-renders the current frame (cached per recipe).
- **Export (FPS spin = trim length):** GIF (silent, `{base}_clip.gif`),
  ZIP (PNG sequence `{base}_frames.zip`), MP4 (`{base}_clip.mp4`,
  software H.264 like still MP4s). Pick a Track for music
  (`-c:v copy -c:a aac -shortest`, video never re-encoded); empty
  track = silent MP4. No audio trimming/fades/playback in-app.

## Exporting
- **File name:** base for all files (weird characters → `_`).
- **Folder:** destination; Settings default.
- **Format/Quality/Size:** the document CANVAS dictates size.
- **Include:** nothing is pre-ticked — pick what you need (main image,
  1080p thumb, vector SVG, GIF/WebP/MP4, separations, SP-404 BMP, JSON).
  The dialog remembers your picks for next time (Quick export repeats them).
  MP4 has its own size (Canvas/1080p/720p, default 1080p); the dialog
  shows a weight estimate and warns on heavy files. The animation
  always follows the live VIDEO section. The VIDEO proxy (Draft 720p /
  HD 1080p / Full doc) never changes the export; particle density scales
  with the canvas, so Full/doc looks as dense as the smaller previews.
- **Collision:** nothing is ever lost — if the name exists it suggests
  `name_2`, `name_3`… (or Overwrite if you choose).
- **SP-404MKII BMP:** tick "SP-404MKII BMP (128×64 1-bit)" to also write
  `{base}_sp404.bmp`: the current still as a 1-bit OLED file. Rename it
  to `startup_N` / `screen_saver_N` yourself and copy to
  `EXPORT/PROJECT/PROJECT_XX/PICTURE`
  (UTILITY > SYSTEM > Scrn Saver Type = Custom), reimport, power cycle.
- **SP-404 live framing:** "SP-404 128×64" button in IMAGE sets a Custom
  128×64 canvas (document only); the "SP-404 OLED Preview: ON/OFF" toggle in
  IMAGE (same as View menu) shows the 1-bit result the device will show
  (DITHER threshold tunes the cut live).
- **Quick export** repeats the last setup without asking. If you switch
  images, it asks again (never reuses the previous name).
- **Distro 3000 (delivering to stores):** distributors (DistroKid,
  TuneCore, Spotify) want a **3000×3000 square JPG in RGB**. The
  `DISTRO_3000` preset sets exactly that (1:1, 3000px, JPG q90); the
  export dialog shows a "Distro 3000" readiness line with honest hints
  (not square / under 3000px / upscaled from a small source / low
  quality) — hints only, nothing is blocked.
- **Print TIFF:** tick "Print TIFF (LZW)" to also write `{base}.tif`:
  full-document lossless RGB with resolution tags, for stores that take
  TIFF and for the print shop.
- **Social pack:** tick "Social pack (YT + 9:16 + 1:1)" to also write
  `{base}_social_yt` (1280×720), `{base}_social_916` (1080×1920) and
  `{base}_social_11` (1080×1080) from the same render, same format.
  All center-anchored: profile grids crop 9:16 to the centered 1:1,
  so keep the subject in the middle band.
- **Apple Motion (animated wallpaper):** presets `APPLE_MOTION` (1:1,
  4000px) and `APPLE_MOTION_TALL` (3:4, 2250×3000) render a dissolve
  loop (64 frames @24fps) whose first frame is the still — the loop
  is seamless by construction. New `3:4` canvas ratio for the tall one.
- **DPI:** resolution tags (72–600, default 300) written on JPG/PNG/TIFF,
  separations and the metadata JSON. Tags only — pixels never change.
  Distributors ignore DPI; RISO/screen print does not. The CMYK dot
  size (LPI) is computed from this DPI at export.
- **RISO trap:** tick "RISO trap (1px ink expand)" with separations to
  grow every ink area by 1px — small misregistrations overprint
  instead of showing white hairlines.
- **CMYK print method:** `rosette` picks the screen assignment
  (standard / alt / single) and `LPI` the ruling in lines/inch at the
  export DPI (0 = off, legacy 8px cell). Both are recipe fields: they
  travel with the preset and the metadata.

## Batch (folders)

File → Batch folder (Ctrl+B): pick input/output, Jobs 1-8
(1 = safe sequential, more = multiprocessing), format and outputs per
operation. With `Drop=Batch` on, dropping a folder asks directly
whether to process it.
Tick "Bundle as ZIP" to also write `<output>_bundle.zip` with every
file of the run next to the folder (stdlib zip, offline).

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
  shares `.json` offline. **Packs:** File → Export/Import pack shares
  the whole library (all presets + the palette library) as one `.zip`
  — sell or share a look pack. Import never overwrites: existing names
  are skipped and reported.
- **File → Settings (Ctrl+,):** default output folder, format/
  quality/size and default outputs, jobs, Drop=Batch, startup
  viewport, recent recipes and data folder.
- **Backup:** in Settings, Export…/Import… save or restore the whole
  config `.json`.
- **Session:** by default it reopens your last image and preset on launch
  (disable in Settings).

## Color confidence (daltonism + contrast + Lospec)

- **Daltonism preview:** View → Daltonism preview → Off/Protan/Deutan/
  Tritan. Display-only simulation (like the safe-area guides and the
  SP-404 OLED preview): document pixels are never touched. Check your
  cover the way red-, green- and blue-blind listeners see it before
  you ship.
- **Contrast hints:** the COLOR swatch strip reports WCAG contrast
  between neighboring inks (✓ ok, ⚠ low <3:1, BW-collapse when two
  inks print as one gray). Low-contrast ramps (SLIME included) are an
  aesthetic — the hint is honest information, not a block.
- **Lospec offline import:** COLOR → Import reads local palette files
  only (no network): `.json` / `.gpl` (GIMP) / `.hex` / `.txt` (one
  `#RRGGBB` per line) / `.pal` (JASC-PAL). Over 16 colors truncate to
  the first 16 (engine cap, deterministic). 21 dither-friendly ramps
  ship in `palettes/` (dark → light), ready to load.

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
