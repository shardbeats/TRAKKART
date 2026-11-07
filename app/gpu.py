"""GPU preview backend (moderngl, offscreen). CPU fallback everywhere.

Split of duties (deliberate, see docs/srs-gpu-preview.md):
- CPU (exact suite code, cheap point ops): canvas -> drift -> pre ->
  grade (adjust/duotone/posterize) -> palette resolve -> brand -> FX stack.
- GPU (the slow stage): ordered/cmyk/edges dither with nearest-palette
  search, bit-exact vs the CPU engine (see tests/test_gpu_parity.py).

supports() gates on the dither method only; everything else runs on CPU
either way, so presets with FX still get GPU dither. Any GL failure
raises inside render_proxy_kwargs and the caller falls back to the CPU
proxy — the preview never crashes.

GL contexts are thread-local (the preview worker renders off-thread).
"""

from __future__ import annotations

import threading

import numpy as np
from PIL import Image

from app.gpu_shaders import DITHER_330, VERT_330

# method -> (map id, bayer cells or None).
# baked = float/RNG threshold masks uploaded exactly (no float32-vs-64 risk).
_BAKED = {"ign", "cross", "bluenoise", "motif", "scan_bayer", "wave_map",
          "white_noise", "blocks"}
_GPU_MAPS: dict[str, tuple[int, float | None]] = {
    "bayer2": (0, 4.0), "bayer4": (0, 16.0), "bayer8": (0, 64.0),
    "bayer16": (0, 256.0), "bayer32": (0, 1024.0),
    "lines": (1, None), "columns": (3, None), "diag": (4, None),
    "pattern": (4, None), "checker": (5, None),
    "ign": (2, None), "cross": (6, None), "bluenoise": (7, None),
    "motif": (8, None), "scan_bayer": (9, None), "wave_map": (10, None),
    "cmyk": (11, None), "edges": (12, None),
    "halftone": (13, None), "cluster": (14, None), "grid": (15, None),
    "white_noise": (16, None), "blocks": (17, None),
}

_LOCAL = threading.local()
_LUT_CACHE: dict[tuple, np.ndarray] = {}


def _dummy_tex(unit_size: tuple[int, int], components: int):
    """Cached placeholder so no sampler is ever unbound (per GL context)."""
    import moderngl

    dummies = getattr(_LOCAL, "dummies", None)
    if dummies is None:
        _LOCAL.dummies = dummies = {}
    key = (unit_size, components)
    hit = dummies.get(key)
    if hit is None:
        w, h = unit_size
        hit = _LOCAL.ctx.texture((w, h), components,
                                 b"\x00" * w * h * components * 4, dtype="f4")
        hit.filter = (moderngl.NEAREST, moderngl.NEAREST)
        dummies[key] = hit
    return hit


def _dummy_lut():
    return _dummy_tex((1, 1), 1)


def _dummy_palette():
    return _dummy_tex((16, 1), 3)


def _get(p, key: str, default=None):
    if isinstance(p, dict):
        return p.get(key, default)
    return getattr(p, key, default)


def available() -> bool:
    """True when moderngl imports and a standalone context works."""
    if getattr(_LOCAL, "dead", False):
        return False
    if getattr(_LOCAL, "ctx", None) is not None:
        return True
    try:
        import moderngl

        _LOCAL.ctx = moderngl.create_standalone_context()
        _LOCAL.progs = {}
        return True
    except Exception:  # noqa: BLE001
        _LOCAL.dead = True
        return False


def supports(p) -> bool:
    """GPU dither covers ordered/cmyk/edges; ED/hilbert/ascii stay on CPU."""
    return str(_get(p, "method", "") or "").lower() in _GPU_MAPS


def _prog(name: str, frag: str):
    progs = getattr(_LOCAL, "progs", None)
    if progs is None:
        _LOCAL.progs = progs = {}
    if name not in progs:
        ctx = _LOCAL.ctx
        verts = np.array([-1.0, -1.0, 3.0, -1.0, -1.0, 3.0], dtype="f4")
        vbo = ctx.buffer(verts.tobytes())
        prog = ctx.program(vertex_shader=VERT_330, fragment_shader=frag)
        vao = ctx.vertex_array(prog, [(vbo, "2f", "in_vert")])
        progs[name] = (prog, vao, vbo)
    return progs[name]


