"""The public site's photo slots hold photographs, and what that has to keep
true.

Five of the six slots carry a generated photograph: the two audience-page
bands (`PHOTO_SLOTS`), the sign-in and sign-up asides and the 404
(`PLACEHOLDER_PHOTOS`). The sixth, `home-on-location`, is still its drawing —
its photograph did not arrive — and every rule here is written over whatever
is wired, so it is held to them the moment it is.

What is pinned, and why each is mechanical rather than remembered:

  - **Every wired file exists, at both widths, and the descriptors are true.**
    `srcSet` says `2400w`; the browser believes it, so a file that is really
    1850px wide is a phone sent the wrong picture. The widths are read out of
    the WebP header, not the filename.
  - **The byte budgets hold** — 140 KB for the small export, 350 KB for the
    large one — over every file in `public/img/photos/`, so a re-export that
    forgot the budget fails here rather than on somebody's mobile data.
  - **Nothing rides along.** No EXIF, XMP or ICC chunk: a generated image's
    provenance block and a phone's GPS tag go the same way.
  - **The export is the slot's ratio**, so the reserved box and the picture
    agree and `focal` only ever trims the edges it was set to trim.
  - **The alt text is one plain sentence that names nobody** — no capital
    after the first word, and none of the names this repo knows are real.
  - **The originals are never committed**: no `_incoming/`, and nothing in
    the folder that the manifest does not serve.
  - **The script's crop never covers the corner mark** and is exactly the
    ratio, for every slot, on originals of every shape.
"""

import json
import re
import struct
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
PUBLIC = FRONTEND / "public"
PHOTOS = PUBLIC / "img" / "photos"
MANIFEST = SRC / "content" / "photoSlots.js"
SCRIPT = FRONTEND / "scripts" / "prepare-photos.mjs"
CONTENT = SRC / "content" / "marketing.js"

BUDGET = {"small": 140 * 1024, "large": 350 * 1024}
# The two widths each orientation is exported at, small then large.
WIDTHS = {"landscape": (1200, 2400), "portrait": (900, 1800)}


def _node(script: str) -> str:
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _manifest():
    """Both tables, evaluated the way a production build sees them."""
    script = MANIFEST.read_text() + "\nconsole.log(JSON.stringify({PHOTO_SLOTS, PLACEHOLDER_PHOTOS}));"
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60, env={"PATH": __import__("os").environ["PATH"], "NODE_ENV": "production"},
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _wired():
    """Every photograph the site serves: (id, entry), from both tables."""
    m = _manifest()
    rows = [(sid, s) for sid, s in m["PHOTO_SLOTS"].items() if s["src"]]
    rows += list(m["PLACEHOLDER_PHOTOS"].items())
    return rows


def _webp(path: Path):
    """(width, height, chunk names) read from a WebP's RIFF header."""
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", path
    chunks = []
    off = 12
    size = None
    while off + 8 <= len(data):
        tag = data[off : off + 4].decode("latin-1")
        n = struct.unpack("<I", data[off + 4 : off + 8])[0]
        body = data[off + 8 : off + 8 + n]
        chunks.append(tag)
        if tag == "VP8 " and size is None:
            w, h = struct.unpack("<HH", body[6:10])
            size = (w & 0x3FFF, h & 0x3FFF)
        elif tag == "VP8L" and size is None:
            bits = struct.unpack("<I", body[1:5])[0]
            size = ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        elif tag == "VP8X":
            w = int.from_bytes(body[4:7], "little") + 1
            h = int.from_bytes(body[7:10], "little") + 1
            size = (w, h)
        off += 8 + n + (n & 1)
    assert size, path
    return size[0], size[1], chunks


def _candidates(src_set: str):
    """`srcSet` as [(path, width)]."""
    out = []
    for part in src_set.split(","):
        url, desc = part.strip().split()
        assert desc.endswith("w"), part
        out.append((url, int(desc[:-1])))
    return out


def test_five_slots_are_wired_and_the_sixth_is_still_its_drawing():
    m = _manifest()
    wired = {sid for sid, _ in _wired()}
    assert wired == {"brands-full-room", "creators-on-shoot", "auth-login", "auth-signup", "not-found"}
    home = m["PHOTO_SLOTS"]["home-on-location"]
    assert home["src"] is None and home["srcSet"] is None and home["alt"] == ""
    assert home["fallbackIllustration"].endswith(".svg")
    # Its size is already the 3:2 frame slide C draws it in.
    assert (home["width"], home["height"]) == (2400, 1600)


@pytest.mark.parametrize("sid,slot", _wired(), ids=lambda v: v if isinstance(v, str) else "")
def test_every_wired_photograph_exists_at_both_widths(sid, slot):
    cands = _candidates(slot["srcSet"])
    assert len(cands) == 2, sid
    (small_url, small_w), (large_url, large_w) = sorted(cands, key=lambda c: c[1])
    assert (small_w, large_w) in WIDTHS.values(), sid
    # `src` is the large file: the one a browser with no srcset support gets.
    assert slot["src"] == large_url, sid
    for url, w in cands:
        assert url.startswith("/img/photos/") and url.endswith(f"-{w}.webp"), url
        assert url == f"/img/photos/{sid}-{w}.webp", url
        path = PUBLIC / url.lstrip("/")
        assert path.is_file(), url
        actual_w, _, _ = _webp(path)
        # The descriptor is what the browser chooses on; it has to be true.
        assert actual_w == w, (url, actual_w)
    assert re.fullmatch(r"\d+% \d+%", slot["focal"]), sid


