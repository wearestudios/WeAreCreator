"""Getting paid, and getting out.

Two families of gap that turned out to be the same gap: the product could take
somebody through a whole collaboration and then had nowhere to put the facts
that decide what happens at the end of one.

- **Payout identity** was a UPI ID and a PAN, which excluded every creator who
  would rather be paid into an account and made "is this profile payable?" a
  question answered by guessing which fields happened to be filled.
- **Withholding** had nowhere to be recorded at all, so a payout run had no
  document to file a return from.
- **Exits** existed only for the parties who were not the creator: a brand
  could decline, an admin could cancel, work could finish. A creator who had
  changed their mind could only go quiet.
- **A cancellation** recorded who and why and not *when relative to the shoot*,
  which is the fact any settlement conversation turns on.
- **A rejected brand** could resubmit, and nobody counted.
- **Nobody could leave**, which under the DPDP Act 2023 is not a missing
  feature but a missing right.

The rules pinned here are the ones that are easy to get subtly wrong: what
"unknown" means as against zero, what a mask may show, and what erasure keeps.
"""
import asyncio
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server


# ---------------------------------------------------------------------------
# Where the money goes
# ---------------------------------------------------------------------------


class TestPayoutIdentity:
    def test_a_bank_creator_is_payable_without_a_upi_id(self):
        """The whole point of the second method. Before it, a creator who does
        not use UPI could complete a shoot and never reach `in_payment`."""
        assert server.payout_ready(
            {
                "payout_method": "bank",
                "payout_account_name": "Priya Rao",
                "payout_account_number": "50100123456789",
                "payout_ifsc": "HDFC0001234",
                "pan": "AAAPR1001A",
            }
        )

    def test_a_half_filled_bank_account_is_not_payable(self):
        missing = server.payout_missing(
            {"payout_method": "bank", "payout_account_number": "50100123456789",
             "pan": "AAAPR1001A"}
        )
        assert "an account number" not in missing
        assert "an IFSC code" in missing
        assert "the account holder's name" in missing

    def test_pan_is_required_whichever_way_the_money_moves(self):
        for method, extra in (
            ("upi", {"payout_upi": "priya@okhdfcbank"}),
            (
                "bank",
                {
                    "payout_account_name": "Priya",
                    "payout_account_number": "50100123456789",
                    "payout_ifsc": "HDFC0001234",
                },
            ),
        ):
            profile = {"payout_method": method, **extra}
            assert server.payout_missing(profile) == ["your PAN"]

    def test_a_profile_written_before_the_method_existed_stays_payable(self):
        """**The migration this could most easily have broken.** Every profile
        on the platform predates `payout_method` and is a UPI profile, because
        that was the only option. Reading absent as "no method chosen" would
        have made every payable creator unpayable on deploy — noticed on a
        payout run rather than in a test."""
        legacy = {"payout_upi": "priya@okhdfcbank", "pan": "AAAPR1001A"}
        assert server._payout_method(legacy) == "upi"
        assert server.payout_ready(legacy)

    def test_an_empty_profile_is_asked_the_first_question_first(self):
        assert server.payout_missing({}) == ["how you want to be paid"]

    def test_gstin_is_never_required(self):
        """Only a registered creator has one, and demanding it would make being
        registered the price of being paid."""
        assert "your GSTIN" not in " ".join(server.payout_missing({}))
        src = inspect.getsource(server.payout_missing)
        assert "gstin" not in src.lower().split('"""')[2]


