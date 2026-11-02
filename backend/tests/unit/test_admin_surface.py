"""The admin console's own version of "a backend flow with no UI is not shipped".

`test_manager_experience.py` made that rule mechanical for **one** router out
of seventeen, and it found five real gaps the day it was written. This is the
same rule pointed at the admin router, which is the largest surface in the
product — 125 routes — and it found three that had cost something real:

- `POST /admin/managers` had no caller anywhere, so **no campaign-manager
  account could be created at all**. Every brand-posted brief is weare-run, so
  with no manager in existence no weare-run campaign could be staffed: no
  roster, no daysheet, no check-in on any of them. The campaign page's own
  assign dialog said "Create one first" and pointed at nothing.
- `POST /admin/campaigns/{id}/spot-check` had none, so the half of the review
  queue that holds *already live* briefs from trusted brands offered approve —
  whose write precondition those rows cannot satisfy — and answered 409 "This
  just moved" every time.
- `POST /admin/case-studies/images` had none, and `hero_image_url` is required
  to publish. So every case study was permanently unpublishable, with the
  publish button correctly disabled and "a hero image" listed as the reason,
  and nothing anywhere able to supply one.

**The route list is only half of it.** A route can have a caller in a file
nothing mounts — the lesson `<SlotAnswer />` taught — and a screen can crash
before it draws the control, which is what the Case studies section was doing:
three of its columns carried a `value` and no `cell`, `DataTable` calls
`col.cell(row)` on every render path, and the section had therefore only ever
rendered as "Case studies couldn't load". So the structural sweep here is
paired with driven assertions over the handlers it is about.
"""
import ast
import re
from pathlib import Path

import pytest
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def no_comments(path: Path) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def frontend_source() -> str:
    """Every source file, comments stripped, as one string.

    Comments go first because this codebase explains a removal where it
    happened, and an explanation necessarily quotes the path it is about — so
    reading them would let a sentence about a route that *used* to be called
    stand in for a caller.
    """
    return "\n".join(
        no_comments(p)
        for p in FRONTEND.rglob("*.js*")
        if p.is_file() and "node_modules" not in p.parts
    )


def admin_routes():
    """(method, path, handler) for everything on the admin router."""
    src = Path(server.__file__).read_text()
    lines = src.splitlines()
    out = []
    for node in ast.parse(src).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            text = "\n".join(lines[d.lineno - 1 : d.end_lineno]).replace("\n", " ")
            m = re.search(r'admin_router\.(\w+)\(\s*"([^"]+)"', text)
            if m:
                out.append((m.group(1), m.group(2), node.name))
    return out


def _body(path: str) -> str:
    parts = [re.escape(seg) for seg in re.split(r"\{[^}]+\}", path)]
    return r"/admin" + r"\$\{[^}]*\}".join(parts)


def call_pattern(method: str, path: str) -> re.Pattern:
    """The route as it is written at a call site, with the method checked.

    **The method is part of it**, which is the whole reason this catches
    anything: `/admin/managers` was already in the source as a `GET`, so a
    pattern matching the path alone passes the missing `POST` — and that was
    one of the three real gaps. Matching path-only was measured against this
    codebase and false-passed two of the three.

    Four call forms are accepted beside the obvious one, each because it is
    genuinely in use here and says the path unambiguously:

    - `api.get(` with whitespace or a newline before the `.`, which is how the
      longer handlers in this console are written.
    - `url: "/admin/..."` on a `POST`, the offline queue's declarative form —
      a request that has to survive a venue's wifi is declared as data so it
      can be put on disk and replayed.
    - `path: "/admin/..."` on a `POST`, the same idea in the review queue: a
      row's action is declared as `{ label, path, message }` and dispatched
      centrally, so one `api.post` serves every queue. Both of these are "the
      request as data", which is a shape worth having rather than one to
      regex around.
    - `endpoint="/admin/..."` as a prop. `NumberSetting` takes one endpoint and
      does both the `GET` and the `PUT` against it, so one prop legitimately
      covers a pair; the method is not checked for this form.
    - `${API_BASE}/admin/...`, an authenticated link or a blob download. The
      method is not checked for this one either.

    A form that matched a *bare* path literal anywhere was tried and rejected:
    it passes any route that shares a path with a called one, which is exactly
    the shape of the bugs this is looking for.
    """
    body = _body(path)
    forms = [
        rf"api\s*\.\s*{method}\s*\(\s*[`\"']{body}",
        rf"endpoint=\{{?\s*[`\"']{body}",
        rf"API_BASE\}}{body}",
        rf"downloadCsv\(\s*[`\"']{body}",
    ]
    if method == "post":
        forms.append(rf"url:\s*[`\"']{body}")
        forms.append(rf"path:\s*[`\"']{body}")
    return re.compile("|".join(forms))