@pytest.mark.parametrize("sid,slot", _wired(), ids=lambda v: v if isinstance(v, str) else "")
def test_the_export_is_the_slot_s_ratio(sid, slot):
    """The reserved box and the picture agree. `PHOTO_SLOTS` says its own
    size; the three tinted slots' frames are 3:4 (the auth asides, portrait)
    and 4:3 (the 404's card)."""
    w, h, _ = _webp(PUBLIC / slot["src"].lstrip("/"))
    if "width" in slot:
        assert (w, h) == (slot["width"], slot["height"]), sid
    else:
        want = {"auth-login": (3, 4), "auth-signup": (3, 4), "not-found": (4, 3)}[sid]
        assert w * want[1] == h * want[0], (sid, w, h)


def test_every_file_is_inside_its_budget():
    files = sorted(PHOTOS.glob("*.webp"))
    assert files, "no photographs exported"
    for path in files:
        m = re.fullmatch(r"([a-z-]+)-(\d+)\.webp", path.name)
        assert m, path.name
        width = int(m.group(2))
        kind = "small" if width in (WIDTHS["landscape"][0], WIDTHS["portrait"][0]) else "large"
        assert width in WIDTHS["landscape"] + WIDTHS["portrait"], path.name
        size = path.stat().st_size
        assert size <= BUDGET[kind], f"{path.name} is {size / 1024:.1f} KB, over {BUDGET[kind] // 1024} KB"


def test_no_metadata_rides_along():
    """sharp writes none unless asked; this is what holds the asking out."""
    for path in sorted(PHOTOS.glob("*.webp")):
        _, _, chunks = _webp(path)
        assert not {"EXIF", "XMP ", "ICCP"} & set(chunks), (path.name, chunks)
    assert ".withMetadata(" not in SCRIPT.read_text()


def test_only_what_is_served_is_committed():
    """No originals, and no export the manifest does not point at — an orphan
    is a picture nobody can see that every clone downloads."""
    assert not (PHOTOS / "_incoming").exists()
    served = set()
    for _, slot in _wired():
        served |= {url.split("/")[-1] for url, _ in _candidates(slot["srcSet"])}
    present = {p.name for p in PHOTOS.iterdir()}
    assert present == served, present ^ served
    gitignore = (ROOT / ".gitignore").read_text()
    assert "frontend/public/img/photos/_incoming/" in gitignore


def _real_names():
    """Every name this repo knows belongs to a real business or person."""
    facts = json.loads(_node(CONTENT.read_text() + "\nconsole.log(JSON.stringify(FACTS));"))
    names = set(facts["confirmedClients"])
    nav = (SRC / "lib" / "siteNav.js").read_text()
    names |= set(re.findall(r'name: "([^"]+)"', nav[nav.index("export const CONTACT_PEOPLE") :]))
    seed = (ROOT / "backend" / "seed_demo.py").read_text()
    names |= set(re.findall(r'"business": "([^"]+)"', seed))
    names |= {"Toit", "Thirdwave", "Third Wave", "Starbucks", "Zomato", "Swiggy", "Blue Tokai",
              "Chai Point", "WeAre", "Gemini"}
    return {n for n in names if n}


@pytest.mark.parametrize("sid,slot", _wired(), ids=lambda v: v if isinstance(v, str) else "")
def test_the_alt_is_one_plain_sentence_naming_nobody(sid, slot):
    alt = slot["alt"]
    assert len(alt) > 30, sid
    # One sentence: a capital, one full stop at the end and none before it.
    assert alt[0].isupper() and alt.endswith(".") and alt.count(".") == 1, alt
    assert not re.search(r"[!?;]", alt), alt
    # No proper noun: nothing capitalised after the first word.
    assert not re.search(r"\s[A-Z]", alt), alt
    for name in _real_names():
        assert name.lower() not in alt.lower(), (sid, name)
    # And it describes the photograph rather than restating the copy.
    assert "brief" not in alt.lower() and "weare" not in alt.lower()


def test_no_photograph_is_fetched_from_anybody_else():
    """The rule `test_marketing_pages` sweeps for stock hosts, stated for the
    manifest directly: every source is a path on our own origin."""
    for sid, slot in _wired():
        for url, _ in _candidates(slot["srcSet"]):
            assert url.startswith("/") and "//" not in url, (sid, url)


# --- The callers say how wide they draw it -----------------------------------


def _read(*parts):
    return (SRC.joinpath(*parts)).read_text()