def _upload_tex(w: int, h: int, data: bytes, components: int = 3, dtype: str = "f1"):
    """PIL bytes upload. dtype stays normalized (f1/f4): integer formats (u1)
    sampled with a float sampler read black, so never use them here."""
    tex = _LOCAL.ctx.texture((w, h), components, dtype=dtype)
    tex.filter = _upload_filter()
    tex.write(data)
    return tex


def _upload_filter():
    import moderngl

    return (moderngl.NEAREST, moderngl.NEAREST)


def _lut_mask(map_name: str, w: int, h: int, motif) -> np.ndarray:
    """Exact baked 0..255 float mask for float/RNG threshold maps."""
    import json

    from app.motif import normalize_config
    from app.ordered_maps import threshold_bias

    mkey = json.dumps(normalize_config(motif), sort_keys=True) if motif else ""
    key = (map_name, w, h, mkey)
    hit = _LUT_CACHE.get(key)
    if hit is not None:
        return hit
    spread = float(np.clip(255.0 - abs(128.0 - 127.5) * 2.0, 32.0, 255.0))
    bias = threshold_bias(map_name, h, w, 128.0, 0, motif=motif)
    mask = ((bias / spread + 0.5) * 255.0).astype("f4")
    if len(_LUT_CACHE) >= 8:
        _LUT_CACHE.pop(next(iter(_LUT_CACHE)))
    _LUT_CACHE[key] = mask
    return mask


def _dither_pass(graded: Image.Image, k: dict, palette) -> Image.Image:
    """One GPU dither pass over an already graded canvas. Raises on GL errors."""
    import moderngl

    method = str(k.get("method", "bayer4") or "bayer4").lower()
    if method not in _GPU_MAPS:
        raise RuntimeError(f"unsupported dither method for GPU: {method!r}")
    map_id, cells = _GPU_MAPS[method]
    w, h = graded.size
    prog, vao, _vbo = _prog("dither", DITHER_330)
    # Uploaded PIL bytes are top-first: sample them unflipped.
    src = _upload_tex(w, h, graded.convert("RGB").tobytes())
    fbo = _LOCAL.ctx.simple_framebuffer((w, h))
    fbo.use()
    src.use(0)
    prog["u_image"].value = 0
    prog["u_h"].value = float(h)
    prog["u_w"].value = float(w)
    prog["u_flip"].value = 0.0
    prog["u_map"].value = map_id
    prog["u_cells"].value = float(cells or 0.0)
    prog["u_threshold"].value = float(k.get("threshold", 128.0))
    prog["u_phase"].value = float(int(k.get("phase", 0) or 0))
    # Every sampler stays explicitly bound: unbound samplers sharing unit 0
    # made the driver read black for u_image on some paths.
    if method in _BAKED:
        mask = _lut_mask(method, w, h, k.get("motif"))
        lut = _LOCAL.ctx.texture((w, h), 1, mask.tobytes(), dtype="f4")
        lut.filter = (moderngl.NEAREST, moderngl.NEAREST)
        lut.use(1)
        prog["u_baked"].value = 1.0
        prog["u_lutW"].value = float(w)
        prog["u_lutH"].value = float(h)
    else:
        _dummy_lut().use(1)
        prog["u_baked"].value = 0.0
        prog["u_lutW"].value = 1.0
        prog["u_lutH"].value = 1.0
    prog["u_lut"].value = 1
    if palette is None:
        prog["u_bw"].value = 1.0
        prog["u_paletteSize"].value = 2.0
        _dummy_palette().use(2)
    else:
        import struct

        cols = [(r / 255.0, g / 255.0, b / 255.0) for r, g, b in list(palette)[:16]]
        prog["u_bw"].value = 0.0
        prog["u_paletteSize"].value = float(len(cols))
        raw = b"".join(struct.pack("fff", r, g, b) for r, g, b in cols)
        raw += b"\x00" * (16 - len(cols)) * 12
        pal = _LOCAL.ctx.texture((16, 1), 3, raw, dtype="f4")
        pal.filter = (moderngl.NEAREST, moderngl.NEAREST)
        pal.use(2)
    prog["u_palette"].value = 2
    vao.render(mode=moderngl.TRIANGLES)
    back = fbo.read(components=3)
    return Image.frombytes("RGB", (w, h), back).transpose(Image.FLIP_TOP_BOTTOM)


