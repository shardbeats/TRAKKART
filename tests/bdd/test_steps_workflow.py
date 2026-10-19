"""BDD steps + scenarios: presets, batch, history (workflow features)."""

from pathlib import Path

from pytest_bdd import given, scenarios, then, when

from app.batch import batch_process
from app.presets import Preset, ensure_bundled, load_preset, save_preset

scenarios(
    "../../features/presets.feature",
    "../../features/batch.feature",
    "../../features/history.feature",
)


# -- presets.feature --
@given("a temporary presets directory")
def empty_pdir(ctx, tmp_path: Path):
    from pathlib import Path as P

    d = P(str(tmp_path)) / "presets"
    d.mkdir(exist_ok=True)
    ctx["pdir"] = d
    return d


@given("a temporary presets directory with bundled presets")
def bundled_pdir(ctx, tmp_path: Path):
    from pathlib import Path as P

    d = P(str(tmp_path)) / "presets"
    d.mkdir(exist_ok=True)
    ensure_bundled(d)
    ctx["pdir"] = d
    return d


@when('I save the "GherkinTest" preset with floyd method and VAPOR palette')
def save_gherkin(ctx):
    save_preset(
        Preset(name="GherkinTest", method="floyd", palette="VAPOR", pixel_size=2, threshold=128),
        ctx["pdir"],
    )


@then('I reload "GherkinTest" with the same values')
def reload_gherkin(ctx):
    back = load_preset("GherkinTest", ctx["pdir"])
    assert (back.method, back.palette, back.pixel_size, back.threshold) == ("floyd", "VAPOR", 2, 128)


@when("I hand-edit SLIME_FS and re-ensure bundled presets")
def edit_bundled(ctx):
    (ctx["pdir"] / "SLIME_FS.json").write_text('{"custom": true}', encoding="utf-8")
    ctx["created"] = ensure_bundled(ctx["pdir"])


@then("my edit is preserved")
def edit_kept(ctx):
    assert ctx["created"] == []
    assert (ctx["pdir"] / "SLIME_FS.json").read_text(encoding="utf-8") == '{"custom": true}'


# -- batch.feature --
@given("a temporary folder with 3 48x48 images")
def folder_3(ctx, tmp_path: Path):
    from pathlib import Path as P

    from PIL import Image as Img

    src = P(str(tmp_path)) / "in"
    src.mkdir(exist_ok=True)
    for i in range(3):
        Img.new("RGB", (48, 48), (30 * i + 40, 90, 140)).save(src / f"beat{i}.png")
    ctx["src"] = src
    ctx["dst"] = P(str(tmp_path)) / "out"
    return src


@when("I run batch with bayer4 preset and SLIME palette")
def run_batch_bdd(ctx):
    ctx["results"] = batch_process(
        ctx["src"], ctx["dst"], Preset(name="t", method="bayer4", palette="SLIME")
    )


@then("the 3 files end up ok with 3 PNGs each")
def batch_ok(ctx):
    from pathlib import Path as P

    assert len(ctx["results"]) == 3
    for r in ctx["results"]:
        assert r["status"] == "ok", r
        pngs = [o for o in r["outputs"] if o.endswith(".png")]
        assert len(pngs) == 3
        for o in r["outputs"]:
            assert P(o).exists()


# -- history.feature --
@given("an empty temporary history")
def empty_history(ctx, tmp_path: Path):
    from app.history import HistoryStore

    ctx["store"] = HistoryStore(tmp_path / "h.db")
    return ctx["store"]


@when('I log an export with base "beat_hist" and preset "SLIME_FS"')
def log_history(ctx):
    ctx["store"].log_export("beat_hist", "SLIME_FS", {"method": "floyd"}, ["a.png"])


@then("the history holds 1 record with that base")
def history_has_it(ctx):
    rows = ctx["store"].list_exports()
    assert len(rows) == 1
    assert rows[0]["base"] == "beat_hist"
    ctx["store"].close()