def test_each_caller_names_its_drawn_width():
    """`sizes` is how a phone gets the small file. Each caller states it,
    because only the caller knows the frame: full bleed, a 540px column, half
    the screen."""
    assert '<PhotoSlot id={id} fill sizes="100vw" />' in _read("components", "marketing", "SiteParts.jsx")
    assert 'sizes="(min-width: 1024px) 540px, 100vw"' in _read("components", "marketing", "heroSlides.jsx")
    for page in ("Login.jsx", "Signup.jsx"):
        src = _read("pages", page)
        assert 'sizes="50vw"' in src, page
        # Eager where it is the first thing on screen, and lazy below `md`,
        # where the aside is `hidden` — an eager image inside display:none
        # is still fetched.
        assert "eager={wide}" in src and "useWide()" in src, page
    nf = _read("pages", "NotFound.jsx")
    assert 'sizes="(min-width: 768px) 50vw, 100vw"' in nf and "eager\n" in nf


def test_both_components_pass_srcset_and_sizes_through():
    slot = _read("components", "marketing", "PhotoSlot.jsx")
    assert "srcSet={slot.srcSet || undefined}" in slot
    assert "sizes={slot.srcSet ? sizes : undefined}" in slot
    ph = _read("components", "marketing", "PlaceholderImage.jsx")
    assert "PLACEHOLDER_PHOTOS[slot]" in ph
    assert "srcSet={photo && photo.srcSet ? photo.srcSet : undefined}" in ph
    assert "sizes={photo && photo.srcSet ? sizes : undefined}" in ph
    # Photograph, then drawing, then tint: the drawing only when there is no
    # photograph, and only in production.
    assert "!photo && !SHOW_BRIEFS && slot ? PLACEHOLDER_ILLUSTRATIONS[slot]" in ph


def test_the_auth_text_sits_on_its_own_ground():
    """The 12px red eyebrow needs 4.5:1 and red on the navy itself is about
    4.9:1, so the text block carries a navy ground that is solid under the
    text and fades above it. Measured in a browser at 768–1920: 4.9:1 on both
    pages, where the gradient alone gave 2.7–3.0:1 over the photographs."""
    for page in ("Login.jsx", "Signup.jsx"):
        src = _read("pages", page)
        scrim = src.split('data-testid="auth-aside-scrim"', 1)[1].split("/>", 1)[0]
        assert "-inset-x-12 -bottom-12 -top-40" in scrim, page
        assert "hsl(var(--background))_calc(100%_-_10rem),transparent" in scrim, page
        # The gradient and the photograph's dimming are kept, not replaced.
        assert "from-background/40 via-background/60 to-background" in src, page
        assert 'className="opacity-60"' in src, page


# --- The script ---------------------------------------------------------------


def _crop(width, height, ratio, anchor):
    text = SCRIPT.read_text().replace('import sharp from "sharp";', "const sharp = null;")
    script = text + f"\nconsole.log(JSON.stringify(cropWindow({width}, {height}, {list(ratio)}, {list(anchor)})));"
    return json.loads(_node(script))


@pytest.mark.parametrize("ratio", [(2, 1), (3, 2), (4, 3), (3, 4)])
@pytest.mark.parametrize("size", [(2000, 989), (2000, 1493), (1493, 2000), (4032, 3024), (3024, 4032), (1600, 1600)])
@pytest.mark.parametrize("anchor", [(0.5, 0.5), (1.0, 1.0), (0.0, 0.0)])
def test_the_crop_is_exact_and_never_covers_the_mark(ratio, size, anchor):
    w, h = size
    c = _crop(w, h, ratio, anchor)
    # Exactly the ratio, so the export is too.
    assert c["width"] * ratio[1] == c["height"] * ratio[0], c
    # Inside the original.
    assert c["left"] >= 0 and c["top"] >= 0
    assert c["left"] + c["width"] <= w and c["top"] + c["height"] <= h
    # Clear of the bottom-right mark box on at least one axis.
    b = c["mark"]
    assert b == max(150, round(0.12 * min(w, h)))
    assert c["left"] + c["width"] <= w - b or c["top"] + c["height"] <= h - b, c
    # And not needlessly small: at least 80% of the original's extent on the
    # axis the ratio binds.
    assert c["width"] >= 0.8 * min(w, h * ratio[0] / ratio[1]) - ratio[0], c


def test_the_script_exports_the_widths_and_budgets_this_file_checks():
    text = SCRIPT.read_text()
    assert "export const BUDGET = { small: 140 * 1024, large: 350 * 1024 };" in text
    assert "const LANDSCAPE = { small: 1200, large: 2400 };" in text
    assert "const PORTRAIT = { small: 900, large: 1800 };" in text
    assert "const START_QUALITY = 78;" in text
    # Every slot the site has is one the script knows how to cut.
    slots = set(re.findall(r'^    "([a-z-]+)": \{ ratio:', text, flags=re.M))
    m = _manifest()
    assert slots == set(m["PHOTO_SLOTS"]) | set(m["PLACEHOLDER_PHOTOS"])
    # And it runs from frontend/ as an npm script, with sharp pinned.
    pkg = json.loads((FRONTEND / "package.json").read_text())
    assert pkg["scripts"]["photos"] == "node scripts/prepare-photos.mjs"
    assert re.fullmatch(r"\d+\.\d+\.\d+", pkg["devDependencies"]["sharp"])