# ---------------------------------------------------------------------------
# Reachable, but not by a string a regex can tie to a method
# ---------------------------------------------------------------------------
#
# **Named one by one, with the file, rather than loosened into the pattern.**
# Each of these is called through a path built at the call site — an action
# interpolated into the last segment, or a path held in an endpoint map — so
# the literal this test would look for does not appear in the source at all.
# A regex tolerant enough to pass them passes the real gaps too, so they are
# exemptions in a list somebody can read in a diff instead, which is the
# arrangement `clock-exempt:` and `ALIASES` already use here.
INDIRECT_CALLERS = {
    # `api.post(`/admin/brands/${userId}/trust/${action}`)` — one route per
    # verb, one call site, the verb in a variable.
    ("post", "/brands/{user_id}/trust/revoke"): "components/admin/BrandTrust.jsx",
    ("post", "/brands/{user_id}/trust/restore"): "components/admin/BrandTrust.jsx",
    # `homepage-logo/${action}`, same shape.
    ("post", "/brands/{user_id}/homepage-logo/approve"):
        "components/admin/BrandHomepageLogo.jsx",
    ("post", "/brands/{user_id}/homepage-logo/revoke"):
        "components/admin/BrandHomepageLogo.jsx",
    # `/admin/deletion-requests/${row.id}/${kind}` where kind is erase|decline.
    ("post", "/deletion-requests/{request_id}/erase"):
        "components/admin/AdminDeletions.jsx",
    ("post", "/deletion-requests/{request_id}/decline"):
        "components/admin/AdminDeletions.jsx",
    # An endpoint map: `confirm: (id) => `/admin/circumvention-reports/...``,
    # then `api.post(ENDPOINTS.confirm(id))`.
    ("post", "/circumvention-reports/{report_id}/confirm"):
        "components/admin/CircumventionQueue.jsx",
    ("post", "/circumvention-reports/{report_id}/dismiss"):
        "components/admin/CircumventionQueue.jsx",
}


# ---------------------------------------------------------------------------
# Built nowhere, and known to be
# ---------------------------------------------------------------------------
#
# **A ratchet, not a permanent exemption.** Every entry is a backend flow with
# no UI — the rule this file exists for — reported rather than wired, because
# wiring nineteen screens in one change is how a change stops being
# reviewable. The test below asserts each of these is *still* uncalled, so the
# day somebody builds one the suite tells them to delete the line. The list
# can only shrink.
#
# Grouped by what is actually wrong, because they are not one problem:
UNBUILT = {
    # --- Admin-editable numbers with an editor endpoint and no form. The
    # other six settings have one (`PlatformSettings` / `SlaSettings`); these
    # three were left out, so each is a number that needs a deploy to change
    # while looking as though it does not.
    ("get", "/settings/trusted-brands"): "TRUSTED_BRAND_APPROVALS has no form",
    ("put", "/settings/trusted-brands"): "TRUSTED_BRAND_APPROVALS has no form",
    ("get", "/settings/large-campaign"): "large_campaign_threshold has no form",
    ("put", "/settings/large-campaign"): "large_campaign_threshold has no form",
    ("get", "/settings/leaderboard"): "leaderboard floor/size have no form",
    ("put", "/settings/leaderboard"): "leaderboard floor/size have no form",

    # --- The six background jobs. Each runs on its own loop and each has an
    # admin door for running it now; only `/admin/jobs/retention` is wired, in
    # `RetentionPanel`. The others are reachable by nothing, so "run it now"
    # means a shell on the box.
    ("post", "/jobs/lifecycle"): "no 'run now' control",
    ("post", "/jobs/creator-nudges"): "no 'run now' control",
    ("post", "/jobs/instagram"): "no 'run now' control",
    ("post", "/jobs/leaderboard"): "no 'run now' control",
    ("post", "/jobs/brand-wall"): "no 'run now' control",
    ("post", "/jobs/analytics"): "no 'run now' control",

    # --- Case-study management beyond the editor.
    ("post", "/case-studies/order"): "display_order is settable and never set",
    ("delete", "/case-studies/{case_study_id}"): "a draft cannot be deleted",

    # --- Campaign actions with no button.
    ("post", "/campaigns/{campaign_id}/duplicate"):
        "the brand has a duplicate button; the console does not",
    ("put", "/campaigns/{campaign_id}/delivery-cost"):
        "delivery cost is recordable and unrecorded",

    # --- Reads whose data reaches the screen another way, so these are
    # redundant routes rather than missing screens. Listed because the rule is
    # about routes nothing calls, and the honest fix may be deleting them.
    ("get", "/campaigns/{campaign_id}/refund"):
        "the campaign detail payload already carries `refund`",
    ("get", "/creators/incomplete"):
        "no screen; `GET /admin/dormant` answers the adjacent question",

    # --- The survey results. `GET /admin/exports/survey` is wired and the
    # JSON read is not, so the answers are downloadable and not readable.
    ("get", "/survey/creator"): "no screen; only the CSV export is wired",
}