class TestMasking:
    def test_only_the_last_four_survive(self):
        assert server.mask_tail("AAAPR1001A") == "••••••001A"
        assert server.mask_tail("50100123456789") == "••••••••••6789"

    def test_absent_is_not_the_same_as_hidden(self):
        """A row of dots where there is no value would tell an admin the
        creator has filled something in."""
        assert server.mask_tail(None) is None
        assert server.mask_tail("  ") is None

    def test_a_short_value_gives_nothing_away(self):
        assert server.mask_tail("1234") == "••••"
        assert server.mask_tail("12") == "••"

    def test_a_upi_id_keeps_the_bank_and_loses_the_number(self):
        """`••••3210@okhdfcbank` is what tells an admin the money is going to
        the right bank; the local part is usually a phone number."""
        out = server._masked_payout({"payout_upi": "9876543210@okhdfcbank"})
        assert out["payout_upi_masked"] == "••••••3210@okhdfcbank"

    def test_an_ifsc_is_shown_whole_because_it_names_a_branch(self):
        out = server._masked_payout({"payout_ifsc": "HDFC0001234"})
        assert out["payout_ifsc"] == "HDFC0001234"

    def test_the_admin_creator_page_serves_no_raw_value(self):
        src = inspect.getsource(server.get_creator_detail)
        assert "_masked_payout(profile)" in src
        for raw in ('"pan": profile.get("pan")', '"payout_upi": profile.get'):
            assert raw not in src, "the full value is being served to a screen"

    @pytest.mark.parametrize(
        "field",
        ["payout_method", "payout_upi", "payout_account_number", "payout_ifsc", "pan", "gstin"],
    )
    def test_every_payout_field_is_forbidden_to_brands(self, field):
        """The allow-list already keeps them out; naming them here is what
        makes the leak test hunt for them."""
        assert field in server.BRAND_FORBIDDEN_CREATOR_FIELDS
        assert field not in server._BRAND_VISIBLE_CREATOR_FIELDS

    @pytest.mark.parametrize(
        "field",
        ["payout_method", "payout_account_number", "payout_ifsc"],
    )
    def test_changing_where_the_money_goes_triggers_a_re_check(self, field):
        """Money moving somewhere new is exactly what re-verification is for —
        it is the shape a takeover of somebody's account takes."""
        assert field in server.MATERIAL_PROFILE_FIELDS


class TestWithholding:
    def test_the_amount_is_recorded_and_never_computed(self):
        """Which section applies, whether the creator is a company, whether
        they are under the threshold this year — all change by finance act and
        by creator. A rate in code would be quietly wrong for somebody."""
        src = inspect.getsource(server.mark_payment_paid)
        for smell in ("0.1", "* 0.0", "TDS_RATE", "tds_rate"):
            assert smell not in src, f"a withholding rate is being calculated: {smell}"

    def test_saying_no_applies_and_entering_an_amount_is_refused(self):
        with pytest.raises(Exception):
            server.MarkPaidPayload(
                payment_reference="x", tds_applicable=False, tds_amount=900
            )

    def test_saying_it_applies_without_the_amount_is_refused(self):
        with pytest.raises(Exception):
            server.MarkPaidPayload(payment_reference="x", tds_applicable=True)

    def test_silence_is_a_third_state_and_stays_one(self):
        """"Nobody has looked yet" and "we decided none applies" are different
        facts, and a bare zero cannot tell them apart."""
        payload = server.MarkPaidPayload(payment_reference="x")
        assert payload.tds_applicable is None and payload.tds_amount is None

    def test_the_export_prints_the_three_states_differently(self):
        src = inspect.getsource(server._export_payments)
        assert '"" if d.get("tds_applicable") is None' in src
        assert '"TDS applicable"' in src and '"TDS amount"' in src and '"Net paid"' in src

    def test_the_export_masks_what_it_carries(self):
        """It is the one export an accountant reconciles a statement against,
        so it carries the payout identity — masked, because it answers "is this
        the right row" without putting an account number in a spreadsheet."""
        cols = server._payout_columns(
            {
                "method": "bank",
                "account_number": "50100123456789",
                "ifsc": "HDFC0001234",
                "pan": "AAAPR1001A",
            },
            {},
        )
        assert "50100123456789" not in cols
        assert "••••••••••6789" in cols
        assert "HDFC0001234" in cols  # a branch, not a person

    def test_the_snapshot_wins_over_the_current_profile(self):
        """A creator editing their bank details next week must not restate
        where last month's payout went."""
        cols = server._payout_columns(
            {"method": "upi", "upi": "old@okhdfcbank"},
            {"payout_upi": "new@okicici", "payout_method": "upi"},
        )
        assert "okhdfcbank" in cols[1]


# ---------------------------------------------------------------------------
# The ways out
# ---------------------------------------------------------------------------


