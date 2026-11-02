"""Every route on the brand and creator routers has a caller in the frontend.

`test_manager_experience.py` made "a backend flow with no UI is not shipped"
mechanical for the manager router, and `test_admin_surface.py` for the admin
one. These are the two routers whose callers are the people the product is
*for*, and a route nobody can reach there is a promise made to a brand or a
creator in a route table and nowhere else.

**Each call form ends where the path ends.** The admin test's `API_BASE` form
has no terminator, so `${API_BASE}/drafts/${id}/file` counted as a caller of
`GET /drafts/{id}` — a prefix passing for a path. Here every form requires the
quote, `?` or end of the template right after the last segment, which is what
surfaced `GET /brand/campaigns` (shadowed by the `POST` beside it and by
longer paths under it) as uncalled.

Three lists, each read in a diff rather than loosened into the pattern:

- `INDIRECT_CALLERS` — reached through a path built at the call site (a verb in
  a variable, a base passed as a prop). Named with the file, and the file is
  checked to mention the path.
- `ALLOWED` — deliberately uncalled, each with why: a read whose answer already
  rides on a payload the screen fetches, or an ops door.
- `UNBUILT` — a ratchet: real gaps, asserted to be *still* uncalled, so
  building one fails the suite until the line is deleted.
"""
import ast
import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def no_comments(path: Path) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


_SOURCE = None


def frontend_source() -> str:
    global _SOURCE
    if _SOURCE is None:
        _SOURCE = "\n".join(
            no_comments(p)
            for p in FRONTEND.rglob("*.js*")
            if p.is_file() and "node_modules" not in p.parts
        )
    return _SOURCE


ROUTERS = {"brand_router": "/brand", "creator_router": "/creator", "drafts_router": "/drafts"}


def routes(router: str):
    src = Path(server.__file__).read_text()
    lines = src.splitlines()
    out = []
    for node in ast.parse(src).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            text = "\n".join(lines[d.lineno - 1 : d.end_lineno]).replace("\n", " ")
            m = re.search(rf'{router}\.(\w+)\(\s*"([^"]*)"', text)
            if m:
                out.append((router, m.group(1), m.group(2), node.name))
    return out


def _body(prefix: str, path: str) -> str:
    parts = [re.escape(seg) for seg in re.split(r"\{[^}]+\}", path)]
    return re.escape(prefix) + r"\$\{[^}]*\}".join(parts)


# The path is over: a closing quote, a query string, or the end of a template.
_END = r"(?=[`\"'?])"


def call_pattern(prefix: str, method: str, path: str) -> re.Pattern:
    body = _body(prefix, path) + _END
    forms = [
        rf"api\s*\.\s*{method}\s*\(\s*[`\"']{body}",
        rf"API_BASE\}}{body}",
        rf"downloadCsv\(\s*[`\"']{body}",
    ]
    # `ImageUploadField` takes one `endpoint` and both uploads (POST) and
    # removes (DELETE) against it, so the prop stands for every method — the
    # same reading the admin test gives `NumberSetting`'s GET/PUT pair.
    forms.append(rf"endpoint=\{{?\s*[`\"']{body}")
    if method == "post":
        forms.append(rf"url:\s*[`\"']{body}")
    return re.compile("|".join(forms))


INDIRECT_CALLERS = {
    # `/creator/collaborations/${id}/${what === "address" ? "confirm-address"
    # : "confirm-received"}` — one handler, the verb in a variable.
    ("creator_router", "post", "/collaborations/{collab_id}/confirm-address"):
        "components/creator/ActiveCampaigns.jsx",
    ("creator_router", "post", "/collaborations/{collab_id}/confirm-received"):
        "components/creator/ActiveCampaigns.jsx",
    # `VerificationExpiry` picks the role's half: `kind === "brand" ?
    # "/brand/verification/confirm" : "/creator/verification/confirm"`.
    ("creator_router", "post", "/verification/confirm"): "components/VerificationExpiry.jsx",
    ("brand_router", "post", "/verification/confirm"): "components/VerificationExpiry.jsx",
    # The proof image, fetched as an authenticated blob through a `path`
    # prop, never an `<img src>` at the API.
    ("creator_router", "get", "/collaborations/{collab_id}/content-proof/{proof_id}/file"):
        "components/collab/StoryProof.jsx",
    # The shared application screen is told where to post — `slotBase` is
    # `/brand` or `/manager` — and never asks what role is looking.
    ("brand_router", "post", "/collaborations/{collab_id}/slot/confirm"):
        "components/application/ApplicationDetail.jsx",
    ("brand_router", "post", "/collaborations/{collab_id}/slot/decline"):
        "components/application/ApplicationDetail.jsx",
}


