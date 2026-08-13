"""Unit tests for the process rules that were wrong or missing.

Every test here maps to a specific defect found in the process review, so a
regression re-breaks a named flow rather than an anonymous assertion.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import server


# ---------------------------------------------------------------------------
# Verification status — this concept has been called three things ("approved",
# "vetted", now "verified"). A mismatch between what approvals write and what
# the directory queries once hid every approved creator from brands, so the
# rules below guard the vocabulary rather than trusting it.
# ---------------------------------------------------------------------------


class TestVerificationStatusIsOneWord:
    SOURCE = None

    @classmethod
    def setup_class(cls):
        cls.SOURCE = (server.ROOT_DIR / "server.py").read_text()

    def test_declared_statuses_are_the_ones_we_write(self):
        assert set(server.VerificationStatus.__args__) == {"pending", "verified", "rejected"}

    def test_the_only_field_name_is_verification_status(self):
        # `vetting_status` may appear solely inside the startup migration that
        # renames it. Anywhere else means two field names are live at once.
        for line in self.SOURCE.splitlines():
            if "vetting_status" not in line:
                continue
            assert any(
                marker in line
                for marker in (
                    "$rename",
                    "$unset",
                    "$exists",
                    "Field rename",
                    "startswith(",
                    '"verification_status")',  # the (old, new) rename pair
                )
            ), f"stray reference to the old field name outside the migration: {line.strip()}"

    def test_legacy_values_are_only_mentioned_where_they_are_migrated_away(self):
        for legacy in ('"approved"', '"vetted"'):
            for line in self.SOURCE.splitlines():
                if legacy not in line:
                    continue
                assert any(
                    marker in line
                    for marker in ("for legacy in", '"state": "vetted"', "#", "Migrated")
                ), f"stray legacy status {legacy} outside the migration: {line.strip()}"

    def test_the_migration_covers_every_legacy_value(self):
        # Databases from either previous version have to land on "verified".
        assert 'for legacy in ("approved", "vetted"):' in self.SOURCE
        assert '{"state": "vetted"}, {"$set": {"state": "verified"}}' in self.SOURCE
        assert '("vetting_status", "verification_status")' in self.SOURCE


# ---------------------------------------------------------------------------
# Collaboration state machine
# ---------------------------------------------------------------------------


class TestCollaborationStateMachine:
    def test_content_approval_sits_between_submission_and_payment(self):
        order = server.COLLAB_STATE_ORDER
        assert order.index("content_submitted") < order.index("content_approved")
        assert order.index("content_approved") < order.index("in_payment")

    def test_exits_are_not_steps_on_the_happy_path(self):
        for exit_state in ("declined", "cancelled"):
            assert exit_state not in server.COLLAB_STATE_ORDER
            assert exit_state in server.TERMINAL_COLLAB_STATES

    def test_exit_states_have_no_next_step(self):
        assert server._next_collab_state("declined") is None
        assert server._next_collab_state("cancelled") is None

    def test_closed_is_the_end(self):
        assert server._next_collab_state("closed") is None

    def test_happy_path_walks_forward_one_step_at_a_time(self):
        walked = ["applied"]
        while (nxt := server._next_collab_state(walked[-1])) is not None:
            walked.append(nxt)
        assert walked == server.COLLAB_STATE_ORDER

    def test_brand_owns_accepting_and_approving(self):
        # An admin advancing through these would cut the buyer out of the
        # only two decisions that are actually theirs.
        assert server._BRAND_OWNED_TRANSITIONS == {"accepted", "content_approved"}

    def test_unknown_state_does_not_crash_the_board(self):
        assert server._next_collab_state("something_we_removed") is None


# ---------------------------------------------------------------------------
# Campaign slots
# ---------------------------------------------------------------------------


class TestCreatorHistoryGroups:
    """Admin oversight groups a creator's collaborations. Every state has to land
    in exactly one bucket, or a collaboration silently disappears from someone's
    record."""

    ALL_GROUPS = (
        "COLLAB_GROUP_APPLIED",
        "COLLAB_GROUP_ONGOING",
        "COLLAB_GROUP_COMPLETED",
        "COLLAB_GROUP_ENDED",
    )

    def _grouped(self):
        out = []
        for name in self.ALL_GROUPS:
            out.extend(getattr(server, name))
        return out

    def test_every_state_belongs_to_a_group(self):
        every_state = set(server.COLLAB_STATE_ORDER) | set(server.TERMINAL_COLLAB_STATES)
        assert set(self._grouped()) == every_state

    def test_no_state_is_in_two_groups(self):
        grouped = self._grouped()
        assert len(grouped) == len(set(grouped))

    def test_applications_awaiting_a_decision_are_not_counted_as_work(self):
        # A pitch nobody has accepted is not an ongoing collaboration.
        assert "applied" in server.COLLAB_GROUP_APPLIED
        assert "verified" in server.COLLAB_GROUP_APPLIED
        for state in server.COLLAB_GROUP_APPLIED:
            assert state not in server.COLLAB_GROUP_ONGOING

    def test_only_closed_counts_as_completed(self):
        assert server.COLLAB_GROUP_COMPLETED == ("closed",)
        assert "declined" not in server.COLLAB_GROUP_COMPLETED
        assert "cancelled" not in server.COLLAB_GROUP_COMPLETED


class TestAdminActionQueue:
    def test_only_states_the_admin_can_actually_move(self):
        # `attended` waits on the creator and `content_submitted` on the brand,
        # so neither belongs on the admin's desk even though the advance
        # endpoint would technically accept them.
        assert "attended" not in server.ADMIN_ACTION_STATES
        assert "content_submitted" not in server.ADMIN_ACTION_STATES
        # These two are the brand's calls.
        for state in ("verified",):
            assert state not in server.ADMIN_ACTION_STATES

    def test_the_admin_owned_steps_are_present(self):
        for state in ("applied", "accepted", "commercial_agreed", "slot_booked"):
            assert state in server.ADMIN_ACTION_STATES

    def test_terminal_states_need_no_action(self):
        for state in server.TERMINAL_COLLAB_STATES:
            assert state not in server.ADMIN_ACTION_STATES


class TestCampaignFill:
    def test_applicants_awaiting_a_decision_do_not_occupy_a_slot(self):
        # Otherwise one campaign with ten hopefuls looks full.
        assert "applied" not in server._FILLED_COLLAB_STATES
        assert "verified" not in server._FILLED_COLLAB_STATES

    def test_accepted_onwards_occupies_a_slot(self):
        for state in ("accepted", "commercial_agreed", "slot_booked", "attended", "closed"):
            assert state in server._FILLED_COLLAB_STATES


# ---------------------------------------------------------------------------
# Pricing — the fee used to be a hardcoded 15% in a frontend dialog.
# ---------------------------------------------------------------------------


class TestPlatformFee:
    def test_default_percent(self, monkeypatch):
        monkeypatch.delenv("PLATFORM_FEE_PERCENT", raising=False)
        assert server.platform_fee_percent() == 15.0

    def test_reads_central_config(self, monkeypatch):
        monkeypatch.setenv("PLATFORM_FEE_PERCENT", "12.5")
        assert server.platform_fee_percent() == 12.5
        assert server.compute_fee(10000) == 1250.0

    @pytest.mark.parametrize("bad", ["abc", "-5", "150", ""])
    def test_nonsense_config_falls_back_rather_than_charging_nonsense(self, monkeypatch, bad):
        monkeypatch.setenv("PLATFORM_FEE_PERCENT", bad)
        assert server.platform_fee_percent() == 15.0

    def test_override_wins_for_a_one_off_deal(self, monkeypatch):
        monkeypatch.setenv("PLATFORM_FEE_PERCENT", "15")
        assert server.compute_fee(10000, override=800) == 800.0

    def test_fee_is_rounded_to_paise(self, monkeypatch):
        monkeypatch.setenv("PLATFORM_FEE_PERCENT", "13.33")
        assert server.compute_fee(7777) == round(7777 * 0.1333, 2)


# ---------------------------------------------------------------------------
# Payout identity — we used to mark payouts paid without knowing where to send
# ---------------------------------------------------------------------------


class TestPayoutReadiness:
    def test_needs_both_a_destination_and_a_tax_identity(self):
        assert server.payout_ready({"payout_upi": "priya@okhdfcbank", "pan": "AAAPR1001A"})
        assert not server.payout_ready({"payout_upi": "priya@okhdfcbank"})
        assert not server.payout_ready({"pan": "AAAPR1001A"})
        assert not server.payout_ready({})
        assert not server.payout_ready(None)


class _PayoutPayload:
    """Stand-in for the profile payload's payout fields."""

    def __init__(self, upi=None, name=None, pan=None, gstin=None):
        self.payout_upi = upi
        self.payout_account_name = name
        self.pan = pan
        self.gstin = gstin


