"""TRAKKART export bundle: cover per ratio + 1080p thumb + metadata.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter

from app import __version__
from app.canvas import canvas_size_for


def export_bundle(
    img: Image.Image,
    out_dir: str | Path,
    base: str = "cover",
    meta: dict | None = None,
    vector_svg: str | None = None,
    gif_frames: list[Image.Image] | None = None,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base) or "cover"

    ratio = (meta or {}).get("ratio", "1:1")
    try:
        big_w, big_h = canvas_size_for(ratio, 3000)
        small_w, small_h = canvas_size_for(ratio, 960)
    except KeyError:
        big_w, big_h = (3000, 3000)
        small_w, small_h = (960, 960)

    rgb = img.convert("RGB")
    pcover = out_dir / f"{safe}_cover.png"
    rgb.resize((big_w, big_h), Image.NEAREST).save(str(pcover), "PNG")
    psmall = out_dir / f"{safe}_small.png"
    rgb.resize((small_w, small_h), Image.NEAREST).save(str(psmall), "PNG")

    # 1080p thumb: cover fitted over a blurred background (works for any ratio)
    bg_src = rgb.resize((1920, 1080)).filter(ImageFilter.GaussianBlur(40))
    dim = Image.new("RGB", (1920, 1080), (0, 0, 0))
    bg = Image.blend(bg_src, dim, 0.25)
    r = min(1920 / rgb.width, 1080 / rgb.height)
    nw, nh = max(1, round(rgb.width * r)), max(1, round(rgb.height * r))
    small_fit = rgb.resize((nw, nh), Image.NEAREST)
    bg.paste(small_fit, ((1920 - nw) // 2, (1080 - nh) // 2))
    p1080 = out_dir / f"{safe}_1080p.png"
    bg.save(str(p1080), "PNG")

    info = {
        "app": "TRAKKART",
        "version": __version__,
        "base": safe,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": [pcover.name, psmall.name, p1080.name],
    }
    if meta:
        info["params"] = meta
    if vector_svg:
        pvec = out_dir / f"{safe}_vector.svg"
        pvec.write_text(vector_svg, encoding="utf-8")
        info["files"].append(pvec.name)
    result: dict[str, Path] = {"cover": pcover, "small": psmall, "thumb_1080p": p1080}
    if vector_svg:
        info["vector"] = {"bytes": len(vector_svg.encode("utf-8"))}
        result["vector"] = pvec
    if gif_frames:
        from app.gif import save_gif

        panim = out_dir / f"{safe}_anim.gif"
        save_gif(gif_frames, panim)
        info["files"].append(panim.name)
        info["gif"] = {"bytes": panim.stat().st_size, "frames": len(gif_frames)}
        result["anim"] = panim
    pmeta = out_dir / f"{safe}_metadata.json"
    pmeta.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    result["metadata"] = pmeta
    return result