class World:
    """One brand-run campaign with a creator applied to it."""

    async def build(self, state="applied", event_in_days=10):
        self.db = AsyncMongoMockClient()["exits"]
        server.db = self.db
        db = self.db
        now = datetime.now(timezone.utc)

        self.brand, self.creator, self.admin_id = ObjectId(), ObjectId(), ObjectId()
        self.campaign, self.collab = ObjectId(), ObjectId()
        await db.users.insert_many([
            {"_id": self.brand, "role": "brand_manager", "name": "Toit",
             "brand_id": self.brand},
            {"_id": self.creator, "role": "creator", "name": "Aditi Rao",
             "phone": "+919900000001", "email": "aditi@example.com"},
            {"_id": self.admin_id, "role": "admin", "name": "Admin"},
        ])
        await db.brand_profiles.insert_one(
            {"user_id": self.brand, "business_name": "Toit", "verified": True,
             "contact_person_name": "Ravi", "contact_email": "ravi@example.com",
             "registered_address": "100 Feet Road", "gst_number": "29ABCDE1234F1Z5"}
        )
        await db.creator_profiles.insert_one(
            {"user_id": self.creator, "name": "Aditi Rao",
             "payout_method": "bank", "payout_account_number": "50100123456789",
             "payout_ifsc": "HDFC0001234", "payout_account_name": "Aditi Rao",
             "pan": "AAAPR1001A", "full_address": "12 Church Street"}
        )
        await db.campaigns.insert_one({
            "_id": self.campaign, "brand_id": self.brand, "title": "Toit tasting",
            "status": "open", "campaign_type": "launch", "creators_needed": 3,
            "budget_per_creator": 8000, "compensation_type": "fixed",
            "execution_owner": "brand", "created_at": now,
            "event_date": now + timedelta(days=event_in_days),
        })
        await db.collaborations.insert_one({
            "_id": self.collab, "campaign_id": self.campaign,
            "creator_id": self.creator, "state": state,
            "agreed_amount": 8000 if state != "applied" else None,
            "created_at": now,
        })

        self.creator_user = await db.users.find_one({"_id": self.creator})
        self.admin = await db.users.find_one({"_id": self.admin_id})
        self.brand_user = await db.users.find_one({"_id": self.brand})
        return self


_LOOP = None


@pytest.fixture
def world(request):
    global _LOOP
    keep = server.db
    _LOOP = asyncio.new_event_loop()
    kwargs = getattr(request, "param", {}) or {}
    try:
        yield _LOOP.run_until_complete(World().build(**kwargs))
    finally:
        _LOOP.close()
        _LOOP = None
        server.db = keep


def run(coro):
    return _LOOP.run_until_complete(coro)


def refuses(coro):
    with pytest.raises(HTTPException) as e:
        run(coro)
    return e.value


class TestWithdrawal:
    def test_a_creator_can_take_an_application_back(self, world):
        out = run(server.withdraw_application(
            str(world.collab),
            server.ReasonPayload(reason="Clashing shoot that week"),
            world.creator_user,
        ))
        assert out["state"] == "withdrawn"
        doc = run(world.db.collaborations.find_one({"_id": world.collab}))
        assert doc["exit_reason"] == "Clashing shoot that week"
        assert doc["withdrawn_from_state"] == "applied"

    @pytest.mark.parametrize("world", [{"state": "accepted"}], indirect=True)
    def test_after_acceptance_it_is_a_cancellation_and_says_so(self, world):
        """By then there is a venue booked and a commitment on both sides. The
        refusal points at the flow that carries a notice period and a fee
        rather than just saying no."""
        err = refuses(server.withdraw_application(
            str(world.collab),
            server.ReasonPayload(reason="Changed my mind"),
            world.creator_user,
        ))
        assert err.status_code == 409
        assert "taken on" in err.detail

    def test_withdrawing_twice_is_refused(self, world):
        run(server.withdraw_application(
            str(world.collab), server.ReasonPayload(reason="Clash"), world.creator_user
        ))
        assert refuses(server.withdraw_application(
            str(world.collab), server.ReasonPayload(reason="Clash"), world.creator_user
        )).status_code == 409

    def test_it_is_terminal_and_on_every_board(self, world):
        """A board that did not account for it would show an applicant who has
        gone as still waiting on somebody."""
        assert "withdrawn" in server.TERMINAL_COLLAB_STATES
        assert "withdrawn" in server.COLLAB_GROUP_ENDED
        assert "withdrawn" in dict(server._APPLICANT_BUCKETS)["rejected"]

    def test_the_flow_draws_it_as_a_banner_rather_than_a_step(self, world):
        flow = server._process_flow({"state": "withdrawn"}, {})
        assert flow["stage"] is None
        assert flow["banner"]["tone"] == "ended"
        assert "withdrew" in flow["banner"]["detail"]

    def test_the_reason_is_required(self, world):
        with pytest.raises(Exception):
            server.ReasonPayload(reason="")