class TestPayoutValidation:
    def test_valid_details_are_normalised(self):
        out = server._clean_payout_fields(
            _PayoutPayload(upi="Priya@okhdfcbank", name=" Priya Rao ", pan="aaapr1001a")
        )
        assert out["payout_upi"] == "Priya@okhdfcbank"
        assert out["payout_account_name"] == "Priya Rao"
        assert out["pan"] == "AAAPR1001A"  # upper-cased, ready for TDS filing

    def test_blank_fields_are_allowed_and_stored_as_none(self):
        out = server._clean_payout_fields(_PayoutPayload())
        assert out == {
            "payout_upi": None,
            "payout_account_name": None,
            "pan": None,
            "gstin": None,
        }

    @pytest.mark.parametrize("bad_upi", ["notaupi", "@bank", "priya@", "priya bank"])
    def test_malformed_upi_is_refused(self, bad_upi):
        # A typo'd UPI ID is a payout that silently goes nowhere.
        with pytest.raises(HTTPException) as exc:
            server._clean_payout_fields(_PayoutPayload(upi=bad_upi))
        assert exc.value.status_code == 422

    @pytest.mark.parametrize("bad_pan", ["ABCD1234F", "ABCDE12345", "1234567890"])
    def test_malformed_pan_is_refused(self, bad_pan):
        with pytest.raises(HTTPException) as exc:
            server._clean_payout_fields(_PayoutPayload(pan=bad_pan))
        assert exc.value.status_code == 422

    def test_valid_gstin_accepted_and_malformed_refused(self):
        ok = server._clean_payout_fields(_PayoutPayload(gstin="29ABCDE1234F1Z5"))
        assert ok["gstin"] == "29ABCDE1234F1Z5"
        with pytest.raises(HTTPException):
            server._clean_payout_fields(_PayoutPayload(gstin="29ABCDE1234"))


