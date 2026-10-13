"""Trace `src/assets/brand/wearecreators-logo.png` into the brand assets.

Run from `frontend/`:  python3 scripts/trace-logo.py

Writes, from one set of constants so the inlined React paths and the static
files in `public/brand/` cannot drift:

    src/components/brand/paths.js      the three bands, for <Logo>
    public/brand/mark.svg              tree only
    public/brand/lockup-horizontal.svg tree | WEARE over CREATORS
    public/brand/lockup-stacked.svg    faithful to the upload
    public/favicon.svg  favicon-32/192/512.png  apple-touch-icon.png

**This is a raster trace and a stopgap.** When the real vector arrives,
replacing the three `d` strings in `paths.js` is the whole job — the layout
below is expressed as transforms over each band's own intrinsic box, so new
curves drop in without any of these numbers moving.

Three traps, each of which costs a cycle:

  * The mask comes from the ALPHA channel. The background is transparent
    WHITE, so any "is this pixel light?" test selects the entire canvas.
  * `potrace.Bitmap` wants a `bool` array and wants the mask INVERTED.
    Passing uint32, or passing it the right way up, traces the bounding
    rectangle with the artwork knocked out of it — which rasterises as a
    solid block, so look at the output rather than at the byte count.
  * `curve.start_point`, `seg.c`, `seg.c1`, `seg.c2` and `seg.end_point` are
    Point objects with `.x`/`.y`. They do not unpack as tuples.
"""
import json
import os

import numpy as np
import potrace
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src/assets/brand/wearecreators-logo.png")

# The ink, from the brand. Only the icons carry it as a literal — everything
# else is `currentColor` so CSS owns the colour.
INK = "#FF2731"
LABEL = "WeAre Creators"
BANDS = ("tree", "weare", "creators")


def find_bands(mask):
    """The three bands, as runs of rows that have any ink in them.

    Found by summing the alpha mask per row rather than by hard-coded pixel
    values, so a re-export with different margins still splits correctly.
    """
    rows = mask.sum(axis=1)
    runs, start = [], None
    for y, n in enumerate(rows):
        if n and start is None:
            start = y
        elif not n and start is not None:
            runs.append((start, y - 1))
            start = None
    if start is not None:
        runs.append((start, len(rows) - 1))
    if len(runs) != len(BANDS):
        raise SystemExit(f"expected {len(BANDS)} bands, found {len(runs)}")
    return runs


def num(n):
    return f"{round(n, 1):g}"


def trace_band(crop):
    """One band's outline, in its own coordinate space with the origin at its
    top-left — so the layout below can place it without knowing where on the
    source canvas it happened to sit."""
    bmp = potrace.Bitmap(np.ascontiguousarray(np.logical_not(crop), dtype=bool))
    parts = []
    for curve in bmp.trace(turdsize=4, alphamax=1.0, opttolerance=0.2):
        p = curve.start_point
        parts.append(f"M{num(p.x)} {num(p.y)}")
        for seg in curve:
            e = seg.end_point
            if seg.is_corner:
                parts.append(f"L{num(seg.c.x)} {num(seg.c.y)}L{num(e.x)} {num(e.y)}")
            else:
                parts.append(
                    f"C{num(seg.c1.x)} {num(seg.c1.y)} "
                    f"{num(seg.c2.x)} {num(seg.c2.y)} {num(e.x)} {num(e.y)}"
                )
        parts.append("Z")
    return "".join(parts)


def main():
    a = np.array(Image.open(SRC).convert("RGBA"))
    mask = a[:, :, 3] > 128

    band = {}
    for name, (y0, y1) in zip(BANDS, find_bands(mask)):
        sub = mask[y0 : y1 + 1]
        cols = np.where(sub.any(axis=0))[0]
        x0, x1 = int(cols.min()), int(cols.max())
        crop = sub[:, x0 : x1 + 1]
        band[name] = {
            "d": trace_band(crop),
            "w": int(crop.shape[1]),
            "h": int(crop.shape[0]),
            # Where it sat on the source canvas, which is what makes the
            # stacked lockup faithful rather than re-laid-out by hand.
            "x": x0,
            "y": int(y0),
        }
    canvas = (int(a.shape[1]), int(a.shape[0]))
    write_outputs(band, canvas)


