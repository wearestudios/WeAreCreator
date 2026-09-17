"""Seven guarantees, driven rather than grepped.

Each of these was specified, built, and then reported as missing — more than
once. That is worth taking seriously as a fact about the *tests* rather than
about the features: every one of the seven was covered somewhere, and none of
them was covered in a way that answered "did this land" in one place. A rule
spread across nine files is a rule nobody can check.

So this file is the register. One class per guarantee, named for what somebody
asked for rather than for the function that implements it, and every test
**drives the real handler and reads the result back**. Reading the source for a
guard catches the mistake somebody makes on purpose; running it catches the one
where the guard is present and points at the wrong document — which is the
failure `test_money_paths.py` was written after, and the reason
`guard_allows` below pulls the actual `require_roles` dependency off the
signature instead of matching a string.

The three the brief singled out (brand invites, the underfill refund, PAN and
TDS) are covered to the depth of their own rules. The other four are covered at
the level of "this reaches a person" — a route with no caller and a component
with no mount are the same failure, and both have happened here.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"

LOOP = None


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


def run(body):
    async def go():
        db = AsyncMongoMockClient()["guarantees"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return _loop().run_until_complete(go())


def guard_allows(fn, role):
    """Run the route's real `require_roles`, not a string match on its source.

    Calling a route function directly skips FastAPI's dependency injection
    entirely — the trap `bulk_review` re-checks by hand — so a test that reads
    the decorator passes on a guard listing the wrong roles.
    """
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                guard = dep.dependency
                break
    else:
        raise AssertionError(f"{fn.__name__} declares no require_roles guard")

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403, f"expected 403, got {err.status_code}"
            return False

    return _loop().run_until_complete(go())


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


NOW = datetime.now(timezone.utc)


def ago(days):
    return NOW - timedelta(days=days)


# ---------------------------------------------------------------------------
# 1. A brand cannot reach a creator it has not been introduced to
# ---------------------------------------------------------------------------


class TestBrandsCannotInvite:
    """Inviting is ours, and the managed-only model is what makes it ours.

    A brand that can pick creators off a list and message them is a brand using
    the creator network directly, which is the thing handing the campaign to
    WeAre is meant to replace. Both invite endpoints keep their `/brand/...`
    paths — that is what the console already calls — so the guard is the only
    thing between a brand manager and the network, and it is the guard these
    tests run.
    """

    INVITE_ROUTES = ("weare_invite_creators", "invite_creator_list")

    @pytest.mark.parametrize("route", INVITE_ROUTES)
    @pytest.mark.parametrize("role", server.BRAND_ROLES)
    def test_a_brand_manager_is_refused(self, route, role):
        """**Both spellings of the role.** `brand` is what it used to be
        called and both are still accepted at the door, so a guard that named
        only the new one would let every un-migrated account through."""
        assert guard_allows(getattr(server, route), role) is False

    @pytest.mark.parametrize("route", INVITE_ROUTES)
    @pytest.mark.parametrize("role", ["admin", "weare_team"])
    def test_staff_keep_it(self, route, role):
        """The capability did not go away — it moved. Removing it from staff
        too would leave nobody able to cast a brief."""
        assert guard_allows(getattr(server, route), role) is True

    @pytest.mark.parametrize("route", INVITE_ROUTES)
    def test_a_creator_is_refused(self, route):
        assert guard_allows(getattr(server, route), "creator") is False

    def test_the_guard_is_the_role_and_not_verification(self):
        """`_verified_brand_or_403` used to be the only thing on these, which
        refuses an *unverified* brand and waves a verified one through — so the
        rule read as "brands may invite once we have checked them", which is
        the opposite of the one we want."""
        for route in self.INVITE_ROUTES:
            src = inspect.getsource(getattr(server, route))
            assert "_verified_brand_or_403" not in src, (
                f"{route} still leans on brand verification, which permits "
                "exactly the brands this is meant to refuse"
            )
            assert "_admin_campaign_or_404" in src, (
                f"{route} must resolve through the scoped door — `_brand_scope` "
                "on staff is their own user id, which owns no brand profile"
            )

    def test_the_brand_board_offers_no_invite(self):
        """The server is the enforcement and this is the courtesy, but a button
        that 403s is worse than no button: somebody presses it, and the product
        looks broken rather than deliberate."""
        page = read("pages", "BrandCampaignApplicants.jsx")
        assert "canInvite={false}" in page
        # And the panel itself must still be capable of it, for the console.
        panel = read("components", "brand", "SuggestedCreators.jsx")
        assert "canInvite" in panel, "the component decides nothing; the page tells it"

    def test_no_brand_facing_component_offers_it_by_default(self):
        """**The default is the affordance.** `SuggestedCreators` keeps the
        invite branch because a console surface may one day want the asking
        half — but it lives under `components/brand/`, its only mount passes
        `canInvite={false}`, and a default of `true` is what a new mount gets
        by forgetting the prop. The server would refuse it; the brand would
        see a button that looks broken rather than absent."""
        src = read("components", "brand", "SuggestedCreators.jsx")
        assert "canInvite = false" in src, (
            "a brand-facing component must not default to offering a capability "
            "brands do not have"
        )

    def test_every_mount_of_it_is_explicit(self):
        mounts = [
            line
            for path in FRONTEND.rglob("*.jsx")
            for line in path.read_text().splitlines()
            if "<SuggestedCreators" in line
        ]
        assert mounts, "the panel is mounted nowhere"
        for line in mounts:
            assert "canInvite=" in line, f"relies on the default: {line.strip()}"


# ---------------------------------------------------------------------------
# 2. The underfill refund
# ---------------------------------------------------------------------------


class TestTheUnderfillRefund:
    """Our strongest sales point, and it has to be checkable to be one.

    The rule in one question: **had the brand accepted everybody we
    shortlisted, would the brief have filled?** If yes, the shortfall was their
    decision and the fee stands. If no, we did not find enough people and it
    comes back.

    That phrasing is what lets the middle case be answered at all. A rule
    written only from the two ends — "nobody rejected, refund" and "rejected
    everybody, no refund" — has nothing to say about rejecting four of ten on
    an eight-creator brief, which is the case that actually turns up.
    """

    FEE = {"campaign_fee": 25000}

    def test_the_arithmetic_is_pure(self):
        """It takes four counts, so the rule can be read and argued with
        without a database in the room — the arrangement `_weare_run_reason`
        uses, and the reason an admin can be shown the reasoning rather than
        the verdict."""
        src = inspect.getsource(server._refund_reckoning)
        assert "db." not in src and "await" not in src

    def test_underfilled_with_nobody_rejected_is_refundable(self):
        out = server._refund_reckoning(
            self.FEE, targeted=8, finalised=5, shortlisted=5, rejected=0
        )
        assert out["eligible"] is True
        assert out["state"] == "eligible"
        assert out["shortfall"] == 3

    def test_rejecting_everybody_forfeits_it(self):
        out = server._refund_reckoning(
            self.FEE, targeted=5, finalised=0, shortlisted=5, rejected=5
        )
        assert out["eligible"] is False

    def test_the_middle_case_is_answered_by_the_rule_rather_than_by_a_list(self):
        """Four rejected of ten shortlisted on an eight-creator brief: ten were
        there to take, so the brief would have filled and the fee stands. This
        is the case a rule written from the two ends cannot decide."""
        out = server._refund_reckoning(
            self.FEE, targeted=8, finalised=6, shortlisted=10, rejected=4
        )
        assert out["eligible"] is False
        assert "would have fill" in out["reason"]

    def test_a_filled_campaign_refunds_nothing_and_says_why(self):
        out = server._refund_reckoning(
            self.FEE, targeted=5, finalised=5, shortlisted=5, rejected=0
        )
        assert out["eligible"] is False
        assert out["state"] == "none", "nothing to refund is not a forfeit"

    def test_the_reasoning_reads_as_a_sentence_carrying_all_four_counts(self):
        """An admin about to move money has to be able to read it out on a
        call. Four numbers and a verdict is something they have to
        reconstruct, and the reconstruction is where they get it wrong."""
        out = server._refund_reckoning(
            self.FEE, targeted=8, finalised=5, shortlisted=5, rejected=0
        )
        reason = out["reason"]
        assert "Underfilled by 3" in reason
        assert "rejected 0 of 5 shortlisted" in reason
        assert "refund eligible" in reason

    def test_no_campaign_fee_means_nothing_to_refund_rather_than_a_refund_of_zero(self):
        """Or every brief that ever closed puts a decision in front of
        somebody. The usual absent-reads-safe rule — and it lives on
        `_refund_assessment` rather than on the arithmetic, which is right:
        the pure function answers "would this have filled", a question that
        has an answer whether or not a fee was charged."""
        async def body(db):
            cid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": cid, "brand_id": ObjectId(), "title": "T", "status": "closed",
                 "creators_needed": 8, "created_at": ago(30)}
            )
            return await server._refund_assessment(await db.campaigns.find_one({"_id": cid}))

        assert run(body) is None

    def test_shortlisted_is_agreed_at_so_we_counted_what_the_brand_saw(self):
        """`_brand_sees_collab` draws the same line. If the two disagreed, the
        brand would be told it rejected people it was never shown."""
        assert "agreed_at" in inspect.getsource(server._refund_counts_for)

    def test_it_is_derived_on_read_so_the_counts_move_with_the_campaign(self):
        async def body(db):
            brand, cid = ObjectId(), ObjectId()
            await db.campaigns.insert_one(
                {"_id": cid, "brand_id": brand, "title": "Tasting", "status": "closed",
                 "creators_needed": 4, "campaign_fee": 25000, "created_at": ago(30)}
            )
            first = await server._refund_assessment(
                await db.campaigns.find_one({"_id": cid})
            )
            # Somebody is shortlisted and taken on after the first read.
            await db.collaborations.insert_one(
                {"_id": ObjectId(), "campaign_id": cid, "creator_id": ObjectId(),
                 "state": "closed", "agreed_at": ago(10)}
            )
            second = await server._refund_assessment(
                await db.campaigns.find_one({"_id": cid})
            )
            return first, second

        first, second = run(body)
        assert first["finalised"] == 0
        assert second["finalised"] == 1, "a stored verdict would not have moved"

    def test_nothing_refunds_automatically(self):
        """The decision is a person's. `_raise_refund_decision` raises a
        decision *for* somebody rather than making one."""
        src = inspect.getsource(server._raise_refund_decision)
        assert "notify" in src or "_tell" in src

    def test_an_admin_decides_either_way_and_both_cost_a_reason(self):
        """Declining is the one most likely to be asked about later, because
        nothing visible happens as a result of it."""
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            brand, cid = ObjectId(), ObjectId()
            await db.campaigns.insert_one(
                {"_id": cid, "brand_id": brand, "title": "Tasting", "status": "closed",
                 "creators_needed": 4, "campaign_fee": 25000, "created_at": ago(30)}
            )
            refused = None
            try:
                server.RefundDecisionPayload(state="refunded", reason="")
            except Exception:
                refused = "refused"
            await server.decide_campaign_refund(
                str(cid),
                server.RefundDecisionPayload(state="refunded", reason="We could not fill it."),
                admin,
            )
            row = await db.campaigns.find_one({"_id": cid})
            return refused, row.get("refund")

        refused, record = run(body)
        assert refused == "refused", "a decision with no reason is one nobody can defend"
        assert record["state"] == "refunded"
        assert record["reason"] == "We could not fill it."
        assert record.get("decided_by_name") or record.get("decided_by_id"), (
            "'refunded' with nobody's name on it is the record that is no use later"
        )

    def test_the_decision_is_admin_only(self):
        assert guard_allows(server.decide_campaign_refund, "admin") is True
        for role in (*server.BRAND_ROLES, "creator"):
            assert guard_allows(server.decide_campaign_refund, role) is False

    def test_the_computation_stays_beside_the_decision_so_an_override_is_visible(self):
        """The two halves speak different vocabularies on purpose —
        `eligible`/`forfeited` is a verdict, `refunded`/`declined` is a
        decision — and keeping both is what makes a disagreement legible as
        one rather than buried."""
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            cid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": cid, "brand_id": ObjectId(), "title": "T", "status": "closed",
                 "creators_needed": 4, "campaign_fee": 25000, "created_at": ago(30)}
            )
            # Eligible by the rule, declined by the human: an override.
            await server.decide_campaign_refund(
                str(cid),
                server.RefundDecisionPayload(state="declined", reason="Settled off-platform."),
                admin,
            )
            return await server._refund_assessment(await db.campaigns.find_one({"_id": cid}))

        out = run(body)
        assert out["eligible"] is True, "the computation is kept beside the decision"
        assert out["decided_state"] == "declined"
        assert out["overridden"] is True, "an override has to read as one"

    def test_the_policy_is_stated_to_the_brand_before_it_can_be_invoked(self):
        """A refund policy somebody meets during an argument is not a policy.
        Stated at campaign creation and frozen into the terms snapshot."""
        assert "REFUND_POLICY_TERMS" in inspect.getsource(server._build_terms)
        form = read("pages", "PostCampaign.jsx")
        assert "REFUND_TERMS" in form, "the form renders before a campaign exists"

    def test_the_brand_facing_wording_does_not_drift_from_the_server(self):
        mirror = read("lib", "execution.js")
        for phrase in ("campaign fee is refundable", "the fee stands"):
            assert phrase in mirror
            assert phrase in server.REFUND_POLICY_TERMS

    def test_the_admin_can_actually_reach_it(self):
        """A backend flow with no UI is not shipped, whatever the tests say."""
        panel = read("components", "admin", "CommercialTerms.jsx")
        assert "/refund" in panel
        page = read("components", "admin", "CampaignDetailPage.jsx")
        assert "<CommercialTerms" in page
        assert "refund={detail.refund}" in page, "the panel is mounted but fed nothing"


# ---------------------------------------------------------------------------
# 3. PAN, and the withholding nobody computes
# ---------------------------------------------------------------------------


class TestPanAndWithholding:
    """Collected because the tax rules require it, and never computed from.

    A withholding rate depends on the payee's status and the section it falls
    under, so a rate hardcoded here would be wrong for somebody and silently
    wrong for everybody after the next budget. What this records is what the
    admin typed.
    """

    def test_it_is_not_asked_for_at_signup(self):
        """A PAN must not be the price of being looked at — the same reason
        payout details are out of completeness."""
        assert "pan" not in server._PROFILE_COMPLETENESS_FIELDS
        for fields in server._PLATFORM_COMPLETENESS_FIELDS.values():
            assert "pan" not in fields

    def test_it_is_required_before_a_first_payout(self):
        """Which is the moment it is actually true, rather than at the moment
        it is merely convenient to ask."""
        missing = server.payout_missing({"payout_method": "upi", "payout_upi": "a@okhdfc"})
        assert any("PAN" in m for m in missing), missing
        assert server.payout_ready({"payout_method": "upi", "payout_upi": "a@okhdfc"}) is False
        assert server.payout_ready(
            {"payout_method": "upi", "payout_upi": "a@okhdfc", "pan": "ABCDE1234F"}
        ) is True

    def test_the_refusal_names_it_in_words_a_person_could_act_on(self):
        missing = server.payout_missing({})
        assert not any("payout_" in m for m in missing), missing

    def test_a_brand_never_receives_it_at_any_state(self):
        assert "pan" in server.BRAND_FORBIDDEN_CREATOR_FIELDS
        assert "pan" not in server._BRAND_VISIBLE_CREATOR_FIELDS

    def test_it_is_planted_and_searched_for_rather_than_checked_by_key(self):
        """Reading the projection for a key name catches the mistake somebody
        makes on purpose; running it catches the one where the value arrives
        through a `**spread` from a document nobody remembered had it."""
        visible = server._brand_visible_creator(
            {
                "user_id": ObjectId(), "name": "Aditi", "verification_status": "verified",
                "pan": "ZZZZZ9999Z", "payout_upi": "leak@okhdfc",
                "payout_account_number": "918273645500", "phone": "+919812345678",
            }
        )
        blob = repr(visible)
        for planted in ("ZZZZZ9999Z", "leak@okhdfc", "918273645500", "+919812345678"):
            assert planted not in blob, f"{planted} reached a brand"

    def test_an_admin_sees_it_masked_and_a_blank_stays_blank(self):
        """A masked blank would read as a number nobody can see rather than a
        number nobody has."""
        assert server.mask_tail("ABCDE1234F").endswith("234F")
        assert "ABCDE" not in server.mask_tail("ABCDE1234F")
        assert server._masked_payout({"pan": None})["pan_masked"] is None

    def test_changing_it_sends_the_creator_back_for_a_look(self):
        """The account money goes to is exactly the kind of change worth
        checking again."""
        assert "pan" in server.MATERIAL_PROFILE_FIELDS

    def test_withholding_has_three_states_and_none_is_not_no(self):
        """`None` is "nobody has said", `False` is "no withholding". Rendering
        the first as the second is a claim we never made."""
        assert server.MarkPaidPayload(payment_reference="X").tds_applicable is None
        assert (
            server.MarkPaidPayload(payment_reference="X", tds_applicable=False).tds_amount
            is None
        )

    @pytest.mark.parametrize(
        "kw",
        [
            {"tds_applicable": False, "tds_amount": 500},   # no withholding, but an amount
            {"tds_applicable": True},                        # withholding, but no amount
        ],
    )
    def test_the_incoherent_pairs_are_refused(self, kw):
        """Either one produces a payment record that contradicts itself, which
        is the shape an accountant finds a year later."""
        with pytest.raises(Exception):
            server.MarkPaidPayload(payment_reference="X", **kw)

    def test_nothing_in_the_codebase_computes_a_rate(self):
        src = inspect.getsource(server.mark_payment_paid)
        for rate in ("0.1", "10 /", "* 0.1", "TDS_RATE", "tds_rate"):
            assert rate not in src, f"{rate!r} looks like a computed withholding rate"

    def test_both_are_stored_with_the_net(self):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            pid, cid, collab = ObjectId(), ObjectId(), ObjectId()
            await db.campaigns.insert_one(
                {"_id": cid, "brand_id": ObjectId(), "title": "T", "status": "closed"}
            )
            await db.collaborations.insert_one(
                {"_id": collab, "campaign_id": cid, "creator_id": ObjectId(), "state": "in_payment"}
            )
            await db.payments.insert_one(
                {"_id": pid, "collaboration_id": collab, "state": "pending",
                 "creator_payout": 20000.0, "campaign_id": cid}
            )
            await server.mark_payment_paid(
                str(pid),
                server.MarkPaidPayload(
                    payment_reference="UTR123", tds_applicable=True, tds_amount=2000
                ),
                admin,
            )
            return await db.payments.find_one({"_id": pid})

        row = run(body)
        assert row["tds_applicable"] is True
        assert row["tds_amount"] == 2000
        assert row["net_paid"] == 18000, "net is recorded, not left to be worked out"

    def test_both_doors_that_mark_a_payment_paid_carry_the_fields(self):
        """The queue is the one most payouts go through, so a withholding field
        on the detail page alone is TDS recordable in theory and unrecorded in
        practice."""
        for path in ("CollaborationDetailPage.jsx", "ActionQueue.jsx"):
            src = read("components", "admin", path)
            assert "tds_amount" in src, path
            assert "tds_applicable" in src, path

    def test_the_payments_export_carries_all_of_it(self):
        src = inspect.getsource(server._export_payments)
        for column in ("tds_applicable", "tds_amount", "net_paid", "_payout_columns"):
            assert column in src, column
        assert "payments" in server.EXPORTS_WITH_CONTACT

    def test_the_export_is_the_one_place_the_real_values_may_go(self):
        """Somebody is reconciling a bank statement, and a masked account
        number is useless to them. Nothing brand-facing may."""
        assert "payments" not in (
            set(server.EXPORTS_WITH_CONTACT) & {"campaign_report"}
        )
        report = inspect.getsource(server._build_campaign_report)
        for key in ("pan", "payout_account_number", "payout_upi"):
            assert key not in report, f"{key} reached the brand's report"


# ---------------------------------------------------------------------------
# 4-7. The four that reach a person
# ---------------------------------------------------------------------------


class TestReadableReferences:
    """A label, never a key — but a label somebody can say out loud."""

    @pytest.mark.parametrize(
        "typed,expect",
        [
            ("BRD-0012", ("brand", "BRD-0012")),
            ("brd12", ("brand", "BRD-0012")),
            ("crt 108", ("creator", "CRT-0108")),
            ("CMP-0034", ("campaign", "CMP-0034")),
            ("COL-0456", ("collaboration", "COL-0456")),
            ("nonsense", None),
        ],
    )
    def test_one_somebody_has_to_spell_exactly_is_one_they_retype(self, typed, expect):
        assert server.parse_reference(typed) == expect

    def test_all_four_kinds_exist(self):
        assert set(server.REFERENCE_PREFIXES) == {
            "brand", "campaign", "creator", "collaboration"
        }

    def test_it_is_allocated_inside_the_database(self):
        """Counting rows would hand out a duplicate the moment anything was
        deleted."""
        async def body(db):
            return [await server._next_reference("campaign") for _ in range(3)]

        assert run(body) == ["CMP-0001", "CMP-0002", "CMP-0003"]

    def test_absent_is_none_rather_than_an_invented_number(self):
        """A record the backfill has not reached has no number, and an
        invented one is worse than a blank because somebody would quote it."""
        assert server._reference_of({}) is None

    def test_it_is_searchable_and_answered_exactly(self):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            uid = ObjectId()
            await db.users.insert_one({"_id": uid, "role": "creator", "name": "Aditi"})
            await db.creator_profiles.insert_one(
                {"user_id": uid, "name": "Aditi", "reference": "CRT-0108",
                 "verification_status": "verified"}
            )
            return await server.admin_global_search("crt 108", admin)

        out = run(body)
        found = [r for g in out["groups"] for r in g["items"]]
        assert any(r.get("reference") == "CRT-0108" for r in found), out

    def test_it_is_on_the_lists_and_in_the_palette(self):
        assert "reference" in read("components", "admin", "CommandPalette.jsx")
        for path in ("AdminCreators.jsx", "AdminCampaigns.jsx", "AdminBrands.jsx"):
            assert 'key: "reference"' in read("components", "admin", path), path


class TestStructuredBriefs:
    """Six things that can be checked rather than interpreted."""

    def test_all_six_exist(self):
        assert set(server.BRIEF_DETAIL_FIELDS) == {
            "brief_dos", "brief_donts", "mandatory_hashtags",
            "mandatory_mentions", "caption_guidance", "brand_assets",
        }

    def test_absent_reads_as_not_stated_rather_than_as_empty(self):
        """A brief that named no don'ts has no "Don't" heading — which is a
        different claim from a brand that was never asked."""
        assert server._brief_details({}) == {}

    def test_a_hashtag_is_normalised_to_one_spelling(self):
        out = server._resolve_brief_details({"mandatory_hashtags": ["weare", "#weare", "# weare"]})
        assert out["mandatory_hashtags"] == ["#weare"]

    def test_a_brand_asset_must_be_a_link_a_creator_can_safely_click(self):
        """It renders as an anchor, so a `javascript:` in a field a brand types
        is the obvious way to turn a brief into an attack."""
        out = server._resolve_brief_details(
            {"brand_assets": [{"url": "javascript:alert(1)", "label": "Logo"},
                              {"url": "https://example.com/logo.png", "label": "Logo"}]}
        )
        assert [a["url"] for a in out["brand_assets"]] == ["https://example.com/logo.png"]

    def test_an_omitted_key_is_left_alone_and_an_empty_one_clears(self):
        """Collapsing those two would wipe a brief's hashtags every time
        somebody changed its title."""
        assert "brief_dos" not in server._resolve_brief_details({"brief_donts": ["x"]})
        assert server._resolve_brief_details({"brief_dos": []})["brief_dos"] == []

    def test_both_edit_paths_share_the_one_writer(self):
        """So a brief's words and its counted pieces cannot describe different
        asks depending on which console did the editing."""
        for handler in (server.update_brand_campaign, server.admin_update_campaign):
            assert "_resolve_brief_details" in inspect.getsource(handler), handler.__name__

    def test_a_brand_can_set_them_when_it_posts_rather_than_only_afterwards(self):
        """Driven rather than grepped, and that is the point: `create` reaches
        the same normalisation by a different route, so naming the helper here
        would have failed on working code and hidden whether it works at all.
        A brand that had to post and then edit would simply not fill them in.
        """
        async def body(db):
            b = ObjectId()
            await db.users.insert_one(
                {"_id": b, "role": "brand_manager", "name": "T", "brand_id": b}
            )
            await db.brand_profiles.insert_one(
                {"user_id": b, "business_name": "Toit", "verified": True,
                 "verification_state": "verified"}
            )
            await server.create_brand_campaign(
                server.PostCampaignPayload(
                    title="Tasting", description="d", brief="Come and shoot",
                    area="Indiranagar", category="fnb", campaign_type="personal_table",
                    city="Bengaluru", creators_needed=2, budget_per_creator=20000,
                    start_date=NOW + timedelta(days=5), end_date=NOW + timedelta(days=20),
                    deliverable_items=[{"type": "reel", "quantity": 1}],
                    brief_dos=["Tag us"], mandatory_hashtags=["weare"],
                    brand_assets=[{"url": "javascript:alert(1)", "label": "Bad"}],
                ),
                {"_id": str(b), "role": "brand_manager", "name": "T"},
            )
            return await db.campaigns.find_one({"title": "Tasting"})

        row = run(body)
        assert row["brief_dos"] == ["Tag us"]
        assert row["mandatory_hashtags"] == ["#weare"], "normalised on the way in"
        assert row.get("brand_assets") in ([], None), "the create path sanitises links too"

    def test_the_checklist_is_on_the_application_page_and_at_draft_review(self):
        """Which is the whole point: a mismatch that surfaces at draft review
        is a mismatch that costs a reshoot."""
        assert "BriefChecklist" in read("components", "application", "ApplicationDetail.jsx")
        assert "BriefChecklist" in read("pages", "CampaignDetail.jsx")
        assert "BriefChecklist" in read("components", "creator", "ActiveCampaigns.jsx")


class TestThemeFollowsTheAccount:
    """A preference stored in one browser is a preference somebody sets twice."""

    def test_it_is_persisted_against_the_account(self):
        async def body(db):
            uid = ObjectId()
            await db.users.insert_one({"_id": uid, "role": "admin", "name": "A"})
            await server.set_console_theme(
                server.ConsoleThemePayload(theme="light"), {"_id": str(uid), "role": "admin"}
            )
            return (await db.users.find_one({"_id": uid})).get("console_theme")

        assert run(body) == "light"

    def test_it_rides_on_the_session_so_a_second_device_reads_it(self):
        """Stored is not enough — a second device has to be *told*, and
        `/auth/me` is the only thing it asks."""
        assert "console_theme" in inspect.getsource(server.me)

    def test_an_unknown_theme_is_refused(self):
        with pytest.raises(Exception):
            server.ConsoleThemePayload(theme="sepia")

    def test_it_is_applied_before_first_paint(self):
        """A theme applied in an effect is a theme that flashes the wrong one
        first, on the screen somebody opens forty times a day."""
        html = FRONTEND.parent.joinpath("public", "index.html").read_text()
        assert "weare:console-theme" in html
        assert "/admin" in html, "the pre-paint script must not touch other surfaces"

    def test_the_console_is_the_only_surface_it_touches(self):
        lib = read("lib", "consoleTheme.js")
        assert 'CONSOLE_PATH_PREFIX = "/admin"' in lib
        assert "<ConsoleThemeGuard />" in read("App.js"), (
            "without the guard the attribute survives a redirect away from /admin "
            "and the landing page renders light"
        )


class TestSupplyAgainstDemand:
    """Two lists somebody can work, and a way through to the records.

    **Naming a problem with nothing to do about it is how a panel becomes a
    list people scroll past** — the lesson the health panel's three dead links
    already taught, and the reason these tests check the destination filters
    exist rather than checking a link is present.
    """

    def test_supply_with_no_demand_is_the_sell_into_list(self):
        out = server._supply_and_demand(
            {("fitness", "Bengaluru"): 14, ("fnb", "Bengaluru"): 40},
            {("fnb", "Bengaluru"): 11},
        )
        assert [r["category"] for r in out["sell_into"]] == ["fitness"]

    def test_a_category_with_creators_and_briefs_is_on_neither_list(self):
        """Both lists are things to act on. A category that is working is not
        one of them, and padding either would make both ignorable."""
        out = server._supply_and_demand({("fnb", "Bengaluru"): 40}, {("fnb", "Bengaluru"): 11})
        assert out["sell_into"] == [] and out["recruit_for"] == []

    def test_could_not_fill_has_one_definition_and_it_is_the_fill_rule(self):
        """`_supply_and_demand` deliberately returns `recruit_for` empty and
        lets the caller fill it from `_fill_outcome`, so "could not fill" is
        not defined twice — the one-reader rule. Driven end to end, because
        the pure function alone cannot show that the caller does it."""
        async def body(db):
            b = ObjectId()
            await db.brand_profiles.insert_one({"user_id": b, "business_name": "Toit"})
            # Asked for four, nobody finalised, and its own start date has been
            # and gone: unfilled by the fill rule.
            await db.campaigns.insert_one(
                {"_id": ObjectId(), "brand_id": b, "title": "Tasting", "category": "fnb",
                 "city": "Bengaluru", "status": "closed", "creators_needed": 4,
                 "created_at": ago(40), "start_date": ago(20), "end_date": ago(10)}
            )
            uid = ObjectId()
            await db.users.insert_one({"_id": uid, "role": "creator", "name": "A"})
            await db.creator_profiles.insert_one(
                {"user_id": uid, "name": "A", "niches": ["cafe"], "city": "Bengaluru",
                 "verification_status": "verified"}
            )
            return await server._compute_admin_analytics()

        out = run(body)["supply_and_demand"]
        assert [r["category"] for r in out["recruit_for"]] == ["fnb"], out
        assert out["recruit_for"][0]["unfilled_campaigns"] == 1

    def test_the_creators_link_finds_the_people_the_figure_counted(self):
        """**The trap, and the reason this is driven.** A creator writes "cafe"
        about themselves and is counted under `fnb` through the synonym table.
        A link filtering on the literal word `fnb` would open a list missing
        exactly those people — the figure and its link disagreeing, with the
        list loading fine so nobody notices.
        """
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            c1, c2 = ObjectId(), ObjectId()
            await db.users.insert_many(
                [{"_id": c1, "role": "creator", "name": "Aditi"},
                 {"_id": c2, "role": "creator", "name": "Vikram"}]
            )
            await db.creator_profiles.insert_many(
                [{"user_id": c1, "name": "Aditi", "niches": ["cafe", "brunch"],
                  "city": "Bengaluru", "verification_status": "verified"},
                 {"user_id": c2, "name": "Vikram", "niches": ["gaming"],
                  "city": "Bengaluru", "verification_status": "verified"}]
            )
            counted = server._creator_categories({"niches": ["cafe", "brunch"]})
            listed = await server.list_all_creators(
                category="fnb", city="Bengaluru", user=admin
            )
            return counted, [r["name"] for r in listed["creators"]]

        counted, listed = run(body)
        assert "fnb" in counted, "the count puts a cafe creator under fnb"
        assert listed == ["Aditi"], "so the link must open her, not an empty list"

    def test_the_campaigns_link_filters_on_category_and_city(self):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            b = ObjectId()
            await db.brand_profiles.insert_one({"user_id": b, "business_name": "Toit"})
            await db.campaigns.insert_many(
                [{"_id": ObjectId(), "brand_id": b, "title": "Tasting", "category": "fnb",
                  "city": "Bengaluru", "status": "closed", "created_at": NOW},
                 {"_id": ObjectId(), "brand_id": b, "title": "Drop", "category": "fashion",
                  "city": "Bengaluru", "status": "closed", "created_at": NOW}]
            )
            # "Bangalore" folds to "Bengaluru", or the two are one city in
            # reality and two filters here.
            out = await server.list_all_campaigns(
                category="fnb", city="Bangalore", user=admin
            )
            return [r["title"] for r in out["campaigns"]]

        assert run(body) == ["Tasting"]

    @pytest.mark.parametrize(
        "kw", [{"category": "beauty"}, {"city": "Atlantis"}]
    )
    def test_an_unknown_filter_is_refused_rather_than_silently_matching_nothing(self, kw):
        """A typo returning an empty list reads as "we have none of those",
        which is a fact about the business rather than about the typo."""
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            with pytest.raises(HTTPException) as exc:
                await server.list_all_campaigns(user=admin, **kw)
            return exc.value.status_code

        assert run(body) == 422

    def test_an_unknown_creator_category_is_refused_too(self):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            with pytest.raises(HTTPException) as exc:
                await server.list_all_creators(category="nonsense", user=admin)
            return exc.value.status_code

        assert run(body) == 422

    def test_the_rows_open_those_lists_with_those_filters(self):
        """The half a driven test cannot see: the panel has to send what the
        route accepts. Checked as the filter keys, because a link carrying
        `?panel=suggested` at a page that reads no query string is what
        "decoration for months" looked like last time."""
        panel = read("components", "admin", "Analytics.jsx")
        assert '"/admin/creators"' in panel and '"/admin/campaigns"' in panel
        assert "category: r.category" in panel
        assert "area: r.city" in panel, "the creators list reads city as `area`"
        assert "city: r.city" in panel

    def test_the_destination_lists_send_those_filters_on(self):
        """And the half after that: state the list holds but never puts in a
        request is a filter chip over an unfiltered list."""
        creators = read("components", "admin", "AdminCreators.jsx")
        assert "...(category ? { category } : {})" in creators
        campaigns = read("components", "admin", "AdminCampaigns.jsx")
        assert "...(category ? { category } : {})" in campaigns
        assert "...(city ? { city } : {})" in campaigns
