"""The managed-only positioning, and the shortlist gate driven end to end.

Two halves, both aimed at failures the existing suite could not see.

**The sweep.** `test_managed_and_commission.py` checks the shortlist gate one
surface at a time — the board, the count, the door to a single application, the
export — and each of those tests names the surface it protects. That is the
right instrument for the surfaces somebody thought of, and it is exactly the
wrong one for the surface nobody did: a new brand-facing payload ships with no
test and the suite stays green. So the sweep below plants a **recognisable
value on an unshortlisted creator**, calls every brand-facing handler for real,
and searches the serialised output for it. It is the arrangement
`test_exports.py` uses for contact details, for the same reason stated there:
source-reading catches the mistake somebody makes on purpose, running it
catches the one where a name arrives through a `**spread` from a document
nobody remembered had it.

**The copy.** The marketing tests already hold the five marketing pages. What
they cannot see is the authenticated product, which is where most of the
self-serve promises actually lived — an empty state offering an Invite button
that no longer renders, an unverify dialog naming a creator directory that was
deleted, a dead `EXECUTION_OPTIONS` export whose label still said "we'll run it
ourselves". Those are one grep each and the grep is the test.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None
FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


def run(body):
    async def go():
        db = AsyncMongoMockClient()["managed_copy"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return _loop().run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def sources(*roots):
    """Every source file under the named directories."""
    for root in roots:
        base = FRONTEND.joinpath(root)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix in (".js", ".jsx") and path.is_file():
                yield path


# The two creators the sweep plants. Both names are unmistakable in a blob of
# JSON, and neither is a substring of the other or of any field name — a
# search that matched "Asha" inside "Ashardware" would be a search that cannot
# fail for the wrong reason.
SHORTLISTED = "Shortlistedzzz"
UNSHORTLISTED = "Unshortlistedqqq"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


async def _brand(db, *, verified=True):
    oid = ObjectId()
    await db.users.insert_one(
        {"_id": oid, "role": "brand_manager", "name": "Toit", "brand_id": oid,
         "phone": "+919900000001"}
    )
    await db.brand_profiles.insert_one(
        {"user_id": oid, "business_name": "Toit", "verified": verified,
         "verified_at": _now()}
    )
    account = await db.users.find_one({"_id": oid})
    return {**account, "_id": str(oid)}, oid


async def _campaign(db, brand_oid, **over):
    oid = ObjectId()
    doc = {
        "_id": oid, "brand_id": brand_oid, "title": "Tasting", "status": "open",
        "execution_owner": "weare", "compensation_type": "fixed",
        "budget_per_creator": 12000, "creators_needed": 4,
        "created_at": _now(), "state_since": _now(), **over,
    }
    await db.campaigns.insert_one(doc)
    return await db.campaigns.find_one({"_id": oid})


async def _collab(db, campaign, *, name, state="applied", shortlisted=False):
    creator_oid, oid = ObjectId(), ObjectId()
    await db.users.insert_one(
        {"_id": creator_oid, "role": "creator", "name": name,
         "phone": "+919900000002"}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": name, "verification_status": "verified",
         "instagram_handle": name.lower(), "city": "Bengaluru"}
    )
    await db.collaborations.insert_one(
        {"_id": oid, "campaign_id": campaign["_id"], "creator_id": creator_oid,
         "state": state, "quoted_rate": 12000, "created_at": _now(),
         "state_since": _now(),
         # `agreed_at` is the shortlist line, written as the app writes it:
         # absent rather than None on a pitch nobody has worked yet.
         **({"agreed_at": _now(), "agreed_amount": 12000} if shortlisted else {})}
    )
    return {"id": str(oid), "oid": oid, "creator_oid": creator_oid}


async def _one_of_each(db, **campaign_over):
    """A weare-run brief with one worked application and one raw one."""
    user, brand_oid = await _brand(db)
    campaign = await _campaign(db, brand_oid, **campaign_over)
    await _collab(db, campaign, name=SHORTLISTED, state="accepted", shortlisted=True)
    raw = await _collab(db, campaign, name=UNSHORTLISTED, state="applied")
    return user, brand_oid, campaign, raw


def blob(value):
    """Everything a payload actually carries, as one searchable string.

    `json.dumps` with `default=str` rather than a recursive walk, because the
    thing being protected against is a value arriving somewhere nobody thought
    to look — including inside a nested list of dicts three levels down that
    the reader of this test has never seen.
    """
    return json.dumps(value, default=str)


# ---------------------------------------------------------------------------
# The sweep: no unshortlisted creator reaches a brand, on any surface
# ---------------------------------------------------------------------------


class TestNothingUnshortlistedLeaks:
    """Every brand-facing payload, with a planted name and a positive control.

    The control is what makes each of these able to fail. A handler that
    returned nothing at all, or one that filtered every creator out, would
    satisfy "the unshortlisted name is absent" perfectly — so every case also
    asserts the *shortlisted* name is present, which is the same assertion
    pointed the other way.
    """

    def test_the_applicant_board(self):
        async def body(db):
            user, _, campaign, _ = await _one_of_each(db)
            out = blob(await server.list_campaign_applicants(str(campaign["_id"]), user))
            assert SHORTLISTED in out
            assert UNSHORTLISTED not in out

        run(body)

    def test_the_campaign_list(self):
        async def body(db):
            user, _, _, _ = await _one_of_each(db)
            out = blob(await server.list_brand_campaigns(None, user))
            assert UNSHORTLISTED not in out
            # The count is a perfectly good way to leak that somebody exists,
            # so the control here is the number rather than the name.
            rows = await server.list_brand_campaigns(None, user)
            assert rows[0]["applicant_count"] == 1

        run(body)

    def test_the_dashboard(self):
        async def body(db):
            user, _, _, _ = await _one_of_each(db)
            dash = await server.get_brand_dashboard(user)
            assert UNSHORTLISTED not in blob(dash)
            assert dash["totals"]["total_applications"] == 1

        run(body)

    def test_the_campaign_detail_read(self):
        async def body(db):
            user, _, campaign, _ = await _one_of_each(db)
            out = blob(await server.get_campaign(str(campaign["_id"]), user))
            assert UNSHORTLISTED not in out

        run(body)

    def test_the_close_out_export(self):
        async def body(db):
            _, _, campaign, _ = await _one_of_each(db, status="closed")
            await db.collaborations.update_many(
                {"campaign_id": campaign["_id"], "state": "accepted"},
                {"$set": {"state": "closed"}},
            )
            # Cancelled straight out of `applied` — in `_BRAND_EXPORT_STATES`
            # and never shortlisted, which is the pair the state list alone
            # would let through.
            await db.collaborations.update_many(
                {"campaign_id": campaign["_id"], "state": "applied"},
                {"$set": {"state": "cancelled"}},
            )
            csv_text = await server._build_brand_campaign_export(campaign)
            assert SHORTLISTED in csv_text
            assert UNSHORTLISTED not in csv_text

        run(body)

    def test_the_door_to_a_single_application(self):
        # A board that hides a row while its id opens the pitch is a shield on
        # one of two doors, which is a shield on neither. Both doors here —
        # the collaboration and the notes thread hanging off it.
        async def body(db):
            user, _, _, raw = await _one_of_each(db)
            for door in (server._brand_collab_or_404, server._note_readable_collab_or_404):
                with pytest.raises(HTTPException) as err:
                    await door(raw["id"], user)
                assert err.value.status_code == 404, door.__name__

        run(body)

    def test_the_notification_a_raw_application_sends(self):
        # Routing, not projection: on a weare-run brief a new application goes
        # to `notify_weare_team`. The brand hears at the shortlist, from
        # `_tell_brand_about_shortlist`, and not before.
        async def body(db):
            user, brand_oid = await _brand(db)
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            campaign = await _campaign(db, brand_oid)
            creator_oid = ObjectId()
            await db.users.insert_one(
                {"_id": creator_oid, "role": "creator", "name": UNSHORTLISTED,
                 "phone": "+919900000003"}
            )
            await db.creator_profiles.insert_one(
                {"user_id": creator_oid, "name": UNSHORTLISTED,
                 "verification_status": "verified", "verified_at": _now()}
            )
            await server.apply_to_campaign(
                str(campaign["_id"]),
                server.ApplyPayload(pitch="I'd love to", quoted_rate=12000),
                {"_id": str(creator_oid), "role": "creator", "name": UNSHORTLISTED},
            )
            told = await db.notifications.find({"user_id": brand_oid}).to_list(length=20)
            assert blob(told) == "[]" or UNSHORTLISTED not in blob(told)
            assert told == []

        run(body)

    def test_a_brand_run_campaign_is_the_control(self):
        """**The gate is `execution_owner`, not "hide everybody".**

        Without this, a `_brand_sees_collab` that returned False unconditionally
        would pass every test above. On a brand-run brief the brand *is* the
        one shortlisting, so a raw application is theirs to read — and only an
        admin can make a campaign brand-run now, which is the point.
        """
        async def body(db):
            user, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid, execution_owner="brand")
            await _collab(db, campaign, name=UNSHORTLISTED, state="applied")

            out = blob(await server.list_campaign_applicants(str(campaign["_id"]), user))
            assert UNSHORTLISTED in out

            rows = await server.list_brand_campaigns(None, user)
            assert rows[0]["applicant_count"] == 1

        run(body)


# ---------------------------------------------------------------------------
# The copy: nothing anywhere offers a capability a brand does not have
# ---------------------------------------------------------------------------


# Phrases that describe the product we stopped selling. Each is matched
# case-insensitively against source with comments left *in* — a comment is
# where a removed promise goes to survive, and the point of this sweep is that
# the next person writing a label does not find one to copy.
#
# Comments explaining a removal necessarily quote the thing removed, so the
# scan reads the rendered strings rather than the whole file: `_strings_of`
# below pulls every double-quoted and single-quoted literal out, which is what
# a reader can actually see.
FORBIDDEN_BRAND_COPY = (
    "run it yourself",
    "self-serve",
    "manage it from your dashboard",
    "you choose per campaign",
    "browse creators",
    "creator directory",
    "invite creators yourself",
)

# Where brand-facing copy lives. Not `components/admin/` — an admin genuinely
# can invite, and an admin screen saying so is accurate.
BRAND_SURFACES = ("pages", "components/brand", "components/marketing", "lib")

# Files under those roots that legitimately name the removed capabilities.
# `Legal.jsx` describes what the platform does with data and has to be able to
# say what a creator directory was; the admin console's own vocabulary lives
# in `consoleScope.js`.
COPY_SWEEP_EXEMPT = {"Legal.jsx", "consoleScope.js"}


def _strip_comments(src):
    """A source file with every comment removed.

    **This is load-bearing, not tidiness.** The convention in this codebase is
    that a removal is explained where it happened, so the comment necessarily
    quotes the phrase that went — in quotation marks, which is exactly what a
    literal scan picks up. Without this, every justification comment written
    for this change would fail the sweep written to enforce it, and the
    obvious fix would be to delete the explanations.

    `{/* … */}` blocks span lines, so a line-prefix filter is not enough.
    """
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def _strings_of(src):
    """Every string literal a reader could actually see, lowercased."""
    src = _strip_comments(src)
    out = []
    for pattern in (r'"((?:[^"\\\n]|\\.)*)"', r"'((?:[^'\\\n]|\\.)*)'"):
        out += re.findall(pattern, src)
    return " ¶ ".join(out).lower()


@pytest.mark.parametrize("phrase", FORBIDDEN_BRAND_COPY)
def test_no_brand_surface_offers_a_capability_the_brand_does_not_have(phrase):
    """**The product is managed-only, so the copy has to be.**

    A brand cannot run a campaign itself, cannot invite a creator and cannot
    reach a directory. Every one of those was still promised somewhere when
    this was written — the audience page, the standalone case, the applicant
    board's empty state, and a dead export in `lib/execution.js` whose label
    read "we'll run it ourselves". A brand that reads any of them arrives
    expecting a screen that does not exist, which is a worse first hour than
    being told plainly what we do.
    """
    for path in sources(*BRAND_SURFACES):
        if path.name in COPY_SWEEP_EXEMPT:
            continue
        assert phrase not in _strings_of(path.read_text()), f"{path.name}: {phrase!r}"


def test_the_sweep_can_actually_fail():
    """A sweep that matches nothing is a sweep nobody can trust.

    The phrases above are gone from the tree, so every assertion passes
    vacuously if `_strings_of` is broken — which it was, twice, while this was
    being written. This drives the same reader over a file that really does
    contain one.
    """
    planted = 'const x = "Run it yourself, or hand it over.";'
    assert "run it yourself" in _strings_of(planted)
    # And a phrase that appears only in a comment is deliberately *not* found,
    # because that is how a removal gets explained.
    assert "run it yourself" not in _strings_of("// Was: run it yourself.\n")


def test_the_dead_execution_picker_is_gone_rather_than_unused():
    """`EXECUTION_OPTIONS` had no caller and still carried the old labels.

    Dead copy offering a removed capability is what the next person reaches
    for when they need a label, so it is deleted rather than left exported.
    The admin's own control spells its two options inline — "we'll run it
    ourselves" means the brand on a brand's form and would mean WeAre on the
    admin's, which is the same words for opposite parties.
    """
    src = read("lib", "execution.js")
    # The export, not the name: the comment explaining why it went says what
    # it was called, which is the whole value of leaving one.
    assert "export const EXECUTION_OPTIONS" not in src
    for path in sources("pages", "components"):
        assert "EXECUTION_OPTIONS" not in _strip_comments(path.read_text()), path.name


def test_the_unverify_dialog_names_gates_that_exist():
    """It said unverifying closes "publishing, inviting and the creator
    directory". A brand has neither of the last two — inviting is ours and the
    directory was removed outright — so two thirds of the sentence described
    nothing, at the moment somebody is deciding to pull a business off the
    air."""
    src = read("components", "admin", "BrandDetailPage.jsx")
    strings = _strings_of(src)
    assert "publishing, inviting and the creator directory" not in strings
    assert "takes the brand back behind the gate" in strings


def test_the_empty_applicant_board_does_not_offer_an_invite():
    """The board's own empty state was the last place still pointing at the
    Invite button — an empty state naming an affordance that is not on the
    screen is worse than an empty state."""
    strings = _strings_of(read("pages", "BrandCampaignApplicants.jsx"))
    assert "invite creators yourself" not in strings
    assert "our team is casting this brief now" in strings


# ---------------------------------------------------------------------------
# The commercial terms, which are the sales points
# ---------------------------------------------------------------------------


class TestTheCommercialTermsAreStated:
    """**Both were true before this and neither was written down anywhere a
    brand could read it.**

    The refund policy was stated at creation and frozen into the snapshot. The
    commission arrangement — charged on top of the creator's rate, never out of
    it — was said only on the creator's side of the marketing site. A brand
    reading "platform fee" with no explanation assumes somebody's rate is being
    clipped, and a squeezed creator is one who takes the next brief
    off-platform, which is the failure `CIRCUMVENTION_TERMS` exists to name.
    """

    def test_the_two_terms_mirror_the_frontend_exactly(self):
        # The post form renders both *before* a campaign exists, so there is
        # nothing to fetch them from at the moment they matter most. Same
        # arrangement `followerTiers.js` and `platformTerms.js` use.
        src = read("lib", "execution.js")
        for name, constant in (
            ("REFUND_TERMS", server.REFUND_POLICY_TERMS),
            ("COMMISSION_TERMS", server.COMMISSION_TERMS),
        ):
            assert f"export const {name} =" in src, name
            joined = re.sub(r'"\s*\+\s*\n\s*"', "", src)
            assert constant in joined, name

    def test_both_ride_on_the_create_response(self):
        async def body(db):
            user, _ = await _brand(db)
            out = await server.create_brand_campaign(
                server.PostCampaignPayload(
                    title="Tasting evening",
                    brief="Come and shoot the new menu.",
                    deliverable_items=[{"type": "reel", "quantity": 1}],
                    budget_per_creator=12000,
                    category="fnb",
                    area="Indiranagar",
                    creators_needed=4,
                    campaign_type="personal_table",
                    start_date=_now(),
                    end_date=_now(),
                ),
                user,
            )
            assert out["refund_terms"] == server.REFUND_POLICY_TERMS
            assert out["commission_terms"] == server.COMMISSION_TERMS
            assert out["managed_note"] == server.MANAGED_BY_DEFAULT_SENTENCE

        run(body)

    def test_the_commission_arrangement_is_frozen_into_the_snapshot(self):
        """Frozen, not fetched. A later rewording must not be applied
        backwards to somebody who agreed to different words — the rule
        `CANCELLATION_TERMS` and `CIRCUMVENTION_TERMS` already hold."""
        terms = server._build_terms({"title": "Tasting"}, {})
        assert terms["commission_terms"] == server.COMMISSION_TERMS
        assert terms["refund_terms"] == server.REFUND_POLICY_TERMS

    def test_the_rate_itself_is_not_in_the_snapshot(self):
        """**The arrangement is frozen; the number is not.**

        A rate is resolved per payment and frozen *there* (`fee_percent`), so
        putting a percentage in the collaboration's snapshot would be a second
        historical record of the same fact — and the two would disagree the
        first time a brand's rate was renegotiated between acceptance and
        payment.
        """
        terms = server._build_terms({"title": "Tasting"}, {})
        assert "commission_percent" not in terms
        assert "fee_percent" not in terms
        assert "%" not in terms["commission_terms"]

    def test_the_form_renders_both_before_the_button(self):
        """A promise a brand reads after posting is not what it decided on."""
        src = read("pages", "PostCampaign.jsx")
        assert "COMMISSION_TERMS" in src and "REFUND_TERMS" in src
        assert "{COMMISSION_TERMS}" in src and "{REFUND_TERMS}" in src

    def test_the_snapshot_card_renders_it(self):
        """The half that nearly shipped with no caller. `_build_terms` putting
        a key in the payload proves nothing about whether anybody draws it —
        the lesson `can_accept_partial` taught, which sat on a shared payload
        rendered by nothing for a whole batch.

        **Twice, not once**, and break-testing is what found that: the key is
        guarded before it is drawn (`{terms.commission_terms && (`), so a
        single mention survives the *body* being replaced by null. One
        occurrence proves the field was considered; two prove it reaches the
        screen. The `Line` around it is asserted for the same reason — a bare
        expression in the tree is not a labelled row somebody can read.
        """
        src = read("components", "campaign", "CampaignTerms.jsx")
        assert src.count("terms.commission_terms") >= 2
        assert re.search(
            r"<Line[^>]*>\s*\{terms\.commission_terms\}", src, flags=re.S
        ), "the value is not inside a labelled Line"

    def test_neither_page_charges_the_creator(self):
        """The strongest thing the commission line says is what it does *not*
        do, so a rewording that loses "never" quietly inverts it."""
        low = server.COMMISSION_TERMS.lower()
        assert "on top" in low
        assert "never taken out of it" in low
        for wrong in ("deducted from", "minus", "out of their fee"):
            assert wrong not in low, wrong
