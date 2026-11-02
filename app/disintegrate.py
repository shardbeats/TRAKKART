"""TRAKKART particle disperse + morph (dither-boy style, MIT). Numpy + Pillow only.

Single-image loop (dissolve_frames: assembled -> dispersed -> assembled)
plus one-shot swap (morph_frames: A -> B through one shared particle cloud).

Loop-perfect dissolve: the turbulence pattern is fixed per clip (seeded
once) and only its amplitude breathes with sin(pi*frac), so progress 0 == 1.
Deterministic: same inputs + frame = same pixels (default_rng(seed)).
Strict 0=off: amount 0 returns the still (identity; hard cut for morph).
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

DISINTEGRATE_MODES = ("wind", "random")

#: Hard cap on rasterized points per frame (perf: vectorized scatter).
MAX_POINTS = 120_000


def dither_bw(img: Image.Image, method: str = "bayer8",
              threshold: float = 128.0, pixel_size: int = 1) -> Image.Image:
    """BW dither of the input (Bayer or Floyd-Steinberg family).

    Uses the main engine (app.dither.apply_method, palette=None) so the
    look matches the still pipeline. Limited grayscale is out of scope
    for Fase 1 (BW only).
    """
    from app.dither import apply_method

    return apply_method(img.convert("RGB"), method=method, palette=None,
                        threshold=float(threshold), pixel_size=max(1, int(pixel_size)))


def points_from_dither(dithered: Image.Image) -> tuple[np.ndarray, int, int]:
    """Active (black) coords of a BW dithered image.

    Returns (coords (N,2) as (y,x) int32, H, W). Deterministic stride
    subsample when N exceeds MAX_POINTS (keeps spatial distribution).
    """
    arr = np.asarray(dithered.convert("L"), dtype=np.uint8)
    h, w = arr.shape[:2]
    ys, xs = np.nonzero(arr < 128)
    coords = np.stack([ys.astype(np.int32), xs.astype(np.int32)], axis=1)
    if len(coords) > MAX_POINTS:
        step = int(math.ceil(len(coords) / MAX_POINTS))
        coords = coords[::step].copy()
    return coords, int(h), int(w)


def _fit_cover(im: Image.Image, w: int, h: int, fx: float = 50.0,
               fy: float = 50.0, zoom: float = 1.0) -> Image.Image:
    """Cover-fit to exact WxH (IMAGE-section semantics, no distortion).

    Same crop_cover the pipeline uses (focus 0-100 + zoom >= 1).
    """
    from app.canvas import CUSTOM_RATIO, crop_cover

    box = crop_cover(im.convert("RGB"), CUSTOM_RATIO, float(fx), float(fy),
                     max(1.0, float(zoom)), canvas_w=int(w), canvas_h=int(h))
    if box.size != (int(w), int(h)):
        box = box.resize((max(1, int(w)), max(1, int(h))), Image.BICUBIC)
    return box


def _refit_coords(coords: np.ndarray, hh: int, ww: int, h: int, w: int) -> np.ndarray:
    """Clip out-of-range points (defensive: same dither op => same shape)."""
    if len(coords) == 0:
        return coords
    out = coords.copy()
    out[:, 0] = np.clip(out[:, 0], 0, h - 1)
    out[:, 1] = np.clip(out[:, 1], 0, w - 1)
    return out


def disperse_positions(coords: np.ndarray, h: int, w: int, progress: float = 0.0,
                       seed: int = 0xD15C, wind: tuple[float, float] = (120.0, -40.0),
                       mode: str = "wind", loops: float = 1.0,
                       amount: float = 1.0) -> np.ndarray:
    """Loop-perfect positions for one frame.

    progress in [0, 1), loops traversals per clip. Envelope
    e = sin(pi*frac) with frac = (progress*loops) % 1: 0 at the loop
    joint (assembled), 1 mid-clip (fully dispersed). Turbulence is fixed
    per clip (seeded once); wind adds a directional offset. amount 0
    freezes everything (identity).
    """
    if mode not in DISINTEGRATE_MODES:
        mode = "wind"
    amt = max(0.0, min(2.0, float(amount or 0.0)))
    if amt <= 0 or len(coords) == 0:
        return np.asarray(coords, dtype=np.float32).copy()
    loops = max(0.25, min(4.0, float(loops or 1.0)))
    frac = (float(progress) * float(loops)) % 1.0
    env = math.sin(math.pi * frac)
    n = int(len(coords))
    rng = np.random.default_rng(int(seed))
    if mode == "random":
        spread = 90.0 * amt
        turb = rng.uniform(-spread, spread, (n, 2)).astype(np.float32)
        # (y,x) order: wind tuple is (wx, wy) -> (dy, dx).
        off = turb * env
    else:
        wx, wy = float(wind[0]), float(wind[1])
        spread = 28.0 * amt
        turb = rng.uniform(-spread, spread, (n, 2)).astype(np.float32)
        base = np.array([[wy * amt, wx * amt]], dtype=np.float32)
        off = (base + turb) * env
    out = coords.astype(np.float32) + off
    out[:, 0] = np.clip(out[:, 0], 0, h - 1)
    out[:, 1] = np.clip(out[:, 1], 0, w - 1)
    return out


def render_points(positions: np.ndarray, h: int, w: int) -> Image.Image:
    """Rasterize float (y,x) points to a BW RGB image (white bg, black dots)."""
    canvas = np.full((h, w), 255, dtype=np.uint8)
    if len(positions):
        ys = np.clip(positions[:, 0].astype(np.int32), 0, h - 1)
        xs = np.clip(positions[:, 1].astype(np.int32), 0, w - 1)
        canvas[ys, xs] = 0
    return Image.fromarray(canvas, mode="L").convert("RGB")


def iter_dissolve(img: Image.Image, method: str = "bayer8",
                  threshold: float = 128.0, pixel_size: int = 1,
                  frames: int = 8, seed: int = 0xD15C,
                  wind: tuple[float, float] = (120.0, -40.0),
                  mode: str = "wind", loops: float = 1.0,
                  amount: float = 1.0,
                  max_side: int = 480,
                  hold_start: int = 0, hold_end: int = 0):
    """Yield dissolve frames one by one (streaming: O(1) RAM).

    Same pixels as dissolve_frames(), no list kept alive. Lets MP4 stream
    long clips (up to 3600f) without the 256-frame list cap blowing RAM.
    """
    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES

    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    small = img.convert("RGB")
    r = side / max(small.width, small.height)
    if r < 1.0:
        small = small.resize((max(1, round(small.width * r)),
                              max(1, round(small.height * r))), Image.BICUBIC)
    dithered = dither_bw(small, method=method, threshold=threshold,
                         pixel_size=pixel_size)
    still = dithered.convert("RGB")
    coords, h, w = points_from_dither(dithered)
    for _ in range(max(0, int(hold_start))):
        yield still.copy()
    for i in range(n):
        progress = float(i) / float(n)
        pos = disperse_positions(coords, h, w, progress=progress, seed=seed,
                                 wind=wind, mode=mode, loops=loops, amount=amount)
        yield render_points(pos, h, w)
    for _ in range(max(0, int(hold_end))):
        yield still.copy()


def dissolve_frames(img: Image.Image, method: str = "bayer8",
                    threshold: float = 128.0, pixel_size: int = 1,
                    frames: int = 8, seed: int = 0xD15C,
                    wind: tuple[float, float] = (120.0, -40.0),
                    mode: str = "wind", loops: float = 1.0,
                    amount: float = 1.0,
                    max_side: int = 480,
                    hold_start: int = 0, hold_end: int = 0) -> list[Image.Image]:
    """Full disperse loop for one image (assembled -> dispersed -> assembled).

    Dithers once at max_side, then marches progress=i/n. amount 0 returns
    n copies of the dithered still (identity, strict 0=off). hold_start /
    hold_end prepend / append assembled copies so the form reads before
    it bursts (loop joint stays assembled -> seamless).
    """
    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES

    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    small = img.convert("RGB")
    r = side / max(small.width, small.height)
    if r < 1.0:
        small = small.resize((max(1, round(small.width * r)),
                              max(1, round(small.height * r))), Image.BICUBIC)
    return list(iter_dissolve(img, method=method, threshold=threshold,
                              pixel_size=pixel_size, frames=n, seed=seed,
                              wind=wind, mode=mode, loops=loops, amount=amount,
                              max_side=side, hold_start=hold_start,
                              hold_end=hold_end))


def morph_frames(img_a: Image.Image, img_b: Image.Image, method: str = "bayer8",
                 threshold: float = 128.0, pixel_size: int = 1,
                 frames: int = 8, seed: int = 0xD15C,
                 wind: tuple[float, float] = (120.0, -40.0),
                 mode: str = "wind", amount: float = 1.0,
                 max_side: int = 480,
                 hold_start: int = 0, hold_end: int = 0,
                 hold_joint: int = 0,
                 crops: list[dict] | None = None) -> list[Image.Image]:
    """One-shot swap A -> B through a shared particle cloud (Fase 5).

    Both images are fitted to the same HxW (B resized to A), dithered
    with the same engine, then: progress<0.5 renders dispersed A,
    progress>=0.5 renders dispersed B, envelope sin(pi*progress) so both
    ends are assembled and the middle is a full cloud. amount 0 returns
    A copies then B copies (hard cut, strict 0=off).
    """
    chained = morph_chain_frames([img_a, img_b], method=method, threshold=threshold,
                                 pixel_size=pixel_size, frames=frames, seed=seed,
                                 wind=wind, mode=mode, amount=amount, max_side=max_side,
                                 hold_start=hold_start, hold_end=hold_end,
                                 hold_joint=hold_joint, crops=crops)
    return chained


#: Hard cap on chain length (A + up to 5 more).
MAX_MORPH_IMAGES = 6


def iter_morph_chain(imgs: list[Image.Image], method: str = "bayer8",
                     threshold: float = 128.0, pixel_size: int = 1,
                     frames: int = 8, seed: int = 0xD15C,
                     wind: tuple[float, float] = (120.0, -40.0),
                     mode: str = "wind", amount: float = 1.0,
                     max_side: int = 480,
                     hold_start: int = 0, hold_end: int = 0,
                     hold_joint: int | list | tuple = 0,
                     crops: list[dict] | None = None,
                     loop: bool = False):
    """Yield chain frames one by one (streaming: O(1) RAM).

    Same pixels as morph_chain_frames(), no list kept alive.
    With loop=True the last form morphs back into the first (closed
    loop, no hard cut): the closing leg reuses the first form's exact
    dithered still/coords, so the loop joint is byte-identical.
    """
    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES

    if len(imgs) < 2:
        raise ValueError("chain needs at least 2 images")
    imgs = list(imgs[:MAX_MORPH_IMAGES])
    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    a = imgs[0].convert("RGB")
    r = side / max(a.width, a.height)
    if r < 1.0:
        a = a.resize((max(1, round(a.width * r)),
                      max(1, round(a.height * r))), Image.BICUBIC)
    fitted = [a]
    for k, im in enumerate(imgs[1:]):
        crop = (crops[k + 1] if crops and k + 1 < len(crops) else None) or {}
        try:
            fx = float(crop.get("fx", 50.0))
            fy = float(crop.get("fy", 50.0))
            zm = max(1.0, float(crop.get("zoom", 1.0)))
        except (TypeError, ValueError):
            fx, fy, zm = 50.0, 50.0, 1.0
        fitted.append(_fit_cover(im, a.width, a.height, fx, fy, zm))
    coord_list: list[np.ndarray] = []
    h = w = 0
    for im in fitted:
        d = dither_bw(im, method=method, threshold=threshold, pixel_size=pixel_size)
        coords, hh, ww = points_from_dither(d)
        if not coord_list:
            h, w = hh, ww  # dithered size rules (pixel_size floors odd sides)
        coord_list.append(coords if (hh, ww) == (h, w) else _refit_coords(coords, hh, ww, h, w))
    segs = len(fitted) - 1
    loop_v = bool(loop) and len(fitted) >= 2
    legs = segs + (1 if loop_v else 0)
    base, rem = divmod(n, legs)
    dithered_all = [dither_bw(im, method=method, threshold=threshold,
                              pixel_size=pixel_size).convert("RGB")
                    for im in fitted]
    for _ in range(max(0, int(hold_start))):
        yield dithered_all[0].copy()
    if isinstance(hold_joint, (list, tuple)):
        hj_list = [max(0, int(v)) for v in list(hold_joint)]
    else:
        hj_list = [max(0, int(hold_joint))] * max(0, legs - 1)
    for k in range(legs):
        nk = base + (1 if k < rem else 0)
        if nk <= 0:
            if k < legs - 1:
                hj_k = hj_list[k] if k < len(hj_list) else (hj_list[-1] if hj_list else 0)
                for _ in range(hj_k):
                    yield dithered_all[(k + 1) % len(dithered_all)].copy()
            continue
        closing = loop_v and k == legs - 1
        ca = coord_list[k] if not closing else coord_list[-1]
        cb = coord_list[k + 1] if not closing else coord_list[0]
        for j in range(nk):
            q = float(j) / float(max(1, nk - 1))
            if q < 0.5:
                pos = disperse_positions(ca, h, w, progress=q, seed=int(seed) + k,
                                         wind=wind, mode=mode, loops=1.0, amount=amount)
            else:
                pos = disperse_positions(cb, h, w, progress=q, seed=int(seed) + k + 1,
                                         wind=wind, mode=mode, loops=1.0, amount=amount)
            yield render_points(pos, h, w)
        if k < legs - 1:
            hj_k = hj_list[k] if k < len(hj_list) else (hj_list[-1] if hj_list else 0)
            for _ in range(hj_k):
                yield dithered_all[(k + 1) % len(dithered_all)].copy()
    for _ in range(max(0, int(hold_end))):
        yield dithered_all[0 if loop_v else -1].copy()


def morph_chain_frames(imgs: list[Image.Image], method: str = "bayer8",
                       threshold: float = 128.0, pixel_size: int = 1,
                       frames: int = 8, seed: int = 0xD15C,
                       wind: tuple[float, float] = (120.0, -40.0),
                       mode: str = "wind", amount: float = 1.0,
                       max_side: int = 480,
                       hold_start: int = 0, hold_end: int = 0,
                       hold_joint: int | list | tuple = 0,
                       crops: list[dict] | None = None,
                       loop: bool = False) -> list[Image.Image]:
    """Chain swap A -> B -> C ... through particle clouds (v1.8 Fase 1).

    All images fitted to the same HxW (rest cover-fit to A), dithered with
    the same engine. Frames split per segment; each segment marches q over
    [0, 1] inclusive (assembled -> cloud -> assembled) so joints meet
    assembled with no pop. hold_start / hold_end freeze the first / last
    form; hold_joint freezes every interior form so each one reads
    (int = same for all joints, list/tuple = per-joint exact share).
    amount 0 gives hard cuts (strict 0=off). Deterministic per segment
    seed (seed + k). With loop=True the last form morphs back into the
    first (closed loop, no hard cut).
    """
    return list(iter_morph_chain(imgs, method=method, threshold=threshold,
                                 pixel_size=pixel_size, frames=frames, seed=seed,
                                 wind=wind, mode=mode, amount=amount,
                                 max_side=max_side, hold_start=hold_start,
                                 hold_end=hold_end, hold_joint=hold_joint,
                                 crops=crops, loop=loop))


__all__ = ["DISINTEGRATE_MODES", "MAX_POINTS", "MAX_MORPH_IMAGES", "dither_bw",
           "points_from_dither", "disperse_positions", "render_points",
           "dissolve_frames", "morph_frames", "morph_chain_frames",
           "iter_dissolve", "iter_morph_chain"]
