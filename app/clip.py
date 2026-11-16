"""TRAKKART clip import (v2.0 Fase A): short clips as first-class input.

Stills stay the core product; a short clip becomes a session-only input
that the still pipeline dithers frame by frame (Fase B). Offline,
Pillow+numpy only (+ imageio-ffmpeg for MP4, same opt-in video backend
as MP4 export). Deterministic, no network.

Rules (see ROADMAP v2.0):
- Session-only: frames live in RAM, never in presets/batch.
- Cap 120f at a 720p proxy (long side <= 720): editing stays light.
- Supported: .mp4 / .gif / .webp. Without the video backend every
  entry point raises VideoBackendMissing (clean message, no traceback).
- Trim is a [start, end] index range over the imported frames.
- Audio: none in-app (visual preview only); a soundtrack joins at
  MP4 export (Fase C mux).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.video_io import VideoBackendMissing, has_video

CLIP_MAX_FRAMES = 120
CLIP_PROXY_SIDE = 720
CLIP_EXTS = (".mp4", ".gif", ".webp")

MIN_CLIP_FPS = 2
MAX_CLIP_FPS = 60


def has_clip_io() -> bool:
    """True when clip import is available (same video backend as MP4)."""
    return bool(has_video())


def _require_clip_io() -> None:
    if not has_clip_io():
        raise VideoBackendMissing()


def _proxy_dims(w: int, h: int, proxy_side: int) -> tuple[int, int]:
    """Proxy dimensions for a source frame (long side <= proxy_side)."""
    side = max(64, min(1920, int(proxy_side or CLIP_PROXY_SIDE)))
    w, h = int(w or 0), int(h or 0)
    if w <= 0 or h <= 0:
        return 0, 0
    r = side / max(w, h)
    if r >= 1.0:
        return w, h
    return max(1, round(w * r)), max(1, round(h * r))


def _fit_proxy(img: Image.Image, proxy_side: int) -> Image.Image:
    w, h = _proxy_dims(img.width, img.height, proxy_side)
    if (w, h) == (img.width, img.height):
        return img.copy()
    return img.resize((max(1, w), max(1, h)), Image.BICUBIC)


def _clamp_fps(fps) -> int:
    try:
        return max(MIN_CLIP_FPS, min(MAX_CLIP_FPS, int(round(float(fps)))))
    except (TypeError, ValueError):
        return 24


def _anim_info(path: Path) -> tuple[int, int, float]:
    """GIF/WebP header: (total_frames, fps, source_duration), no decode."""
    with Image.open(path) as im:
        total = int(getattr(im, "n_frames", 1) or 1)
        try:
            dur = float(im.info.get("duration", 125) or 125)
            fps = _clamp_fps(1000.0 / max(1.0, dur))
        except (AttributeError, TypeError, ValueError):
            fps = 8
    return total, fps, total / max(1, fps)


def _read_anim_frames(path: Path, skip_frames: int, n: int,
                      proxy_side: int) -> tuple[list, int, int]:
    """Raw window read for GIF/WebP: `n` proxy frames from `skip_frames`.

    No time math, no errors past the end (returns what exists, possibly
    empty). The public entry points keep their clamps and clean errors;
    the long-clip iterator builds on this.
    """
    frames: list[Image.Image] = []
    with Image.open(path) as im:
        total = int(getattr(im, "n_frames", 1) or 1)
        try:
            dur = float(im.info.get("duration", 125) or 125)
            fps = _clamp_fps(1000.0 / max(1.0, dur))
        except (AttributeError, TypeError, ValueError):
            fps = 8
        skip = max(0, min(total, int(skip_frames)))
        want = max(0, min(int(n), total - skip))
        for i in range(skip, skip + want):
            try:
                im.seek(i)
            except EOFError:
                break
            frames.append(_fit_proxy(im.convert("RGB"), proxy_side))
    return frames, fps, total


def _read_anim_pil(path: Path, max_frames: int, proxy_side: int,
                   start_s: float = 0.0) -> tuple[list, int, bool, float, float]:
    """Read .gif/.webp via Pillow (offline, no ffmpeg frames needed).

    `start_s` skips the first `round(start_s * fps)` frames via `im.seek`
    (Pillow has no time seek; frame-accurate by construction).
    Returns (frames, fps, truncated, start_s, source_duration).
    """
    start = max(0.0, float(start_s or 0.0))
    total, fps, source_duration = _anim_info(path)
    if start >= source_duration:
        raise ValueError(f"start {start:.2f}s beyond clip length {source_duration:.2f}s: {path}")
    skip = min(total - 1, int(start * fps))
    n = min(int(total - skip), max(1, int(max_frames)))
    frames, _, _ = _read_anim_frames(path, skip, n, proxy_side)
    truncated = bool(skip > 0 or total > skip + n)
    if not frames:
        raise ValueError(f"no frames: {path}")
    return frames, fps, truncated, start, source_duration


def _probe_meta(path: Path) -> dict:
    """Cheap metadata probe (ffmpeg parses the header, no frame decode)."""
    import imageio.v2 as iio2

    try:
        probe = iio2.get_reader(str(path))
    except Exception:  # noqa: BLE001
        return {}
    try:
        return dict(probe.get_meta_data() or {})
    except Exception:  # noqa: BLE001
        return {}
    finally:
        try:
            probe.close()
        except Exception:  # noqa: BLE001
            pass


def _read_mp4(path: Path, max_frames: int, proxy_side: int,
              start_s: float = 0.0) -> tuple[list, int, bool, float, float | None]:
    """Read .mp4 via imageio-ffmpeg (first N frames from `start_s`, session proxy).

    The proxy downscale happens *inside* ffmpeg (`size=` -> `-s`), not in
    Python: a 4K 452MB source went from 12.9s to 1.2s (11x) because the
    pipe never carries 24MB native frames. A header probe (no decode)
    gives the source size first; anything unexpected falls back to the
    native-size reader.

    In-point seek uses a fast input `-ss` (`input_params`, before `-i`):
    frame-accurate on ffmpeg 7.1 (frame 10/30 reads back exact gray).
    Returns (frames, fps, truncated, start_s, source_duration).

    VFR normalization: phone captures are VFR and imageio's native pass
    **duplicates frames** (a 30-real-frame VFR test read back 57), so
    120 imported frames would cover less real time than the label says.
    The reader always gets `-vf fps=N` (N = rounded source fps, clamped
    2–60): a no-op passthrough on CFR sources (verified: 30/30 frames
    identical), and on VFR it outputs an honest CFR (57 → 29 frames ≈
    duration × N). The returned fps is the *effective* CFR.
    """
    import imageio.v2 as iio2

    frames: list[Image.Image] = []
    fps = 24
    truncated = False
    start = max(0.0, float(start_s or 0.0))
    meta = _probe_meta(path)
    try:
        fps = _clamp_fps(meta.get("fps", 24))
    except Exception:  # noqa: BLE001
        fps = 24
    norm = _clamp_fps(round(fps))
    source_duration: float | None = None
    try:
        import math as _math

        d = float(meta.get("duration") or 0.0)
        if d > 0 and _math.isfinite(d):
            source_duration = d
    except (TypeError, ValueError):
        source_duration = None
    if source_duration is not None and start >= source_duration:
        raise ValueError(f"start {start:.2f}s beyond clip length {source_duration:.2f}s: {path}")
    total = meta.get("nframes", None)
    src = meta.get("size")
    kw: dict = {"output_params": ["-vf", f"fps={norm}"]}
    if start > 0:
        kw["input_params"] = ["-ss", f"{start:.3f}"]
    if isinstance(src, (tuple, list)) and len(src) == 2:
        try:
            sw, sh = int(src[0]), int(src[1])
            pw, ph = _proxy_dims(sw, sh, proxy_side)
        except (TypeError, ValueError):
            pw = ph = 0
        if pw and ph and (pw, ph) != (sw, sh):
            kw["size"] = (pw, ph)
    try:
        reader = iio2.get_reader(str(path), **kw)
    except Exception:  # noqa: BLE001
        reader = iio2.get_reader(str(path))
    try:
        n = 0
        cap = max(1, int(max_frames))
        for arr in reader:
            if n >= cap:
                truncated = True
                break
            frames.append(_fit_proxy(Image.fromarray(arr).convert("RGB"), proxy_side))
            n += 1
        if start > 0:
            truncated = True  # frames exist before the window
        if total is not None:
            try:
                import math as _math

                t = float(total)
                # imageio reports inf for many MP4s (no index): that is
                # "unknown", never "not truncated" — the cap flag set
                # above must survive.
                if _math.isfinite(t):
                    truncated = truncated or int(t) > len(frames) + int(start * norm)
            except (TypeError, ValueError, OverflowError):
                pass
    finally:
        try:
            reader.close()
        except Exception:  # noqa: BLE001
            pass
    if not frames:
        raise ValueError(f"no frames: {path}")
    return frames, norm, truncated, start, source_duration


def import_clip(path: str | Path, max_frames: int = CLIP_MAX_FRAMES,
                proxy_side: int = CLIP_PROXY_SIDE,
                start_s: float = 0.0) -> tuple[list[Image.Image], dict]:
    """Import a short clip (session-only proxy frames + info).

    `start_s` is the in-point in seconds (fast input `-ss` for MP4,
    frame skip for GIF/WebP); clamped to the source duration, clean
    ValueError past the end. Returns (frames, info) with info {path,
    frames, fps, truncated, size, start_s, source_duration}.
    Raises VideoBackendMissing without the video extra,
    FileNotFoundError for missing paths, ValueError for bad ext/empty.
    """
    _require_clip_io()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"clip not found: {path}")
    ext = p.suffix.lower()
    if ext not in CLIP_EXTS:
        raise ValueError(f"clip must be {CLIP_EXTS}: {path}")
    try:
        start = max(0.0, float(start_s or 0.0))
    except (TypeError, ValueError):
        start = 0.0
    cap = max(1, min(CLIP_MAX_FRAMES, int(max_frames or CLIP_MAX_FRAMES)))
    side = max(64, min(1920, int(proxy_side or CLIP_PROXY_SIDE)))
    if ext in (".gif", ".webp"):
        frames, fps, truncated, start, duration = _read_anim_pil(p, cap, side, start)
    else:
        frames, fps, truncated, start, duration = _read_mp4(p, cap, side, start)
    info = {"path": str(p), "frames": len(frames), "fps": int(fps),
            "truncated": bool(truncated), "size": [frames[0].width, frames[0].height],
            "start_s": float(start), "source_duration": duration}
    return frames, info


def trim_clip(frames: list[Image.Image], start: int, end: int) -> list[Image.Image]:
    """Trim to the inclusive [start, end] range (clamped, deterministic)."""
    n = len(frames or [])
    if n == 0:
        raise ValueError("no frames")
    try:
        s = int(start)
    except (TypeError, ValueError):
        s = 0
    try:
        e = int(end)
    except (TypeError, ValueError):
        e = n - 1
    s = max(0, min(n - 1, s))
    e = max(0, min(n - 1, e))
    if s > e:
        raise ValueError(f"empty range: {start}-{end}")
    return list(frames[s:e + 1])


def clip_duration(frames: int, fps: int) -> float:
    """Derived clip length in seconds (frames / fps, preview math)."""
    return max(0.0, float(int(frames or 0)) / max(1, _clamp_fps(fps)))


# ---------------------------------------------------------------------------
# Fase B — dither: the current preset recipe applied per frame.
# ---------------------------------------------------------------------------
_SEED_ATTRS = ("grain_seed", "dust_seed", "glitch_slice_seed", "wave_seed",
               "mosh_seed", "drift_seed", "paste_seed", "pixelsort_seed")


def _spec_for(preset, index: int, n: int, dpi: int = 300, envelopes=None):
    """RenderSpec for frame `index`: base recipe + index-shifted seeds.

    Per-frame flicker is the aesthetic (documented): seeded post-fx
    (grain/dust/slice/wave/mosh/drift/paste) re-roll per frame while
    the recipe (method/palette/pixel/threshold/stack) stays put.
    Drift traverses 0->1 across the clip when enabled.
    `envelopes` (session-only) modulates drift_amount + grain over
    t=index/(n-1); motion_amount is still-motion only and ignored here.
    Empty/None renders byte-identical.
    """
    from app.pipeline import RenderSpec

    progress = float(index) / max(1, int(n) - 1) if int(n) > 1 else 0.0
    spec = RenderSpec.from_preset(preset, phase=0,
                                  drift_progress=progress, dpi=dpi)
    try:
        from app.envelopes import frame_values as _env_vals
        from app.envelopes import normalize_envelopes as _norm_env

        _env = _norm_env(envelopes)
        if _env:
            _v = _env_vals(_env, progress,
                           {"motion_amount": 1.0,
                            "drift_amount": float(getattr(spec, "drift_amount", 0.0) or 0.0),
                            "grain": float(getattr(spec, "grain", 0.0) or 0.0)})
            spec.drift_amount = float(_v["drift_amount"])
            spec.grain = float(_v["grain"])
    except Exception:  # noqa: BLE001
        pass
    for attr in _SEED_ATTRS:
        try:
            setattr(spec, attr, int(getattr(spec, attr, 0) or 0) + int(index))
        except (TypeError, ValueError):
            pass
    return spec


def iter_dither_clip(frames, preset, dpi: int = 300, envelopes=None):
    """Yield dithered frames one by one (streaming: O(1) RAM for MP4).

    Same pixels as dither_clip. Reuses render_spec, so combo/stack/
    GIF/MP4 writers inherit the recipe with zero extra plumbing.
    `envelopes` modulates drift+grain per frame (session-only).
    """
    from app.pipeline import render_spec

    seq = list(frames or [])
    if not seq:
        raise ValueError("no frames")
    n = len(seq)
    for i, frame in enumerate(seq):
        yield render_spec(frame.convert("RGB"), _spec_for(preset, i, n, dpi, envelopes))


def dither_clip(frames, preset, dpi: int = 300, envelopes=None) -> list[Image.Image]:
    """Dither every frame with the preset recipe (deterministic).

    seed = base + index: same inputs -> same bytes; consecutive
    identical frames differ only through seeded post-fx (grain/dust/...
    >0), which is the documented flicker aesthetic.
    `envelopes` is session-only (never in presets).
    """
    return list(iter_dither_clip(frames, preset, dpi, envelopes))


# ---------------------------------------------------------------------------
# Fase C — export wiring: silent GIF, frame ZIP, MP4 (+ optional soundtrack).
# ---------------------------------------------------------------------------
def save_clip_zip(frames, out_path: str | Path) -> Path:
    """Frame ZIP: PNG sequence `frame_0001.png...` (stdlib only, offline).

    Same helper spirit as the batch bundle-ZIP (v1.8C), but the
    members are a deterministic PNG sequence instead of a folder.
    """
    import io
    import zipfile

    seq = list(frames or [])
    if not seq:
        raise ValueError("no frames")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, frame in enumerate(seq, 1):
            buf = io.BytesIO()
            frame.convert("RGB").save(buf, "PNG")
            zf.writestr(f"frame_{i:04d}.png", buf.getvalue())
    return out


def write_clip_mp4(frames_or_iter, out_path: str | Path,
                   fps: int = 24) -> Path:
    """Silent clip MP4 (software libx264-only, same writer as still MP4)."""
    from app.video_io import write_mp4, write_mp4_iter

    out = Path(out_path)
    if isinstance(frames_or_iter, list):
        return write_mp4(list(frames_or_iter), out, fps=fps)
    wrote, _ = write_mp4_iter(frames_or_iter, out, fps=fps)
    return wrote


def _mp4_duration(path: str | Path) -> float | None:
    """Duration in seconds from the video stream (None when unknown)."""
    try:
        import math

        import imageio.v2 as iio2

        with iio2.get_reader(str(path)) as reader:
            d = float((reader.get_meta_data() or {}).get("duration") or 0.0)
        return d if d > 0 and math.isfinite(d) else None
    except Exception:  # noqa: BLE001
        return None


def mux_soundtrack(silent_mp4: str | Path, audio_path: str | Path,
                   out_path: str | Path) -> Path:
    """Mux a chosen soundtrack (video copied, never re-encoded).

    `-c:v copy -c:a aac` keeps the libx264-only guarantee. The output is
    cut at the *video* duration (`-t`), so a track shorter than the clip
    no longer truncates the video (a 3s song used to turn a 10s clip
    into 3s) and a long track is cut at the clip end. `-af apad` was
    tried first: padding infinite silence with `-shortest` on a copied
    video stream **hangs** ffmpeg, so it is deliberately not used.
    Writes a `.part` file and renames on success, so a failed mux never
    leaves a half-written export behind.
    """
    import subprocess

    from imageio_ffmpeg import get_ffmpeg_exe

    src = Path(silent_mp4)
    if not src.is_file():
        raise FileNotFoundError(f"silent mp4 not found: {silent_mp4}")
    track = Path(audio_path)
    if not track.is_file():
        raise FileNotFoundError(f"audio not found: {audio_path}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(f"{out.stem}.part{out.suffix}")
    duration = _mp4_duration(src)
    cmd = [get_ffmpeg_exe(), "-y", "-i", str(src), "-i", str(track),
           "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy", "-c:a", "aac"]
    if duration is not None:
        cmd += ["-t", f"{duration:.3f}"]
    else:
        cmd += ["-shortest"]
    cmd.append(str(part))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not part.is_file() or part.stat().st_size == 0:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"ffmpeg mux failed: {proc.stderr[-500:]}")
    try:
        out.unlink(missing_ok=True)
    except OSError:
        pass
    part.replace(out)
    return out


# ---------------------------------------------------------------------------
# Long-clip MP4 via streaming (v2.x follow-up): the 120f preview window
# stays, but a full-length MP4 no longer needs the whole clip in RAM.
# Windows of <=120f decode sequentially from the source file (MP4 seeks
# with the same fast input `-ss`; GIF/WebP skip by frame index), each
# frame dithered with its *global* index so seeds/envelopes stay
# identical to a hypothetical full-RAM render. Hard cap 3600f (60s@60fps,
# same as write_mp4_iter): the limit becomes CPU/time, not memory.
# ---------------------------------------------------------------------------
LONG_MP4_MAX_FRAMES = 3600


def clip_full_length(path: str | Path, start_s: float = 0.0,
                     max_total: int = LONG_MP4_MAX_FRAMES) -> dict:
    """Plan a full-length export without decoding (header probe only).

    Returns {fps, source_duration, start_s, total_frames|None, capped}.
    `total_frames=None` means the header gave no duration (MP4 with
    unknown length): the iterator then decodes until exhausted or capped.
    GIF/WebP always know their frame count. Never raises for unknown
    lengths; errors only on missing path/bad ext/past-the-end start.
    """
    _require_clip_io()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"clip not found: {path}")
    ext = p.suffix.lower()
    if ext not in CLIP_EXTS:
        raise ValueError(f"clip must be {CLIP_EXTS}: {path}")
    try:
        start = max(0.0, float(start_s or 0.0))
    except (TypeError, ValueError):
        start = 0.0
    cap = max(1, min(LONG_MP4_MAX_FRAMES, int(max_total or LONG_MP4_MAX_FRAMES)))
    if ext in (".gif", ".webp"):
        total, fps, duration = _anim_info(p)
        if start >= duration:
            raise ValueError(f"start {start:.2f}s beyond clip length {duration:.2f}s: {path}")
        skip = min(total, int(start * fps))
        remaining = max(0, total - skip)
        n = min(remaining, cap)
        return {"fps": fps, "source_duration": duration, "start_s": start,
                "total_frames": n, "capped": remaining > n}
    meta = _probe_meta(p)
    try:
        fps = _clamp_fps(meta.get("fps", 24))
    except Exception:  # noqa: BLE001
        fps = 24
    duration: float | None = None
    try:
        import math as _math

        d = float(meta.get("duration") or 0.0)
        if d > 0 and _math.isfinite(d):
            duration = d
    except (TypeError, ValueError):
        duration = None
    if duration is not None:
        if start >= duration:
            raise ValueError(f"start {start:.2f}s beyond clip length {duration:.2f}s: {path}")
        import math as _math

        remaining = max(0, int(_math.floor((duration - start) * fps)))
        n = min(remaining, cap)
        return {"fps": fps, "source_duration": duration, "start_s": start,
                "total_frames": n, "capped": remaining > n}
    return {"fps": fps, "source_duration": None, "start_s": start,
            "total_frames": None, "capped": True}


def iter_source_frames(path: str | Path, start_s: float = 0.0,
                       max_total: int = LONG_MP4_MAX_FRAMES,
                       proxy_side: int = CLIP_PROXY_SIDE):
    """Yield source proxy frames across 120f windows (O(window) RAM).

    Stops at the source end or `max_total` (3600). Deterministic: window
    reads reuse the exact single-window code paths, so frames match
    `import_clip` byte for byte over the same range.
    """
    _require_clip_io()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"clip not found: {path}")
    ext = p.suffix.lower()
    if ext not in CLIP_EXTS:
        raise ValueError(f"clip must be {CLIP_EXTS}: {path}")
    try:
        start = max(0.0, float(start_s or 0.0))
    except (TypeError, ValueError):
        start = 0.0
    cap = max(1, min(LONG_MP4_MAX_FRAMES, int(max_total or LONG_MP4_MAX_FRAMES)))
    side = max(64, min(1920, int(proxy_side or CLIP_PROXY_SIDE)))
    produced = 0
    if ext in (".gif", ".webp"):
        _, fps, duration = _anim_info(p)
        if start >= duration:
            raise ValueError(f"start {start:.2f}s beyond clip length {duration:.2f}s: {path}")
        skip = min(int(_anim_info(p)[0]), int(start * fps))
        while produced < cap:
            want = min(CLIP_MAX_FRAMES, cap - produced)
            batch, _, _ = _read_anim_frames(p, skip + produced, want, side)
            if not batch:
                break
            for frame in batch:
                yield frame
                produced += 1
                if produced >= cap:
                    break
        return
    try:
        plan = clip_full_length(p, start, cap)
        fps = int(plan["fps"])
    except ValueError:
        raise
    except Exception:  # noqa: BLE001
        fps = 24
    while produced < cap:
        want = min(CLIP_MAX_FRAMES, cap - produced)
        t = start + produced / max(1, fps)
        try:
            batch, *_ = _read_mp4(p, want, side, t)
        except ValueError:
            break
        if not batch:
            break
        for frame in batch:
            if produced >= cap:
                break
            yield frame
            produced += 1
        if len(batch) < want:
            break


def iter_dither_source(path: str | Path, preset, start_s: float = 0.0,
                       max_total: int = LONG_MP4_MAX_FRAMES,
                       proxy_side: int = CLIP_PROXY_SIDE, dpi: int = 300,
                       envelopes=None, total_hint: int | None = None):
    """Yield dithered full-length frames (streaming, O(window) RAM).

    Global progress t = i/(n-1) drives seeds + envelopes exactly like
    `iter_dither_clip` would over the same range. `total_hint` (from
    `clip_full_length`) avoids a second probe; unknown lengths fall back
    to per-window progress (still deterministic, envelopes approximate).
    """
    from app.pipeline import render_spec

    n_hint = None
    try:
        if total_hint is not None and int(total_hint) > 0:
            n_hint = int(total_hint)
    except (TypeError, ValueError):
        n_hint = None
    if n_hint is None:
        try:
            plan = clip_full_length(path, start_s, max_total)
            n_hint = plan["total_frames"]
        except Exception:  # noqa: BLE001
            n_hint = None
    try:
        from app.envelopes import frame_values as _env_vals
        from app.envelopes import normalize_envelopes as _norm_env

        _env = _norm_env(envelopes)
    except Exception:  # noqa: BLE001
        _env = {}
    i = 0
    yielded = False
    for frame in iter_source_frames(path, start_s, max_total, proxy_side):
        # Unknown length: progress falls back to the running count (still
        # deterministic per run; envelopes approximate until the end).
        n = n_hint if n_hint else max(2, i + 1)
        progress = float(i) / max(1, n - 1) if n > 1 else 0.0
        spec = _spec_for(preset, i, max(2, n), dpi, None)
        if _env:
            try:
                _v = _env_vals(_env, progress,
                               {"motion_amount": 1.0,
                                "drift_amount": float(getattr(spec, "drift_amount", 0.0) or 0.0),
                                "grain": float(getattr(spec, "grain", 0.0) or 0.0)})
                spec.drift_amount = float(_v["drift_amount"])
                spec.grain = float(_v["grain"])
            except Exception:  # noqa: BLE001
                pass
        yield render_spec(frame.convert("RGB"), spec)
        yielded = True
        i += 1
    if not yielded:
        raise ValueError(f"no frames: {path}")


def write_clip_mp4_long(path: str | Path, out_path: str | Path, preset,
                        start_s: float = 0.0, fps: int = 24,
                        max_total: int = LONG_MP4_MAX_FRAMES,
                        proxy_side: int = CLIP_PROXY_SIDE, dpi: int = 300,
                        envelopes=None) -> tuple[Path, int]:
    """Full-length silent MP4 from the source file (streaming, O(window)).

    Returns (path, n_written). Same pixels as a full-RAM render over the
    same range (global seeds/progress), capped at 3600f.
    """
    from app.video_io import write_mp4_iter

    plan = clip_full_length(path, start_s, max_total)
    out = Path(out_path)
    total = plan["total_frames"]
    stream = iter_dither_source(path, preset, plan["start_s"], max_total,
                                proxy_side, dpi, envelopes, total)
    wrote, n = write_mp4_iter(stream, out, fps=int(plan["fps"] if fps is None else fps or plan["fps"]))
    return wrote, n


__all__ = ["CLIP_MAX_FRAMES", "CLIP_PROXY_SIDE", "CLIP_EXTS",
           "VideoBackendMissing", "has_clip_io",
           "import_clip", "trim_clip", "clip_duration",
           "iter_dither_clip", "dither_clip",
           "save_clip_zip", "write_clip_mp4", "mux_soundtrack",
           "LONG_MP4_MAX_FRAMES", "clip_full_length",
           "iter_source_frames", "iter_dither_source",
           "write_clip_mp4_long"]
