"""The signed-in app's type: Manrope, one Fraunces title, sentence-case labels.

The complaint this answers is that the app read thin and fussy: Fraunces at
every size including card titles and buttons, an 11px uppercase tracked
eyebrow above almost everything, and one sans (Inter Tight) chosen for a
poster-scale marketing site doing the work of a dense tool. Inside
`[data-surface="app"]` there is now one sans and it does all of it.

What is held here, and how:

* **The scope**, written on `<html>` for every app path by the pre-paint
  script and by `applyAppScope` — never on a public page. Both are evaluated
  in node against the same list of paths and must agree with each other.
* **Inside it, every family token is Manrope.** That is the guarantee behind
  "no computed font-family includes Inter Tight or JetBrains Mono": nothing in
  the stylesheet names either family except to define the public tokens, and
  the app redefines every one of those tokens.
* **The rules a file can break** — `font-serif`, tracked uppercase labels,
  mono, sub-12px and sub-400 type — are swept over the files that only ever
  render inside the app, walked from the router (`app_surface.py`). A file
  shared with a public page keeps its markup; the scope is what makes it read
  as the app inside the app.
* **One Fraunces per screen**: `.app-title`, at 28px or more, is the only way
  to reach Fraunces in the app, it lives on a page's own heading, and the
  files allowed to carry it are named below with a reason each.

The computed-style half — walking every element of a rendered screen for its
family, weight and size — is measured in a browser in the PR, against the
seeded demo data; jsdom computes no stylesheet.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from app_surface import APP_ONLY, SHARED, SRC, code_of, is_app_path

FRONTEND = SRC.parent
CSS = (SRC / "index.css").read_text()
INDEX_HTML = (FRONTEND / "public" / "index.html").read_text()
FONTS = FRONTEND / "public" / "fonts"


def _node(script: str) -> str:
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _block(selector: str) -> str:
    """The body of the first rule whose selector list is exactly `selector`."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert m, f"no rule for {selector}"
    return m.group(1)


def _faces():
    out = {}
    for body in re.findall(r"@font-face\s*\{(.*?)\}", CSS, flags=re.S):
        fam = re.search(r'font-family:\s*"([^"]+)"', body).group(1)
        out[fam] = body
    return out


def _px(value: str) -> float:
    value = value.strip()
    if value.endswith("px"):
        return float(value[:-2])
    if value.endswith("rem"):
        return float(value[:-3]) * 16
    raise AssertionError(f"unreadable size {value}")


# ---------------------------------------------------------------------------
# The font
# ---------------------------------------------------------------------------


