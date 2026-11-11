"""BDD steps + scenarios: dither engine (dither/floyd/kernels/adjust_text features)."""

from pytest_bdd import scenarios, then, when

from app.dither import apply_method, error_diffusion, floyd_steinberg, ordered, ordered_bayer
from app.palettes import get_palette

scenarios(
    "../../features/dither.feature",
    "../../features/floyd.feature",
    "../../features/kernels.feature",
    "../../features/adjust_text.feature",
    "../../features/ascii.feature",
)


@when("I apply 4x4 B&W Bayer with threshold 128")
def bayer_bw(ctx):
    ctx["out"] = ordered_bayer(ctx["img"], palette=None, matrix="4x4", threshold=128.0)


@when("I apply 4x4 Bayer with the SLIME palette")
def bayer_slime(ctx):
    ctx["pal"] = get_palette("SLIME")
    ctx["out"] = ordered_bayer(ctx["img"], palette=ctx["pal"], matrix="4x4")


@when("I apply each method bayer4, bayer8 and floyd in B&W")
def all_methods(ctx):
    ctx["outs"] = [apply_method(ctx["img"], method=m, palette=None) for m in ("bayer4", "bayer8", "floyd")]


@when("I apply B&W Floyd-Steinberg with threshold 128")
def floyd_bw(ctx):
    ctx["out"] = floyd_steinberg(ctx["img"], palette=None, threshold=128.0)


@then("the image only contains the values 0 and 255")
def only_bw(ctx):
    assert set(ctx["out"].convert("L").get_flattened_data()) <= {0, 255}


@then("the image keeps the 64x64 size")
def keeps_64(ctx):
    assert ctx["out"].size == (64, 64)


@then("every pixel belongs to the SLIME palette")
def only_slime(ctx):
    assert set(ctx["out"].get_flattened_data()) <= set(ctx["pal"])


@then("every result keeps the 64x64 size")
def all_64(ctx):
    assert all(o.size == (64, 64) for o in ctx["outs"])


# -- kernels.feature --
@when("I apply B&W Atkinson")
def atkinson_bw(ctx):
    ctx["out"] = error_diffusion(ctx["img"], kernel="atkinson", palette=None)


@when("I apply blue-noise twice")
def bluenoise_twice(ctx):
    ctx["out_a"] = ordered(ctx["img"], palette=None, map_name="bluenoise")
    ctx["out_b"] = ordered(ctx["img"], palette=None, map_name="bluenoise")


@when("I diffuse Floyd with both backends")
def floyd_both(ctx):
    import pytest

    from app.accelerate import has_numba
    from app.kernels import run_kernel

    if not has_numba():
        pytest.skip("numba not installed")
    ctx["out_a"] = run_kernel(ctx["img"], "floyd", None, 128.0, backend="numpy")
    ctx["out_b"] = run_kernel(ctx["img"], "floyd", None, 128.0, backend="numba")


@when("I apply B&W halftone")
def halftone_bw(ctx):
    ctx["out"] = ordered(ctx["img"], palette=None, map_name="halftone")


@when("I apply JJN with the SLIME palette")
def jjn_slime(ctx):
    ctx["pal"] = get_palette("SLIME")
    ctx["out"] = error_diffusion(ctx["img"], kernel="jjn", palette=ctx["pal"])


@when("I apply shiaufan, filterlite, sierralite, sierra3 and ign in B&W")
def new_kernels_bw(ctx):
    ctx["outs"] = [apply_method(ctx["img"], method=m, palette=None)
                   for m in ("shiaufan", "filterlite", "sierralite", "sierra3")]
    ctx["outs"].append(ordered(ctx["img"], palette=None, map_name="ign"))


@then("the outputs are not all identical")
def outputs_differ(ctx):
    flats = [tuple(o.get_flattened_data()) for o in ctx["outs"]]
    assert len(set(flats)) > 1


@when("I apply Hilbert twice")
def hilbert_twice(ctx):
    ctx["out_a"] = apply_method(ctx["img"], palette=None, method="hilbert")
    ctx["out_b"] = apply_method(ctx["img"], palette=None, method="hilbert")


# -- adjust_text.feature --
@when("I apply 4x4 Bayer with brightness 1.5 and with brightness 1.0")
def bayer_brightness(ctx):
    from app.adjust import Adjust

    ctx["out_hi"] = ordered_bayer(ctx["img"], palette=None, matrix="4x4", adjust=Adjust(brightness=1.5))
    ctx["out_lo"] = ordered_bayer(ctx["img"], palette=None, matrix="4x4", adjust=Adjust(brightness=1.0))


@then("both outputs differ")
def brightness_differs(ctx):
    assert list(ctx["out_hi"].get_flattened_data()) != list(ctx["out_lo"].get_flattened_data())


@when("I export the bundle with preset metadata")
def export_with_meta(ctx):
    from app.exporter import export_bundle
    from app.presets import Preset

    ctx["paths"] = export_bundle(ctx["img"], ctx["tmp"], base="meta", meta=Preset(name="m", method="floyd", palette="VAPOR").meta())


@then("metadata exists with TRAKKART app and params")
def metadata_ok(ctx):
    import json

    assert ctx["paths"]["metadata"].exists()
    info = json.loads(ctx["paths"]["metadata"].read_text(encoding="utf-8"))
    assert info["app"] == "TRAKKART"
    assert info["params"]["method"] == "floyd"


# -- ascii.feature --
@when("I apply ASCII twice with 32 columns")
def ascii_twice(ctx):
    from app.ascii import ascii_render
    cfg = {"columns": 32}
    ctx["out_a"] = ascii_render(ctx["img"], config=cfg)
    ctx["out_b"] = ascii_render(ctx["img"], config=cfg)
    ctx["out"] = ctx["out_a"]


@then("both outputs are identical")
def both_identical(ctx):
    assert list(ctx["out_a"].get_flattened_data()) == list(ctx["out_b"].get_flattened_data())