class TestCancellation:
    @pytest.mark.parametrize("world", [{"state": "slot_booked"}], indirect=True)
    def test_the_notice_period_is_recorded_as_a_fact(self, world):
        """Whether four days is enough is a commercial judgement that differs
        by brand and by venue. What the record has to survive is *when*."""
        run(server.cancel_collaboration(
            str(world.collab),
            server.CancelCollabPayload(reason="Venue flooded", cancellation_type="brand_cancelled"),
            world.admin,
        ))
        doc = run(world.db.collaborations.find_one({"_id": world.collab}))
        assert doc["cancellation_notice_days"] == 10
        assert doc["cancelled_by_name"] == "Admin"
        assert doc["cancelled_by_role"] == "admin"

    @pytest.mark.parametrize(
        "world", [{"state": "slot_booked", "event_in_days": -2}], indirect=True
    )
    def test_a_shoot_already_past_counts_negative_rather_than_zero(self, world):
        run(server.cancel_collaboration(
            str(world.collab),
            server.CancelCollabPayload(reason="Never happened"),
            world.admin,
        ))
        doc = run(world.db.collaborations.find_one({"_id": world.collab}))
        assert doc["cancellation_notice_days"] == -2

    @pytest.mark.parametrize("world", [{"state": "slot_booked"}], indirect=True)
    def test_a_kill_fee_raises_a_payable_row_where_none_existed(self, world):
        """A payment is only raised at `in_payment`, so a kill fee agreed on
        the way out has nowhere to live. Without a row the money owed exists
        only in a cancellation reason nobody reconciles against."""
        run(server.cancel_collaboration(
            str(world.collab),
            server.CancelCollabPayload(reason="Called it off", kill_fee=2000),
            world.admin,
        ))
        payment = run(world.db.payments.find_one({"collaboration_id": world.collab}))
        assert payment["kill_fee"] == 2000
        assert payment["is_kill_fee"] is True
        assert payment["state"] == "pending"
        assert payment["creator_payout"] == 2000
        # And the payout identity travels with it, so somebody can actually pay.
        assert payment["payout_snapshot"]["ifsc"] == "HDFC0001234"

    @pytest.mark.parametrize("world", [{"state": "slot_booked"}], indirect=True)
    def test_no_kill_fee_leaves_nothing_payable_behind(self, world):
        run(server.cancel_collaboration(
            str(world.collab), server.CancelCollabPayload(reason="Called it off"), world.admin
        ))
        assert run(world.db.payments.find_one({"collaboration_id": world.collab})) is None

    @pytest.mark.parametrize("world", [{"state": "slot_booked"}], indirect=True)
    def test_the_creator_is_told_what_they_are_owed(self, world):
        """A cancellation they find out about without being told about the fee
        is a conversation they then have to start themselves."""
        run(server.cancel_collaboration(
            str(world.collab),
            server.CancelCollabPayload(reason="Called it off.", kill_fee=2000),
            world.admin,
        ))
        note = run(world.db.notifications.find_one({"user_id": world.creator}))
        assert "2,000" in note["body"]

    @pytest.mark.parametrize("world", [{"state": "slot_booked"}], indirect=True)
    def test_it_shows_on_both_entity_pages(self, world):
        run(server.cancel_collaboration(
            str(world.collab),
            server.CancelCollabPayload(reason="Venue flooded", kill_fee=1500),
            world.admin,
        ))
        for kwargs in ({"creator_id": world.creator}, {"brand_ids": [world.brand]}):
            rows = run(server._cancellation_history(**kwargs))
            assert len(rows) == 1
            assert rows[0]["reason"] == "Venue flooded"
            assert rows[0]["kill_fee"] == 1500
            assert rows[0]["notice_days"] == 10

    def test_a_withdrawal_is_in_the_history_without_being_a_black_mark(self, world):
        """It happens before anybody is committed and is the creator's to make
        — but a page claiming to show how a relationship has gone that omitted
        it would be telling half a story."""
        run(server.withdraw_application(
            str(world.collab), server.ReasonPayload(reason="Clash"), world.creator_user
        ))
        rows = run(server._cancellation_history(creator_id=world.creator))
        assert rows[0]["state"] == "withdrawn"
        assert rows[0]["cancelled_by"] == "The creator"
        assert rows[0]["kill_fee"] is None


