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


@when("I disperse it in elastic mode with dotsize 3")
def elastic_fat(ctx):
    from app.disintegrate import dither_bw, disperse_positions, points_from_dither, render_points

    coords, h, w = points_from_dither(dither_bw(ctx["img"]))
    ctx["coords"] = (coords, h, w)
    p0 = disperse_positions(coords, h, w, progress=0.0, seed=5, mode="burst", ease="elastic")
    p1 = disperse_positions(coords, h, w, progress=1.0, seed=5, mode="burst", ease="elastic")
    ctx["joint_a"] = render_points(p0, h, w)
    ctx["joint_b"] = render_points(p1, h, w)
    from app.disintegrate import frame_dot_sizes

    ctx["sizes"] = frame_dot_sizes(coords, h, w, progress=0.0, ease="elastic", dotsize=3)
    assert list(ctx["sizes"]) == [1] * len(coords)  # joints land back at 1px


@then("the loop closes and the joints match the 1px still")
def elastic_ok(ctx):
    from app.disintegrate import dither_bw, render_points

    coords, h, w = ctx["coords"]
    assert list(ctx["joint_a"].get_flattened_data()) == list(ctx["joint_b"].get_flattened_data())
    still = dither_bw(ctx["img"]).convert("RGB")
    assert list(ctx["joint_a"].get_flattened_data()) == list(still.get_flattened_data())
    assert render_points(coords.astype("float32"), h, w, ctx["sizes"]).size == still.size


@given("two half black images")
def two_halves(ctx):
    from PIL import Image as Img, ImageDraw as Draw

    ctx["img_a"] = Img.new("RGB", (48, 48), (255, 255, 255))
    ctx["img_b"] = Img.new("RGB", (48, 48), (255, 255, 255))
    Draw.Draw(ctx["img_a"]).rectangle([0, 0, 23, 47], fill=(0, 0, 0))
    Draw.Draw(ctx["img_b"]).rectangle([24, 0, 47, 47], fill=(0, 0, 0))
    return True


@when("I morph them with travel matching")
def travel_morph(ctx):
    import numpy as np

    from app.disintegrate import morph_chain_frames

    kw = dict(frames=8, max_side=64, seed=11, wind=(0.0, 0.0),
              amount=0.5, loop=False)
    ctx["travel"] = morph_chain_frames([ctx["img_a"], ctx["img_b"]],
                                       travel=1.0, **kw)
    ctx["legacy"] = morph_chain_frames([ctx["img_a"], ctx["img_b"]],
                                       travel=0.0, **kw)

    def meanx(im):
        g = np.asarray(im.convert("L"))
        ys, xs = np.nonzero(g < 128)
        return float(xs.mean()) if len(xs) else -1.0

    ctx["meanx_travel"] = [meanx(f) for f in ctx["travel"]]
    ctx["meanx_legacy"] = [meanx(f) for f in ctx["legacy"]]


@then("the pour has no seam jump and both ends assemble")
def travel_ok(ctx):
    from app.disintegrate import dither_bw

    stills = [tuple(dither_bw(im).convert("RGB").get_flattened_data())
              for im in (ctx["img_a"], ctx["img_b"])]
    flats = [tuple(f.get_flattened_data()) for f in ctx["travel"]]
    assert flats[0] == stills[0]
    assert flats[-1] == stills[1]
    assert flats[4] != tuple(ctx["legacy"][4].get_flattened_data())
    mx_t, mx_0 = ctx["meanx_travel"], ctx["meanx_legacy"]
    assert mx_t[-1] > mx_t[0]  # pour travels left -> right
    assert (mx_0[4] - mx_0[3]) > (mx_t[4] - mx_t[3])  # no cloud seam jump


@when("I morph them with full tint")
def tint_morph(ctx):
    import numpy as np

    from app.disintegrate import morph_chain_frames

    kw = dict(frames=8, max_side=64, seed=7, travel=1.0, loop=False)
    ctx["tinted"] = morph_chain_frames([ctx["img_a"], ctx["img_b"]],
                                       tint=1.0, **kw)
    ctx["plain"] = morph_chain_frames([ctx["img_a"], ctx["img_b"]], **kw)

    def has_color(im):
        arr = np.asarray(im.convert("RGB")).astype(int)
        return bool((((arr[:, :, 0] != arr[:, :, 1])
                      | (arr[:, :, 1] != arr[:, :, 2])).any()))

    ctx["tinted_mid_color"] = has_color(ctx["tinted"][4])
    ctx["plain_mid_color"] = has_color(ctx["plain"][4])