class TestManrope:
    def test_it_is_self_hosted_latin_and_400_to_800(self):
        face = _faces()["Manrope"]
        assert 'url("/fonts/manrope-latin.woff2") format("woff2")' in face
        assert "font-weight: 400 800;" in face
        assert "font-display: swap;" in face
        assert "unicode-range: U+0000-00FF," in face
        assert (FONTS / "manrope-latin.woff2").is_file()
        assert "fonts.googleapis.com" not in CSS and "fonts.gstatic.com" not in INDEX_HTML

    def test_the_file_carries_exactly_that_weight_axis(self):
        ttlib = pytest.importorskip("fontTools.ttLib")
        font = ttlib.TTFont(FONTS / "manrope-latin.woff2")
        axes = {a.axisTag: (a.minValue, a.maxValue) for a in font["fvar"].axes}
        assert axes == {"wght": (400, 800)}, axes

    def test_it_has_metric_matched_fallbacks_for_desktop_and_android(self):
        faces = _faces()
        for name, local in (("Manrope Fallback", 'local("Arial")'),
                            ("Manrope Fallback Android", 'local("Roboto")')):
            face = faces[name]
            assert local in face and "url(" not in face, name
            for d in ("size-adjust", "ascent-override", "descent-override", "line-gap-override"):
                assert re.search(rf"{d}:\s*[\d.]+%;", face), (name, d)
        assert "Liberation Sans" in faces["Manrope Fallback"]

    def test_the_stack_names_its_fallbacks(self):
        stack = re.search(r"--font-app:\s*([^;]+);", CSS).group(1)
        assert stack.startswith('"Manrope", "Manrope Fallback", "Manrope Fallback Android"')
        title = re.search(r"--font-title:\s*([^;]+);", CSS).group(1)
        assert title.startswith('"Fraunces"')

    def test_the_build_script_and_readme_carry_it(self):
        script = (FRONTEND.parent / "scripts" / "build-fonts.py").read_text()
        assert '"manrope-latin.woff2", (400, 800)' in script
        assert '"Manrope Fallback"' in script and '"Manrope Fallback Android"' in script
        readme = (FONTS / "README.md").read_text()
        assert "manrope-latin.woff2" in readme and "wght 400–800" in readme

    def test_no_static_preload_and_the_scripted_one_is_app_only(self):
        """**A marketing route never asks for the file.** There is no
        `<link rel=preload>` for it in the document; the pre-paint script
        appends one inside the app branch, and only there."""
        static = re.findall(r"<link\s+rel=\"preload\"(.*?)/>", INDEX_HTML, flags=re.S)
        assert not any("manrope" in s for s in static), static
        script = _pre_paint_script()
        branch = script[script.index('setAttribute("data-surface", "app")') - 400:]
        assert "manrope-latin.woff2" in branch.split("if (theme")[0]


# ---------------------------------------------------------------------------
# The scope
# ---------------------------------------------------------------------------


def _pre_paint_script() -> str:
    m = re.search(r"<script>\s*(/\*.*?\*/)?\s*(\(function \(\) \{.*?\}\)\(\);)\s*</script>", INDEX_HTML, flags=re.S)
    assert m, "the pre-paint script moved"
    return m.group(2)


PATHS = [
    "/", "/for-brands", "/for-creators", "/about", "/contact", "/login", "/signup",
    "/terms", "/campaigns", "/campaigns/abc", "/c/abc", "/brands/abc", "/no-such-page",
    "/admin/login", "/admin/login/",
    "/dashboard", "/profile", "/calendar", "/check-in", "/onboarding/creator",
    "/onboarding/brand", "/campaigns/new", "/campaigns/abc/edit",
    "/brand/campaigns/abc/applicants", "/brand/applications/abc", "/manager",
    "/manager/campaigns/abc", "/admin", "/admin/queue", "/admin/campaigns/abc",
]