class TestBrandResubmission:
    def test_coming_back_after_a_refusal_is_counted(self, world):
        run(world.db.brand_profiles.update_one(
            {"user_id": world.brand},
            {"$set": {
                "verified": False,
                "verification_reason": "The GST certificate was unreadable.",
                "legal_entity_name": "Toit Pvt Ltd", "business_type": "private_limited",
                "category": "fnb", "contact_person_designation": "Owner",
            }},
        ))
        run(world.db.brand_documents.insert_one(
            {"brand_id": world.brand, "stored_name": "x.pdf"}
        ))

        run(server.submit_brand_for_verification(world.brand_user))
        profile = run(world.db.brand_profiles.find_one({"user_id": world.brand}))
        assert profile["verification_resubmissions"] == 1
        # The refusal is cleared — it is not a verdict on what they just sent —
        # but kept, because the reviewer wants to know what we asked for.
        assert profile["verification_reason"] is None
        assert profile["previous_verification_reason"] == "The GST certificate was unreadable."

    def test_a_first_submission_counts_as_none(self, world):
        run(world.db.brand_profiles.update_one(
            {"user_id": world.brand},
            {"$set": {
                "verified": False, "legal_entity_name": "Toit Pvt Ltd",
                "business_type": "private_limited", "category": "fnb",
                "contact_person_designation": "Owner",
            }},
        ))
        run(world.db.brand_documents.insert_one(
            {"brand_id": world.brand, "stored_name": "x.pdf"}
        ))
        run(server.submit_brand_for_verification(world.brand_user))
        profile = run(world.db.brand_profiles.find_one({"user_id": world.brand}))
        assert int(profile.get("verification_resubmissions") or 0) == 0

    def test_there_is_no_cap(self):
        """A cap would refuse a brand that is genuinely trying on the attempt
        where they finally got it right."""
        src = inspect.getsource(server.submit_brand_for_verification)
        assert "MAX_RESUBMISSIONS" not in src
        assert "resubmissions >" not in src

    def test_the_count_reaches_the_reviewer(self):
        src = inspect.getsource(server._admin_brand_fields)
        assert '"verification_resubmissions"' in src
        assert '"previous_verification_reason"' in src


# ---------------------------------------------------------------------------
# Being forgotten
# ---------------------------------------------------------------------------