def place(b, scale, tx, ty):
    """One band as a <path> under a transform. Rounded to 4 places: at these
    scales that is sub-thousandth-of-a-pixel and keeps the files readable."""
    return (
        f'<path transform="translate({round(tx, 2):g} {round(ty, 2):g}) '
        f'scale({round(scale, 6):g})" d="{b["d"]}"/>'
    )


def svg(view_w, view_h, body, extra=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {num(view_w)} {num(view_h)}"'
        f' fill="currentColor" role="img" aria-label="{LABEL}"{extra}>'
        f"{body}</svg>\n"
    )


def layout_mark(band, side=100.0, pad=0.08):
    """Tree alone in a square box, ~8% padding."""
    t = band["tree"]
    inner = side * (1 - 2 * pad)
    s = inner / max(t["w"], t["h"])
    return s, (side - t["w"] * s) / 2, (side - t["h"] * s) / 2, side


def layout_horizontal(band):
    """Tree on the left; WEARE over CREATORS on the right, both sharing a left
    edge and the pair centred against the tree."""
    tree, we, cr = band["tree"], band["weare"], band["creators"]
    # The two words keep the source's own relative size and the source's own
    # gap, so the right block is the upload's typography rather than a new
    # arrangement of it.
    src_gap = cr["y"] - (we["y"] + we["h"])
    block_src_h = we["h"] + src_gap + cr["h"]
    height = 100.0
    s = height / block_src_h
    t = height / tree["h"]
    gap = tree["w"] * t * 0.28
    left = tree["w"] * t + gap
    width = left + we["w"] * s
    return s, t, gap, left, width, height, src_gap


def layout_stacked(band, canvas, width=400.0):
    """The upload's own arrangement, at the upload's own proportions."""
    s = width / canvas[0]
    return s, canvas[1] * s


def icon_svg(side, rounded=True):
    """White tree on a brand-red tile. The tile is the whole square, so the
    apple-touch icon has no transparency to be composited against."""
    import __main__ as m

    t = m.BAND["tree"]
    inset = 0.62
    s = side * inset / max(t["w"], t["h"])
    tx = (side - t["w"] * s) / 2
    ty = (side - t["h"] * s) / 2
    r = f' rx="{num(side * 0.18)}"' if rounded else ""
    body = (
        f'<rect width="{num(side)}" height="{num(side)}"{r} fill="{INK}"/>'
        f'<path fill="#fff" transform="translate({round(tx, 2):g} {round(ty, 2):g}) '
        f'scale({round(s, 6):g})" d="{t["d"]}"/>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {num(side)} {num(side)}"'
        f' role="img" aria-label="{LABEL}">{body}</svg>\n'
    )


def write_outputs(band, canvas):
    global BAND
    BAND = band

    pub = os.path.join(ROOT, "public")
    brand_dir = os.path.join(pub, "brand")
    os.makedirs(brand_dir, exist_ok=True)

    # --- mark -----------------------------------------------------------
    s, tx, ty, side = layout_mark(band)
    mark = svg(side, side, place(band["tree"], s, tx, ty))

    # --- horizontal lockup ----------------------------------------------
    s, t, gap, left, width, height, src_gap = layout_horizontal(band)
    we_h = band["weare"]["h"] * s
    body = (
        place(band["tree"], t, 0, 0)
        + place(band["weare"], s, left, 0)
        + place(band["creators"], s, left, we_h + src_gap * s)
    )
    horizontal = svg(width, height, body)

    # --- stacked lockup --------------------------------------------------
    s, sh = layout_stacked(band, canvas)
    body = "".join(
        place(band[n], s, band[n]["x"] * s, band[n]["y"] * s) for n in BANDS
    )
    stacked = svg(400.0, sh, body)

    for name, text in (
        ("mark.svg", mark),
        ("lockup-horizontal.svg", horizontal),
        ("lockup-stacked.svg", stacked),
    ):
        with open(os.path.join(brand_dir, name), "w") as fh:
            fh.write(text)
        print(f"public/brand/{name:24s} {len(text):>6,} bytes")

    with open(os.path.join(pub, "favicon.svg"), "w") as fh:
        fh.write(icon_svg(64))
    print(f"public/favicon.svg{'':14s} {len(icon_svg(64)):>6,} bytes")

    import cairosvg

    for name, px, rounded in (
        ("favicon-32.png", 32, True),
        ("favicon-192.png", 192, True),
        ("favicon-512.png", 512, True),
        # iOS applies its own mask, so the source is a full-bleed square.
        ("apple-touch-icon.png", 180, False),
    ):
        cairosvg.svg2png(
            bytestring=icon_svg(64, rounded).encode(),
            write_to=os.path.join(pub, name),
            output_width=px,
            output_height=px,
            background_color="#FFFFFF" if name == "apple-touch-icon.png" else None,
        )
        print(f"public/{name}")

    write_paths_module(band, canvas)


