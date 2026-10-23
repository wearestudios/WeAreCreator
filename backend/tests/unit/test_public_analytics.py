"""The public-site recorder runs on the marketing pages, and nowhere else.

A session recording of a signed-in screen is a recording of a phone number, a
payout account and a PAN. The rule is enforced in code — `lib/track.js` plus
`components/AnalyticsGate.jsx` — and these tests hold it from both ends:

  - no tracked path is a signed-in route, read off the router itself;
  - the recorder is loaded by exactly one module, started by exactly one
    caller, and that caller requires a signed-out visitor;
  - `track.js`, driven in node, does nothing without an id, injects nothing
    before it is started, and stops for good once it is stopped;
  - every field on the one public form is masked, statically;
  - the privacy page says all of this.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "frontend" / "src"
TRACK = SRC / "lib" / "track.js"
GATE = SRC / "components" / "AnalyticsGate.jsx"
APP = SRC / "App.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _tracked_paths() -> list[str]:
    block = re.search(r"TRACKED_PATHS = \[(.*?)\];", _read(TRACK), re.S).group(1)
    return re.findall(r'"([^"]+)"', block)


def _protected_paths() -> list[str]:
    """Every `<Route path=…>` whose element is wrapped in `<ProtectedRoute>`."""
    app = _read(APP)
    out = []
    for m in re.finditer(r"<Route\s+path=\"([^\"]+)\"(.*?)(?=<Route\s|</Routes>)", app, re.S):
        if "ProtectedRoute" in m.group(2):
            out.append(m.group(1))
    return out


def _node(script: str, env: dict | None = None) -> str:
    """Run `track.js` as a module in node with a fake DOM, return stdout."""
    import os

    with tempfile.TemporaryDirectory() as d:
        mod = Path(d) / "track.mjs"
        mod.write_text(_read(TRACK), encoding="utf-8")
        runner = Path(d) / "run.mjs"
        runner.write_text(
            """
const appended = [];
const calls = [];
globalThis.window = globalThis;
globalThis.document = {
  createElement: (tag) => ({ tag, dataset: {} }),
  head: { appendChild: (el) => appended.push(el) },
};
const t = await import("./track.mjs");
"""
            + script,
            encoding="utf-8",
        )
        full_env = {**os.environ, **(env or {})}
        full_env.pop("REACT_APP_CLARITY_ID", None) if env is None else None
        res = subprocess.run(
            ["node", str(runner)], capture_output=True, text=True, timeout=30, env=full_env
        )
        assert res.returncode == 0, res.stderr
        return res.stdout.strip()


# --------------------------------------------------------------- where it runs


def test_no_tracked_path_is_a_signed_in_route():
    protected = _protected_paths()
    assert len(protected) > 10, "the router parse found too few protected routes to be trusted"
    tracked = set(_tracked_paths())
    for path in protected:
        assert path not in tracked, f"{path} is a signed-in route and is on the tracked list"
        # A tracked prefix must not cover a protected path either.
        assert not any(t != "/" and path.startswith(t + "/") for t in tracked), path


def test_the_tracked_list_is_the_public_marketing_pages_only():
    tracked = set(_tracked_paths())
    assert tracked == {
        "/",
        "/for-brands",
        "/for-creators",
        "/how-it-works",
        "/why-weare",
        "/contact",
        "/terms",
        "/privacy",
    }
    # Sign-in, signup and the brief feed are public but are not marketing:
    # two of them are where a phone number is typed.
    for path in ("/login", "/signup", "/campaigns", "/admin/login", "/dashboard"):
        assert path not in tracked


def test_the_recorder_is_loaded_by_one_module():
    hits = []
    for f in SRC.rglob("*.js*"):
        text = _read(f)
        if "clarity.ms" in text or "window.clarity" in text:
            hits.append(f.relative_to(SRC).as_posix())
    assert hits == ["lib/track.js"], hits


def test_only_the_gate_starts_it_and_the_gate_requires_a_signed_out_visitor():
    starters = [
        f.relative_to(SRC).as_posix()
        for f in SRC.rglob("*.js*")
        if f != TRACK and re.search(r"\bstartTracking\b", _read(f))
    ]
    assert starters == ["components/AnalyticsGate.jsx"], starters
    gate = _read(GATE)
    # Both conditions, in the one expression that decides.
    assert re.search(r"allowed\s*=\s*isTrackedPath\(pathname\)\s*&&\s*user\s*===\s*false", gate)
    # Anything else stops it.
    assert "stopTracking()" in gate
    # Mounted once, in the app shell, inside the router and the auth provider.
    app = _read(APP)
    assert app.count("<AnalyticsGate />") == 1
    assert app.index("<AuthProvider>") < app.index("<BrowserRouter>") < app.index("<AnalyticsGate />")


def test_no_signed_in_surface_imports_the_tracker():
    """Pages track through the gate's delegated listeners, not by importing it."""
    allowed = {"components/AnalyticsGate.jsx"}
    offenders = [
        f.relative_to(SRC).as_posix()
        for f in SRC.rglob("*.js*")
        if f != TRACK and "@/lib/track" in _read(f)
    ]
    assert set(offenders) <= allowed | {
        p.relative_to(SRC).as_posix()
        for p in (SRC / "components" / "marketing").rglob("*.js*")
    } | {
        f"pages/{n}.jsx"
        for n in ("Landing", "ForBrands", "ForCreators", "HowItWorks", "WhyWeAre", "Contact", "Home")
    }, offenders