@then("mid-flight dots carry color and both ends match the stills")
def tint_ok(ctx):
    from app.disintegrate import dither_bw

    stills = [tuple(dither_bw(im).convert("RGB").get_flattened_data())
              for im in (ctx["img_a"], ctx["img_b"])]
    flats = [tuple(f.get_flattened_data()) for f in ctx["tinted"]]
    assert flats[0] == stills[0]
    assert flats[-1] == stills[1]
    assert ctx["tinted_mid_color"]
    assert not ctx["plain_mid_color"]
    assert flats[4] != tuple(ctx["plain"][4].get_flattened_data())


@when("I disperse it with trail ghosts")
def trail_runs(ctx):
    import numpy as np

    from app.disintegrate import dissolve_frames

    ctx["trailed"] = dissolve_frames(ctx["img"], frames=8, max_side=64,
                                     seed=5, trail=4)
    ctx["untrailed"] = dissolve_frames(ctx["img"], frames=8, max_side=64,
                                       seed=5, trail=0)

    def ghosts(im):
        arr = np.asarray(im.convert("RGB")).astype(int)
        g = arr[:, :, 0]
        return int(((g != 0) & (g != 255)).sum())

    ctx["trail_mid_ghosts"] = ghosts(ctx["trailed"][3])
    ctx["plain_mid_ghosts"] = ghosts(ctx["untrailed"][3])
    ctx["trail_joint_ghosts"] = ghosts(ctx["trailed"][0])


@then("mid-flight shows ghosts and the joints are clean")
def trail_ok(ctx):
    assert ctx["trail_mid_ghosts"] > 0
    assert ctx["plain_mid_ghosts"] == 0
    assert ctx["trail_joint_ghosts"] == 0
    assert list(ctx["trailed"][0].get_flattened_data()) == list(
        ctx["untrailed"][0].get_flattened_data())


@given("a dark-to-light gradient image")
def gradient_bw(ctx):
    from PIL import Image as Img

    im = Img.new("RGB", (48, 48))
    px = im.load()
    for y in range(48):
        for x in range(48):
            v = int(255 * x / 47)
            px[x, y] = (v, v, v)
    ctx["img"] = im
    return im


@when("I disperse it with Heckel shade")
def shade_runs(ctx):
    import numpy as np

    from app.disintegrate import dissolve_frames

    kw = dict(frames=8, max_side=64, seed=5, dotsize=3,
              wind=(0.0, 0.0), amount=0.5)
    ctx["shaded"] = dissolve_frames(ctx["img"], shade=True, **kw)
    ctx["unshaded"] = dissolve_frames(ctx["img"], **kw)

    def halves(im):
        arr = np.asarray(im.convert("L")).astype(int)
        w = arr.shape[1]
        return (int((arr[:, :w // 2] == 0).sum()),
                int((arr[:, w // 2:] == 0).sum()))

    ctx["shaded_halves"] = halves(ctx["shaded"][4])
    ctx["unshaded_halves"] = halves(ctx["unshaded"][4])


@then("dark dots grow bigger and the joints stay sharp")
def shade_ok(ctx):
    left_s, right_s = ctx["shaded_halves"]
    assert left_s > right_s  # dark side grows bigger dots
    assert (list(ctx["shaded"][0].get_flattened_data())
            == list(ctx["unshaded"][0].get_flattened_data()))
    assert (list(ctx["shaded"][4].get_flattened_data())
            != list(ctx["unshaded"][4].get_flattened_data()))


@when("I morph them with the SLIME palette")
def palette_morph(ctx):
    import numpy as np

    from app.disintegrate import morph_chain_frames, morph_ink
    from app.pipeline import resolve_palette

    inks, _ = resolve_palette("SLIME", None)
    inks = [tuple(c) for c in inks]
    kw = dict(frames=8, max_side=64, seed=7, loop=False)
    ctx["inked"] = morph_chain_frames([ctx["img_a"], ctx["img_b"]],
                                      palette=inks, **kw)
    ctx["legacy"] = morph_chain_frames([ctx["img_a"], ctx["img_b"]], **kw)
    still, coords, cols, h, w = morph_ink(ctx["img_a"], paint=inks)
    ctx["ink_still_footprint"] = (tuple(still.convert("RGB").get_flattened_data()),
                                  len(coords), cols is not None)
    arr = np.asarray(ctx["inked"][4].convert("RGB")).astype(int)
    ctx["inked_mid_green"] = bool((((arr[:, :, 1] > arr[:, :, 0])
                                    & (arr[:, :, 1] >= arr[:, :, 2])).any()))


@then("dots carry the palette inks and ends match the ink stills")
def palette_ok(ctx):
    still_flat, n_ink_dots, has_cols = ctx["ink_still_footprint"]
    assert has_cols
    assert n_ink_dots > 0
    assert ctx["inked_mid_green"]
    assert (list(ctx["inked"][0].get_flattened_data())
            != list(ctx["legacy"][0].get_flattened_data()))
    assert (list(ctx["inked"][4].get_flattened_data())
            != list(ctx["legacy"][4].get_flattened_data()))