def write_paths_module(band, canvas):
    s, t, gap, left, width, height, src_gap = layout_horizontal(band)
    mark_s, mark_x, mark_y, side = layout_mark(band)
    st_s, st_h = layout_stacked(band, canvas)

    def entry(name):
        b = band[name]
        return (
            f'    {name}: {{\n'
            f'        w: {b["w"]},\n'
            f'        h: {b["h"]},\n'
            f'        d: "{b["d"]}",\n'
            f"    }},"
        )

    def xf(scale, tx, ty):
        return f'"translate({round(tx, 2):g} {round(ty, 2):g}) scale({round(scale, 6):g})"'

    out = f'''// Generated by `scripts/trace-logo.py` — do not hand-edit the curves.
//
// **The one file to touch when the real vector arrives.** The three `d`
// strings below are a raster trace of `src/assets/brand/wearecreators-logo.png`
// and are a stopgap; every layout here is expressed as a transform over a
// band's own intrinsic box, so replacing a `d` (and its `w`/`h`) is the whole
// swap. Nothing else in the app knows these numbers.
//
// Colour is deliberately absent: every path renders `currentColor` so the
// surface decides, which is what lets one component serve the navy marketing
// site and the light product. See `Logo.jsx`.

/** The three bands of the mark, each in its own coordinate space. */
export const BANDS = {{
{entry("tree")}
{entry("weare")}
{entry("creators")}
}};

/**
 * Where each band sits in each lockup.
 *
 * `view` is the viewBox; `parts` are the bands to draw and the transform to
 * draw each under, in paint order.
 */
export const LAYOUTS = {{
    // Tree alone, square, 8% padding.
    mark: {{
        view: "0 0 {num(side)} {num(side)}",
        parts: [["tree", {xf(mark_s, mark_x, mark_y)}]],
    }},
    // The navbar lockup: tree, then the two words sharing a left edge,
    // optically centred against the tree's height.
    horizontal: {{
        view: "0 0 {num(width)} {num(height)}",
        parts: [
            ["tree", {xf(t, 0, 0)}],
            ["weare", {xf(s, left, 0)}],
            ["creators", {xf(s, left, band["weare"]["h"] * s + src_gap * s)}],
        ],
    }},
    // Faithful to the upload: tree centred, WEARE beneath, CREATORS beneath
    // that, at the source's own proportions and spacing.
    stacked: {{
        view: "0 0 400 {num(st_h)}",
        parts: [
            ["tree", {xf(st_s, band["tree"]["x"] * st_s, band["tree"]["y"] * st_s)}],
            ["weare", {xf(st_s, band["weare"]["x"] * st_s, band["weare"]["y"] * st_s)}],
            ["creators", {xf(st_s, band["creators"]["x"] * st_s, band["creators"]["y"] * st_s)}],
        ],
    }},
}};

/** Width ÷ height per variant, so a call site can set both and not reflow. */
export const RATIOS = {{
    mark: 1,
    horizontal: {round(width / height, 4)},
    stacked: {round(400.0 / st_h, 4)},
}};
'''
    path = os.path.join(ROOT, "src/components/brand/paths.js")
    with open(path, "w") as fh:
        fh.write(out)
    print(f"src/components/brand/paths.js   {len(out):>6,} bytes")


if __name__ == "__main__":
    main()