# ---------------------------------------------------------------------------
# OTP simulation — a missing env var used to downgrade auth to "read the log"
# ---------------------------------------------------------------------------


class TestOtpSimulationGuard:
    def _clear(self, monkeypatch):
        for var in ("ALLOW_OTP_SIMULATION", "APP_ENV", "ENV"):
            monkeypatch.delenv(var, raising=False)

    def test_refused_by_default(self, monkeypatch):
        self._clear(monkeypatch)
        assert server._simulation_allowed() is False

    def test_allowed_when_asked_for_explicitly(self, monkeypatch):
        self._clear(monkeypatch)
        monkeypatch.setenv("ALLOW_OTP_SIMULATION", "true")
        assert server._simulation_allowed() is True

    @pytest.mark.parametrize("env", ["dev", "development", "local", "test"])
    def test_allowed_in_non_production_environments(self, monkeypatch, env):
        self._clear(monkeypatch)
        monkeypatch.setenv("APP_ENV", env)
        assert server._simulation_allowed() is True

    def test_refused_in_production(self, monkeypatch):
        self._clear(monkeypatch)
        monkeypatch.setenv("APP_ENV", "production")
        assert server._simulation_allowed() is False


# ---------------------------------------------------------------------------
# Brand-facing serialization — contact details must not leak to a brand that
# has not accepted the creator yet.
# ---------------------------------------------------------------------------