class TestAccountDeletion:
    def test_a_creator_can_ask(self, world):
        out = run(server.request_account_deletion(
            server.DeletionRequestPayload(reason="Not creating any more"),
            world.creator_user,
        ))
        assert out["state"] == "requested"

    @pytest.mark.parametrize("world", [{"state": "slot_booked"}], indirect=True)
    def test_work_in_flight_blocks_it_and_names_what(self, world):
        """Not a refusal, a wait — and "three collaborations" is not something
        anybody can act on, while "the Toit tasting" is."""
        err = refuses(server.request_account_deletion(
            server.DeletionRequestPayload(), world.creator_user
        ))
        assert err.status_code == 409
        assert err.detail["code"] == "work_in_flight"
        assert err.detail["blocking"][0]["campaign_title"] == "Toit tasting"

    def test_asking_twice_is_refused(self, world):
        run(server.request_account_deletion(
            server.DeletionRequestPayload(), world.creator_user
        ))
        assert refuses(server.request_account_deletion(
            server.DeletionRequestPayload(), world.creator_user
        )).status_code == 409

    def test_staff_are_pointed_at_a_person_instead(self, world):
        """There is no personal-data case for a login that exists to do a job,
        and a self-service door on one is a way to lock the company out of its
        own console."""
        err = refuses(server.request_account_deletion(
            server.DeletionRequestPayload(), world.admin
        ))
        assert err.status_code == 403
        assert "admin" in err.detail

    def test_a_request_can_be_taken_back(self, world):
        run(server.request_account_deletion(
            server.DeletionRequestPayload(), world.creator_user
        ))
        out = run(server.withdraw_deletion_request(world.creator_user))
        assert out["state"] == "withdrawn"

    def test_erasure_removes_the_person_and_keeps_the_arithmetic(self, world):
        """The rule the whole flow turns on. A collaboration keeps its dates,
        its states and its amounts — a brand's proof of what it paid for — and
        loses every field that says who it was."""
        run(world.db.collaborations.update_one(
            {"_id": world.collab}, {"$set": {"state": "closed", "agreed_amount": 8000}}
        ))
        run(world.db.payments.insert_one({
            "collaboration_id": world.collab, "creator_payout": 8000, "state": "paid",
            "payout_snapshot": {"account_number": "50100123456789", "pan": "AAAPR1001A"},
        }))
        request = run(server.request_account_deletion(
            server.DeletionRequestPayload(), world.creator_user
        ))
        run(server.approve_account_deletion(
            request["id"], server.DeletionDecisionPayload(), world.admin
        ))

        account = run(world.db.users.find_one({"_id": world.creator}))
        profile = run(world.db.creator_profiles.find_one({"user_id": world.creator}))
        collab = run(world.db.collaborations.find_one({"_id": world.collab}))
        payment = run(world.db.payments.find_one({"collaboration_id": world.collab}))

        # Gone.
        assert account.get("phone") is None and account.get("email") is None
        assert profile.get("pan") is None
        assert profile.get("payout_account_number") is None
        assert profile.get("full_address") is None
        assert payment.get("payout_snapshot") is None
        # Kept.
        assert collab["state"] == "closed"
        assert collab["agreed_amount"] == 8000
        assert payment["creator_payout"] == 8000
        assert account["status"] == "deleted"

    def test_the_payment_snapshot_is_reached_through_the_collaboration(self):
        """**The bug this test exists for.** A payment has no `creator_id` — it
        keys on `collaboration_id` and nothing else — so querying the field
        that felt like it should be there matched no documents and left every
        bank account and PAN in place, silently, on the one operation whose
        whole purpose is removing them."""
        src = inspect.getsource(server._erase_personal_data)
        assert 'db.payments.update_many(\n                {"collaboration_id"' in src
        assert 'db.payments.update_many(\n        {"creator_id"' not in src

    def test_erasure_is_checked_again_at_the_moment_it_happens(self, world):
        """Work can start after somebody asks, and erasing then would leave a
        brand with a booking against nobody."""
        request = run(server.request_account_deletion(
            server.DeletionRequestPayload(), world.creator_user
        ))
        run(world.db.collaborations.update_one(
            {"_id": world.collab}, {"$set": {"state": "slot_booked"}}
        ))
        err = refuses(server.approve_account_deletion(
            request["id"], server.DeletionDecisionPayload(), world.admin
        ))
        assert err.status_code == 409

    def test_the_confirmation_goes_out_before_the_number_is_erased(self):
        """A confirmation sent to a number we have just deleted is a
        confirmation nobody receives."""
        src = inspect.getsource(server.approve_account_deletion)
        assert src.index('"account_deleted"') < src.index("_erase_personal_data(")

    def test_the_audit_line_does_not_re_record_the_person(self):
        """Erasing somebody and then writing their name into the log of having
        erased them is the whole exercise undone in its last line."""
        src = inspect.getsource(server.approve_account_deletion)
        after = src.split('"account.erased"', 1)[1].split("return", 1)[0]
        for leak in ("account.get(\"name\")", "account.get(\"phone\")", "account.get(\"email\")"):
            assert leak not in after

    def test_a_refusal_demands_a_reason_and_an_erasure_does_not(self, world):
        """Somebody told they cannot leave is owed a reason; somebody who has
        left cannot read one."""
        request = run(server.request_account_deletion(
            server.DeletionRequestPayload(), world.creator_user
        ))
        assert refuses(server.decline_account_deletion(
            request["id"], server.DeletionDecisionPayload(), world.admin
        )).status_code == 422

        out = run(server.decline_account_deletion(
            request["id"],
            server.DeletionDecisionPayload(note="We still owe you for two shoots."),
            world.admin,
        ))
        assert out["state"] == "declined"

    def test_a_brands_documents_go_with_it(self):
        """They are scans of a GST certificate and a director's address —
        keeping them after erasure would be keeping the most identifying thing
        in the product."""
        src = inspect.getsource(server._erase_personal_data)
        assert "db.brand_documents.delete_many" in src
        assert "_remove_private_upload" in src

    def test_nothing_is_deleted_that_a_join_still_reads(self):
        """A collaboration whose creator row had simply vanished would break
        every join that reads it, and a payment with no counterparty is not a
        record of anything."""
        src = inspect.getsource(server._erase_personal_data)
        for collection in ("users", "creator_profiles", "brand_profiles", "collaborations"):
            assert f"db.{collection}.delete_many" not in src
            assert f"db.{collection}.delete_one" not in src

    def test_the_queue_and_the_decisions_are_admin_only(self):
        """This is not scoped work — it is a person exercising a right against
        the whole company."""
        for fn in (
            server.list_deletion_requests,
            server.approve_account_deletion,
            server.decline_account_deletion,
        ):
            head = inspect.getsource(fn).split("):", 1)[0]
            assert 'require_roles("admin")' in head


