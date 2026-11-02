"""Animation budget constants (R2 split step 1: zero-dependency leaf).

Single home for GIF/MP4 caps. app.gif imports from here; external
callers keep importing from app.gif (shim).
"""

from __future__ import annotations

GIF_MODES = ("phase", "hue", "both", "glitch", "mix", "dissolve", "morph")

GIF_MAX_SIDE = 480
GIF_MIN_SIDE = 240
GIF_LIMIT_SIDE = 8000  # canvas rules: the anim ships at document size
GIF_MIN_FPS = 2
GIF_MAX_FPS = 60
GIF_MIN_FRAMES = 2
GIF_MAX_FRAMES = 64
# Suggested (editable combos: the list guides, the value is free).
GIF_FPS_SUGGESTED = (8, 12, 24, 30, 48, 60)
GIF_FRAMES_SUGGESTED = (4, 6, 8, 12, 24, 32, 48, 64, 96, 128, 256)
# Full-canvas video preview (customizable, default 1200).
VIDEO_DEFAULT_SIZE = 1200
VIDEO_MIN_SIZE = 480
VIDEO_MAX_SIZE = 1920

#: Hard cap on total built frames (transitions + holds + pads).
#: GIF/preview stay here (RAM + format + browsers choke past ~25MB).
MAX_TOTAL_FRAMES = 256
#: MP4 streams frame by frame (O(1) RAM), so long hold-heavy clips
#: still export: 60s * 60fps = 3600 frames max.
MAX_MP4_FRAMES = 3600

#: RAM budget for a GIF frame list (pixels): beyond this save_gif would
#: transiently hold ~4 bytes/px (caller list + paletted copy) and OOM a
#: typical machine. Checked with planned totals (builders, approx) and
#: exact dims (save_gif): fewer Frames/Hold, smaller canvas, or WebP/MP4.
MAX_GIF_PIXELS = 1_200_000_000

#: Calibrated H.264 cost at quality=8 (measured 256px bayer8, x264/yuv420p):
#: dithered transition frames are near-incompressible noise (~0.43 B/px),
#: duplicated assembled holds collapse to near-zero (~0.011 B/px, ~40x).
MP4_BYTES_PER_PX_TRANS = 0.43
MP4_BYTES_PER_PX_HOLD = 0.011

#: MP4 long-side choices (main image always stays at canvas size).
MP4_SIZES = ("Canvas", "1080p", "720p")

__all__ = ["GIF_MODES", "GIF_MAX_SIDE", "GIF_MIN_SIDE", "GIF_LIMIT_SIDE",
           "GIF_MIN_FPS", "GIF_MAX_FPS", "GIF_MIN_FRAMES", "GIF_MAX_FRAMES",
           "GIF_FPS_SUGGESTED", "GIF_FRAMES_SUGGESTED",
           "VIDEO_DEFAULT_SIZE", "VIDEO_MIN_SIZE", "VIDEO_MAX_SIZE",
           "MAX_TOTAL_FRAMES", "MAX_MP4_FRAMES", "MAX_GIF_PIXELS",
           "MP4_BYTES_PER_PX_TRANS", "MP4_BYTES_PER_PX_HOLD", "MP4_SIZES"]
