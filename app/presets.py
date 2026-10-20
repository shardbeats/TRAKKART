"""TRAKKART presets — JSON in presets/ (bundled + user).

Format: {"name", "method", "palette", "pixel_size", "threshold"}.
Bundled ones are created if missing (never overwrite user edits).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.adjust import Adjust
from app.canvas import CROP_MODES, ratio_names
from app.dither import METHODS
from app.fx import normalize_custom_palette, parse_hex
from app.palettes import palette_names

PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"

BUNDLED: dict[str, dict] = {
    "SLIME_FS": {"method": "floyd", "palette": "SLIME", "pixel_size": 2, "threshold": 128},
    "VAPOR_BAYER8": {"method": "bayer8", "palette": "VAPOR", "pixel_size": 3, "threshold": 128},
    "EMBER_BW": {"method": "floyd", "palette": "BW", "pixel_size": 2, "threshold": 128},
    "CRT_HARD": {"method": "bayer4", "palette": "BW", "pixel_size": 4, "threshold": 160},
}


@dataclass
class Preset:
    name: str = ""
    method: str = "bayer4"
    palette: str = "SLIME"
    pixel_size: int = 2
    threshold: int = 128
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    ratio: str = "1:1"
    crop_mode: str = "cover"
    focus_x: float = 50.0
    focus_y: float = 50.0
    crop_zoom: float = 1.0
    pre_blur: float = 0.0
    pre_sharpen: int = 0
    pre_hue: float = 0.0
    pre_denoise: int = 0
    pre_smooth: float = 0.0
    glow_radius: float = 0.0
    glow_intensity: float = 0.0
    grain: float = 0.0
    vignette: float = 0.0
    scanlines: int = 0
    replace_color: str = ""
    custom_palette: list | None = None
    vector_export: bool = False
    vector_cell: int = 8
    glitch_chroma: int = 0
    glitch_slice_bands: int = 0
    glitch_slice_max: int = 24
    gif_export: bool = False
    gif_frames: int = 6
    gif_mode: str = "both"
    export_size: int = 3000  # lado largo px de la imagen principal
    export_format: str = "png"  # png | jpg | webp
    export_quality: int = 90  # solo jpg/webp, 1-100

    def validate(self) -> None:
        if self.method not in METHODS:
            raise ValueError(f"invalid method: {self.method}")
        if self.palette not in palette_names():
            raise ValueError(f"invalid palette: {self.palette}")
        if not 1 <= int(self.pixel_size) <= 8:
            raise ValueError(f"pixel_size out of range 1-8: {self.pixel_size}")
        if not 1 <= int(self.threshold) <= 254:
            raise ValueError(f"threshold out of range 1-254: {self.threshold}")
        Adjust(
            brightness=float(self.brightness),
            contrast=float(self.contrast),
            saturation=float(self.saturation),
        ).validate()
        if self.ratio not in ratio_names():
            raise ValueError(f"invalid ratio: {self.ratio}")
        if self.crop_mode not in CROP_MODES:
            raise ValueError(f"invalid crop_mode: {self.crop_mode}")
        for name in ("focus_x", "focus_y"):
            v = float(getattr(self, name))
            if not 0.0 <= v <= 100.0:
                raise ValueError(f"{name} out of range 0-100: {v}")
        if not 1.0 <= float(self.crop_zoom) <= 4.0:
            raise ValueError(f"crop_zoom out of range 1-4: {self.crop_zoom}")
        if not 0.0 <= float(self.pre_blur) <= 5.0:
            raise ValueError(f"pre_blur out of range 0-5: {self.pre_blur}")
        if int(self.pre_sharpen) not in (0, 1, 2, 3):
            raise ValueError(f"pre_sharpen out of range 0-3: {self.pre_sharpen}")
        if not -180.0 <= float(self.pre_hue) <= 180.0:
            raise ValueError(f"pre_hue out of range -180-180: {self.pre_hue}")
        if int(self.pre_denoise) not in (0, 1, 2, 3, 4, 5):
            raise ValueError(f"pre_denoise out of range 0-5: {self.pre_denoise}")
        if not 0.0 <= float(self.pre_smooth) <= 5.0:
            raise ValueError(f"pre_smooth out of range 0-5: {self.pre_smooth}")
        if not 0.0 <= float(self.glow_radius) <= 50.0:
            raise ValueError(f"glow_radius out of range 0-50: {self.glow_radius}")
        for name in ("glow_intensity", "grain", "vignette"):
            v = float(getattr(self, name))
            if not 0.0 <= v <= 100.0:
                raise ValueError(f"{name} out of range 0-100: {v}")
        if int(self.scanlines) not in (0, 2, 3, 4, 6, 8):
            raise ValueError(f"scanlines must be 0,2,3,4,6 or 8: {self.scanlines}")
        if self.replace_color and parse_hex(self.replace_color) is None:
            raise ValueError(f"replace_color is not #RRGGBB hex: {self.replace_color!r}")
        normalize_custom_palette(self.custom_palette)
        if int(self.vector_cell) not in range(4, 17):
            raise ValueError(f"vector_cell out of range 4-16: {self.vector_cell}")
        if not 0 <= int(self.glitch_chroma) <= 20:
            raise ValueError(f"glitch_chroma out of range 0-20: {self.glitch_chroma}")
        if int(self.glitch_slice_bands) not in (0, 2, 3, 4, 6, 8, 12, 16):
            raise ValueError(f"invalid glitch_slice_bands: {self.glitch_slice_bands}")
        if not 0 <= int(self.glitch_slice_max) <= 64:
            raise ValueError(f"glitch_slice_max out of range 0-64: {self.glitch_slice_max}")
        if int(self.gif_frames) not in (2, 3, 4, 5, 6, 7, 8):
            raise ValueError(f"gif_frames out of range 2-8: {self.gif_frames}")
        if self.gif_mode not in ("phase", "hue", "both"):
            raise ValueError(f"invalid gif_mode: {self.gif_mode}")
        if not 64 <= int(self.export_size) <= 8000:
            raise ValueError(f"export_size out of range 64-8000: {self.export_size}")
        if str(self.export_format) not in ("png", "jpg", "webp"):
            raise ValueError(f"invalid export_format: {self.export_format!r}")
        if not 1 <= int(self.export_quality) <= 100:
            raise ValueError(f"export_quality out of range 1-100: {self.export_quality}")

    def to_dict(self) -> dict:
        import copy

        d = asdict(self)
        d["pixel_size"] = int(d["pixel_size"])
        d["threshold"] = int(d["threshold"])
        d["pre_sharpen"] = int(d["pre_sharpen"])
        d["pre_denoise"] = int(d["pre_denoise"])
        d["scanlines"] = int(d["scanlines"])
        d["vector_cell"] = int(d["vector_cell"])
        d["vector_export"] = bool(d["vector_export"])
        d["glitch_chroma"] = int(d["glitch_chroma"])
        d["glitch_slice_bands"] = int(d["glitch_slice_bands"])
        d["glitch_slice_max"] = int(d["glitch_slice_max"])
        d["gif_frames"] = int(d["gif_frames"])
        d["gif_export"] = bool(d["gif_export"])
        d["export_size"] = int(d["export_size"])
        d["export_format"] = str(d["export_format"])
        d["export_quality"] = int(d["export_quality"])
        for k in ("brightness", "contrast", "saturation", "focus_x", "focus_y",
                  "crop_zoom",
                  "pre_blur", "pre_hue", "pre_smooth",
                  "glow_radius", "glow_intensity", "grain", "vignette"):
            d[k] = float(d[k])
        d["custom_palette"] = copy.deepcopy(d["custom_palette"])
        return d

    @staticmethod
    def from_dict(d: dict) -> "Preset":
        p = Preset(
            name=str(d.get("name", "")),
            method=str(d.get("method", "bayer4")),
            palette=str(d.get("palette", "SLIME")),
            pixel_size=int(d.get("pixel_size", 2)),
            threshold=int(d.get("threshold", 128)),
            brightness=float(d.get("brightness", 1.0)),
            contrast=float(d.get("contrast", 1.0)),
            saturation=float(d.get("saturation", 1.0)),
            ratio=str(d.get("ratio", "1:1")),
            crop_mode=str(d.get("crop_mode", "cover")),
            focus_x=float(d.get("focus_x", 50.0)),
            focus_y=float(d.get("focus_y", 50.0)),
            crop_zoom=float(d.get("crop_zoom", 1.0)),
            pre_blur=float(d.get("pre_blur", 0.0)),
            pre_sharpen=int(d.get("pre_sharpen", 0)),
            pre_hue=float(d.get("pre_hue", 0.0)),
            pre_denoise=int(d.get("pre_denoise", 0)),
            pre_smooth=float(d.get("pre_smooth", 0.0)),
            glow_radius=float(d.get("glow_radius", 0.0)),
            glow_intensity=float(d.get("glow_intensity", 0.0)),
            grain=float(d.get("grain", 0.0)),
            vignette=float(d.get("vignette", 0.0)),
            scanlines=int(d.get("scanlines", 0)),
            replace_color=str(d.get("replace_color", "")),
            custom_palette=d.get("custom_palette"),
            vector_export=bool(d.get("vector_export", False)),
            vector_cell=int(d.get("vector_cell", 8)),
            glitch_chroma=int(d.get("glitch_chroma", 0)),
            glitch_slice_bands=int(d.get("glitch_slice_bands", 0)),
            glitch_slice_max=int(d.get("glitch_slice_max", 24)),
            gif_export=bool(d.get("gif_export", False)),
            gif_frames=int(d.get("gif_frames", 6)),
            gif_mode=str(d.get("gif_mode", "both")),
            export_size=int(d.get("export_size", 3000)),
            export_format=str(d.get("export_format", "png")),
            export_quality=int(d.get("export_quality", 90)),
        )
        p.validate()
        return p

    def adjust(self) -> Adjust:
        return Adjust(brightness=float(self.brightness), contrast=float(self.contrast), saturation=float(self.saturation))

    def to_render_kwargs(self, phase: int = 0) -> dict:
        """Kwargs de pipeline.render(). Única conversión (ver render_params)."""
        from app.render_params import preset_to_render_kwargs

        return preset_to_render_kwargs(self, phase=phase)

    def meta(self) -> dict:
        from app.pipeline import meta_dict

        m = meta_dict(
            self.method, self.palette, float(self.threshold), int(self.pixel_size),
            self.adjust(), self.ratio, self.crop_mode, float(self.focus_x), float(self.focus_y),
            float(self.crop_zoom),
            float(self.pre_blur), int(self.pre_sharpen),
            float(self.pre_hue), int(self.pre_denoise), float(self.pre_smooth),
            float(self.glow_radius), float(self.glow_intensity),
            float(self.grain), float(self.vignette), int(self.scanlines),
            self.replace_color, self.custom_palette,
            glitch_chroma=int(self.glitch_chroma),
            glitch_slice_bands=int(self.glitch_slice_bands),
            glitch_slice_max=int(self.glitch_slice_max),
            vector_export=bool(self.vector_export),
            vector_cell=int(self.vector_cell),
            gif_export=bool(self.gif_export),
            gif_frames=int(self.gif_frames),
            gif_mode=self.gif_mode,
        )
        m["export"] = {
            "size": int(self.export_size),
            "format": str(self.export_format),
            "quality": int(self.export_quality),
        }
        return m


def _safe_name(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    return safe or "preset"


def ensure_bundled(presets_dir: Path | None = None) -> list[str]:
    """Create missing bundled presets. Returns created names."""
    d = Path(presets_dir) if presets_dir else PRESETS_DIR
    d.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name, params in BUNDLED.items():
        path = d / f"{name}.json"
        if not path.exists():
            p = Preset(name=name, **params)
            p.validate()
            path.write_text(json.dumps(p.to_dict(), indent=2), encoding="utf-8")
            created.append(name)
    return created


def save_preset(preset: Preset, presets_dir: Path | None = None) -> Path:
    preset.validate()
    if not preset.name.strip():
        raise ValueError("preset needs a name")
    d = Path(presets_dir) if presets_dir else PRESETS_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_safe_name(preset.name)}.json"
    path.write_text(json.dumps(preset.to_dict(), indent=2), encoding="utf-8")
    return path


def load_preset(name: str, presets_dir: Path | None = None) -> Preset:
    d = Path(presets_dir) if presets_dir else PRESETS_DIR
    base = name[:-5] if name.endswith(".json") else name
    path = d / f"{base}.json"
    if not path.exists():
        raise FileNotFoundError(f"preset does not exist: {name}")
    return Preset.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_presets(presets_dir: Path | None = None) -> list[str]:
    d = Path(presets_dir) if presets_dir else PRESETS_DIR
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def delete_preset(name: str, presets_dir: Path | None = None) -> bool:
    d = Path(presets_dir) if presets_dir else PRESETS_DIR
    base = name[:-5] if name.endswith(".json") else name
    path = d / f"{base}.json"
    if path.exists():
        path.unlink()
        return True
    return False
