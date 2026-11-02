"""BDD steps: particle fields x stagger x ease (morph_modes.feature). Pure logic, no Qt."""

from pytest_bdd import given, scenarios, then, when

scenarios("../../features/morph_modes.feature")


@given("a 48x48 gradient image")
def gradient_48(ctx):
    from PIL import Image as Img

    im = Img.new("RGB", (48, 48))
    px = im.load()
    for y in range(48):
        for x in range(48):
            px[x, y] = ((x * 5) % 256, (y * 7) % 256, 140)
    ctx["img"] = im
    return im


@when("I disperse it twice in burst mode and once in wind mode")
def burst_runs(ctx):
    from app.disintegrate import dither_bw, disperse_positions, points_from_dither

    coords, h, w = points_from_dither(dither_bw(ctx["img"]))
    ctx["burst_a"] = disperse_positions(coords, h, w, progress=0.3, seed=5, mode="burst")
    ctx["burst_b"] = disperse_positions(coords, h, w, progress=0.3, seed=5, mode="burst")
    ctx["wind"] = disperse_positions(coords, h, w, progress=0.3, seed=5, mode="wind")


@then("the burst runs match and differ from the wind run")
def burst_ok(ctx):
    assert (ctx["burst_a"] == ctx["burst_b"]).all()
    assert not (ctx["burst_a"] == ctx["wind"]).all()


@when("I disperse it with explicit wind off sine and with rank stagger")
def stagger_runs(ctx):
    from app.disintegrate import dither_bw, disperse_positions, points_from_dither

    coords, h, w = points_from_dither(dither_bw(ctx["img"]))
    ctx["legacy"] = disperse_positions(coords, h, w, progress=0.3, seed=5, mode="wind")
    ctx["explicit"] = disperse_positions(coords, h, w, progress=0.3, seed=5,
                                         mode="wind", stagger="off", ease="sine")
    ctx["ranked"] = disperse_positions(coords, h, w, progress=0.3, seed=5,
                                       mode="wind", stagger="rank", ease="sine")


@then("the explicit legacy matches the default and the stagger differs")
def stagger_ok(ctx):
    assert (ctx["legacy"] == ctx["explicit"]).all()
    assert not (ctx["ranked"] == ctx["explicit"]).all()


@given("two flat images")
def two_flats(ctx):
    from PIL import Image as Img

    ctx["img_a"] = Img.new("RGB", (48, 48), (200, 40, 40))
    ctx["img_b"] = Img.new("RGB", (48, 48), (40, 200, 40))
    return True


@when("I morph them in blocks mode without loop")
def blocks_morph(ctx):
    from app.disintegrate import morph_chain_frames

    ctx["frames"] = morph_chain_frames([ctx["img_a"], ctx["img_b"]], frames=8,
                                       max_side=64, mode="blocks", loop=False)


@then("the first frame is A assembled and the last is B assembled")
def blocks_ends(ctx):
    from app.disintegrate import dither_bw

    stills = [tuple(dither_bw(im).convert("RGB").get_flattened_data())
              for im in (ctx["img_a"], ctx["img_b"])]
    flats = [tuple(f.get_flattened_data()) for f in ctx["frames"]]
    assert flats[0] == stills[0]
    assert flats[-1] == stills[1]
    assert len(set(flats)) > 2