def _render_spec_tail(spec, img: Image.Image) -> Image.Image:
    """Brand + ordered FX stack over a dithered image (CPU, suite code)."""
    from app.fx import replace_white
    from app.fx_dispatch import apply_fx as _apply_fx
    from app.fx_stack import normalize_stack

    out = img
    if getattr(spec, "replace_color", ""):
        out = replace_white(out, color=spec.replace_color)
    for entry in normalize_stack(getattr(spec, "fx_stack", None)):
        if entry.get("enabled", True):
            out = _apply_fx(spec, out, entry["id"])
    return out


def render_proxy_kwargs(img: Image.Image, kwargs: dict) -> Image.Image:
    """Full proxy chain: CPU grade, GPU dither, CPU brand/stack.

    Mirrors pipeline.render_spec stage order exactly (canvas -> drift ->
    pre -> grade -> dither(pixel-aware) -> brand -> stack); only the
    dither engine runs on the GPU. Raises on any GL failure.
    """
    return _run_chain(img, kwargs, full=False)


def render_full_kwargs(img: Image.Image, kwargs: dict) -> Image.Image:
    """Doc-size chain for Full stills: same stages, no 640px downscale
    and no pixel compensation (pixel units are source pixels at f=1.0).
    Display-only; export/batch/CLI/video stay on CPU. Raises on any
    GL failure so the caller falls back to the CPU full render.
    """
    return _run_chain(img, kwargs, full=True)