def _collab(state, **extra):
    from bson import ObjectId

    base = {
        "_id": ObjectId(),
        "state": state,
        "pitch": "I shoot warm, food-first reels.",
        "quoted_rate": 8000,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    base.update(extra)
    return base


class TestApplicantProjection:
    CREATOR_USER = {"_id": "u1", "name": "Priya Rao", "email": "p@x.in", "phone": "+9198"}
    PROFILE = {"name": "Priya Rao", "instagram_handle": "priyaeats", "city": "Bengaluru"}

    @pytest.mark.parametrize("state", ["applied", "verified", "declined", "cancelled"])
    def test_contact_details_hidden_before_a_working_relationship(self, state):
        row = server._serialize_applicant(
            _collab(state), self.CREATOR_USER, self.PROFILE, None
        )
        assert row["creator"]["email"] is None
        assert row["creator"]["phone"] is None
        # The things a brand needs in order to decide are still there.
        assert row["creator"]["instagram_handle"] == "priyaeats"
        assert row["pitch"]

    @pytest.mark.parametrize("state", ["accepted", "slot_booked", "closed"])
    def test_contact_details_revealed_once_working_together(self, state):
        row = server._serialize_applicant(
            _collab(state), self.CREATOR_USER, self.PROFILE, None
        )
        assert row["creator"]["email"] == "p@x.in"
        assert row["creator"]["phone"] == "+9198"

    def test_actions_are_decided_server_side(self):
        verified = server._serialize_applicant(_collab("verified"), self.CREATOR_USER, self.PROFILE, None)
        assert verified["can_accept"] and verified["can_decline"]

        # Already accepted: no second acceptance, but it can still be declined.
        accepted = server._serialize_applicant(_collab("accepted"), self.CREATOR_USER, self.PROFILE, None)
        assert not accepted["can_accept"]
        assert accepted["can_decline"]

        # Too far along to decline — that's a cancellation, not a decline.
        booked = server._serialize_applicant(_collab("slot_booked"), self.CREATOR_USER, self.PROFILE, None)
        assert not booked["can_decline"]

        submitted = server._serialize_applicant(
            _collab("content_submitted"), self.CREATOR_USER, self.PROFILE, None
        )
        assert submitted["can_review_content"]


class TestCampaignActionFlags:
    def _campaign(self, status, **extra):
        from bson import ObjectId

        base = {
            "_id": ObjectId(),
            "title": "Weekend brunch reel",
            "status": status,
            "creators_needed": 3,
            "created_at": datetime.now(timezone.utc),
        }
        base.update(extra)
        return base

    def test_a_draft_can_be_published_edited_and_deleted(self):
        row = server._serialize_brand_campaign(self._campaign("draft"), 0)
        assert row["can_publish"] and row["can_edit"] and row["can_delete"]

    def test_a_draft_with_applicants_is_not_deletable(self):
        row = server._serialize_brand_campaign(self._campaign("draft"), 2)
        assert not row["can_delete"]

    def test_a_live_campaign_can_be_edited_and_closed_but_not_republished(self):
        row = server._serialize_brand_campaign(self._campaign("open"), 4)
        assert row["can_edit"] and row["can_close"]
        assert not row["can_publish"]

    def test_a_closed_campaign_is_finished(self):
        row = server._serialize_brand_campaign(self._campaign("closed"), 4)
        assert not row["can_edit"]
        assert not row["can_close"]
        assert not row["can_delete"]

    def test_spots_left_never_goes_negative(self):
        row = server._serialize_brand_campaign(self._campaign("open"), 9, filled=5)
        assert row["spots_left"] == 0
        assert row["filled_slots"] == 5


# ---------------------------------------------------------------------------
# Existing helpers that had no coverage
# ---------------------------------------------------------------------------


class TestPhoneNormalisation:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("+91 98765 43210", "+919876543210"),
            ("+91-98765-43210", "+919876543210"),
            ("  +919876543210  ", "+919876543210"),
        ],
    )
    def test_accepts_the_ways_people_actually_type_numbers(self, raw, expected):
        assert server._normalize_phone(raw) == expected

    @pytest.mark.parametrize("raw", ["9876543210", "", "+0123", "not a phone"])
    def test_rejects_what_it_cannot_deliver_to(self, raw):
        with pytest.raises(HTTPException) as exc:
            server._normalize_phone(raw)
        assert exc.value.status_code == 400


class TestInstagramHandleExtraction:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("@priyaeats", "priyaeats"),
            ("priyaeats", "priyaeats"),
            ("https://instagram.com/priyaeats", "priyaeats"),
            ("https://instagram.com/priyaeats/", "priyaeats"),
            ("https://instagram.com/priyaeats?hl=en", "priyaeats"),
            ("PriyaEats", "priyaeats"),
        ],
    )
    def test_pulls_a_handle_out_of_whatever_was_pasted(self, raw, expected):
        assert server._extract_ig_handle(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "has spaces", "no!"])
    def test_returns_none_rather_than_a_bad_lookup(self, raw):
        assert server._extract_ig_handle(raw) is None


class TestJsonSafety:
    def test_audit_snapshots_survive_serialization(self):
        from bson import ObjectId

        oid = ObjectId()
        when = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
        out = server._jsonable({"id": oid, "at": when, "rows": [{"x": oid}]})
        assert out["id"] == str(oid)
        assert out["at"] == when.isoformat()
        assert out["rows"][0]["x"] == str(oid)


class TestTermsConsent:
    def test_signup_payloads_default_to_not_accepted(self):
        # Consent has to be an act, not a default.
        assert server.RegisterInput.model_fields["accept_terms"].default is False
        assert server.OtpVerifyInput.model_fields["accept_terms"].default is False