ROUTES = admin_routes()
CHECKED = [r for r in ROUTES if (r[0], r[1]) not in INDIRECT_CALLERS]


def test_the_route_list_is_not_empty():
    """A structural test that matches nothing passes for free."""
    assert len(ROUTES) >= 100, f"only found {len(ROUTES)} admin routes"


def test_the_exemption_lists_name_real_routes():
    """An entry for a route that no longer exists is a line nobody will delete.

    Both lists are keyed on (method, path), so a route renamed or removed
    leaves a stale key behind that quietly exempts nothing — and the next
    person reads it as a known gap that does not exist.
    """
    live = {(m, p) for m, p, _ in ROUTES}
    stale = sorted(k for k in set(INDIRECT_CALLERS) | set(UNBUILT) if k not in live)
    assert not stale, f"these are exempted but no longer exist: {stale}"


@pytest.mark.parametrize(
    "method,path,name",
    [r for r in CHECKED if (r[0], r[1]) not in UNBUILT],
    ids=[
        f"{m.upper()} {p}"
        for m, p, _ in CHECKED
        if (m, p) not in UNBUILT
    ],
)
def test_every_admin_route_has_a_caller_in_the_frontend(method, path, name):
    """The rule, made mechanical for the biggest router in the product.

    A route nobody can reach is not a feature, it is a promise in a route
    table — and on this router the promise was load-bearing three times over.
    """
    assert call_pattern(method, path).search(frontend_source()), (
        f"{method.upper()} /admin{path} ({name}) has no caller in the frontend. "
        "Either build the UI, or — if it is genuinely not wired yet — add it to "
        "UNBUILT with a line saying what is missing, so it is reported rather "
        "than forgotten."
    )


@pytest.mark.parametrize(
    "method,path,why",
    [(m, p, why) for (m, p), why in sorted(UNBUILT.items())],
    ids=[f"{m.upper()} {p}" for m, p in sorted(UNBUILT)],
)
def test_the_unbuilt_list_only_shrinks(method, path, why):
    """**The ratchet.** Each known gap is asserted to be *still* a gap.

    So this file cannot rot into a list of things that were fixed years ago:
    build one of these and the suite fails here, telling you to delete the
    line. That is the opposite of an exemption, which is why it is a separate
    test from the one above rather than a skip inside it.
    """
    assert not call_pattern(method, path).search(frontend_source()), (
        f"{method.upper()} /admin{path} now HAS a caller ({why}) — "
        "delete its line from UNBUILT, which is a backlog rather than a licence."
    )


@pytest.mark.parametrize(
    "method,path,where",
    [(m, p, w) for (m, p), w in sorted(INDIRECT_CALLERS.items())],
    ids=[f"{m.upper()} {p}" for m, p in sorted(INDIRECT_CALLERS)],
)
def test_the_indirect_callers_are_where_they_say(method, path, where):
    """An exemption naming a file is checkable, so it is checked.

    The path's own head has to appear in the file the exemption names. Without
    this the list would be a set of claims, and a component deleted or renamed
    would leave a route exempted on the strength of a comment.
    """
    src = no_comments(FRONTEND / where)
    head = path.rsplit("/", 1)[0]
    assert re.search(_body(head), src), (
        f"{method.upper()} /admin{path} is exempted as called from {where}, "
        f"but that file does not mention /admin{head}"
    )