ALLOWED = {
    # **Reads whose answer already rides on a payload the screen fetches.**
    # Kept because they are cheap, scoped and used by the integration suite;
    # listed so nobody mistakes them for a missing screen.
    ("brand_router", "get", "/campaigns"):
        "the brand dashboard (`GET /brand/dashboard`) carries every campaign",
    ("brand_router", "get", "/verification"):
        "`GET /brand/profile` carries the same `verification` block",
    ("creator_router", "get", "/held-applications"):
        "the creator dashboard carries `held_applications`",
    ("creator_router", "get", "/invitations"):
        "the creator dashboard carries `invitations`",
    # The draft block rides on the application screen (`GET /applications/{id}`)
    # and the creator's own card; the file itself is the audited `/file` route.
    ("drafts_router", "get", "/{collab_id}"):
        "the application payload and the creator's card carry `draft`",
}


UNBUILT = {
    # The brand's launch-night roster and its attendance button. The screen
    # for these is being built separately; on this branch nothing calls them,
    # so a brand cannot read its phone-free roster or mark a creator present.
    ("brand_router", "get", "/campaigns/{campaign_id}/roster"):
        "brand launch roster screen not on this branch",
    ("brand_router", "post", "/collaborations/{collab_id}/check-in"):
        "brand launch roster screen not on this branch",
    # `CreatorLists` creates, lists and deletes lists, and has no way to put a
    # creator on one — the PATCH that edits members has no caller.
    ("brand_router", "patch", "/creator-lists/{list_id}"):
        "no control adds or removes a list's members",
}


ROUTES = [r for router in ROUTERS for r in routes(router)]
EXEMPT = set(INDIRECT_CALLERS) | set(ALLOWED) | set(UNBUILT)
CHECKED = [r for r in ROUTES if (r[0], r[1], r[2]) not in EXEMPT]


def test_the_route_lists_are_not_empty():
    by_router = {name: [r for r in ROUTES if r[0] == name] for name in ROUTERS}
    assert len(by_router["brand_router"]) >= 30
    assert len(by_router["creator_router"]) >= 20


def test_the_exemptions_name_real_routes():
    live = {(r[0], r[1], r[2]) for r in ROUTES}
    stale = sorted(k for k in EXEMPT if k not in live)
    assert not stale, f"exempted but no longer exist: {stale}"


@pytest.mark.parametrize(
    "router,method,path,name",
    CHECKED,
    ids=[f"{ROUTERS[r]} {m.upper()} {p}" for r, m, p, _ in CHECKED],
)
def test_every_route_has_a_caller(router, method, path, name):
    prefix = ROUTERS[router]
    assert call_pattern(prefix, method, path).search(frontend_source()), (
        f"{method.upper()} {prefix}{path} ({name}) has no caller in the frontend. "
        "Build the UI, or add it to ALLOWED (with why it needs none) or "
        "UNBUILT (with what is missing)."
    )


@pytest.mark.parametrize(
    "key,why", sorted(UNBUILT.items()), ids=[f"{k[1].upper()} {k[2]}" for k in sorted(UNBUILT)]
)
def test_the_unbuilt_list_only_shrinks(key, why):
    router, method, path = key
    assert not call_pattern(ROUTERS[router], method, path).search(frontend_source()), (
        f"{method.upper()} {ROUTERS[router]}{path} now has a caller ({why}) — delete its line."
    )


@pytest.mark.parametrize(
    "key,where",
    sorted(INDIRECT_CALLERS.items()),
    ids=[f"{k[1].upper()} {k[2]}" for k in sorted(INDIRECT_CALLERS)],
)
def test_the_indirect_callers_are_where_they_say(key, where):
    router, method, path = key
    src = no_comments(FRONTEND / where)
    tail = [seg for seg in path.split("/") if seg and not seg.startswith("{")][-1]
    assert tail in src, f"{where} does not mention {tail} for {method.upper()} {path}"


def test_the_terminator_is_what_stops_a_prefix_passing():
    """The reason this file does not reuse the admin pattern, held directly."""
    pat = call_pattern("/drafts", "get", "/{collab_id}")
    assert not pat.search("href={`${API_BASE}/drafts/${id}/file`}")
    assert pat.search("api.get(`/drafts/${id}`)")


def test_the_dead_duplicate_slot_list_is_gone():
    """`GET /campaigns/{id}/slots` let an admin read what the live creator
    route does not, and nothing called it."""
    assert not hasattr(server, "list_slots_for_creator")
    paths = {getattr(r, "path", "") for r in server.app.routes}
    assert "/api/campaigns/{campaign_id}/slots" not in paths
    assert "/api/creator/campaigns/{campaign_id}/slots" in paths
