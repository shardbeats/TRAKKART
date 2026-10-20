"""BDD steps: viewport + tutorial (ux.feature). Pure logic, no Qt."""

from pytest_bdd import given, scenarios, then, when

scenarios("../../features/ux.feature")


@given("a live viewport by default")
def live_default(ctx):
    from app.viewport import normalize_mode

    ctx["mode"] = normalize_mode(None)
    return ctx["mode"]


@when("I resolve intervals for full and still")
def resolve_modes(ctx):
    from app.viewport import resolve_interval

    ctx["full_ms"] = resolve_interval("full")
    ctx["still_ms"] = resolve_interval("still")
    ctx["fast_ms"] = resolve_interval("live", fast=True)
    ctx["slow_ms"] = resolve_interval("live", fast=False)


@then("full is instant and still never auto-refreshes")
def intervals_ok(ctx):
    assert ctx["mode"] == "live"
    assert ctx["full_ms"] == 0
    assert ctx["still_ms"] is None
    assert ctx["fast_ms"] == 120 and ctx["slow_ms"] == 350


@given("a clean preset and a blur preset")
def two_presets(ctx):
    from types import SimpleNamespace

    ctx["clean"] = SimpleNamespace(pre_blur=0.0, pre_denoise=0, pre_smooth=0.0)
    ctx["heavy"] = SimpleNamespace(pre_blur=2.0, pre_denoise=0, pre_smooth=0.0)
    return True


@when("I check heaviness")
def check_heavy(ctx):
    from app.viewport import is_heavy_preset

    ctx["clean_heavy"] = is_heavy_preset(ctx["clean"])
    ctx["heavy_heavy"] = is_heavy_preset(ctx["heavy"])


@then("only the blur preset is heavy")
def heavy_ok(ctx):
    assert ctx["clean_heavy"] is False
    assert ctx["heavy_heavy"] is True