class TestTheScope:
    def test_the_pre_paint_script_and_the_module_agree_on_every_path(self):
        """Two implementations of "is this the app", and the one that runs
        first is the one nobody debugs. Both evaluated, path by path."""
        module = (SRC / "lib" / "surfaceTheme.js").read_text()
        out = json.loads(_node(
            module
            + f"\nconst SCRIPT = {json.dumps(_pre_paint_script())};\n"
            + f"const PATHS = {json.dumps(PATHS)};\n"
            + """
const res = {};
for (const path of PATHS) {
  const attrs = {}; const head = [];
  globalThis.location = { pathname: path };
  globalThis.localStorage = { getItem: () => null };
  globalThis.document = {
    documentElement: { setAttribute: (k, v) => { attrs[k] = v; }, style: {} },
    createElement: () => ({}),
    head: { appendChild: (el) => head.push(el.href) },
  };
  (0, eval)(SCRIPT);
  res[path] = { script: attrs["data-surface"] === "app",
                preload: head.some((h) => String(h).includes("manrope")),
                module: isAppPath(path) };
}
console.log(JSON.stringify(res));
"""))
        for path, r in out.items():
            assert r["script"] == r["module"], (path, r)
            assert r["preload"] == r["module"], (path, r)
            assert r["module"] == is_app_path(path), (path, r)
        # And the line itself, so a bug shared by all three still fails.
        assert not out["/"]["module"] and not out["/login"]["module"]
        assert not out["/admin/login"]["module"] and not out["/campaigns"]["module"]
        assert not out["/no-such-page"]["module"]
        assert out["/dashboard"]["module"] and out["/admin/queue"]["module"]
        assert out["/manager"]["module"] and out["/campaigns/new"]["module"]

    def test_the_attribute_has_two_writers(self):
        """The pre-paint script and `applyAppScope`; the route guard calls
        the second on every navigation."""
        writers = [
            p.relative_to(SRC) for p in SRC.rglob("*.js*")
            if "node_modules" not in p.parts and "__tests__" not in p.parts
            and 'setAttribute("data-surface"' in p.read_text()
        ]
        assert writers == [Path("lib/surfaceTheme.js")], writers
        app = (SRC / "App.js").read_text()
        guard = app[app.index("function SurfaceGuard"):app.index("function App()")]
        assert "applyAppScope(pathname)" in guard

    def test_every_family_token_is_manrope_inside_it(self):
        """**This is "no Inter Tight and no JetBrains Mono in the app".** Every
        text in the document gets its family through one of these four
        tokens, and inside the scope all four are Manrope."""
        body = _block('[data-surface="app"]')
        for token in ("--font-sans", "--font-serif", "--font-display", "--font-label"):
            assert f"{token}: var(--font-app);" in body, token

    def test_nothing_names_a_public_family_outside_the_tokens(self):
        """The guarantee above holds only while no rule reaches past the
        tokens to a family by name. `font-family: "Inter Tight"` in a rule, or
        a component's inline `fontFamily`, would escape the scope."""
        no_faces = re.sub(r"@font-face\s*\{.*?\}", "", CSS, flags=re.S)
        for decl in re.findall(r"font-family:\s*([^;]+);", no_faces):
            assert decl.strip().startswith("var(--font-"), decl
        for p in list(APP_ONLY) + list(SHARED):
            code = code_of(p.read_text())
            assert not re.search(r"Inter Tight|JetBrains|fontFamily", code), p.relative_to(SRC)

    def test_marketing_keeps_inter_tight_and_fraunces(self):
        root = re.search(r":root\s*\{\s*--font-serif:(.*?)\}", CSS, flags=re.S).group(0)
        assert '--font-sans: "Inter Tight"' in root
        assert '--font-serif: "Fraunces"' in root
        assert "font-family: var(--font-sans);" in _block("html,\n    body")

    def test_the_sizes_inside_it(self):
        """Body 15px, meta 13–13.5px, labels 12.5px — and nothing below 12px,
        compact density included."""
        body = _block('[data-surface="app"]')
        sizes = dict(re.findall(r"(--text-[\w-]+):\s*([^;]+);", body))
        assert _px(sizes["--text-body"]) == 15
        assert 13 <= _px(sizes["--text-meta"]) <= 13.5
        assert _px(sizes["--text-eyebrow"]) >= 12
        assert "--tracking-eyebrow: 0em;" in body
        label = re.search(r"--text-label:\s*([^;]+);", CSS).group(1)
        assert _px(label) >= 12
        compact = _block('[data-density="compact"]')
        for v in re.findall(r"--text-[\w-]+:\s*([^;]+);", compact):
            assert _px(v) >= 12, v
        tw = (FRONTEND / "tailwind.config.js").read_text()
        assert 'label: ["var(--text-label)", { lineHeight: "1.4", fontWeight: "600" }]' in tw

    def test_the_public_sans_corrections_are_undone(self):
        """Inter Tight's stylistic sets and its -0.005em mean nothing to
        Manrope."""
        m = re.search(r'html\[data-surface="app"\],\s*\[data-surface="app"\] body\s*\{([^}]*)\}', CSS)
        assert m and "font-feature-settings: normal;" in m.group(1) and "letter-spacing: 0;" in m.group(1)

    def test_a_heading_inside_it_is_manrope_bold_and_yields_to_a_class(self):
        body = _block('[data-surface="app"] :where(h1, h2, h3, h4, h5)')
        assert "font-weight: 700;" in body
        assert ":where(" in '[data-surface="app"] :where(h1, h2, h3, h4, h5)'

    def test_a_shared_eyebrow_reads_as_a_label_inside_it(self):
        body = _block('[data-surface="app"] .text-eyebrow')
        assert "text-transform: none;" in body and "font-weight: 600;" in body