# ---------------------------------------------------------------------------
# Every new route has a caller
# ---------------------------------------------------------------------------


import re
from pathlib import Path

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def no_comments(path: Path) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def frontend_source() -> str:
    return "\n".join(
        no_comments(p)
        for p in FRONTEND.rglob("*.js*")
        if p.is_file() and "node_modules" not in p.parts
    )


class TestNothingShippedWithoutAWayIn:
    """The rule this codebase learned the hard way, applied to six new flows.

    Four brand-verification endpoints once spent months with no caller: a brand
    could sign up, draft, and then hit the wall forever with no route to the
    thing that would clear it. A backend flow with no UI is not shipped,
    whatever the tests say.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "/creator/collaborations/${row.id}/withdraw",
            "/account/deletion-request",
            "/admin/deletion-requests",
        ],
    )
    def test_the_new_routes_are_called(self, path):
        src = frontend_source()
        assert path in src, f"{path} has no caller in the frontend"

    def test_the_erase_and_decline_decisions_are_reachable(self):
        src = no_comments(FRONTEND / "components" / "admin" / "AdminDeletions.jsx")
        assert "/admin/deletion-requests/${row.id}/${kind}" in src
        assert '"erase"' in src and '"decline"' in src

    @pytest.mark.parametrize(
        "component,mounted_in",
        [
            ("DeleteAccount", "pages/CreatorProfile.jsx"),
            ("DeleteAccount", "pages/BrandOnboarding.jsx"),
            ("CancellationHistory", "components/admin/CreatorDetailPage.jsx"),
            ("CancellationHistory", "components/admin/BrandDetailPage.jsx"),
            ("WithdrawDialog", "components/creator/Applications.jsx"),
        ],
    )
    def test_every_new_panel_is_on_a_screen(self, component, mounted_in):
        """A component that exists is not a component anybody sees."""
        assert f"<{component}" in no_comments(FRONTEND / mounted_in)

    def test_the_deletion_queue_has_a_route_and_a_sidebar_entry(self):
        app = no_comments(FRONTEND / "App.js")
        sidebar = no_comments(FRONTEND / "components" / "admin" / "console" / "Sidebar.jsx")
        assert 'path="deletions"' in app
        assert 'key: "deletions"' in sidebar
        # Not scoped work: a right exercised against the whole company.
        chunk = sidebar.split('key: "deletions"', 1)[1].split("},", 1)[0]
        assert "adminOnly: true" in chunk


class TestTheFormsMatchTheServer:
    ONBOARDING = FRONTEND / "pages" / "CreatorOnboarding.jsx"

    def test_the_payout_method_list_does_not_drift(self):
        src = no_comments(FRONTEND / "lib" / "payout.js")
        for method in server.PAYOUT_METHOD_FIELDS:
            assert f'value: "{method}"' in src

    def test_the_form_asks_the_method_before_the_fields(self):
        """Showing both sets at once asks everybody to ignore half a form, and
        leaves a half-typed bank account beside a UPI ID with nothing saying
        which one we should pay."""
        src = no_comments(self.ONBOARDING)
        assert 'form.payout_method === "upi"' in src
        assert 'form.payout_method === "bank"' in src
        assert src.index("PAYOUT_METHODS.map") < src.index('form.payout_method === "upi"')

    def test_the_bank_fields_are_sent(self):
        src = no_comments(self.ONBOARDING)
        for field in ("payout_method", "payout_account_number", "payout_ifsc"):
            assert f"{field}:" in src

    def test_the_admin_page_renders_only_masked_values(self):
        src = no_comments(FRONTEND / "components" / "admin" / "CreatorDetailPage.jsx")
        assert "creator.pan_masked" in src
        assert "creator.payout_account_number_masked" in src
        assert "{creator.pan}" not in src
        assert "{creator.payout_upi}" not in src

    def test_the_creators_own_page_shows_the_real_values(self):
        """They are theirs, and checking a digit against a passbook is what
        that screen is for."""
        src = no_comments(FRONTEND / "pages" / "CreatorProfile.jsx")
        assert "profile.payout_account_number" in src
        assert "profile.pan" in src

    def test_mark_paid_sends_the_field_the_server_reads(self):
        """**The bug this caught.** The dialog's extra field was named
        `reference`, so every mark-paid from the collaboration page answered
        422 on a required field the form was filling in under another name."""
        src = no_comments(FRONTEND / "components" / "admin" / "CollaborationDetailPage.jsx")
        assert "payment_reference: body.payment_reference" in src
        assert 'name: "reference"' not in src

    def test_every_mark_paid_door_can_record_withholding(self):
        """**The bug this caught.** The withholding fields went onto the
        collaboration page and not onto the action queue — which is the door
        most payouts actually go through, because working the queue is the fast
        path. TDS was recordable in theory and unrecorded in practice.

        Found by walking the callers rather than by reading the one screen this
        was built on: a second door is exactly the thing nobody remembers.
        """
        doors = [
            p
            for p in (FRONTEND / "components" / "admin").rglob("*.jsx")
            if "/mark_paid" in no_comments(p)
        ]
        assert len(doors) >= 2, "expected the queue and the collaboration page"
        for door in doors:
            src = no_comments(door)
            call = src.split("/mark_paid", 1)[1].split("),", 1)[0]
            assert "payment_reference:" in call, door.name
            assert "tds_applicable:" in call, door.name
            assert "tds_amount:" in call, door.name

    def test_a_dialog_driven_by_a_config_forwards_both_field_shapes(self):
        """**The bug this caught, and the one the test above could not see.**

        The action queue builds its dialog configs into state and renders one
        `ConfirmDialog` from them. It forwarded `extra` and not `extras`, so
        moving the payout config to the multi-field shape dropped *every* field
        — the payment reference included, which the server requires. The POST
        body was right and the form had nothing in it to fill.

        Checking the call body is not enough for this class: the fields and the
        submit handler are wired in different places.
        """
        for path in (FRONTEND / "components" / "admin").rglob("*.jsx"):
            src = no_comments(path)
            if "<ConfirmDialog" not in src or "extras:" not in src:
                continue
            assert "extras={" in src, (
                f"{path.name} builds `extras:` configs but never forwards them"
            )

    def test_the_cancel_dialog_offers_a_kill_fee(self):
        src = no_comments(FRONTEND / "components" / "admin" / "CollaborationDetailPage.jsx")
        assert 'name: "kill_fee"' in src

    def test_the_withholding_field_does_not_calculate_anything(self):
        """Arithmetic, not the word — the hint copy says "it doesn't work the
        rate out", which is the sentence this rule wants on screen."""
        src = no_comments(FRONTEND / "components" / "admin" / "CollaborationDetailPage.jsx")
        block = src.split('name: "tds_amount"', 1)[1].split("]}", 1)[0]
        for smell in ("0.1", "* 0.0", "creator_payout *", "TDS_RATE"):
            assert smell not in block
        # And the copy that makes the rule visible to whoever is filling it in.
        assert "doesn't work the rate out" in block
