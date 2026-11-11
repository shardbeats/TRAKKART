"""Animation budgets: frame plans and weight estimates (R2-anim, verbatim move).

Pure functions moved from app.gif (no logic change). app.gif
re-exports them so existing imports keep working.
"""

from __future__ import annotations

from app.anim.limits import (GIF_MAX_FRAMES, GIF_MIN_FRAMES, MAX_GIF_PIXELS,
                             MAX_TOTAL_FRAMES,
                             MP4_BYTES_PER_PX_HOLD, MP4_BYTES_PER_PX_TRANS)


def _clamp_frames(frames: int) -> int:
    return max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))


def leg_transitions(n_req: int, legs: int) -> list[int]:
    """Transition frames per morph leg (exact engine split).

    Same budget the engine renders: n_trans clamped like plan_dissolve
    (2-per-leg floor so every form appears assembled), split across legs
    with the same divmod (first legs take the remainder). <=2f/leg means
    joints only: hard cut, no mid-flight pour or color.
    """
    legs_v = max(1, int(legs or 1))
    n_trans = min(GIF_MAX_FRAMES, max(2 * legs_v, _clamp_frames(n_req)))
    base, rem = divmod(n_trans, legs_v)
    return [base + (1 if k < rem else 0) for k in range(legs_v)]


def plan_dissolve(n_req: int, segs: int, fps: int, hold_s: float,
                  target_s: float | None = None,
                  cap: int | None = None, loop: bool = False) -> dict:
    """Frame budget where Hold mandates and Length is derived.

    Total = transitions + requested holds, nothing else: there is no pad
    to a sacred total (Hold-manda). Every Hold tick adds still frames, so
    the slider is never dead. `target_s` is accepted for backward
    compat but IGNORED (old presets carrying dissolve_length render
    without padding; their stored value is just not honored anymore).
    n_trans covers transitions (min 2 per segment so every form appears
    assembled). Holds duplicate assembled forms: start + end + one per
    interior joint (v1.14: every form reads, not just the last one),
    shared equally across ALL forms (differ by at most 1 frame).
    Transitions always win over holds: when the requested holds do not
    fit `cap` they shrink to it (capped=True). The total never exceeds
    `cap` (default MAX_TOTAL_FRAMES=256 for GIF/preview; MP4 streaming
    passes MAX_MP4_FRAMES=3600 so long hold-heavy clips still stream).
    With loop=True the chain closes (last morphs back into first for a
    seamless loop): one extra leg, and A's share is split between the
    opening and closing holds so no form reads double.
    Returns dict(n_trans, hs, he, hj, holds, pad, total, capped,
    actual_s, cap, loop). `holds` is the exact per-position list
    ([start, joints..., end]; loop splits A across both ends);
    hs/he/hj mirror it (hj = first joint, representative when the
    remainder spills unevenly by 1). `pad` is always 0 (kept key).
    """
    cap_v = int(cap) if cap else MAX_TOTAL_FRAMES
    cap_v = max(GIF_MAX_FRAMES, cap_v)
    fps_v = max(1, int(fps or 8))
    segs_v = max(1, int(segs or 1))
    loop_v = bool(loop)
    legs = segs_v + (1 if loop_v else 0)
    forms = segs_v + 1  # unique images: A + chain
    joints = max(0, segs_v - 1)
    n_trans = min(GIF_MAX_FRAMES, max(2 * legs, max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(n_req)))))
    # Hold mandates: requested still frames per form, uncapped by the
    # 64-frame transition budget (that cap is what made the slider dead
    # under a sacred Length). Only the output `cap` can shrink holds,
    # transitions always win.
    per = int(round(max(0.0, min(3.0, float(hold_s or 0.0))) * fps_v))
    room = max(0, cap_v - n_trans)
    req = per * forms
    capped = req > room
    # Share still time equally across every unique form so no single
    # image hogs the clip. Remainder round-robin starts at the end
    # (legacy bias), then start, then joints in play order.
    q, r = divmod(min(req, room), max(1, forms))
    shares = [q] * forms
    order = [forms - 1, 0] + list(range(1, forms - 1))
    for i in range(r):
        shares[order[i % forms]] += 1
    if loop_v:
        # A's share lives at both loop ends (they are adjacent in loop
        # playback): split it so A reads the same total as every form.
        a_half, a_rest = divmod(max(0, int(shares[0])), 2)
        holds = [a_half] + shares[1:] + [a_half + a_rest]
    else:
        holds = list(shares)
    hs, he = holds[0], holds[-1]
    hj = holds[1] if len(holds) > 1 else 0
    total = n_trans + sum(holds)
    return {"n_trans": n_trans, "hs": hs, "he": he, "hj": hj, "holds": holds,
            "pad": 0, "total": total, "joints": joints, "cap": cap_v,
            "capped": capped, "actual_s": total / fps_v, "loop": loop_v}