# ------------------------------------------------------------- the module, run


def test_with_no_id_every_call_is_a_no_op():
    out = _node(
        """
t.startTracking();
t.track("cta_click", { page: "/", cta: "x" });
t.stopTracking();
console.log(JSON.stringify({ appended: appended.length, clarity: typeof window.clarity, active: t.trackingActive() }));
"""
    )
    assert json.loads(out) == {"appended": 0, "clarity": "undefined", "active": False}


def test_nothing_is_injected_until_it_is_started():
    out = _node(
        """
t.track("section_view", { page: "/", section: "hero" });
const before = appended.length;
t.startTracking();
t.startTracking();
console.log(JSON.stringify({ before, after: appended.length, src: appended[0] && appended[0].src }));
""",
        env={"REACT_APP_CLARITY_ID": "abc123"},
    )
    data = json.loads(out)
    assert data["before"] == 0
    assert data["after"] == 1, "a second start must not inject a second tag"
    assert data["src"] == "https://www.clarity.ms/tag/abc123"


def test_events_reach_the_provider_while_running_and_stop_is_final():
    out = _node(
        """
t.startTracking();
t.track("cta_click", { page: "/for-brands", cta: "hero-cta" });
t.stopTracking();
t.track("cta_click", { page: "/for-brands", cta: "after-stop" });
t.startTracking();
console.log(JSON.stringify({ q: window.clarity.q.map((a) => Array.from(a)), appended: appended.length, active: t.trackingActive() }));
""",
        env={"REACT_APP_CLARITY_ID": "abc123"},
    )
    data = json.loads(out)
    assert data["q"] == [
        ["event", "cta_click"],
        ["event", "cta_click:/for-brands#hero-cta"],
        ["stop"],
    ]
    assert data["appended"] == 1 and data["active"] is False


def test_a_stop_before_anything_started_does_not_latch():
    """Landing on sign-in first must not cost the home page its measurement."""
    out = _node(
        """
t.stopTracking();
t.startTracking();
console.log(JSON.stringify({ appended: appended.length, active: t.trackingActive() }));
""",
        env={"REACT_APP_CLARITY_ID": "abc123"},
    )
    assert json.loads(out) == {"appended": 1, "active": True}


# ------------------------------------------------------------------- masking


def test_the_contact_form_and_its_echo_are_masked_statically():
    contact = _read(SRC / "pages" / "Contact.jsx")
    mask = contact.index('data-clarity-mask="true"')
    assert mask < contact.index("data-testid={IDS.form}")
    assert mask < contact.index("data-testid={IDS.doneEcho}")


def test_the_gate_masks_every_field_it_sees():
    gate = _read(GATE)
    selector = re.search(r'MASK_SELECTOR = "([^"]+)"', gate).group(1)
    for kind in ("input", "textarea", "select", "contenteditable"):
        assert kind in selector
    assert 'setAttribute("data-clarity-mask", "true")' in gate


def test_the_whatsapp_event_never_carries_the_number():
    gate = _read(GATE)
    block = gate[gate.index("WHATSAPP_HREF.test(href)"):]
    block = block[: block.index("}")]
    assert "href" not in block.split("return", 1)[1], "the outbound event must not report the link"


def test_the_three_events_are_the_three_named():
    track = _read(TRACK)
    assert re.findall(r'"(section_view|cta_click|outbound_whatsapp)"', track) == [
        "section_view",
        "cta_click",
        "outbound_whatsapp",
    ]


# ----------------------------------------------------------- said in public


def test_the_privacy_page_says_what_is_recorded_and_where():
    legal = re.sub(r"\s+", " ", _read(SRC / "pages" / "Legal.jsx"))
    privacy = legal[legal.index("export function Privacy"):]
    assert "Analytics on our public pages" in privacy
    assert "Microsoft Clarity" in privacy
    assert "masked" in privacy
    assert "Nothing is recorded once you are signed in" in privacy
    # And it is named among the people we share with, not only described.
    sharing = privacy[privacy.index("Who we share it with"):]
    assert "Clarity" in sharing[: sharing.index("</Section>")]


def test_the_variable_is_documented():
    env = _read(SRC.parent / ".env.example")
    assert re.search(r"^REACT_APP_CLARITY_ID=$", env, re.M)