# ---------------------------------------------------------------------------
# The rules a file can break
# ---------------------------------------------------------------------------


def _offenders(files, pattern, allow=lambda line: False):
    out = []
    for p in files:
        for i, line in enumerate(code_of(p.read_text()).splitlines(), 1):
            if re.search(pattern, line) and not allow(line):
                out.append(f"{p.relative_to(SRC)}:{i}: {line.strip()[:100]}")
    return out


class TestTheAppsOwnFiles:
    def test_the_walk_found_the_app(self):
        names = {p.relative_to(SRC).as_posix() for p in APP_ONLY}
        for must in ("pages/Dashboard.jsx", "pages/BrandDashboardView.jsx", "pages/AdminConsole.jsx",
                     "components/admin/console/DataTable.jsx", "pages/ManagerHome.jsx",
                     "components/creator/Hero.jsx"):
            assert must in names, must
        assert len(APP_ONLY) >= 120

    def test_no_fraunces_by_class(self):
        """`font-serif` points at Manrope inside the scope anyway; in a file
        that only renders there it is a word that says the opposite of what
        happens. The one way to Fraunces is `.app-title`."""
        assert not _offenders(APP_ONLY, r"\bfont-serif\b")

    def test_labels_are_sentence_case_and_untracked(self):
        """No tracked uppercase label, no eyebrow. The three inputs that
        upper-case what somebody types (IFSC, PAN) are not labels."""
        assert not _offenders(APP_ONLY, r"\btext-eyebrow\b|\btracking-(?:eyebrow|wide|wider|widest|\[0?\.\d+em\])",
                              allow=lambda l: "generated ?" in l or "select-all" in l)
        assert not _offenders(APP_ONLY, r"\buppercase\b", allow=lambda l: 'inputClass + " uppercase"' in l)

    def test_no_monospace_except_a_credential_shown_once(self):
        """The one-time password on the team screen is read aloud down a
        phone, character by character; that is what a monospace face is for.
        Nothing else in the app is."""
        offenders = _offenders(APP_ONLY, r"\bfont-mono\b|\bmkt-label\b|var\(--font-label\)")
        assert all(o.startswith("components/admin/AdminTeam.jsx") for o in offenders), offenders

    def test_nothing_below_12px(self):
        small = r"\btext-\[(?:[0-9]|1[01])(?:\.\d+)?px\]|\btext-\[0\.(?:[0-6]\d*|7[0-4]\d*)rem\]"
        assert not _offenders(list(APP_ONLY) + list(SHARED), small)

    def test_nothing_lighter_than_400_and_nothing_unloaded(self):
        assert not _offenders(list(APP_ONLY) + list(SHARED),
                              r"\bfont-(?:thin|extralight|light|black)\b|\bfont-\[[1-3]00\]")

    def test_figures_are_tabular_and_heavy(self):
        """Every figure is tabular already (set once on the document); a stat
        is Manrope 800 at -0.02em through `.app-figure`."""
        m = re.search(r"\.app-figure\s*\{([^}]*)\}", CSS)
        assert m, "no .app-figure"
        for d in ("font-weight: 800;", "letter-spacing: -0.02em;", "font-variant-numeric: tabular-nums;"):
            assert d in m.group(1), d
        html = re.search(r"html\s*\{\s*font-variant-numeric:\s*tabular-nums;", CSS)
        assert html, "the document-wide tabular rule moved"
        assert 'font-variant-numeric' not in _block('[data-surface="app"]')


# ---------------------------------------------------------------------------
# One Fraunces per screen
# ---------------------------------------------------------------------------