def solve_hold_for_length(n_req: int, segs: int, fps: int, target_s: float,
                          loop: bool = False,
                          cap: int | None = None) -> tuple[float, dict, bool]:
    """Hold seconds so the derived total reaches target_s (Length sacred).

    Inverse of plan_dissolve with no pad anywhere: transitions come from
    n_req (density/quality), holds fill up to the target, shared equally
    across forms. Hold caps at 3.0s; transitions alone may overshoot a
    tiny target (then hold 0 and fits=False: fewer Frames needed). The
    output cap can shrink holds (capped=True): shorter clip, honest report.
    Returns (hold_s, plan, fits).
    """
    from math import ceil

    fps_v = max(1, int(fps or 8))
    want = int(round(max(0.0, float(target_s or 0.0)) * fps_v))
    base = plan_dissolve(n_req, segs, fps_v, 0.0, None, cap=cap, loop=loop)
    nt = int(base["n_trans"])
    forms = max(1, int(segs or 1) + 1)
    need = want - nt
    if need <= 0:
        return (0.0, base, nt <= want)  # transitions alone overshoot: fewer Frames needed
    per = min(int(ceil(need / forms)), 3 * fps_v)
    hold = per / fps_v
    plan = plan_dissolve(n_req, segs, fps_v, hold, None, cap=cap, loop=loop)
    return (hold, plan, int(plan["total"]) >= want)


def _check_gif_budget(n_frames: int, w: int, h: int) -> None:
    total = max(0, int(n_frames)) * max(1, int(w)) * max(1, int(h))
    if total > MAX_GIF_PIXELS:
        gb = total * 4 / 1_000_000_000
        raise MemoryError(
            f"GIF needs ~{gb:.1f}GB transient RAM for {int(n_frames)} frames "
            f"at {int(w)}x{int(h)} (budget {MAX_GIF_PIXELS // 1_000_000}MP): "
            "fewer Frames/Hold, smaller canvas, or WebP/MP4 instead")


def estimate_gif(n_trans: int, w: int, h: int, n_hold_forms: int = 0) -> int:
    """Hold-collapse-aware weight estimate (bytes).

    R8: Pillow fuses identical hold frames (measured: a 20f hold-heavy
    clip collapses ~37x under the old flat frames*w*h//2). Transitions
    cost a full frame each; every still form costs ~1 fused frame.
    The default (0 hold forms) keeps transition-only counts exact.
    """
    px = max(1, int(w)) * max(1, int(h))
    return px * max(0, int(n_trans)) // 2 + px * max(0, int(n_hold_forms)) // 2


def estimate_webp(n_trans: int, w: int, h: int, n_hold_forms: int = 0) -> int:
    """Rough weight estimate (bytes): ~1/3 of the GIF at equal quality."""
    return estimate_gif(n_trans, w, h, n_hold_forms) // 3


def _even_down(n: int) -> int:
    """Round down to an even int, floor 2 (H.264/yuv420p needs multiples of 2)."""
    return max(2, int(n) & ~1)


def mp4_dims(doc_w: int, doc_h: int, size_opt: str | int = "1080p") -> tuple[int, int]:
    """MP4 frame dims preserving aspect (long side per option).

    Always even (H.264/yuv420p requires multiples of 2; imageio would
    otherwise rescale to a multiple of 16, e.g. 1080x1920 -> 1088x1920).
    Rounds down to even so the long side never exceeds the request.
    """
    dw, dh = max(1, int(doc_w)), max(1, int(doc_h))
    if isinstance(size_opt, int) or str(size_opt).isdigit():
        long_side = max(64, int(size_opt))
    elif str(size_opt) == "720p":
        long_side = 720
    elif str(size_opt) == "Canvas":
        return (_even_down(dw), _even_down(dh))
    else:
        long_side = 1080
    r = long_side / max(dw, dh)
    if r >= 1.0:
        return (_even_down(dw), _even_down(dh))
    return (_even_down(round(dw * r)), _even_down(round(dh * r)))


def estimate_mp4(w: int, h: int, n_trans: int, n_hold: int) -> int:
    """Content-aware MP4 weight estimate (bytes).

    Transitions are dither noise (expensive); holds are duplicated stills
    (cheap). The old flat 0.12 B/px/frame overestimated hold-heavy clips
    ~8x and hid that 3000px/60fps is impagable even when honest.
    """
    px = max(1, int(w)) * max(1, int(h))
    return int(px * (max(0, int(n_trans)) * MP4_BYTES_PER_PX_TRANS
                     + max(0, int(n_hold)) * MP4_BYTES_PER_PX_HOLD))


__all__ = ["_clamp_frames", "plan_dissolve", "leg_transitions",
           "solve_hold_for_length",
           "_check_gif_budget", "estimate_gif", "estimate_webp",
           "_even_down", "mp4_dims", "estimate_mp4"]
