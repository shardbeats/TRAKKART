"""Animation facade (R2 split step 1).

New import path; app.gif remains the canonical shim so all existing
`from app.gif import ...` call sites keep working.
"""

from __future__ import annotations

from app.anim.frames import (GIF_MODE_INFO, _canvas_a, _dissolve_adjust,  # noqa: F401
                             _dissolve_paint, _dissolve_shade, _dissolve_style,
                             _dissolve_tint, _dissolve_trail, _morph_loop,
                             _split_chain_entries, gif_dissolve_frames, gif_frames,
                             gif_morph_frames, iter_dissolve_frames,
                             iter_morph_frames, mode_desc, mode_label)
from app.anim.io import _fit_small, _pingpong, save_gif, save_webp  # noqa: F401
from app.anim.limits import (GIF_FRAMES_SUGGESTED, GIF_FPS_SUGGESTED, GIF_LIMIT_SIDE,  # noqa: F401
                             GIF_MAX_FPS, GIF_MAX_FRAMES, GIF_MAX_SIDE, GIF_MIN_FPS,
                             GIF_MIN_FRAMES, GIF_MIN_SIDE, GIF_MODES,
                             MAX_GIF_PIXELS, MAX_MP4_FRAMES, MAX_TOTAL_FRAMES,
                             MP4_BYTES_PER_PX_HOLD, MP4_BYTES_PER_PX_TRANS, MP4_SIZES,
                             VIDEO_DEFAULT_SIZE, VIDEO_MAX_SIZE, VIDEO_MIN_SIZE)
from app.anim.plan import (_check_gif_budget, _clamp_frames, estimate_gif,  # noqa: F401
                           estimate_mp4, estimate_webp, _even_down, mp4_dims,
                           plan_dissolve, solve_hold_for_length)

__all__ = ["GIF_MODES", "GIF_MODE_INFO", "mode_label", "mode_desc",
           "GIF_MAX_SIDE", "GIF_MIN_SIDE", "GIF_LIMIT_SIDE",
           "GIF_MIN_FPS", "GIF_MAX_FPS", "GIF_MIN_FRAMES", "GIF_MAX_FRAMES",
           "GIF_FPS_SUGGESTED", "GIF_FRAMES_SUGGESTED",
           "VIDEO_DEFAULT_SIZE", "VIDEO_MIN_SIZE", "VIDEO_MAX_SIZE",
           "_fit_small", "_clamp_frames",
           "_dissolve_style", "_dissolve_tint", "_dissolve_trail",
           "_dissolve_shade", "_dissolve_paint", "_dissolve_adjust",
           "_pingpong", "gif_frames",
           "MAX_TOTAL_FRAMES", "MAX_MP4_FRAMES",
           "plan_dissolve", "solve_hold_for_length",
           "_canvas_a", "_split_chain_entries",
           "iter_dissolve_frames", "_morph_loop", "iter_morph_frames",
           "gif_dissolve_frames", "gif_morph_frames",
           "MAX_GIF_PIXELS", "_check_gif_budget", "save_gif",
           "estimate_gif", "save_webp", "estimate_webp",
           "MP4_BYTES_PER_PX_TRANS", "MP4_BYTES_PER_PX_HOLD", "MP4_SIZES",
           "_even_down", "mp4_dims", "estimate_mp4"]
