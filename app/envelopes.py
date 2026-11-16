"""Timeline parameter envelopes (candidate v2.x #3, Fase A).

Session-only curves that modulate preset params over normalized time
t in [0, 1] instead of flat values. Offline, deterministic (sin only,
no random), Pillow/numpy-free pure math.

Supported params (ranges match the preset fields):
- motion_amount: 0.0-3.0 (still-motion intensity, gif path only)
- drift_amount:  0.0-100.0 (Signal Drift, still + clip paths)
- grain:         0.0-100.0 (film grain, still + clip paths)

Kinds (all loop-perfect: t=0 == t=1):
- flat: {"kind": "flat", "value": v}
- ramp: {"kind": "ramp", "v0": a, "v1": b} (linear a -> b)
- lfo:  {"kind": "lfo", "base": b, "amp": a, "loops": n} (n integer 1-4)
- keys: {"kind": "keys", "points": [[t, v], ...]} (linear interp)

Missing param / None / {"kind": "off"} = follow the preset (no override).
Everything clamps to the param range; garbage normalizes to off (never
crashes the render).
"""

from __future__ import annotations

import math

ENVELOPE_PARAMS: dict[str, tuple[float, float]] = {
    "motion_amount": (0.0, 3.0),
    "drift_amount": (0.0, 100.0),
    "grain": (0.0, 100.0),
}

KINDS = ("off", "flat", "ramp", "lfo", "keys")


def _clamp(v, lo: float, hi: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = lo
    if not math.isfinite(f):
        return float(lo)
    return max(float(lo), min(float(hi), f))


def _num(v, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float(default)
    return f if math.isfinite(f) else float(default)


def normalize_envelope(raw, param: str) -> dict | None:
    """Canonical spec or None (off = follow preset). Never raises."""
    if param not in ENVELOPE_PARAMS:
        return None
    lo, hi = ENVELOPE_PARAMS[param]
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return {"kind": "flat", "value": _clamp(raw, lo, hi)}
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind", "off") or "off").lower()
    if kind == "off":
        return None
    if kind == "flat":
        return {"kind": "flat", "value": _clamp(raw.get("value", lo), lo, hi)}
    if kind == "ramp":
        return {"kind": "ramp",
                "v0": _clamp(raw.get("v0", lo), lo, hi),
                "v1": _clamp(raw.get("v1", raw.get("v0", lo)), lo, hi)}
    if kind == "lfo":
        try:
            loops = int(raw.get("loops", 1))
        except (TypeError, ValueError):
            loops = 1
        loops = max(1, min(4, loops))
        return {"kind": "lfo",
                "base": _clamp(raw.get("base", lo), lo, hi),
                "amp": max(0.0, _num(raw.get("amp", 0.0))),
                "loops": loops}
    if kind == "keys":
        pts = []
        try:
            raw_pts = list(raw.get("points", []) or [])
        except TypeError:
            return None
        for p in raw_pts:
            try:
                t, v = p
                pts.append([_clamp(_num(t), 0.0, 1.0), _clamp(v, lo, hi)])
            except (TypeError, ValueError):
                continue
        if not pts:
            return None
        pts.sort(key=lambda pv: pv[0])
        return {"kind": "keys", "points": pts}
    return None


def normalize_envelopes(raw) -> dict:
    """Whole session dict -> {param: spec} with off entries dropped."""
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    for param in ENVELOPE_PARAMS:
        if param in raw:
            spec = normalize_envelope(raw[param], param)
            if spec is not None:
                out[param] = spec
    return out


def eval_envelope(spec, progress: float, fallback: float, param: str) -> float:
    """Value at t in [0,1]. Empty spec -> clamped fallback. Deterministic."""
    lo, hi = ENVELOPE_PARAMS.get(param, (0.0, 100.0))
    if spec is None:
        return _clamp(fallback, lo, hi)
    try:
        t = _clamp(progress, 0.0, 1.0)
    except Exception:  # noqa: BLE001
        t = 0.0
    kind = str(spec.get("kind", "off"))
    if kind == "flat":
        return _clamp(spec.get("value", fallback), lo, hi)
    if kind == "ramp":
        v0 = _num(spec.get("v0", fallback), fallback)
        v1 = _num(spec.get("v1", v0), v0)
        return _clamp(v0 + (v1 - v0) * t, lo, hi)
    if kind == "lfo":
        base = _num(spec.get("base", fallback), fallback)
        amp = max(0.0, _num(spec.get("amp", 0.0)))
        try:
            loops = max(1, min(4, int(spec.get("loops", 1))))
        except (TypeError, ValueError):
            loops = 1
        v = base + amp * math.sin(2.0 * math.pi * loops * t)
        return _clamp(round(v, 6), lo, hi)
    if kind == "keys":
        pts = list(spec.get("points", []) or [])
        if not pts:
            return _clamp(fallback, lo, hi)
        if t <= pts[0][0]:
            return _clamp(pts[0][1], lo, hi)
        if t >= pts[-1][0]:
            return _clamp(pts[-1][1], lo, hi)
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                span = (t1 - t0) or 1.0
                return _clamp(v0 + (v1 - v0) * (t - t0) / span, lo, hi)
        return _clamp(pts[-1][1], lo, hi)
    return _clamp(fallback, lo, hi)


def frame_values(envelopes, progress: float, fallback: dict) -> dict:
    """Per-frame values for every supported param (fallback = preset flat)."""
    env = normalize_envelopes(envelopes)
    out: dict = {}
    for param in ENVELOPE_PARAMS:
        base = _num((fallback or {}).get(param, 0.0))
        out[param] = eval_envelope(env.get(param), progress, base, param)
    return out


def envelope_peak(envelopes, param: str, fallback: float = 0.0) -> float:
    """Peak value of one param over t in [0, 1] (weight estimates).

    Exact for flat/ramp/keys (endpoints), base+amp for LFO (the sine
    peak is always hit with integer loops). Empty spec = clamped fallback.
    """
    lo, hi = ENVELOPE_PARAMS.get(param, (0.0, 100.0))
    spec = normalize_envelope((envelopes or {}).get(param)
                              if isinstance(envelopes, dict) else None, param)
    if spec is None:
        return _clamp(fallback, lo, hi)
    kind = str(spec.get("kind", "off"))
    if kind == "flat":
        return _clamp(spec.get("value", fallback), lo, hi)
    if kind == "ramp":
        v0 = _num(spec.get("v0", fallback), fallback)
        v1 = _num(spec.get("v1", v0), v0)
        return _clamp(max(v0, v1), lo, hi)
    if kind == "lfo":
        base = _num(spec.get("base", fallback), fallback)
        amp = max(0.0, _num(spec.get("amp", 0.0)))
        return _clamp(base + amp, lo, hi)
    if kind == "keys":
        pts = list(spec.get("points", []) or [])
        if not pts:
            return _clamp(fallback, lo, hi)
        return _clamp(max(v for _, v in pts), lo, hi)
    return _clamp(fallback, lo, hi)


def envelopes_signature(envelopes) -> str:
    """Stable short signature for fingerprints (\"off\" when empty)."""
    import hashlib
    import json

    env = normalize_envelopes(envelopes)
    if not env:
        return "off"
    raw = json.dumps(env, sort_keys=True, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


__all__ = ["ENVELOPE_PARAMS", "KINDS", "normalize_envelope",
           "normalize_envelopes", "eval_envelope", "frame_values",
           "envelope_peak", "envelopes_signature"]
