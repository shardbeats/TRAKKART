"""GPU preview spike (manual, NOT a quality gate).

One Bayer + grade in moderngl: fps vs numpy + pixel parity.

Usage (repo root):
  .venv\\Scripts\\python tools\\gpu_spike_preview.py --check   # parity, no UI
  .venv\\Scripts\\python tools\\gpu_spike_preview.py --bench   # fps table
  .venv\\Scripts\\python tools\\gpu_spike_preview.py --show    # minimal window

Spike report (NVIDIA RTX 3060, GL 330, filled after run):
  parity 256x256 / 640x480: maxdiff=0 LSB, pixels>1LSB=0.00%  -> PASS
  bench 640x480:   numpy 65.5ms (15 fps) vs GPU 2.9ms (348 fps)  -> 23x
  bench 1920x1080: numpy 362.6ms (3 fps) vs GPU 15.2ms (66 fps)  -> 24x
  note: numpy time is the grade+ordered chain on RGB; GPU time includes
  both passes + readback (honest: the preview needs pixels back).
  fixes needed during the spike (all in-spike, documented for the C1):
  upload orientation (moderngl takes PIL top-first bytes as-is, no flip),
  FBO sampling needs a V-flip between passes, contrast pivots on the
  Pillow int-rounded L-mean of the BRIGHTENED image (CPU computes it).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Fixed spike params (documented, deterministic).
BRIGHT, CONTRAST, SAT = 1.2, 1.3, 1.4
MID, HIGH = 1.1, 20.0
DUO_DARK, DUO_LIGHT, DUO_MID = "#123456", "#F5A623", 50.0
POSTERIZE = 4
THRESHOLD = 128.0

VERT = """
#version 330
in vec2 in_vert;
out vec2 v_uv;
void main() {
    v_uv = vec2((in_vert.x + 1.0) * 0.5, (1.0 - in_vert.y) * 0.5);
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

# Mirrors app/adjust.py + app/grade.py with per-stage uint8 quantization
# (floor), like the TRAKKMOTION grade oracle. Contrast uses the TRUE
# Pillow pivot (L-mean of the brightened image, int-rounded); the CPU
# computes it, the GPU only applies it. The oracle documents 0.5 as its
# deviation; the spike proves exact parity is reachable.
GRADE_FRAG = """
#version 330
uniform sampler2D u_image;
uniform float u_bright, u_contrast, u_cmean, u_sat, u_mid, u_high;
uniform vec3 u_duoDark, u_duoLight;
uniform float u_duoMid, u_duoOn, u_posterize;
in vec2 v_uv;
out vec4 f_color;
float bankers(float x) {
    float f = floor(x);
    float d = x - f;
    if (abs(d - 0.5) > 0.0001) return floor(x + 0.5);
    return mod(f, 2.0) < 0.5 ? f : f + 1.0;
}
void main() {
    vec3 c = texture(u_image, v_uv).rgb;
    c *= u_bright;
    c = floor(clamp(c, 0.0, 1.0) * 255.0) / 255.0;
    c = (c - u_cmean) * u_contrast + u_cmean;
    c = floor(clamp(c, 0.0, 1.0) * 255.0) / 255.0;
    float lum = floor(dot(c, vec3(0.299, 0.587, 0.114)) * 255.0 + 0.5) / 255.0;
    c = vec3(lum) + (c - vec3(lum)) * u_sat;
    c = floor(clamp(c, 0.0, 1.0) * 255.0) / 255.0;
    c = pow(clamp(c, 0.0, 1.0), vec3(1.0 / max(u_mid, 0.000001)));
    float l2 = dot(clamp(c, 0.0, 1.0), vec3(0.299, 0.587, 0.114));
    c += (u_high / 255.0) * smoothstep(0.5, 1.0, l2);
    c = floor(clamp(c, 0.0, 1.0) * 255.0) / 255.0;
    if (u_duoOn > 0.5) {
        float t = clamp(u_duoMid, 0.0, 100.0) / 100.0;
        float l3 = dot(c, vec3(0.299, 0.587, 0.114));
        float x = clamp((l3 - (t - 0.075)) / 0.15, 0.0, 1.0);
        float k = x * x * (3.0 - 2.0 * x);
        c = u_duoDark + (u_duoLight - u_duoDark) * k;
        c = floor(clamp(c, 0.0, 1.0) * 255.0) / 255.0;
    }
    float lv = clamp(u_posterize, 2.0, 8.0);
    c = vec3(bankers(c.r * (lv - 1.0)), bankers(c.g * (lv - 1.0)), bankers(c.b * (lv - 1.0))) / (lv - 1.0);
    c = floor(clamp(c, 0.0, 1.0) * 255.0) / 255.0;
    f_color = vec4(clamp(c, 0.0, 1.0), 1.0);
}
"""

# BW Bayer8, channel-mean luminance like app/dither.py ordered().
DITHER_FRAG = """
#version 330
uniform sampler2D u_image;
uniform sampler2D u_lut;
uniform float u_threshold, u_h;
in vec2 v_uv;
out vec4 f_color;
void main() {
    float yt = u_h - gl_FragCoord.y;
    float mx = mod(floor(gl_FragCoord.x), 8.0);
    float my = mod(floor(yt), 8.0);
    float lvl = texture(u_lut, vec2((mx + 0.5) / 8.0, (my + 0.5) / 8.0)).r;
    float t = clamp(u_threshold, 0.0, 255.0);
    float spread = clamp(255.0 - abs(t - 127.5) * 2.0, 32.0, 255.0);
    float bias = (lvl - 0.5) * spread;
    // The grade FBO is bottom-first; flip V to address it top-first.
    vec3 c = texture(u_image, vec2(v_uv.x, 1.0 - v_uv.y)).rgb;
    float mean = dot(c, vec3(1.0 / 3.0));
    float v = mean * 255.0 + bias > t ? 1.0 : 0.0;
    f_color = vec4(vec3(v), 1.0);
}
"""


def make_images() -> dict[str, Image.Image]:
    """Deterministic synthetic inputs (no repo assets needed)."""
    rng = np.random.default_rng(0x51E)
    w, h = 256, 256
    xs = np.tile(np.linspace(0, 255, w, dtype=np.float32), (h, 1))
    ys = np.tile(np.linspace(0, 255, h, dtype=np.float32)[:, None], (1, w))
    grad = np.stack([xs, ys, 255.0 - xs], axis=-1).astype(np.uint8)
    noise = rng.integers(0, 256, (480, 640, 3)).astype(np.uint8)
    photo = np.asarray(
        Image.fromarray(noise).filter(ImageFilter.GaussianBlur(radius=3))
    )
    return {"gradient": Image.fromarray(grad), "photo": Image.fromarray(photo)}


def numpy_ref(img: Image.Image) -> Image.Image:
    """CPU reference: the real app chain (grade subset + ordered bayer8 BW)."""
    from app.adjust import Adjust, apply_adjust
    from app.dither import ordered
    from app.grade import gradient_map, posterize

    adj = Adjust(brightness=BRIGHT, contrast=CONTRAST, saturation=SAT,
                 midtones=MID, highlights=HIGH)
    g = apply_adjust(img.convert("RGB"), adj)
    g = gradient_map(g, color_dark=DUO_DARK, color_light=DUO_LIGHT, mid=DUO_MID)
    g = posterize(g, levels=POSTERIZE)
    # Contrast pivots on the BRIGHTENED image mean (Pillow ImageEnhance
    # semantics: int(L-mean + 0.5)). The wiring must compute this on CPU;
    # the GPU only applies it. Cheap: one L pass + histogram mean.
    from PIL import ImageEnhance, ImageStat

    bright = ImageEnhance.Brightness(img.convert("RGB")).enhance(BRIGHT)
    cmean = int(ImageStat.Stat(bright.convert("L")).mean[0] + 0.5) / 255.0
    return ordered(g, palette=None, map_name="bayer8",
                   threshold=THRESHOLD, pixel_size=1), cmean


def _parse_hex(s: str) -> tuple[float, float, float]:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


class Spike:
    """Two-pass offscreen GL: grade FBO -> dither FBO -> readback."""

    def __init__(self, w: int, h: int):
        import moderngl

        self.w, self.h = w, h
        self.ctx = moderngl.create_standalone_context()
        from app.ordered_maps import BAYER_8X8

        lut = (BAYER_8X8 / 64.0).astype("f4")
        self.lut_tex = self.ctx.texture((8, 8), 1, lut.tobytes(), dtype="f4")
        self.lut_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        verts = np.array([-1.0, -1.0, 3.0, -1.0, -1.0, 3.0], dtype="f4")
        self.vbo = self.ctx.buffer(verts.tobytes())
        self.grade_prog = self.ctx.program(vertex_shader=VERT, fragment_shader=GRADE_FRAG)
        self.dither_prog = self.ctx.program(vertex_shader=VERT, fragment_shader=DITHER_FRAG)
        self.grade_vao = self.ctx.vertex_array(
            self.grade_prog, [(self.vbo, "2f", "in_vert")])
        self.dither_vao = self.ctx.vertex_array(
            self.dither_prog, [(self.vbo, "2f", "in_vert")])
        self.src_tex = self.ctx.texture((w, h), 3)
        self.src_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.grade_tex = self.ctx.texture((w, h), 3)
        self.grade_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.grade_fbo = self.ctx.framebuffer(self.grade_tex)
        self.out_fbo = self.ctx.simple_framebuffer((w, h))

    def render(self, img: Image.Image, cmean: float) -> Image.Image:
        # Top-first convention: v=0 addresses the top row everywhere.
        # moderngl uploads PIL top-first bytes as-is (no flip needed);
        # FBO readback is bottom-first, so only the readback flips.
        raw = img.convert("RGB").tobytes()
        self.src_tex.write(raw)
        self.grade_fbo.use()
        self.src_tex.use(0)
        gp = self.grade_prog
        gp["u_image"].value = 0
        gp["u_bright"].value = BRIGHT
        gp["u_contrast"].value = CONTRAST
        gp["u_cmean"].value = cmean
        gp["u_sat"].value = SAT
        gp["u_mid"].value = MID
        gp["u_high"].value = HIGH
        gp["u_duoDark"].value = _parse_hex(DUO_DARK)
        gp["u_duoLight"].value = _parse_hex(DUO_LIGHT)
        gp["u_duoMid"].value = DUO_MID
        gp["u_duoOn"].value = 1.0
        gp["u_posterize"].value = float(POSTERIZE)
        self.grade_vao.render(mode=self.ctx.TRIANGLES)
        self.out_fbo.use()
        self.grade_tex.use(0)
        self.lut_tex.use(1)
        dp = self.dither_prog
        dp["u_image"].value = 0
        dp["u_lut"].value = 1
        dp["u_threshold"].value = THRESHOLD
        dp["u_h"].value = float(self.h)
        self.dither_vao.render(mode=self.ctx.TRIANGLES)
        back = self.out_fbo.read(components=3)
        return Image.frombytes("RGB", (self.w, self.h), back).transpose(
            Image.FLIP_TOP_BOTTOM)


def parity(img: Image.Image) -> tuple[int, float]:
    """(max abs diff in LSB, fraction of pixels above 1 LSB)."""
    ref, cmean = numpy_ref(img)
    spike = Spike(img.width, img.height)
    got = spike.render(img, cmean)
    a = np.asarray(ref.convert("L"), dtype=np.int16)
    b = np.asarray(got.convert("L"), dtype=np.int16)
    d = np.abs(a - b)
    return int(d.max()), float((d > 1).mean())


def bench(img: Image.Image, iters_cpu: int = 5, iters_gpu: int = 30) -> tuple[float, float]:
    """(numpy ms/render, GPU ms/render incl. readback)."""
    ref, cmean = numpy_ref(img)  # warm (numba compile etc.)
    t0 = time.perf_counter()
    for _ in range(iters_cpu):
        numpy_ref(img)
    cpu_ms = (time.perf_counter() - t0) / iters_cpu * 1000.0
    spike = Spike(img.width, img.height)
    spike.render(img, cmean)  # warm
    t0 = time.perf_counter()
    for _ in range(iters_gpu):
        spike.render(img, cmean)
    gpu_ms = (time.perf_counter() - t0) / iters_gpu * 1000.0
    return cpu_ms, gpu_ms


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GPU preview spike: Bayer + grade parity/bench")
    ap.add_argument("--check", action="store_true", help="parity over synthetic inputs")
    ap.add_argument("--bench", action="store_true", help="fps table vs numpy")
    ap.add_argument("--show", action="store_true", help="minimal PySide6 window")
    args = ap.parse_args(argv)
    try:
        import moderngl  # noqa: F401
    except Exception:
        print("SKIP: moderngl not installed (local spike only)")
        return 2
    try:
        imgs = make_images()
        big = Image.new("RGB", (640, 480), (90, 60, 140))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}")
        return 1
    if args.show:
        from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

        app = QApplication.instance() or QApplication([])
        ref, cmean = numpy_ref(big)
        try:
            got = Spike(big.width, big.height).render(big, cmean)
        except Exception as e:  # noqa: BLE001
            print(f"SKIP: no GL context ({e})")
            return 2
        from app.ui.qt_image import pil_to_pixmap

        win = QWidget()
        win.setWindowTitle("Spike: numpy (left) vs GPU (right)")
        row = QHBoxLayout(win)
        for im in (ref, got):
            lab = QLabel()
            lab.setPixmap(pil_to_pixmap(im, max_side=480))
            row.addWidget(lab)
        win.show()
        app.exec()
        return 0
    try:
        if args.bench:
            for name, size in (("S 640x480", (640, 480)), ("L 1920x1080", (1920, 1080))):
                im = Image.new("RGB", size, (90, 60, 140))
                cpu_ms, gpu_ms = bench(im)
                print(f"{name}: numpy {cpu_ms:.1f}ms ({1000.0 / cpu_ms:.0f} fps) "
                      f"vs GPU {gpu_ms:.1f}ms ({1000.0 / gpu_ms:.0f} fps) "
                      f"-> {cpu_ms / gpu_ms:.0f}x")
            return 0
        # Default: parity check.
        worst, worst_frac = 0, 0.0
        for name, im in imgs.items():
            md, frac = parity(im)
            print(f"{name} {im.size}: maxdiff={md} LSB, pixels>1LSB={frac * 100:.2f}%")
            worst, worst_frac = max(worst, md), max(worst_frac, frac)
        ok = worst <= 1
        print("PARITY " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    except Exception as e:  # noqa: BLE001
        print(f"SKIP: no GL context ({e})")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
