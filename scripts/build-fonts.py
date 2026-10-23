#!/usr/bin/env python3
"""Build the self-hosted public-site fonts and print their fallback metrics.

Inputs are the latin woff2 files this repository serves, as fetched once from
their upstreams (see `frontend/public/fonts/README.md` for the exact URLs):

  Fraunces   Google Fonts, requested as ital,opsz,wght,WONK — the request
             leaves SOFT out, so the file has no SOFT axis at all
  Inter Tight  @fontsource-variable/inter-tight (wght)
  JetBrains Mono  @fontsource/jetbrains-mono (400, static)

Two jobs:

1. **Narrow the weight axis to what the site uses.** Fraunces ships 100–900
   and Inter Tight 100–900; the site sets Fraunces at 400–700 and Inter Tight
   at 400–600, and a test bans the weights outside them. Pinning the range is
   lossless inside it and drops the deltas outside it.

2. **Print `@font-face` descriptors for a metric-matched fallback**, so the
   swap from the local face to the webfont moves nothing. The fallback is the
   metric-compatible pair available everywhere — Times New Roman / Liberation
   Serif, Arial / Liberation Sans, Courier New / Liberation Mono — and the
   arithmetic is next/font's: `size-adjust` is the ratio of average advance
   over a sample, and the vertical overrides are the webfont's own ascent,
   descent and line gap divided by that ratio, because the browser applies
   them to the already-adjusted face.

   The hero gets its own fallback because the LCP element is the display
   headline and Fraunces' widths change with optical size. It is matched on
   the headline's own words at **opsz 52, WONK 1** — the instance a phone
   renders, where `mkt-display` sits at its 52px minimum. An earlier version
   matched at opsz 144 (the desktop end) and the fallback set the phone
   headline on two lines where Fraunces needs four: a 0.28 layout shift on
   Lighthouse's mobile run, the whole of it from this one element. A phone
   is where the swap is slow enough to be seen, so it is the size to match.

    python3 scripts/build-fonts.py <src-dir> <out-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SAMPLE = (
    "The quick brown fox jumps over the lazy dog. Creators, brands, briefs and "
    "payments agreed in writing before anyone shoots, in one place."
)
HERO_SAMPLE = "Creator campaigns, minus the chasing."

# Each fallback is measured against a file with the same metrics as the font
# the visitor's device actually has. Liberation is metric-compatible with
# Times New Roman, Arial and Courier New by design (desktop and iOS); Noto
# Serif and Roboto are what Android has, measured from their fontsource
# builds. A `local()` face that is not installed is skipped by the browser,
# so the stack tries the desktop face, then the Android one.
FALLBACKS = {
    "serif": "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "serif-android": "noto-serif-latin-400-normal.woff2",
    "sans": "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "sans-android": "roboto-latin-400-normal.woff2",
    "mono": "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "serif-italic": "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
}

# The words set in true italic on the public pages: the hero's drawn word and
# the photo panel's.
ITALIC_SAMPLE = "chasing good"

BUILDS = [
    # (source, output, weight range or None)
    ("fraunces-latin-normal.woff2", "fraunces-latin-normal.woff2", (400, 700)),
    ("fraunces-latin-italic.woff2", "fraunces-latin-italic.woff2", (400, 700)),
    ("inter-tight-latin-wght-normal.woff2", "inter-tight-latin.woff2", (400, 600)),
    ("jetbrains-mono-latin-400-normal.woff2", "jetbrains-mono-latin-400.woff2", None),
]


def avg_advance(font: TTFont, text: str) -> float:
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    widths = [hmtx[cmap[ord(c)]][0] for c in text if ord(c) in cmap]
    return sum(widths) / len(widths) / font["head"].unitsPerEm


def vertical(font: TTFont) -> tuple[float, float, float]:
    upm = font["head"].unitsPerEm
    hhea = font["hhea"]
    return hhea.ascent / upm, abs(hhea.descent) / upm, hhea.lineGap / upm


def static_at(path: Path, coords: dict) -> TTFont:
    font = TTFont(path)
    if "fvar" in font:
        axes = {a.axisTag for a in font["fvar"].axes}
        font = instancer.instantiateVariableFont(font, {k: v for k, v in coords.items() if k in axes})
    return font


def descriptors(web: TTFont, fallback: TTFont, sample: str) -> dict:
    size_adjust = avg_advance(web, sample) / avg_advance(fallback, sample)
    ascent, descent, gap = vertical(web)
    return {
        "size-adjust": f"{size_adjust * 100:.2f}%",
        "ascent-override": f"{ascent / size_adjust * 100:.2f}%",
        "descent-override": f"{descent / size_adjust * 100:.2f}%",
        "line-gap-override": f"{gap / size_adjust * 100:.2f}%",
    }


def main(src: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, target, wght in BUILDS:
        font = TTFont(src / name)
        before = (src / name).stat().st_size
        if wght:
            font = instancer.instantiateVariableFont(font, {"wght": wght})
        font.flavor = "woff2"
        font.save(out / target)
        print(f"{target}: {before} -> {(out / target).stat().st_size} bytes")

    fb = {k: TTFont(v if v.startswith("/") else src / v) for k, v in FALLBACKS.items()}
    fr = out / "fraunces-latin-normal.woff2"
    body = static_at(fr, {"opsz": 144, "wght": 600, "WONK": 0})
    display = static_at(fr, {"opsz": 52, "wght": 400, "WONK": 1})
    # From 1024px up the headline is 80–104px, and Fraunces is narrower at
    # that optical size; index.css swaps to this pair at that breakpoint.
    display_large = static_at(fr, {"opsz": 100, "wght": 400, "WONK": 1})
    inter = static_at(out / "inter-tight-latin.woff2", {"wght": 400})
    mono = TTFont(out / "jetbrains-mono-latin-400.woff2")
    rows = {
        "Fraunces Fallback": descriptors(body, fb["serif"], SAMPLE),
        "Fraunces Fallback Android": descriptors(body, fb["serif-android"], SAMPLE),
        "Fraunces Display Fallback": descriptors(display, fb["serif"], HERO_SAMPLE),
        "Fraunces Display Fallback Android": descriptors(display, fb["serif-android"], HERO_SAMPLE),
        "Fraunces Display Large Fallback": descriptors(display_large, fb["serif"], HERO_SAMPLE),
        # Without these, an italic word in the fallback state is a slanted
        # copy of the upright fallback — a different width from Fraunces'
        # real italic, so the words after it move when the italic file lands.
        "Fraunces Display Fallback (italic)": descriptors(
            static_at(out / "fraunces-latin-italic.woff2", {"opsz": 52, "wght": 400, "WONK": 1}),
            fb["serif-italic"], ITALIC_SAMPLE,
        ),
        "Fraunces Display Large Fallback (italic)": descriptors(
            static_at(out / "fraunces-latin-italic.woff2", {"opsz": 100, "wght": 400, "WONK": 1}),
            fb["serif-italic"], ITALIC_SAMPLE,
        ),
        "Inter Tight Fallback": descriptors(inter, fb["sans"], SAMPLE),
        "Inter Tight Fallback Android": descriptors(inter, fb["sans-android"], SAMPLE),
        "JetBrains Mono Fallback": descriptors(mono, fb["mono"], SAMPLE.upper()),
    }
    for family, d in rows.items():
        print(family, " ".join(f"{k}: {v};" for k, v in d.items()))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