#: The files allowed to carry `.app-title`, each with how many and why. A
#: file with more than one renders them in mutually exclusive branches — one
#: screen never shows two. Adding a file here is a decision about which
#: heading is a screen's title, which is why it is a list somebody reviews.
TITLE_OWNERS = {
    "components/admin/DetailPage.jsx": (1, "every admin detail page's title, through DetailShell"),
    "components/admin/shared.jsx": (1, "every console section's header"),
    "components/creator/Hero.jsx": (1, "the creator's own name on their home"),
    "components/dashboard/CampaignDashboard.jsx": (1, "the campaign on its results page"),
    "components/manager/shared.jsx": (1, "the manager screens' page header"),
    "pages/BrandCampaignApplicants.jsx": (1, "the campaign on its applicant board"),
    "components/admin/Today.jsx": (1, "the overview's heading: how many things need a person today"),
    "components/brand/BrandOverview.jsx": (2, "the live campaign, or the post-a-brief panel in its place — one at a time"),
    "pages/BrandOnboarding.jsx": (1, "onboarding"),
    "pages/CreatorOnboarding.jsx": (1, "the profile builder"),
    "pages/CreatorProfile.jsx": (1, "the creator's own profile"),
    "pages/InstagramCallback.jsx": (3, "connecting, connected and failed — one at a time"),
    "pages/PostCampaign.jsx": (1, "posting or editing a brief"),
    "pages/SelfCheckIn.jsx": (3, "checking, checked in and refused — one at a time"),
    "pages/ShootCalendar.jsx": (1, "the calendar"),
}


def _titles(path: Path):
    code = code_of(path.read_text())
    return [m.start() for m in re.finditer(r"\bapp-title\b", code)], code


class TestOneTitle:
    def test_the_class_is_fraunces_600_and_never_below_28px(self):
        body = re.search(r"\.app-title\s*\{([^}]*)\}", CSS).group(1)
        assert "font-family: var(--font-title);" in body
        assert "font-weight: 600;" in body
        lo = re.search(r"font-size:\s*clamp\(([^,]+),", body).group(1)
        assert _px(lo) >= 28, lo

    def test_only_the_named_files_carry_it_and_no_more_than_named(self):
        found = {}
        for p in SRC.rglob("*.js*"):
            if "node_modules" in p.parts or "__tests__" in p.parts or ".test." in p.name:
                continue
            spots, _ = _titles(p)
            if spots:
                found[p.relative_to(SRC).as_posix()] = len(spots)
        assert set(found) == set(TITLE_OWNERS), set(found) ^ set(TITLE_OWNERS)
        for f, n in found.items():
            assert n <= TITLE_OWNERS[f][0], (f, n)

    def test_it_sits_on_a_heading_and_brings_no_size_of_its_own(self):
        """The size is the class's, so the 28px floor is structural: an
        element carrying it carries no `text-*` size, weight, tracking or
        leading of its own."""
        for rel in TITLE_OWNERS:
            spots, code = _titles(SRC / rel)
            for at in spots:
                tag_start = code.rfind("<", 0, at)
                tag = code[tag_start:code.find(">", at)]
                assert re.match(r"<(h1|h2)\b", tag), (rel, tag[:60])
                cls = re.search(r'className="([^"]*app-title[^"]*)"', tag).group(1)
                for bad in (r"\btext-(?:xs|sm|base|lg|xl|\dxl|h\d|body|meta|label|fluid|\[)",
                            r"\bfont-(?:normal|medium|semibold|bold|extrabold)\b",
                            r"\btracking-", r"\bleading-"):
                    assert not re.search(bad, cls), (rel, cls)

    def test_the_rule_can_fail(self):
        tag = '<p className="app-title text-h1">'
        assert not re.match(r"<(h1|h2)\b", tag)
        assert re.search(r"\btext-(?:xs|sm|base|lg|xl|\dxl|h\d|body|meta|label|fluid|\[)", "app-title text-h1")
