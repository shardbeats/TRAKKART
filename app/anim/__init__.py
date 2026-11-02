"""Animation facade (R2 split step 1).

New import path; app.gif remains the canonical shim so all existing
`from app.gif import ...` call sites keep working.
"""

from __future__ import annotations

from app.anim.limits import (GIF_FRAMES_SUGGESTED, GIF_FPS_SUGGESTED, GIF_LIMIT_SIDE,
                             GIF_MAX_FPS, GIF_MAX_FRAMES, GIF_MAX_SIDE, GIF_MIN_FPS,
                             GIF_MIN_FRAMES, GIF_MIN_SIDE, GIF_MODES,
                             MAX_GIF_PIXELS, MAX_MP4_FRAMES, MAX_TOTAL_FRAMES,
                             MP4_BYTES_PER_PX_HOLD, MP4_BYTES_PER_PX_TRANS, MP4_SIZES,
                             VIDEO_DEFAULT_SIZE, VIDEO_MAX_SIZE, VIDEO_MIN_SIZE)

__all__ = ["GIF_MODES", "GIF_MAX_SIDE", "GIF_MIN_SIDE", "GIF_LIMIT_SIDE",
           "GIF_MIN_FPS", "GIF_MAX_FPS", "GIF_MIN_FRAMES", "GIF_MAX_FRAMES",
           "GIF_FPS_SUGGESTED", "GIF_FRAMES_SUGGESTED",
           "VIDEO_DEFAULT_SIZE", "VIDEO_MIN_SIZE", "VIDEO_MAX_SIZE",
           "MAX_TOTAL_FRAMES", "MAX_MP4_FRAMES", "MAX_GIF_PIXELS",
           "MP4_BYTES_PER_PX_TRANS", "MP4_BYTES_PER_PX_HOLD", "MP4_SIZES"]
