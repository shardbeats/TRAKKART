"""Preview staleness fingerprint (v1.7 Phase C, pure logic, no Qt).

The export service always re-renders fresh, so MP4s can never go stale.
The *preview* can: `win._video_frames` were built for inputs that the
user may have changed since. `clip_fingerprint()` hashes exactly the
inputs that produce those frames (source thumb + preset meta + chain
signature + anim spec); the VIDEO panel compares it on every refresh
and shows a Rebuild badge on mismatch.
"""

from __future__ import annotations

import hashlib
import json


def thumb_hash(img, side: int = 64) -> str:
    """Content hash of a small grayscale thumb (cheap, size-independent)."""
    try:
        small = img.convert("RGB").convert("L").resize((side, side))
        return hashlib.md5(small.tobytes()).hexdigest()[:16]
    except Exception:  # noqa: BLE001
        return "unknown"


def _jsonable(value):
    try:
        return json.loads(json.dumps(value, sort_keys=True, default=str))
    except (TypeError, ValueError):
        return str(value)


def clip_fingerprint(src=None, preset_meta=None, chain=None, spec=None) -> str:
    """Stable fingerprint of everything a preview/MP4 render depends on."""
    try:
        meta = preset_meta() if callable(preset_meta) else preset_meta
    except Exception:  # noqa: BLE001
        meta = None
    payload = {
        "src": thumb_hash(src) if src is not None else None,
        "preset": _jsonable(meta),
        "chain": _jsonable(chain),
        "spec": _jsonable(spec),
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


__all__ = ["clip_fingerprint", "thumb_hash"]