# ---------------------------------------------------------------------------
# The three gaps, driven rather than read
# ---------------------------------------------------------------------------


LOOP = None


def run(coro):
    """One loop, kept in a module global — the idiom the money suites use.

    `asyncio.get_event_loop()` fails inside a pytest-xdist worker thread and
    `asyncio.run` closes the loop mongomock's cursors were built on, so a
    helper written either of those ways passes alone and fails in the suite.
    Which is exactly what this one did first: four green tests in isolation
    and four red in `pytest tests/unit`.
    """
    import asyncio

    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP.run_until_complete(coro)


@pytest.fixture
def db(monkeypatch):
    client = AsyncMongoMockClient()
    database = client["test_admin_surface"]
    monkeypatch.setattr(server, "db", database)
    return database


ADMIN = {"_id": None, "role": "admin", "name": "An admin"}


def _campaign(**over):
    from datetime import datetime, timezone

    doc = {
        "brand_id": server.ObjectId(),
        "title": "A brief",
        "status": "draft",
        "created_at": datetime.now(timezone.utc),
    }
    doc.update(over)
    return doc


class TestTheReviewBadgeCountsBothKinds:
    """`campaigns_to_review` counted one of the two kinds the queue returns.

    `list_campaigns_for_review` deliberately returns submitted briefs **and**
    trusted brands' auto-published ones awaiting a spot check. The badge was
    `campaigns_by_status[pending_review]`, which a status aggregation can
    answer and which is therefore blind to the second kind — those rows carry
    status `open`. A console with four live briefs waiting on a read showed
    `0` over a queue with four rows in it.

    **Driven rather than read.** The badge and the queue are asserted against
    each other through the real handlers, because the failure this is about is
    exactly the two disagreeing — and a source check for `auto_published_at`
    passes on a query that names the field and gets the logic wrong.
    """

    def _both(self, db):
        """What the badge says, and how many rows the queue actually returns."""
        dash = run(server.admin_dashboard(user=ADMIN))
        rows = run(server.list_campaigns_for_review(user=ADMIN))
        return dash["awaiting"], rows

    def test_a_submitted_brief_is_counted(self, db):
        run(db.campaigns.insert_one(_campaign(status=server.CAMPAIGN_REVIEW_STATUS)))
        awaiting, rows = self._both(db)
        assert len(rows) == 1
        assert awaiting["campaigns_to_review"] == 1
        assert awaiting["campaigns_to_spot_check"] == 0, (
            "a brief nobody published is not awaiting a spot check"
        )

    def test_an_auto_published_brief_awaiting_a_spot_check_is_counted_too(self, db):
        from datetime import datetime, timezone

        run(
            db.campaigns.insert_one(
                _campaign(
                    status="open",
                    auto_published_at=datetime.now(timezone.utc),
                    spot_checked_at=None,
                )
            )
        )
        awaiting, rows = self._both(db)
        # The control, and it is the whole bug: by status alone this is zero.
        assert awaiting["campaigns_to_review"] == len(rows) == 1, (
            "the badge has to count the row the queue shows"
        )
        assert awaiting["campaigns_to_spot_check"] == 1

    def test_the_two_kinds_sum(self, db):
        from datetime import datetime, timezone

        run(db.campaigns.insert_one(_campaign(status=server.CAMPAIGN_REVIEW_STATUS)))
        run(
            db.campaigns.insert_many(
                [
                    _campaign(
                        status="open",
                        auto_published_at=datetime.now(timezone.utc),
                        spot_checked_at=None,
                    )
                    for _ in range(3)
                ]
            )
        )
        awaiting, rows = self._both(db)
        assert awaiting["campaigns_to_review"] == len(rows) == 4
        assert awaiting["campaigns_to_spot_check"] == 3, (
            "and the live half is reported apart, because it is a different job"
        )

    def test_one_already_spot_checked_is_neither(self, db):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        run(
            db.campaigns.insert_one(
                _campaign(status="open", auto_published_at=now, spot_checked_at=now)
            )
        )
        awaiting, rows = self._both(db)
        assert rows == [] or len(rows) == 0, "a read that happened is not in the queue"
        assert awaiting["campaigns_to_review"] == 0
        assert awaiting["campaigns_to_spot_check"] == 0


