"""GLSL sources for the GPU preview backend (moderngl, GL 330 core).

DITHER_330 mirrors app/dither.py ordered/cmyk/edges. Integer-matrix
maps are procedural (bit-exact); float/RNG masks (ign, cross,
bluenoise, motif, scan_bayer, wave_map, white_noise, blocks) are baked
on CPU to an exact LUT and selected with u_baked. The CPU fallback
covers everything else (ED family, hilbert, ascii).

The pre-dither grade chain stays on CPU (exact suite code, cheap point
ops); the GPU accelerates the dither, which is the slow stage
(nearest-palette search). Post-dither FX stay on CPU for now.

Orientation: textures upload PIL top-first bytes as-is; v=0 addresses
the top row. FBO contents are bottom-first, so passes sampling an FBO
flip V explicitly (u_flip).
"""

VERT_330 = """
#version 330
in vec2 in_vert;
out vec2 v_uv;
void main() {
    v_uv = vec2((in_vert.x + 1.0) * 0.5, (1.0 - in_vert.y) * 0.5);
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

HALFTONE_4X4 = (7, 13, 11, 4, 12, 16, 14, 8, 10, 15, 6, 2, 5, 9, 3, 1)
CLUSTER_4X4 = (12, 5, 6, 13, 4, 0, 1, 7, 11, 3, 2, 8, 15, 10, 9, 14)
GRID_4X4 = (0, 0, 0, 16, 0, 16, 16, 16, 0, 16, 8, 16, 16, 16, 16, 16)

DITHER_330 = """
#version 330
uniform sampler2D u_image;
uniform sampler2D u_lut;
uniform sampler2D u_palette;
uniform float u_paletteSize, u_bw;
uniform float u_threshold, u_h, u_w, u_phase, u_flip;
uniform int u_map;
uniform float u_cells, u_baked;
uniform float u_lutW, u_lutH;
in vec2 v_uv;
out vec4 f_color;
float quadOff(vec2 q) {
    return (1.0 - q.y) * (q.x * 2.0) + q.y * (3.0 - q.x * 2.0);
}
float bayer32(vec2 p) {
    vec2 q = mod(p, 32.0);
    float v = quadOff(mod(q, 2.0));
    v = v * 4.0 + quadOff(floor(mod(q, 4.0) / 2.0));
    v = v * 4.0 + quadOff(floor(mod(q, 8.0) / 4.0));
    v = v * 4.0 + quadOff(floor(mod(q, 16.0) / 8.0));
    v = v * 4.0 + quadOff(floor(q / 16.0));
    return v;
}
float bayer8raw(vec2 p) {
    return floor(bayer32(p) / 16.0);
}
// Integer Rec.601 luma, bit-exact with Pillow convert("L").
// Exact .5 ties round up in integer math; float32 cannot tie-break them.
float tapL(vec3 c) {
    ivec3 v = ivec3(round(c * 255.0));
    return float((299 * v.x + 587 * v.y + 114 * v.z + 500) / 1000);
}
// Round-half-even (bankers): matches numpy rint / Pillow kernel output.
float bankers(float x) {
    float f = floor(x);
    float d = x - f;
    if (abs(d - 0.5) > 0.0001) return floor(x + 0.5);
    return mod(f, 2.0) < 0.5 ? f : f + 1.0;
}
float mat4(vec2 q, int id) {
    vec2 m = mod(q, 4.0);
    int idx = int(m.y) * 4 + int(m.x);
    float v = 0.0;
    if (id == 13) {
        float M[16] = float[16](__HALFTONE__);
        v = M[idx];
    } else if (id == 14) {
        float M[16] = float[16](__CLUSTER__);
        v = M[idx];
    } else {
        float M[16] = float[16](__GRID__);
        v = M[idx];
    }
    return v / 16.0;
}
vec3 nearestColor(vec3 noisy) {
    vec3 best = vec3(0.0);
    float bestD = 1e18;
    for (int i = 0; i < 16; i++) {
        float ci = min(float(i), u_paletteSize - 1.0);
        // Palette texture is always 16 wide (padded); size only bounds the loop.
        vec3 c = texture(u_palette, vec2((ci + 0.5) / 16.0, 0.5)).rgb;
        vec3 d = noisy - c;
        float dist = dot(d, d);
        if (dist < bestD) {
            bestD = dist;
            best = c;
        }
    }
    return best;
}
float screenChan(float v, float shift, vec2 c, vec2 dims) {
    // Roll-then-crop like the CPU (_screened rolls the cropped array):
    // wrap at the image dims first, then at the 8-period. Matters when
    // dims are not multiples of 8 (angle shifts are nonzero at phase 0).
    vec2 m = mod(mod(c - shift, dims), 8.0);
    return v > bayer8raw(m) / 64.0 * 255.0 ? 255.0 : 0.0;
}
void main() {
    float s = float(int(u_phase));
    vec2 fuv = vec2(v_uv.x, abs(u_flip - v_uv.y));
    vec2 q = vec2(floor(gl_FragCoord.x), floor(u_h - gl_FragCoord.y));
    vec3 src = texture(u_image, fuv).rgb;
    float t = clamp(u_threshold, 0.0, 255.0);
    float spread = clamp(255.0 - abs(t - 127.5) * 2.0, 32.0, 255.0);
    vec3 outc;
    if (u_map == 11) {
        float gain = (t - 128.0) * 0.8;
        float mx = max(src.r, max(src.g, src.b)) * 255.0;
        float k = clamp(255.0 - mx + gain, 0.0, 255.0);
        float ch = clamp(255.0 - src.r * 255.0 - (255.0 - mx) + gain, 0.0, 255.0);
        float mg = clamp(255.0 - src.g * 255.0 - (255.0 - mx) + gain, 0.0, 255.0);
        float yl = clamp(255.0 - src.b * 255.0 - (255.0 - mx) + gain, 0.0, 255.0);
        vec2 gd = vec2(u_w, u_h);
        vec2 c = q - s;
        float cs = screenChan(ch, 0.0, c, gd);
        float ms = screenChan(mg, 13.0, c, gd);
        float ys = screenChan(yl, 29.0, c, gd);
        float ks = screenChan(k, 47.0, c, gd);
        outc = vec3(
            (1.0 - cs / 255.0) * (1.0 - ks / 255.0),
            (1.0 - ms / 255.0) * (1.0 - ks / 255.0),
            (1.0 - ys / 255.0) * (1.0 - ks / 255.0));
    } else if (u_map == 12) {
        float lum255 = tapL(src);
        float ink;
        vec2 gd = vec2(u_w, u_h);
        if (q.x < 0.5 || q.y < 0.5 || q.x > gd.x - 1.5 || q.y > gd.y - 1.5) {
            ink = min(lum255 * 1.5, 255.0);
        } else {
            float acc = 0.0;
            for (int ky = -1; ky <= 1; ky++) {
                for (int kx = -1; kx <= 1; kx++) {
                    float w = (kx == 0 && ky == 0) ? 8.0 : -1.0;
                    vec2 cell = clamp(q + vec2(float(kx), float(ky)), vec2(0.0), gd - 1.0);
                    vec2 tap = (cell + 0.5) / gd;
                    acc += tapL(texture(u_image, vec2(tap.x, abs(u_flip - tap.y))).rgb) * w;
                }
            }
            // Integer-exact like Pillow: bankers the kernel sum, then x1.5.
            ink = min(bankers(clamp(acc, 0.0, 255.0)) * 1.5, 255.0);
        }
        vec2 c = mod(q - s, vec2(8.0));
        float lvl = bayer8raw(c) / 64.0;
        float bias = (lvl - 0.5) * spread;
        float dith = lum255 + bias > t ? 255.0 : 0.0;
        float v = clamp(dith * 0.55 + (255.0 - ink) * 0.45, 0.0, 255.0);
        if (u_bw > 0.5) {
            outc = vec3(v > t ? 1.0 : 0.0);
        } else {
            outc = nearestColor(vec3(v / 255.0));
        }
    } else {
        float lvl;
        if (u_baked > 0.5) {
            vec2 sc = mod(q - s, vec2(u_lutW, u_lutH));
            lvl = texture(u_lut, (sc + 0.5) / vec2(u_lutW, u_lutH)).r / 255.0;
        } else if (u_map == 0) {
            vec2 mb = mod(q - s, vec2(32.0));
            float div = 1024.0 / u_cells;
            lvl = floor(bayer32(mb) / div) / u_cells;
        } else if (u_map == 1) {
            lvl = mod((q.y - s), 8.0) / 8.0;
        } else if (u_map == 3) {
            lvl = mod((q.x - s), 8.0) / 8.0;
        } else if (u_map == 4) {
            lvl = mod((q.x + q.y - s), 8.0) / 8.0;
        } else if (u_map == 5) {
            lvl = abs(mod(q.x - s, 2.0) - mod(q.y - s, 2.0)) / 2.0;
        } else {
            lvl = mat4(q - s, u_map);
        }
        float bias = (lvl - 0.5) * spread;
        if (u_bw > 0.5) {
            float mean = dot(src, vec3(1.0 / 3.0));
            outc = vec3(mean * 255.0 + bias > t ? 1.0 : 0.0);
        } else {
            vec3 noisy = clamp(src + bias / 255.0, 0.0, 1.0);
            outc = nearestColor(noisy);
        }
    }
    gl_FragColor = vec4(outc, 1.0);
}
"""

DITHER_330 = (
    DITHER_330.replace("__HALFTONE__", ", ".join(f"{v}.0" for v in HALFTONE_4X4))
    .replace("__CLUSTER__", ", ".join(f"{v}.0" for v in CLUSTER_4X4))
    .replace("__GRID__", ", ".join(f"{v}.0" for v in GRID_4X4))
)

__all__ = ["DITHER_330", "VERT_330"]
