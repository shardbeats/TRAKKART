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

BUNDLED: dict[str, dict] = {
    "SLIME_FS": {"method": "floyd", "palette": "SLIME", "pixel_size": 2, "threshold": 128},
    "VAPOR_BAYER8": {"method": "bayer8", "palette": "VAPOR", "pixel_size": 3, "threshold": 128},
    "EMBER_BW": {"method": "floyd", "palette": "BW", "pixel_size": 2, "threshold": 128},
    "CRT_HARD": {"method": "bayer4", "palette": "BW", "pixel_size": 4, "threshold": 160},
}


# ---------------------------------------------------------------------------
# Declarative field schema: single source for validate/to_dict/from_dict.
# Añadir un campo = 1 línea @dataclass + 1 línea aquí (antes: 5 ediciones).
# kind: int|float|str|bool|colors. rule: ("range", lo, hi) | ("oneof", values|key)
#        | ("hex",) | ("hexreq",) | ("palette",) | () = sin check.
# Claves dinámicas de oneof: METHODS, PALETTES, RATIOS, CROPS, GIFMODES.
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
            # 0 = auto (sigue a ratio+export_size); si no, rango normal.
            _, lo, hi = self.rule
            v = float(value)
            if v != 0 and not lo <= v <= hi:
                raise ValueError(f"{self.name} out of range 0 or {lo:g}-{hi:g}: {value}")
        elif kind == "oneof":
            vals = self._oneof_values()
            ok = str(value) in [str(x) for x in vals] if self.kind == "str" else value in vals
            # numéricos con bool: int(True)==1, se evita comparando tipos vía int()
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
    _Field("gif_frames", "int", ("range", 2, 24)),
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
    return value  # colors/stack: passthrough (valida, no transforma)


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
    canvas_w: int = 0  # 0 = auto desde ratio+export_size; UI y from_dict dejan valores concretos
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
    vector_black: bool = False  # v1.3: solo tinta negra sobre transparente (print)
    glitch_chroma: int = 0
    glitch_slice_bands: int = 0
    glitch_slice_max: int = 24
    gif_export: bool = False
    gif_frames: int = 6
    gif_mode: str = "both"
    gif_fps: int = 8
    gif_size: int = 1200  # anim único: lo usan el preview VIDEO y el GIF exportado
    gif_pingpong: bool = False
    motion_amount: float = 1.0  # animation intensity: 0 = freeze, 1 = legacy, up to 3
    export_size: int = 3000  # lado largo px de la imagen principal
    export_format: str = "png"  # png | jpg | webp
    export_quality: int = 90  # solo jpg/webp, 1-100
    # -- grade (pack A) --
    duotone_dark: str = ""  # #RRGGBB o "" = off (requiere duotone_light)
    duotone_light: str = ""
    duotone_mid: float = 50.0  # corte 0-100
    posterize: int = 0  # 0 = off, 2-8 niveles
    split_tone: float = 0.0  # 0-100
    fade: float = 0.0  # 0-100
    glow_threshold: int = 0  # 0-255, 0 = todo brilla
    # -- texture/decay (pack B) --
    halftone: int = 0  # 0 = off, si no 3-12 px por celda
    halftone_shape: str = "dots"  # dots | lines
    dust: float = 0.0  # 0-100
    border: int = 0  # 0-64 px, 0 = off
    border_color: str = "#000000"
    letterbox: int = 0  # 0-25 % por lado, 0 = off
    # -- glitch extra (pack C) --
    pixelsort: int = 0  # umbral luminancia 0-255, 0 = off
    wave: int = 0  # amplitud px 0-30, 0 = off
    mosh: float = 0.0  # 0-100
    grille: int = 0  # 0 = off, 2 | 3
    # -- v1.2 stackable FX --
    jpeg: float = 0.0  # JPEG glitch 0-100, 0 = off
    post_blur: float = 0.0  # post blur 0.0-5.0 (post-dither, en stack)
    post_sharpen: int = 0  # post sharpen 0-3 (post-dither, en stack)
    fx_stack: list | None = None  # None = orden legacy; si no [{id, enabled}]
    # -- v1.3 motif --
    motif: dict | None = None  # None = default_config(); {"bands": [{shape, size}x4]}
    # -- v1.4 signal drift + paste-up --
    drift_pattern: str = "off"  # Signal Drift pattern pre-dither
    drift_amount: float = 0.0  # 0-100, 0 = off
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
            # Migración: presets viejos (ratio + export_size) -> W/H concretos.
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
        m["glitch"]["grille"] = int(self.grille)
        m["glitch"]["jpeg"] = float(getattr(self, "jpeg", 0.0) or 0.0)
        m["post"] = {
            "blur": float(getattr(self, "post_blur", 0.0) or 0.0),
            "sharpen": int(getattr(self, "post_sharpen", 0) or 0),
        }
        m["gif"]["motion_amount"] = float(getattr(self, "motion_amount", 1.0))
        m["fx_stack"] = copy.deepcopy(getattr(self, "fx_stack", None))
        m["motif"] = copy.deepcopy(getattr(self, "motif", None))
        return m


def _safe_name(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    return safe or "preset"


# Guardia fail-fast: el schema cubre exactamente los campos del dataclass.
assert {f.name for f in FIELDS} == set(Preset.__dataclass_fields__), (
    "FIELDS desincronizado de Preset"
)


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