# ---------------------------------------------------------------------------
# The screens, not just the routes
# ---------------------------------------------------------------------------


def test_the_manager_form_is_gated_on_all_access():
    """`POST /admin/managers` is admin-only where this console is CONSOLE_ROLES.

    A `weare_team` member drawing the form would be drawing a form the server
    refuses, which is the failure `_why_brand_is_blocked` exists to avoid one
    level up: a control that 403s is worse than one that is absent.
    """
    src = no_comments(FRONTEND / "components/admin/AdminTeam.jsx")
    assert "allAccess" in src, "the manager block has to be gated"
    assert re.search(r"allAccess\s*&&\s*<Managers", src), (
        "the gate has to be on the manager block, not merely imported"
    )
    routes = no_comments(FRONTEND / "components/admin/routes.jsx")
    assert re.search(r"AdminTeam\s+allAccess=\{allAccess\}", routes), (
        "and the route has to pass it, or the prop defaults open"
    )


def test_a_created_password_is_never_read_back_from_the_server():
    """It is shown once, from what the browser generated, and never logged.

    The create route answers with the account and no credential, so there is
    nothing to echo — this pins that the screen does not start echoing one,
    and that nothing here reaches for a logger with it.
    """
    src = no_comments(FRONTEND / "components/admin/AdminTeam.jsx")
    assert "data.password" not in src, "the server does not return one to show"
    assert not re.search(r"console\.(log|info|warn|error)", src), (
        "a password on this screen must not reach a console line"
    )
    assert "crypto.getRandomValues" in src, "Math.random is not a password source"


def test_the_live_half_of_the_review_queue_cannot_be_approved():
    """Approve is not offered on a row whose approve cannot succeed.

    The precondition is `status == pending_review`, which an auto-published
    brief does not have, so the button answered 409 "This just moved — reload
    and try again": a refusal describing a race that did not happen.
    """
    src = no_comments(FRONTEND / "components/admin/Reviews.jsx")
    assert "altPrimary" in src, "the queue needs a per-row primary action"
    assert "spot-check" in src, "and the action that can actually succeed"
    # The badge read the queue rather than the row, so a live brief was
    # labelled with the one word for it that is false.
    assert re.search(r"renderBadge:\s*\(r\)", src), (
        "the badge has to take the row, or both kinds read the same"
    )
    assert "auto_published" in src, "which is the field that tells them apart"


def test_the_case_study_editor_can_supply_the_hero_publish_requires():
    """`hero_image_url` is required to publish and the editor never sent it.

    Two halves, and both were missing: a control that uploads to the one route
    that issues an image path, and the key in the `PUT` body — `PUT` writes
    only the keys it is sent, so a field the form never sends is a field the
    form cannot change.
    """
    src = no_comments(FRONTEND / "components/admin/CaseStudies.jsx")
    assert "/admin/case-studies/images" in src, "no way to get a path we issued"
    assert "hero_image_url" in src, "and no way to store it"
    assert re.search(r"hero_image_url:\s*form\.hero_image_url", src), (
        "the PUT body has to carry it"
    )
    assert "hero_image_url" in server._CASE_STUDY_REQUIRED, (
        "if this stops being required, this test is the wrong shape"
    )


def test_every_case_study_column_can_draw_itself():
    """`DataTable` calls `col.cell(row, index)` on every path it renders.

    Three of this list's columns carried a `value` and no `cell`, so the
    section threw `col.cell is not a function` on first paint and the whole
    Case studies screen had only ever rendered as "Case studies couldn't
    load" — behind which sat the editor this change is about. `value` is what
    sorts and `cell` is what draws; a column needs both.
    """
    src = (FRONTEND / "components/admin/CaseStudies.jsx").read_text()
    block = src[src.index("const columns = useMemo") : src.index("return (", src.index("const columns = useMemo"))]
    # Each column object in that block, by its key.
    for m in re.finditer(r"\{\s*\n\s*key:\s*[\"'](\w+)[\"'],(.*?)\n\s{12}\},", block, re.S):
        key, body = m.group(1), m.group(2)
        assert "cell:" in body, (
            f"the '{key}' column has no `cell`, so DataTable throws on it"
        )