def _run_chain(img: Image.Image, kwargs: dict, full: bool) -> Image.Image:
    if not available():
        raise RuntimeError("GPU unavailable")
    if not supports(kwargs):
        raise RuntimeError("GPU dither does not cover this preset")
    from dataclasses import fields as _dc_fields

    from app.adjust import apply_adjust
    from app.canvas import to_canvas
    from app.drift import apply_drift_loop
    from app.grade import gradient_map
    from app.grade import posterize as _grade_posterize
    from app.pipeline import RenderSpec, resolve_palette
    from app.render_params import apply_palette_depth
    from app.services.render_service import (
        compensate_preview_params,
        downscale_for_preview,
    )

    fields = [f.name for f in _dc_fields(RenderSpec) if f.name in kwargs]
    spec = RenderSpec(**{name: kwargs[name] for name in fields})
    if full:
        small, f = img, 1.0
        k = dict(kwargs)
    else:
        small, f = downscale_for_preview(img)
        k = compensate_preview_params(dict(kwargs), f)
    canvas = to_canvas(small, ratio=str(k.get("ratio", "1:1")),
                       mode=str(k.get("crop_mode", "cover")),
                       fx=float(k.get("focus_x", 50.0)),
                       fy=float(k.get("focus_y", 50.0)),
                       zoom=float(k.get("crop_zoom", 1.0)),
                       canvas_w=int(k.get("canvas_w", 0) or 0),
                       canvas_h=int(k.get("canvas_h", 0) or 0))
    if str(k.get("drift_pattern", "off") or "off") != "off" \
            and float(k.get("drift_amount", 0.0) or 0.0) > 0:
        if k.get("drift_progress") is not None:
            canvas = apply_drift_loop(canvas, pattern=str(k["drift_pattern"]),
                                      amount=float(k.get("drift_amount", 0.0)),
                                      progress=float(k["drift_progress"]),
                                      loops=float(k.get("drift_loops", 1.0) or 1.0))
        else:
            try:
                pos = max(0.0, min(100.0, float(k.get("drift_position", 50.0)))) / 100.0
            except (TypeError, ValueError):
                pos = 0.5
            canvas = apply_drift_loop(canvas, pattern=str(k["drift_pattern"]),
                                      amount=float(k.get("drift_amount", 0.0)),
                                      progress=pos, loops=1.0)
    if any(float(k.get(key, 0.0) or 0.0) for key in
           ("pre_blur", "pre_sharpen", "pre_hue", "pre_denoise", "pre_smooth")):
        from app.fx import apply_pre as _apply_pre

        canvas = _apply_pre(canvas, blur=float(k.get("pre_blur", 0.0) or 0.0),
                            sharpen=int(k.get("pre_sharpen", 0) or 0),
                            hue=float(k.get("pre_hue", 0.0) or 0.0),
                            denoise=int(k.get("pre_denoise", 0) or 0),
                            smooth=float(k.get("pre_smooth", 0.0) or 0.0))
    if k.get("duotone_dark") or k.get("duotone_light"):
        canvas = gradient_map(canvas, color_dark=str(k.get("duotone_dark", "")),
                              color_light=str(k.get("duotone_light", "")),
                              mid=float(k.get("duotone_mid", 50.0)))
    if int(k.get("posterize", 0) or 0) >= 2:
        canvas = _grade_posterize(canvas, levels=int(k.get("posterize")))
    pal, _label = resolve_palette(str(k.get("palette_name", "BW")),
                                  k.get("custom_palette"))
    if pal == "SOURCE":
        from app.palette_extract import extract_palette

        pal = extract_palette(canvas, n=int(k.get("palette_depth", 6) or 6))
    else:
        pal = apply_palette_depth(pal, int(k.get("palette_depth", 0) or 0))
    pixel = max(1, int(k.get("pixel_size", 1) or 1))
    if pixel > 1:
        small_canvas = canvas.resize((max(1, canvas.width // pixel),
                                      max(1, canvas.height // pixel)), Image.NEAREST)
    else:
        small_canvas = canvas
    adjusted = apply_adjust(small_canvas.convert("RGB"), k.get("adjust"))
    dithered = _dither_pass(adjusted, k, pal)
    if pixel > 1:
        dithered = dithered.resize((dithered.width * pixel, dithered.height * pixel),
                                   Image.NEAREST)
    return _render_spec_tail(spec, dithered)


def render_proxy_or_cpu(img: Image.Image, preset) -> tuple[Image.Image, str]:
    """Proxy preview: GPU when supported and working, else CPU. Never raises."""
    from app.render_params import preset_to_render_kwargs
    from app.services.render_service import render_preview_small

    try:
        kwargs = preset_to_render_kwargs(preset)
    except Exception:  # noqa: BLE001
        kwargs = dict(preset) if isinstance(preset, dict) else {}
    if available() and supports(kwargs):
        try:
            return render_proxy_kwargs(img, kwargs), "GPU"
        except Exception:  # noqa: BLE001
            pass
    return render_preview_small(img, preset), "CPU"


def render_full_or_cpu(img: Image.Image, preset) -> tuple[Image.Image, str]:
    """Full-res still preview: GPU when supported and working, else CPU.

    Display-only (export/batch/CLI/video never call this). Never raises.
    """
    from app.render_params import preset_to_render_kwargs
    from app.services.render_service import render_full

    try:
        kwargs = preset_to_render_kwargs(preset)
    except Exception:  # noqa: BLE001
        kwargs = dict(preset) if isinstance(preset, dict) else {}
    if available() and supports(kwargs):
        try:
            return render_full_kwargs(img, kwargs), "GPU"
        except Exception:  # noqa: BLE001
            pass
    return render_full(img, preset), "CPU"


def render_kwargs_or_cpu(img: Image.Image, kwargs: dict) -> tuple[Image.Image, str]:
    """Dict-kwargs variant for the background worker. Never raises."""
    from app.pipeline import render
    from app.services.render_service import (
        compensate_preview_params,
        downscale_for_preview,
    )

    if available() and supports(kwargs):
        try:
            return render_proxy_kwargs(img, kwargs), "GPU"
        except Exception:  # noqa: BLE001
            pass
    small, f = downscale_for_preview(img)
    k = compensate_preview_params(dict(kwargs), f)
    return render(small, **k), "CPU"


__all__ = ["available", "render_kwargs_or_cpu", "render_proxy_or_cpu",
           "render_full_or_cpu", "render_proxy_kwargs", "render_full_kwargs",
           "supports"]
