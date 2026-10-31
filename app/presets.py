"""TRAKKART presets — JSON in presets/ (bundled + user).

Format: {"name", "method", "palette", "pixel_size", "threshold"}.
Bundled ones are created if missing (never overwrite user edits).
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.adjust import Adjust
from app.canvas import CROP_MODES, CUSTOM_RATIO, ratio_names
from app.dither import METHODS
from app.fx import normalize_custom_palette, parse_hex
from app.gif import GIF_MODES
from app.palettes import palette_names

PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"

_BUNDLED_DIR = PRESETS_DIR  # repo copy (frozen: _MEIPASS, read-only seed)


def _user_dir() -> Path:
    """Writable user dir (data/presets). Frozen-safe; explicit arg wins."""
    from app.paths import get_presets_dir

    return get_presets_dir()


def _default_dir() -> Path:
    # Test seam: a monkeypatched PRESETS_DIR keeps working as the default.
    if PRESETS_DIR != _BUNDLED_DIR:
        return Path(PRESETS_DIR)
    return _user_dir()


BUNDLED: dict[str, dict] = {
    "SLIME_FS": {"method": "floyd", "palette": "SLIME", "pixel_size": 2, "threshold": 128},
    "VAPOR_BAYER8": {"method": "bayer8", "palette": "VAPOR", "pixel_size": 3, "threshold": 128},
    "EMBER_BW": {"method": "floyd", "palette": "BW", "pixel_size": 2, "threshold": 128},
    "CRT_HARD": {"method": "bayer4", "palette": "BW", "pixel_size": 4, "threshold": 160},
    "ASH_WIND": {"method": "bayer8", "palette": "BW", "pixel_size": 3, "threshold": 128,
                 "dissolve_mode": "wind", "dissolve_amount": 1.0, "dissolve_seed": 53596,
                 "dissolve_wind_x": 140.0, "dissolve_wind_y": -50.0, "dissolve_speed": 1.0},
    "DUST_RANDOM": {"method": "floyd", "palette": "BW", "pixel_size": 2, "threshold": 128,
                    "dissolve_mode": "random", "dissolve_amount": 1.0, "dissolve_seed": 12345,
                    "dissolve_speed": 1.0},
}


# ---------------------------------------------------------------------------
# Declarative field schema: single source for validate/to_dict/from_dict.
# Adding a field = 1 @dataclass line + 1 line here (was: 5 edits).
# kind: int|float|str|bool|colors. rule: ("range", lo, hi) | ("oneof", values|key)
#        | ("hex",) | ("hexreq",) | ("palette",) | () = no check.
# Dynamic oneof keys: METHODS, PALETTES, RATIOS, CROPS, GIFMODES.
# ---------------------------------------------------------------------------
def _canvas_ratios():
    from app.canvas import CUSTOM_RATIO, ratio_names

    return [*ratio_names(), CUSTOM_RATIO]


_DYNAMIC_CHOICES = {
    "METHODS": lambda: METHODS,
    "PALETTES": palette_names,
    "RATIOS": ratio_names,
    "CANVAS_RATIOS": _canvas_ratios,
    "CROPS": lambda: CROP_MODES,
    "GIFMODES": lambda: GIF_MODES,
}


@dataclass(frozen=True)
class _Field:
    name: str
    kind: str
    rule: tuple = ()

    def _oneof_values(self):
        key = self.rule[1]
        vals = _DYNAMIC_CHOICES[key]() if isinstance(key, str) else key
        return tuple(vals)

    def check_value(self, value) -> None:
        if not self.rule:
            return
        kind = self.rule[0]
        if kind == "range":
            _, lo, hi = self.rule
            v = float(value)
            if not lo <= v <= hi:
                raise ValueError(f"{self.name} out of range {lo:g}-{hi:g}: {value}")
        elif kind == "range0":
            # 0 = auto (follows ratio+export_size); else, normal range.
            _, lo, hi = self.rule
            v = float(value)
            if v != 0 and not lo <= v <= hi:
                raise ValueError(f"{self.name} out of range 0 or {lo:g}-{hi:g}: {value}")
        elif kind == "oneof":
            vals = self._oneof_values()
            ok = str(value) in [str(x) for x in vals] if self.kind == "str" else value in vals
            # numerics with bool: int(True)==1, avoided by comparing types via int()
            if not ok and self.kind == "int":
                try:
                    ok = int(value) in [int(x) for x in vals]
                except (TypeError, ValueError):
                    ok = False
            if not ok:
                raise ValueError(f"invalid {self.name}: {value!r}")
        elif kind == "hex":
            if value and parse_hex(value) is None:
                raise ValueError(f"{self.name} is not #RRGGBB hex: {value!r}")
        elif kind == "hexreq":
            if parse_hex(value) is None:
                raise ValueError(f"{self.name} is not #RRGGBB hex: {value!r}")
        elif kind == "palette":
            normalize_custom_palette(value)
        else:  # pragma: no cover - tabla cerrada
            raise ValueError(f"unknown rule: {kind}")


FIELDS: tuple[_Field, ...] = (
    _Field("name", "str"),
    _Field("method", "str", ("oneof", "METHODS")),
    _Field("palette", "str", ("oneof", "PALETTES")),
    _Field("pixel_size", "int", ("range", 1, 8)),
    _Field("threshold", "int", ("range", 1, 254)),
    _Field("brightness", "float", ("range", 0.0, 3.0)),
    _Field("contrast", "float", ("range", 0.0, 3.0)),
    _Field("saturation", "float", ("range", 0.0, 3.0)),
    _Field("midtones", "float", ("range", 0.0, 2.0)),
    _Field("highlights", "float", ("range", -100.0, 100.0)),
    _Field("palette_depth", "int", ("range", 0, 16)),
    _Field("ratio", "str", ("oneof", "CANVAS_RATIOS")),
    _Field("canvas_w", "int", ("range0", 64, 8000)),
    _Field("canvas_h", "int", ("range0", 64, 8000)),
    _Field("crop_mode", "str", ("oneof", "CROPS")),
    _Field("focus_x", "float", ("range", 0.0, 100.0)),
    _Field("focus_y", "float", ("range", 0.0, 100.0)),
    _Field("crop_zoom", "float", ("range", 1.0, 4.0)),
    _Field("pre_blur", "float", ("range", 0.0, 5.0)),
    _Field("pre_sharpen", "int", ("oneof", (0, 1, 2, 3))),
    _Field("pre_hue", "float", ("range", -180.0, 180.0)),
    _Field("pre_denoise", "int", ("oneof", (0, 1, 2, 3, 4, 5))),
    _Field("pre_smooth", "float", ("range", 0.0, 5.0)),
    _Field("glow_radius", "float", ("range", 0.0, 50.0)),
    _Field("glow_intensity", "float", ("range", 0.0, 100.0)),
    _Field("grain", "float", ("range", 0.0, 100.0)),
    _Field("vignette", "float", ("range", 0.0, 100.0)),
    _Field("scanlines", "int", ("oneof", (0, 2, 3, 4, 6, 8))),
    _Field("replace_color", "str", ("hex",)),
    _Field("custom_palette", "colors", ("palette",)),
    _Field("vector_export", "bool"),
    _Field("vector_cell", "int", ("range", 4, 16)),
    _Field("vector_black", "bool"),
    _Field("glitch_chroma", "int", ("range", 0, 20)),
    _Field("glitch_slice_bands", "int", ("oneof", (0, 2, 3, 4, 6, 8, 12, 16))),
    _Field("glitch_slice_max", "int", ("range", 0, 64)),
    _Field("gif_export", "bool"),
    _Field("gif_frames", "int", ("range", 2, 64)),
    _Field("gif_mode", "str", ("oneof", "GIFMODES")),
    _Field("gif_fps", "int", ("range", 2, 60)),
    _Field("gif_size", "int", ("range", 64, 8000)),
    _Field("gif_pingpong", "bool"),
    _Field("motion_amount", "float", ("range", 0.0, 3.0)),
    _Field("export_size", "int", ("range", 64, 8000)),
    _Field("export_format", "str", ("oneof", ("png", "jpg", "webp"))),
    _Field("export_quality", "int", ("range", 1, 100)),
    _Field("duotone_dark", "str", ("hex",)),
    _Field("duotone_light", "str", ("hex",)),
    _Field("duotone_mid", "float", ("range", 0.0, 100.0)),
    _Field("posterize", "int", ("oneof", (0, 2, 3, 4, 5, 6, 7, 8))),
    _Field("split_tone", "float", ("range", 0.0, 100.0)),
    _Field("fade", "float", ("range", 0.0, 100.0)),
    _Field("glow_threshold", "int", ("range", 0, 255)),
    _Field("halftone", "int", ("oneof", (0, *range(3, 13)))),
    _Field("halftone_shape", "str", ("oneof", ("dots", "lines"))),
    _Field("dust", "float", ("range", 0.0, 100.0)),
    _Field("border", "int", ("range", 0, 64)),
    _Field("border_color", "str", ("hexreq",)),
    _Field("letterbox", "int", ("range", 0, 25)),
    _Field("pixelsort", "int", ("range", 0, 255)),
    _Field("wave", "int", ("range", 0, 30)),
    _Field("mosh", "float", ("range", 0.0, 100.0)),
    _Field("mosh_mode", "str", ("oneof", (
        "blocks", "smear", "ghost", "rows", "chroma", "crush", "speckle"))),
    _Field("mosh_seed", "int", ("range", 0, 99)),
    _Field("mosh_size", "int", ("range", 10, 200)),
    _Field("grille", "int", ("oneof", (0, 2, 3))),
    _Field("jpeg", "float", ("range", 0.0, 100.0)),
    _Field("post_blur", "float", ("range", 0.0, 5.0)),
    _Field("post_sharpen", "int", ("oneof", (0, 1, 2, 3))),
    _Field("fx_stack", "stack"),
    _Field("motif", "stack"),
    _Field("drift_pattern", "str", ("oneof", (
        "off", "hum_bar", "roll", "crawl", "snow",
        "weave", "flicker", "moire", "sweep", "jitter"))),
    _Field("drift_amount", "float", ("range", 0.0, 100.0)),
    _Field("drift_speed", "float", ("range", 0.25, 4.0)),
    _Field("drift_position", "float", ("range", 0.0, 100.0)),
    _Field("dissolve_amount", "float", ("range", 0.0, 2.0)),
    _Field("dissolve_seed", "int", ("range", 0, 999999)),
    _Field("dissolve_wind_x", "float", ("range", -500.0, 500.0)),
    _Field("dissolve_wind_y", "float", ("range", -500.0, 500.0)),
    _Field("dissolve_mode", "str", ("oneof", ("wind", "random"))),
    _Field("dissolve_speed", "float", ("range", 0.25, 4.0)),
    _Field("dissolve_hold", "float", ("range", 0.0, 3.0)),
    _Field("dissolve_length", "float", ("range", 0.5, 32.0)),
    _Field("paste_mode", "str", ("oneof", ("off", "paper", "riso", "fiber"))),
    _Field("paste_opacity", "float", ("range", 0.0, 100.0)),
    _Field("paste_blend", "str", ("oneof", ("overlay", "multiply", "screen"))),
)


def _coerce(kind: str, value):
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "str":
        return str(value)
    if kind == "bool":
        return bool(value)
    return value  # colors/stack: passthrough (validates, no transform)


def _field_default(name: str):
    return Preset.__dataclass_fields__[name].default


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
    midtones: float = 1.0
    highlights: float = 0.0
    palette_depth: int = 0
    ratio: str = "1:1"
    canvas_w: int = 0  # 0 = auto from ratio+export_size; UI and from_dict keep concrete values
    canvas_h: int = 0
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
    vector_black: bool = False  # v1.3: black ink only over transparent (print)
    glitch_chroma: int = 0
    glitch_slice_bands: int = 0
    glitch_slice_max: int = 24
    gif_export: bool = False
    gif_frames: int = 6
    gif_mode: str = "both"
    gif_fps: int = 8
    gif_size: int = 1200  # single anim: used by the VIDEO preview and the exported GIF
    gif_pingpong: bool = False
    motion_amount: float = 1.0  # animation intensity: 0 = freeze, 1 = legacy, up to 3
    export_size: int = 3000  # long side px of the main image
    export_format: str = "png"  # png | jpg | webp
    export_quality: int = 90  # jpg/webp only, 1-100
    # -- grade (pack A) --
    duotone_dark: str = ""  # #RRGGBB or "" = off (needs duotone_light)
    duotone_light: str = ""
    duotone_mid: float = 50.0  # cut 0-100
    posterize: int = 0  # 0 = off, 2-8 levels
    split_tone: float = 0.0  # 0-100
    fade: float = 0.0  # 0-100
    glow_threshold: int = 0  # 0-255, 0 = everything glows
    # -- texture/decay (pack B) --
    halftone: int = 0  # 0 = off, else 3-12 px per cell
    halftone_shape: str = "dots"  # dots | lines
    dust: float = 0.0  # 0-100
    border: int = 0  # 0-64 px, 0 = off
    border_color: str = "#000000"
    letterbox: int = 0  # 0-25 % per side, 0 = off
    # -- extra glitch (pack C) --
    pixelsort: int = 0  # luminance threshold 0-255, 0 = off
    wave: int = 0  # px amplitude 0-30, 0 = off
    mosh: float = 0.0  # 0-100
    mosh_mode: str = "blocks"  # datamosh flavor (app/mosh.py)
    mosh_seed: int = 0  # variation 0-99 (re-rolls the damage)
    mosh_size: int = 100  # feature scale % (100 = classic)
    grille: int = 0  # 0 = off, 2 | 3
    # -- v1.2 stackable FX --
    jpeg: float = 0.0  # JPEG glitch 0-100, 0 = off
    post_blur: float = 0.0  # post blur 0.0-5.0 (post-dither, in stack)
    post_sharpen: int = 0  # post sharpen 0-3 (post-dither, in stack)
    fx_stack: list | None = None  # None = legacy order; else [{id, enabled}]
    # -- v1.3 motif --
    motif: dict | None = None  # None = default_config(); {"bands": [{shape, size}x4]}
    # -- v1.4 signal drift + paste-up --
    drift_pattern: str = "off"  # Signal Drift pattern pre-dither
    drift_amount: float = 0.0  # 0-100, 0 = off
    drift_speed: float = 1.0  # traversals per clip 0.25-4.0
    drift_position: float = 50.0  # still freeze 0-100 (50 = mid-traverse)
    # -- v1.6 particle disperse (solo dispersion) --
    dissolve_amount: float = 1.0  # 0-2, 0 = off (identity)
    dissolve_seed: int = 53596  # deterministic pattern
    dissolve_wind_x: float = 120.0  # px at full disperse
    dissolve_wind_y: float = -40.0  # px at full disperse
    dissolve_mode: str = "wind"  # wind | random
    dissolve_speed: float = 1.0  # traversals per clip 0.25-4.0
    dissolve_hold: float = 1.0  # still pause per end, seconds 0-3
    dissolve_length: float = 5.0  # sacred total clip length, seconds
    paste_mode: str = "off"  # paper | riso | fiber overlay post-dither
    paste_opacity: float = 0.0  # 0-100, 0 = off
    paste_blend: str = "overlay"  # overlay | multiply | screen

    def validate(self) -> None:
        for spec in FIELDS:
            spec.check_value(getattr(self, spec.name))
        if self.ratio == CUSTOM_RATIO and not (
                64 <= int(self.canvas_w or 0) <= 8000
                and 64 <= int(self.canvas_h or 0) <= 8000):
            raise ValueError(
                f"custom canvas needs concrete W/H 64-8000: "
                f"{self.canvas_w}x{self.canvas_h}")

    def to_dict(self) -> dict:
        d = asdict(self)
        for spec in FIELDS:
            if spec.kind in ("colors", "stack"):
                d[spec.name] = copy.deepcopy(d[spec.name])
            else:
                d[spec.name] = _coerce(spec.kind, d[spec.name])
        return d

    @staticmethod
    def from_dict(d: dict) -> "Preset":
        data = dict(d)
        if "canvas_w" not in data or "canvas_h" not in data:
            # Migration: old presets (ratio + export_size) -> concrete W/H.
            from app.canvas import doc_dimensions

            try:
                w, h = doc_dimensions(
                    str(data.get("ratio", "1:1")), int(data.get("export_size", 3000)),
                    int(data.get("canvas_w", 0) or 0), int(data.get("canvas_h", 0) or 0),
                )
            except (ValueError, KeyError):
                w, h = (3000, 3000)
            data.setdefault("canvas_w", w)
            data.setdefault("canvas_h", h)
        kwargs = {
            spec.name: _coerce(spec.kind, data.get(spec.name, _field_default(spec.name)))
            if spec.kind not in ("colors", "stack")
            else copy.deepcopy(data.get(spec.name, _field_default(spec.name)))
            for spec in FIELDS
        }
        p = Preset(**kwargs)
        p.validate()
        return p

    def adjust(self) -> Adjust:
        return Adjust(
            brightness=float(self.brightness),
            contrast=float(self.contrast),
            saturation=float(self.saturation),
            midtones=float(getattr(self, "midtones", 1.0)),
            highlights=float(getattr(self, "highlights", 0.0)),
        )

    def to_render_kwargs(self, phase: int = 0) -> dict:
        """pipeline.render() kwargs. Single conversion (see render_params)."""
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
            canvas_w=int(getattr(self, "canvas_w", 0) or 0),
            canvas_h=int(getattr(self, "canvas_h", 0) or 0),
            vector_export=bool(self.vector_export),
            vector_cell=int(self.vector_cell),
            gif_export=bool(self.gif_export),
            gif_frames=int(self.gif_frames),
            gif_mode=self.gif_mode,
            gif_fps=int(getattr(self, "gif_fps", 8)),
            gif_size=int(getattr(self, "gif_size", 1200)),
            gif_pingpong=bool(getattr(self, "gif_pingpong", False)),
        )
        m["export"] = {
            "size": int(self.export_size),
            "format": str(self.export_format),
            "quality": int(self.export_quality),
        }
        m["grade"] = {
            "duotone": [self.duotone_dark, self.duotone_light, float(self.duotone_mid)],
            "posterize": int(self.posterize),
            "split_tone": float(self.split_tone),
            "fade": float(self.fade),
            "glow_threshold": int(self.glow_threshold),
        }
        m["texture"] = {
            "halftone": int(self.halftone),
            "halftone_shape": str(self.halftone_shape),
            "dust": float(self.dust),
            "border": int(self.border),
            "border_color": str(self.border_color),
            "letterbox": int(self.letterbox),
        }
        m["glitch"]["pixelsort"] = int(self.pixelsort)
        m["glitch"]["wave"] = int(self.wave)
        m["glitch"]["mosh"] = float(self.mosh)
        m["glitch"]["mosh_mode"] = str(getattr(self, "mosh_mode", "blocks"))
        m["glitch"]["mosh_seed"] = int(getattr(self, "mosh_seed", 0) or 0)
        m["glitch"]["mosh_size"] = int(getattr(self, "mosh_size", 100) or 100)
        m["glitch"]["grille"] = int(self.grille)
        m["glitch"]["jpeg"] = float(getattr(self, "jpeg", 0.0) or 0.0)
        m["post"] = {
            "blur": float(getattr(self, "post_blur", 0.0) or 0.0),
            "sharpen": int(getattr(self, "post_sharpen", 0) or 0),
        }
        m["gif"]["motion_amount"] = float(getattr(self, "motion_amount", 1.0))
        m["dissolve"] = {
            "amount": float(getattr(self, "dissolve_amount", 1.0)),
            "seed": int(getattr(self, "dissolve_seed", 53596) or 0),
            "mode": str(getattr(self, "dissolve_mode", "wind") or "wind"),
            "speed": float(getattr(self, "dissolve_speed", 1.0) or 1.0),
            "wind_x": float(getattr(self, "dissolve_wind_x", 120.0) or 0.0),
            "wind_y": float(getattr(self, "dissolve_wind_y", -40.0) or 0.0),
            "hold": float(getattr(self, "dissolve_hold", 1.0) or 0.0),
            "length": float(getattr(self, "dissolve_length", 5.0) or 5.0),
        }
        m["fx_stack"] = copy.deepcopy(getattr(self, "fx_stack", None))
        m["motif"] = copy.deepcopy(getattr(self, "motif", None))
        return m


def _safe_name(name: str) -> str:
    from app.names import safe_stem

    return safe_stem(name, "preset")


# Fail-fast guard: the schema covers exactly the dataclass fields.
assert {f.name for f in FIELDS} == set(Preset.__dataclass_fields__), (
    "FIELDS out of sync with Preset"
)


def ensure_bundled(presets_dir: Path | None = None) -> list[str]:
    """Create missing bundled presets. Returns created names."""
    d = Path(presets_dir) if presets_dir else _default_dir()
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
    d = Path(presets_dir) if presets_dir else _default_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_safe_name(preset.name)}.json"
    path.write_text(json.dumps(preset.to_dict(), indent=2), encoding="utf-8")
    return path


def load_preset(name: str, presets_dir: Path | None = None) -> Preset:
    base = name[:-5] if name.endswith(".json") else name
    if presets_dir is not None:
        d = Path(presets_dir)
        path = d / f"{base}.json"
        if not path.exists():
            raise FileNotFoundError(f"preset does not exist: {name}")
        return Preset.from_dict(json.loads(path.read_text(encoding="utf-8")))
    # User dir first (own edits shadow bundled), repo copy as fallback.
    if presets_dir is not None:
        search = [Path(presets_dir)]
    elif PRESETS_DIR != _BUNDLED_DIR:
        search = [Path(PRESETS_DIR)]  # test seam
    else:
        search = [_user_dir(), PRESETS_DIR]
    for d in search:
        path = d / f"{base}.json"
        if path.exists():
            return Preset.from_dict(json.loads(path.read_text(encoding="utf-8")))
    raise FileNotFoundError(f"preset does not exist: {name}")


def _stems(d: Path) -> list[str]:
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def list_presets(presets_dir: Path | None = None) -> list[str]:
    if presets_dir is not None:
        return _stems(Path(presets_dir))
    if PRESETS_DIR != _BUNDLED_DIR:
        return _stems(Path(PRESETS_DIR))  # test seam
    return sorted(set(_stems(_user_dir())) | set(_stems(PRESETS_DIR)))


def delete_preset(name: str, presets_dir: Path | None = None) -> bool:
    base = name[:-5] if name.endswith(".json") else name
    if presets_dir is not None:
        dirs = [Path(presets_dir)]
    elif PRESETS_DIR != _BUNDLED_DIR:
        dirs = [Path(PRESETS_DIR)]  # test seam
    else:
        dirs = [_user_dir(), PRESETS_DIR]
    for d in dirs:
        path = d / f"{base}.json"
        if path.exists():
            path.unlink()
            return True
    return False


def preset_from_metadata(data: dict, name: str | None = None) -> "Preset":
    """Build a Preset from an export _metadata.json dict (nested params).

    Metadata is an export record, not a preset: params are nested
    (params.glitch.mosh, params.gif.frames...) and palette may be
    "custom" with a custom_palette list. Missing keys fall back to
    Preset defaults via from_dict (old exports predate drift fields).
    """
    from app.palettes import palette_names

    if not isinstance(data, dict):
        raise ValueError("metadata must be a JSON object")
    params = data.get("params")
    if not isinstance(params, dict):
        raise ValueError("not a TRAKKART metadata file (missing params)")

    def _get(d: dict, key: str, default=None):
        v = d.get(key, default) if isinstance(d, dict) else default
        return default if v is None else v

    adjust = _get(params, "adjust", {}) or {}
    canvas = _get(params, "canvas", {}) or {}
    focus = _get(params, "focus", [50.0, 50.0]) or [50.0, 50.0]
    pre = _get(params, "pre", {}) or {}
    post = _get(params, "post", {}) or {}
    glitch = _get(params, "glitch", {}) or {}
    gif = _get(params, "gif", {}) or {}
    export = _get(params, "export", {}) or _get(data, "export", {}) or {}
    grade = _get(params, "grade", {}) or {}
    texture = _get(params, "texture", {}) or {}
    fx = _get(params, "fx", {}) or {}
    dissolve = _get(params, "dissolve", {}) or {}
    duotone = _get(grade, "duotone", ["", "", 50.0]) or ["", "", 50.0]

    raw_palette = str(_get(params, "palette", "SLIME") or "SLIME")
    names = set(palette_names())
    palette = raw_palette if raw_palette in names else "SLIME"
    try:
        focus_x = float(focus[0])
    except (TypeError, IndexError, ValueError):
        focus_x = 50.0
    try:
        focus_y = float(focus[1])
    except (TypeError, IndexError, ValueError):
        focus_y = 50.0
    try:
        duo_dark = str(duotone[0] or "")
        duo_light = str(duotone[1] or "")
        duo_mid = float(duotone[2])
    except (TypeError, IndexError, ValueError):
        duo_dark, duo_light, duo_mid = "", "", 50.0

    flat: dict = {
        "name": str(name or data.get("base") or "imported_metadata"),
        "method": str(_get(params, "method", "bayer4") or "bayer4"),
        "palette": palette,
        "pixel_size": _get(params, "pixel_size", 2),
        "threshold": _get(params, "threshold", 128),
        "brightness": _get(adjust, "brightness", 1.0),
        "contrast": _get(adjust, "contrast", 1.0),
        "saturation": _get(adjust, "saturation", 1.0),
        "midtones": _get(adjust, "midtones", 1.0),
        "highlights": _get(adjust, "highlights", 0.0),
        "palette_depth": _get(params, "palette_depth", 0),
        "ratio": str(_get(params, "ratio", "1:1") or "1:1"),
        "canvas_w": _get(canvas, "w", 0),
        "canvas_h": _get(canvas, "h", 0),
        "crop_mode": str(_get(params, "crop_mode", "cover") or "cover"),
        "focus_x": focus_x,
        "focus_y": focus_y,
        "crop_zoom": _get(params, "zoom", 1.0),
        "pre_blur": _get(pre, "blur", 0.0),
        "pre_sharpen": _get(pre, "sharpen", 0),
        "pre_hue": _get(pre, "hue", 0.0),
        "pre_denoise": _get(pre, "denoise", 0),
        "pre_smooth": _get(pre, "smooth", 0.0),
        "custom_palette": _get(params, "custom_palette", None),
        "glitch_chroma": _get(glitch, "chroma", 0),
        "glitch_slice_bands": _get(glitch, "slice_bands", 0),
        "glitch_slice_max": _get(glitch, "slice_max", 24),
        "gif_export": bool(_get(gif, "export", False)),
        "gif_frames": _get(gif, "frames", 6),
        "gif_mode": str(_get(gif, "mode", "both") or "both"),
        "gif_fps": _get(gif, "fps", 8),
        "gif_size": _get(gif, "size", 1200),
        "gif_pingpong": bool(_get(gif, "pingpong", False)),
        "motion_amount": _get(gif, "motion_amount", 1.0),
        "dissolve_amount": _get(dissolve, "amount", 1.0),
        "dissolve_seed": _get(dissolve, "seed", 53596),
        "dissolve_mode": str(_get(dissolve, "mode", "wind") or "wind"),
        "dissolve_speed": _get(dissolve, "speed", 1.0),
        "dissolve_wind_x": _get(dissolve, "wind_x", 120.0),
        "dissolve_wind_y": _get(dissolve, "wind_y", -40.0),
        "dissolve_hold": _get(dissolve, "hold", 1.0),
        "dissolve_length": _get(dissolve, "length", 5.0),
        "export_size": _get(export, "size", 3000),
        "export_format": str(_get(export, "format", "png") or "png"),
        "export_quality": _get(export, "quality", 90),
        "duotone_dark": duo_dark,
        "duotone_light": duo_light,
        "duotone_mid": duo_mid,
        "posterize": _get(grade, "posterize", 0),
        "split_tone": _get(grade, "split_tone", 0.0),
        "fade": _get(grade, "fade", 0.0),
        "glow_threshold": _get(grade, "glow_threshold", 0),
        "halftone": _get(texture, "halftone", 0),
        "halftone_shape": str(_get(texture, "halftone_shape", "dots") or "dots"),
        "dust": _get(texture, "dust", 0.0),
        "border": _get(texture, "border", 0),
        "border_color": str(_get(texture, "border_color", "#000000") or "#000000"),
        "letterbox": _get(texture, "letterbox", 0),
        "pixelsort": _get(glitch, "pixelsort", 0),
        "wave": _get(glitch, "wave", 0),
        "mosh": _get(glitch, "mosh", 0.0),
        "mosh_mode": str(_get(glitch, "mosh_mode", "blocks") or "blocks"),
        "mosh_seed": _get(glitch, "mosh_seed", 0),
        "mosh_size": _get(glitch, "mosh_size", 100),
        "grille": _get(glitch, "grille", 0),
        "jpeg": _get(glitch, "jpeg", _get(fx, "jpeg", 0.0)),
        "post_blur": _get(fx, "post_blur", _get(post, "blur", 0.0)),
        "post_sharpen": _get(fx, "post_sharpen", _get(post, "sharpen", 0)),
        "fx_stack": _get(params, "fx_stack", None),
        "motif": _get(params, "motif", None),
        "vector_export": bool(_get(params, "vector_export", False)),
        "vector_cell": _get(params, "vector_cell", 8),
    }
    return Preset.from_dict(flat)
