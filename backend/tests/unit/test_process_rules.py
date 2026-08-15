"""Unit tests for the process rules that were wrong or missing.

Every test here maps to a specific defect found in the process review, so a
regression re-breaks a named flow rather than an anonymous assertion.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import httpx
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


class TestCampaignVisibility:
    """The creator feed and the admin view answer different questions, and the
    admin one must never narrow to the feed's rule."""

    def test_the_feed_stays_narrow(self):
        assert server.LIVE_CAMPAIGN_STATUSES == ("open", "upcoming")
        assert server._LIVE_STATUSES == server.LIVE_CAMPAIGN_STATUSES

    def test_active_is_wider_than_live_but_excludes_finished_work(self):
        active = set(server.ACTIVE_CAMPAIGN_STATUSES)
        assert set(server.LIVE_CAMPAIGN_STATUSES) < active, (
            "a campaign mid-delivery is still active even though the feed hides it"
        )
        for finished in ("closed", "completed", "draft"):
            assert finished not in active

    def test_every_active_status_is_a_real_campaign_status(self):
        for status in server.ACTIVE_CAMPAIGN_STATUSES:
            assert status in server.CampaignStatus.__args__


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


# ---------------------------------------------------------------------------
# Profile image uploads. The declared content type comes from the client, so
# the only thing that decides what a file is are its own leading bytes.
# ---------------------------------------------------------------------------


class TestUploadSniffing:
    @pytest.mark.parametrize(
        "head,expected",
        [
            (b"\xff\xd8\xff\xe0\x00\x10JFIF", ("image/jpeg", ".jpg")),
            (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", ("image/png", ".png")),
            (b"GIF87a\x01\x00", ("image/gif", ".gif")),
            (b"GIF89a\x01\x00", ("image/gif", ".gif")),
            (b"RIFF\x24\x00\x00\x00WEBPVP8 ", ("image/webp", ".webp")),
        ],
    )
    def test_recognises_the_formats_creators_actually_upload(self, head, expected):
        assert server.sniff_image_type(head) == expected

    @pytest.mark.parametrize(
        "head",
        [
            b"",
            b"GIF",                              # truncated below the magic
            b"%PDF-1.4",                         # a document renamed to .jpg
            b"<?php system($_GET['c']); ?>",     # the one that matters
            b"RIFF\x24\x00\x00\x00AVI LIST",     # RIFF, but not WebP
            b"\x89PNG",                          # partial PNG magic
        ],
    )
    def test_refuses_anything_that_is_not_an_image(self, head):
        assert server.sniff_image_type(head) is None


class TestUploadSizeLimit:
    def test_defaults_to_five_megabytes(self, monkeypatch):
        monkeypatch.delenv("MAX_UPLOAD_MB", raising=False)
        assert server.max_upload_bytes() == 5 * 1024 * 1024

    @pytest.mark.parametrize(
        "raw,expected_mb",
        [
            ("2", 2),
            ("25", 25),
            ("400", 25),        # clamped down: disk is not free
            ("0", 0.1),         # clamped up: zero would reject every upload
            ("-3", 0.1),
            ("not a number", 5),
        ],
    )
    def test_environment_value_is_clamped_to_something_sane(
        self, monkeypatch, raw, expected_mb
    ):
        monkeypatch.setenv("MAX_UPLOAD_MB", raw)
        assert server.max_upload_bytes() == int(expected_mb * 1024 * 1024)


class TestUploadDeletionStaysInsideItsDirectory:
    @pytest.mark.parametrize(
        "url",
        [
            None,
            "",
            "https://cdn.example.com/evil.jpg",   # not ours
            "/uploads/../../server.py",           # traversal
            "/uploads/",
            "/etc/passwd",
        ],
    )
    def test_ignores_anything_it_did_not_write(self, url, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "UPLOAD_DIR", tmp_path)
        victim = tmp_path.parent / "server.py"
        victim.write_text("do not delete me")
        server._delete_upload(url)
        assert victim.exists()

    def test_deletes_a_file_it_did_write(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "UPLOAD_DIR", tmp_path)
        stored = tmp_path / "creator-abc123.jpg"
        stored.write_bytes(b"\xff\xd8\xff")
        server._delete_upload("/uploads/creator-abc123.jpg")
        assert not stored.exists()

    def test_a_missing_file_is_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "UPLOAD_DIR", tmp_path)
        server._delete_upload("/uploads/creator-gone.jpg")  # must not raise


# ---------------------------------------------------------------------------
# The Instagram scraper is gone. Scraping breached Instagram's terms and put
# the connected Meta Business account at risk, so this guards against it
# quietly reappearing — including via a new client or a renamed helper.
# ---------------------------------------------------------------------------


class TestNoInstagramScraper:
    SOURCE = None

    @classmethod
    def setup_class(cls):
        cls.SOURCE = (server.ROOT_DIR / "server.py").read_text()

    @pytest.mark.parametrize(
        "name",
        [
            "_fetch_instagram_from_apify",
            "_apify_token",
            "APIFY_ACTOR",
            "_get_or_refresh_ig",
            "_load_cached_ig_stats",
            "_save_ig_stats",
            "INSTAGRAM_STATS_TTL_SECONDS",
        ],
    )
    def test_the_scraper_symbols_are_gone(self, name):
        assert not hasattr(server, name)

    def test_no_route_serves_scraped_stats(self):
        paths = {getattr(r, "path", "") for r in server.app.routes}
        assert not any("instagram-stats" in p for p in paths)

    def test_nothing_calls_a_scraping_service(self):
        # The word may only survive in the comment explaining the removal and
        # in the startup warning about the orphaned cache.
        allowed = ("removed", "breach", "cache", "drop", "gone", "scraper")
        for n, line in enumerate(self.SOURCE.splitlines(), 1):
            low = line.lower()
            if "apify" not in low:
                continue
            assert low.lstrip().startswith("#") or any(a in low for a in allowed), (
                f"server.py:{n} looks like live Apify code: {line.strip()!r}"
            )

    def test_follower_counts_are_labelled_self_reported(self):
        # A number presented without provenance reads as measured. It isn't.
        assert '"follower_count_source": "self_reported"' in self.SOURCE


# ---------------------------------------------------------------------------
# Campaign invites. Sourcing is manual, so an admin picks creators and asks
# them over WhatsApp. The rules that matter: nobody is asked twice, and a
# partial send is reported as a partial send rather than rounded to success.
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    """Stands in for httpx.AsyncClient. Records the call, returns or raises."""

    calls = []

    def __init__(self, result):
        self._result = result

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).calls.append({"url": url, "json": json, "headers": headers})
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _patch_client(monkeypatch, result):
    _FakeClient.calls = []
    monkeypatch.setattr(server.httpx, "AsyncClient", _FakeClient(result))
    return _FakeClient.calls


class TestUtilityWhatsAppSender:
    """`_send_aisensy_utility` mirrors the OTP sender, minus the OTP."""

    def _send(self, template="invite_v1", params=("Camp", "Brand", "₹5,000")):
        return asyncio.run(
            server._send_aisensy_utility("+919876543210", "Priya", template, list(params))
        )

    def test_simulates_when_credentials_are_missing_in_dev(self, monkeypatch):
        monkeypatch.delenv("AISENSY_API_KEY", raising=False)
        monkeypatch.setenv("ALLOW_OTP_SIMULATION", "true")
        assert self._send() == "simulation"

    def test_refuses_to_pretend_outside_dev(self, monkeypatch):
        # Reporting a send that never happened is worse than a visible failure.
        monkeypatch.delenv("AISENSY_API_KEY", raising=False)
        monkeypatch.setenv("ALLOW_OTP_SIMULATION", "false")
        monkeypatch.setenv("APP_ENV", "production")
        with pytest.raises(HTTPException) as exc:
            self._send()
        assert exc.value.status_code == 503

    def test_a_configured_key_with_no_template_is_still_not_a_send(self, monkeypatch):
        monkeypatch.setenv("AISENSY_API_KEY", "key-123")
        monkeypatch.setenv("ALLOW_OTP_SIMULATION", "false")
        monkeypatch.setenv("APP_ENV", "production")
        with pytest.raises(HTTPException) as exc:
            self._send(template="")
        assert exc.value.status_code == 503

    def test_posts_the_template_params_in_order(self, monkeypatch):
        monkeypatch.setenv("AISENSY_API_KEY", "key-123")
        calls = _patch_client(monkeypatch, _FakeResponse(200))
        assert self._send(params=("Diwali brief", "The Permit Room", "₹5,000")) == "aisensy"
        assert len(calls) == 1
        body = calls[0]["json"]
        assert calls[0]["url"] == "https://backend.aisensy.com/campaign/t1/api/v2"
        assert body["campaignName"] == "invite_v1"
        assert body["destination"] == "+919876543210"
        assert body["userName"] == "Priya"
        # Campaign title, brand, budget — the order the template expects.
        assert body["templateParams"] == ["Diwali brief", "The Permit Room", "₹5,000"]

    def test_does_not_leak_the_api_key_into_the_template_params(self, monkeypatch):
        monkeypatch.setenv("AISENSY_API_KEY", "key-123")
        calls = _patch_client(monkeypatch, _FakeResponse(200))
        self._send()
        assert "key-123" not in " ".join(calls[0]["json"]["templateParams"])

    @pytest.mark.parametrize("status,expected", [(429, 503), (500, 503), (503, 503), (400, 502), (401, 502)])
    def test_maps_provider_failures_to_retryable_and_not(
        self, monkeypatch, status, expected
    ):
        monkeypatch.setenv("AISENSY_API_KEY", "key-123")
        _patch_client(monkeypatch, _FakeResponse(status, "nope"))
        with pytest.raises(HTTPException) as exc:
            self._send()
        assert exc.value.status_code == expected

    def test_a_network_error_is_a_failure_not_a_crash(self, monkeypatch):
        monkeypatch.setenv("AISENSY_API_KEY", "key-123")
        _patch_client(monkeypatch, httpx.ConnectError("boom"))
        with pytest.raises(HTTPException) as exc:
            self._send()
        assert exc.value.status_code == 503

    def test_it_is_a_separate_function_from_the_otp_sender(self):
        # The OTP sender reads AISENSY_CAMPAIGN_NAME and logs a live code; the
        # utility sender must not be quietly re-pointed at it.
        assert server._send_aisensy_utility is not server._send_aisensy_otp
        import inspect

        # The docstring names it to explain the difference; the code must not
        # read it, or every invite would go out on the OTP template.
        code = [
            line
            for line in inspect.getsource(server._send_aisensy_utility).splitlines()
            if "os.environ" in line
        ]
        assert code, "the sender no longer reads any configuration"
        assert not any("AISENSY_CAMPAIGN_NAME" in line for line in code)


class TestInviteEndpointShape:
    def test_the_route_exists_and_is_a_post(self):
        routes = [
            r for r in server.app.routes
            if getattr(r, "path", "") == "/api/admin/campaigns/{campaign_id}/invite"
        ]
        assert routes, "the invite route is not mounted"
        assert routes[0].methods == {"POST"}

    def test_it_takes_a_list_of_creator_ids(self):
        fields = server.CampaignInvitePayload.model_fields
        assert "creator_ids" in fields
        with pytest.raises(Exception):
            server.CampaignInvitePayload(creator_ids=[])  # an empty ask is a mistake

    def test_a_batch_is_bounded(self):
        # 100 invites is a big manual sourcing push; 10,000 is an accident.
        with pytest.raises(Exception):
            server.CampaignInvitePayload(creator_ids=[str(n) for n in range(101)])

    def test_finished_campaigns_cannot_be_invited_to(self):
        # An invite to a closed brief is one the creator can never take up.
        assert "completed" not in server.INVITABLE_CAMPAIGN_STATUSES
        assert "closed" not in server.INVITABLE_CAMPAIGN_STATUSES
        assert "open" in server.INVITABLE_CAMPAIGN_STATUSES

    def test_the_invite_is_a_known_notification_event(self):
        assert "campaign_invite" in server.NOTIFY_EVENTS

    def test_the_duplicate_guard_is_in_the_database_not_just_the_check(self):
        # Two admins clicking at once must not double-message a creator, and a
        # pre-check alone cannot promise that.
        source = (server.ROOT_DIR / "server.py").read_text()
        assert "one_invite_per_creator" in source
        assert "DuplicateKeyError" in source.split("def invite_creators_to_campaign")[1][:6000]


class TestNotificationRecordSplit:
    def test_the_record_writer_never_sends_whatsapp(self):
        # The invite sends its own utility message; going back through notify()
        # would message the creator twice.
        import inspect

        src = inspect.getsource(server.record_notification)
        assert "aisensy" not in src.lower()
        assert "AISENSY_TEMPLATE" not in src


# ---------------------------------------------------------------------------
# Moderation gates. Two things used to reach the public with nobody's approval:
# a brand that signed itself up, and a campaign whose payload said "open".
# ---------------------------------------------------------------------------


class TestCampaignReviewStatus:
    def test_pending_review_is_a_real_campaign_status(self):
        assert server.CAMPAIGN_REVIEW_STATUS == "pending_review"
        assert server.CAMPAIGN_REVIEW_STATUS in server.CampaignStatus.__args__

    def test_a_brief_nobody_has_read_is_not_on_the_feed(self):
        # The whole point of the gate.
        assert server.CAMPAIGN_REVIEW_STATUS not in server.LIVE_CAMPAIGN_STATUSES
        assert server.CAMPAIGN_REVIEW_STATUS not in server._LIVE_STATUSES

    def test_review_is_not_counted_as_a_running_campaign(self):
        # It is waiting on us, not taking applications or in delivery.
        assert server.CAMPAIGN_REVIEW_STATUS not in server.ACTIVE_CAMPAIGN_STATUSES

    def test_a_brand_may_only_ask_for_draft_or_review(self):
        assert server.BRAND_SETTABLE_CAMPAIGN_STATUSES == ("draft", "pending_review")
        for forbidden in ("open", "upcoming", "in_progress", "completed", "closed"):
            assert forbidden not in server.BRAND_SETTABLE_CAMPAIGN_STATUSES

    def test_the_payload_still_accepts_open_so_it_can_be_explained(self):
        # Refusing in the handler gives a sentence; refusing in the schema gives
        # a pydantic error nobody can act on.
        field = server.PostCampaignPayload.model_fields["status"]
        assert "open" in field.annotation.__args__
        assert field.default == "draft"

    def test_the_handler_is_what_refuses_open(self):
        import inspect

        src = inspect.getsource(server.create_brand_campaign)
        assert "BRAND_SETTABLE_CAMPAIGN_STATUSES" in src
        assert "payload.status" in src

    def test_invites_cannot_reach_an_unapproved_brief(self):
        # Inviting to a draft or a brief in review would walk it past the gate
        # over WhatsApp, to a campaign the creator cannot even open.
        assert "draft" not in server.INVITABLE_CAMPAIGN_STATUSES
        assert server.CAMPAIGN_REVIEW_STATUS not in server.INVITABLE_CAMPAIGN_STATUSES
        assert "open" in server.INVITABLE_CAMPAIGN_STATUSES


class TestModerationRoutes:
    ROUTES = {
        ("/api/admin/brands/pending", "GET"),
        ("/api/admin/brands/{user_id}/verify", "POST"),
        ("/api/admin/brands/{user_id}/reject", "POST"),
        ("/api/admin/campaigns/pending", "GET"),
        ("/api/admin/campaigns/{campaign_id}/approve", "POST"),
        ("/api/admin/campaigns/{campaign_id}/reject", "POST"),
    }

    @pytest.mark.parametrize("path,method", sorted(ROUTES))
    def test_the_gate_endpoints_exist(self, path, method):
        matches = [r for r in server.app.routes if getattr(r, "path", "") == path]
        assert matches, f"{path} is not mounted"
        assert method in matches[0].methods

    def test_the_fixed_queues_are_declared_before_the_parameterised_paths(self):
        # /brands/pending must not be swallowed by /brands/{user_id}.
        paths = [getattr(r, "path", "") for r in server.app.routes]
        for fixed, param in (
            ("/api/admin/brands/pending", "/api/admin/brands/{user_id}/verify"),
            ("/api/admin/campaigns/pending", "/api/admin/campaigns/{campaign_id}/approve"),
        ):
            assert paths.index(fixed) < paths.index(param)

    def test_every_moderation_decision_is_guarded_by_the_admin_role(self):
        import inspect

        for fn in (
            server.list_pending_brands,
            server.reject_brand,
            server.list_campaigns_for_review,
            server.approve_campaign,
            server.reject_campaign,
        ):
            assert 'require_roles("admin")' in inspect.getsource(fn)


class TestModerationNotifications:
    @pytest.mark.parametrize(
        "event",
        ["brand_verified", "brand_rejected", "campaign_approved", "campaign_rejected"],
    )
    def test_each_decision_has_a_declared_event(self, event):
        assert event in server.NOTIFY_EVENTS

    def test_decisions_go_out_on_the_utility_sender(self):
        # Which is the one with the simulation fallback; `_send_aisensy_template`
        # fails silently when unconfigured, and a brand not being told is not a
        # silent condition.
        import inspect

        src = inspect.getsource(server.notify_over_utility_template)
        assert "_send_aisensy_utility" in src
        assert "record_notification" in src

    def test_a_failed_message_cannot_undo_the_decision(self):
        import inspect

        src = inspect.getsource(server.notify_over_utility_template)
        assert "except HTTPException" in src, "a send failure must not 502 the decision"
        assert "raise" not in src.split("except HTTPException")[1][:400]

    @pytest.mark.parametrize(
        "fn_name,event",
        [
            ("verify_brand", "brand_verified"),
            ("reject_brand", "brand_rejected"),
            ("approve_campaign", "campaign_approved"),
            ("reject_campaign", "campaign_rejected"),
        ],
    )
    def test_the_endpoint_sends_the_matching_event(self, fn_name, event):
        import inspect

        src = inspect.getsource(getattr(server, fn_name))
        assert "notify_over_utility_template" in src
        assert f'"{event}"' in src


class TestRejectionsCarryAReason:
    @pytest.mark.parametrize("fn_name", ["reject_brand", "reject_campaign"])
    def test_a_reason_is_required_not_optional(self, fn_name):
        import inspect

        src = inspect.getsource(getattr(server, fn_name))
        # A refusal the brand can't act on is worse than no refusal.
        assert "status_code=422" in src
        assert "Give a reason" in src

    def test_approval_writes_the_state_with_a_precondition(self):
        import inspect

        src = inspect.getsource(server.approve_campaign)
        # Two admins working the queue must not both publish it.
        assert '"status": CAMPAIGN_REVIEW_STATUS' in src
        assert "409" in src

    def test_a_rejected_campaign_goes_back_to_the_brand_not_to_a_dead_end(self):
        import inspect

        src = inspect.getsource(server.reject_campaign)
        assert '"status": "draft"' in src
        assert "review_reason" in src


# ---------------------------------------------------------------------------
# Reversal, failure paths and refunds. The ladder used to only go up: a fee
# agreed at the wrong number had no fix short of cancelling the whole thing,
# and a payout that went out could not come back.
# ---------------------------------------------------------------------------


class TestReversal:
    def test_the_step_back_mirrors_the_step_forward(self):
        for state in server.COLLAB_STATE_ORDER[1:]:
            back = server._previous_collab_state(state)
            assert server._next_collab_state(back) == state

    def test_the_first_step_has_nothing_behind_it(self):
        assert server._previous_collab_state(server.COLLAB_STATE_ORDER[0]) is None

    @pytest.mark.parametrize("state", ["declined", "cancelled"])
    def test_an_exit_is_not_a_step_you_can_walk_back(self, state):
        # Coming back from an exit is a different decision, not a reversal.
        assert server._previous_collab_state(state) is None

    def test_unknown_state_does_not_crash_the_board(self):
        assert server._previous_collab_state("something_we_removed") is None

    def test_closed_cannot_be_reverted(self):
        import inspect

        src = inspect.getsource(server.revert_collaboration)
        assert 'current == "closed"' in src
        assert "409" in src

    def test_a_paid_payout_sends_you_to_refund_instead(self):
        import inspect

        src = inspect.getsource(server.revert_collaboration)
        assert '"paid"' in src
        assert "refund" in src.lower()

    def test_stepping_back_out_of_payment_takes_the_payable_with_it(self):
        # `collaboration_id` is unique on payments, so a cancelled row left
        # behind would stop a new one being created on the way forward again.
        import inspect

        src = inspect.getsource(server.revert_collaboration)
        assert "payments.delete_one" in src

    def test_reverting_frees_the_campaign_slot(self):
        import inspect

        assert "_sync_campaign_fill" in inspect.getsource(server.revert_collaboration)

    def test_a_revert_has_to_be_explained(self):
        assert server.ReasonPayload.model_fields["reason"].is_required()
        with pytest.raises(Exception):
            server.ReasonPayload(reason="")


class TestFailurePaths:
    def test_the_exits_are_terminal_states(self):
        for exit_state in ("cancelled", "declined"):
            assert exit_state in server.TERMINAL_COLLAB_STATES
            assert exit_state not in server.COLLAB_STATE_ORDER

    def test_cancellation_types_are_the_three_ways_it_actually_fails(self):
        assert set(server.CANCELLATION_TYPES) == {
            "creator_no_show",
            "brand_cancelled",
            "admin_cancelled",
        }
        assert set(server.CancellationType.__args__) == set(server.CANCELLATION_TYPES)

    def test_an_unattributed_cancellation_is_ours(self):
        payload = server.CancelCollabPayload(reason="Venue flooded")
        assert payload.cancellation_type == "admin_cancelled"

    def test_a_cancellation_has_to_be_explained(self):
        with pytest.raises(Exception):
            server.CancelCollabPayload(cancellation_type="brand_cancelled")

    def test_an_invented_cancellation_type_is_refused(self):
        with pytest.raises(Exception):
            server.CancelCollabPayload(reason="because", cancellation_type="vibes")

    def test_declining_is_only_before_anyone_took_them_on(self):
        # Past these the brand has accepted the creator, and ending it is a
        # cancellation — a different admission with money attached.
        assert server._DECLINABLE_STATES == ("applied", "verified")
        for later in ("accepted", "commercial_agreed", "attended"):
            assert later not in server._DECLINABLE_STATES

    def test_cancelling_after_an_agreement_keeps_the_number(self):
        # The collaboration leaves the "ongoing" group it was counted in, so
        # without this the agreed figure disappears from the record entirely.
        import inspect

        src = inspect.getsource(server.cancel_collaboration)
        assert "agreed_amount_at_cancellation" in src
        assert "commercial_agreed" in src

    def test_a_no_show_is_not_flagged_for_settlement(self):
        # Attendance is what makes a settlement a question; a creator who never
        # turned up did not do the work.
        import inspect

        src = inspect.getsource(server.cancel_collaboration)
        assert 'cancellation_type != "creator_no_show"' in src

    def test_a_paid_collaboration_cannot_be_cancelled(self):
        import inspect

        src = inspect.getsource(server.cancel_collaboration)
        assert '"paid"' in src and "409" in src


class TestRefunds:
    def test_refunded_is_its_own_payment_state(self):
        # Cancelled is a payout that never happened; refunded is one that did
        # and came back. Revenue figures have to tell them apart.
        states = set(server.PaymentState.__args__)
        assert {"pending", "paid", "cancelled", "refunded"} == states

    def test_only_a_paid_payout_can_be_refunded(self):
        import inspect

        src = inspect.getsource(server.refund_payment)
        assert 'state != "paid"' in src

    def test_refunding_twice_is_refused(self):
        import inspect

        src = inspect.getsource(server.refund_payment)
        assert 'state == "refunded"' in src
        assert '{"_id": pid, "state": "paid"}' in src, "the write needs a precondition"

    def test_a_refund_cancels_the_collaboration_with_it(self):
        import inspect

        src = inspect.getsource(server.refund_payment)
        assert '"state": "cancelled"' in src
        assert "collaborations.update_one" in src

    def test_a_settled_brand_invoice_is_flagged_not_quietly_voided(self):
        # We would be holding the brand's money; paying it back is a decision
        # with an invoice attached, not a status flip.
        import inspect

        src = inspect.getsource(server.refund_payment)
        assert "brand_refund_due" in src
        assert '"void"' in src

    def test_a_refund_has_to_be_explained(self):
        assert server.RefundPayload.model_fields["reason"].is_required()
        assert not server.RefundPayload.model_fields["refund_reference"].is_required()


class TestCampaignControls:
    def test_paused_is_a_real_status_and_off_the_feed(self):
        assert "paused" in server.CampaignStatus.__args__
        assert "paused" not in server.LIVE_CAMPAIGN_STATUSES
        assert "paused" not in server._LIVE_STATUSES

    def test_a_paused_campaign_is_not_counted_as_running(self):
        assert "paused" not in server.ACTIVE_CAMPAIGN_STATUSES

    def test_nobody_can_be_invited_to_a_paused_campaign(self):
        assert "paused" not in server.INVITABLE_CAMPAIGN_STATUSES

    def test_only_a_running_campaign_can_be_paused(self):
        assert server._PAUSABLE_STATUSES == ("upcoming", "open", "in_progress")
        for finished in ("draft", "pending_review", "completed", "closed"):
            assert finished not in server._PAUSABLE_STATUSES

    def test_pause_remembers_where_to_come_back_to(self):
        import inspect

        assert "paused_from_status" in inspect.getsource(server.pause_campaign)
        assert "paused_from_status" in inspect.getsource(server.resume_campaign)

    def test_resuming_re_checks_the_end_date(self):
        # A campaign paused past its window must not quietly reopen.
        import inspect

        src = inspect.getsource(server.resume_campaign)
        assert "end_date" in src and '"completed"' in src

    def test_closing_answers_everyone_still_waiting(self):
        import inspect

        src = inspect.getsource(server.admin_close_campaign)
        assert "_DECLINABLE_STATES" in src
        assert '"declined"' in src

    def test_the_admin_edit_keeps_the_same_floor_as_the_brands(self):
        import inspect

        src = inspect.getsource(server.admin_update_campaign)
        assert "_filled_counts_for" in src, "an edit must not shrink below the committed"
        assert "End date cannot be before start date" in src

    def test_a_finished_campaign_cannot_be_edited(self):
        assert server._CLOSED_CAMPAIGN_STATUSES == ("completed", "closed")


class TestAuditCoverage:
    """Every admin mutation has to leave a trace. A payout with no author is
    the thing this log exists to make impossible."""

    SOURCE = None

    @classmethod
    def setup_class(cls):
        cls.SOURCE = (server.ROOT_DIR / "server.py").read_text()

    def _admin_mutations(self):
        import re as _re

        blocks = _re.split(r"\n(?=@admin_router\.)", self.SOURCE)
        out = []
        for b in blocks[1:]:
            m = _re.match(r'@admin_router\.(post|patch|put|delete)\("([^"]+)"\)', b)
            if not m:
                continue
            fn = _re.search(r"async def (\w+)", b)
            end = b.find("\n@")
            out.append((m.group(2), fn.group(1), b[:end] if end > 0 else b))
        return out

    def test_there_are_mutations_to_check(self):
        assert len(self._admin_mutations()) >= 15

    def test_every_admin_mutation_writes_to_the_audit_log(self):
        missing = []
        for path, fn, body in self._admin_mutations():
            if "await audit(" in body:
                continue
            # Some endpoints delegate to a helper that audits on their behalf.
            delegates = any(
                f"await {helper}(" in body
                for helper in ("_set_creator_verification",)
            )
            if not delegates:
                missing.append(f"{path} ({fn})")
        assert not missing, f"admin mutations with no audit trail: {missing}"

    @pytest.mark.parametrize(
        "fn_name,action",
        [
            ("advance_collaboration", "collaboration.advance"),
            ("revert_collaboration", "collaboration.revert"),
            ("cancel_collaboration", "collaboration.cancel"),
            ("decline_applicant", "collaboration.decline"),
            ("mark_payment_paid", "payment.mark_paid"),
            ("refund_payment", "payment.refund"),
            ("approve_campaign", "campaign.approve"),
            ("reject_campaign", "campaign.reject"),
            ("pause_campaign", "campaign.pause"),
            ("resume_campaign", "campaign.resume"),
            ("admin_close_campaign", "campaign.close"),
            ("admin_update_campaign", "campaign.update"),
        ],
    )
    def test_each_action_is_logged_under_its_own_name(self, fn_name, action):
        import inspect

        assert f'"{action}"' in inspect.getsource(getattr(server, fn_name))

    def test_the_log_records_who_as_an_id_not_just_a_name(self):
        import inspect

        # Names change; "which admin" is the question the log exists to answer.
        assert '"actor_id"' in inspect.getsource(server.audit)
        assert '"actor_id"' in inspect.getsource(server.list_audit_log)

    def test_before_and_after_are_both_recorded(self):
        params = list(
            __import__("inspect").signature(server.audit).parameters
        )
        for field in ("before", "after", "note"):
            assert field in params

    def test_writing_the_log_can_never_break_the_operation(self):
        import inspect

        src = inspect.getsource(server.audit)
        assert "except Exception" in src
        assert "raise" not in src.split("except Exception")[1]


class TestAuditFilters:
    def test_it_filters_on_the_three_things_people_ask_for(self):
        params = list(
            __import__("inspect").signature(server.list_audit_log).parameters
        )
        for field in ("actor_id", "action", "date_from", "date_to"):
            assert field in params

    def test_a_bare_action_matches_the_whole_family(self):
        # "everything that happened to money" is the question people arrive with.
        import inspect

        src = inspect.getsource(server.list_audit_log)
        assert "$regex" in src
        assert '"." in term' in src

    def test_a_bad_actor_id_is_a_422_not_a_500(self):
        import inspect

        src = inspect.getsource(server.list_audit_log)
        assert "422" in src


# ---------------------------------------------------------------------------
# Campaign types. The shape of the work decides the shape of the dates, and
# storing both shapes on every campaign is how a brief ends up with an event
# day AND a booking window.
# ---------------------------------------------------------------------------


def _campaign_body(**overrides):
    body = {
        "title": "Weekend reel",
        "brief": "b",
        "deliverables": "d",
        "budget_per_creator": 5000,
        "category": "fnb",
        "area": "Indiranagar",
        "creators_needed": 2,
    }
    body.update(overrides)
    return body


class TestCampaignTypes:
    def test_the_three_types_are_the_declared_ones(self):
        assert set(server.CampaignType.__args__) == {
            "launch",
            "group_event",
            "personal_table",
        }
        assert server.EVENT_CAMPAIGN_TYPES == ("launch", "group_event")

    def test_a_type_is_required(self):
        with pytest.raises(Exception):
            server.PostCampaignPayload(**_campaign_body())

    @pytest.mark.parametrize("ctype", ["launch", "group_event"])
    def test_an_event_campaign_takes_one_day(self, ctype):
        payload = server.PostCampaignPayload(
            **_campaign_body(campaign_type=ctype, event_date="2026-09-01T10:00:00Z")
        )
        assert payload.event_date is not None
        assert payload.start_date is None and payload.end_date is None

    @pytest.mark.parametrize("ctype", ["launch", "group_event"])
    def test_an_event_campaign_without_a_day_is_refused(self, ctype):
        with pytest.raises(Exception):
            server.PostCampaignPayload(**_campaign_body(campaign_type=ctype))

    @pytest.mark.parametrize("ctype", ["launch", "group_event"])
    def test_an_event_campaign_cannot_also_carry_a_window(self, ctype):
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_campaign_body(
                    campaign_type=ctype,
                    event_date="2026-09-01T10:00:00Z",
                    start_date="2026-09-01T00:00:00Z",
                )
            )
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_campaign_body(
                    campaign_type=ctype,
                    event_date="2026-09-01T10:00:00Z",
                    end_date="2026-09-30T00:00:00Z",
                )
            )

    def test_a_personal_table_runs_over_a_window(self):
        payload = server.PostCampaignPayload(
            **_campaign_body(
                campaign_type="personal_table",
                start_date="2026-09-01T00:00:00Z",
                end_date="2026-09-30T00:00:00Z",
            )
        )
        assert payload.event_date is None
        assert payload.start_date is not None and payload.end_date is not None

    @pytest.mark.parametrize(
        "dates",
        [
            {},
            {"start_date": "2026-09-01T00:00:00Z"},
            {"end_date": "2026-09-30T00:00:00Z"},
        ],
    )
    def test_a_personal_table_needs_both_ends(self, dates):
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_campaign_body(campaign_type="personal_table", **dates)
            )

    def test_a_personal_table_cannot_carry_an_event_day(self):
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_campaign_body(
                    campaign_type="personal_table",
                    start_date="2026-09-01T00:00:00Z",
                    end_date="2026-09-30T00:00:00Z",
                    event_date="2026-09-15T10:00:00Z",
                )
            )

    def test_a_window_has_to_run_forwards(self):
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_campaign_body(
                    campaign_type="personal_table",
                    start_date="2026-09-30T00:00:00Z",
                    end_date="2026-09-01T00:00:00Z",
                )
            )

    def test_an_invented_type_is_refused(self):
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_campaign_body(campaign_type="popup", event_date="2026-09-01T10:00:00Z")
            )

    def test_the_type_cannot_be_changed_by_an_edit(self):
        # It decides which date fields exist; changing it would orphan whichever
        # dates were already set.
        assert "campaign_type" not in server.UpdateCampaignPayload.model_fields

    def test_an_edit_cannot_hand_a_campaign_the_other_types_dates(self):
        launch = {"campaign_type": "launch"}
        with pytest.raises(HTTPException) as exc:
            server._refuse_dates_foreign_to_type(launch, {"start_date": datetime.now(timezone.utc)})
        assert exc.value.status_code == 422

        table = {"campaign_type": "personal_table"}
        with pytest.raises(HTTPException):
            server._refuse_dates_foreign_to_type(table, {"event_date": datetime.now(timezone.utc)})

    def test_an_edit_cannot_strip_the_dates_a_type_requires(self):
        with pytest.raises(HTTPException):
            server._refuse_dates_foreign_to_type(
                {"campaign_type": "launch"}, {"event_date": None}
            )
        with pytest.raises(HTTPException):
            server._refuse_dates_foreign_to_type(
                {"campaign_type": "personal_table"}, {"end_date": None}
            )

    def test_an_edit_that_touches_neither_is_fine(self):
        server._refuse_dates_foreign_to_type({"campaign_type": "launch"}, {"title": "x"})

    def test_a_passed_event_day_expires_the_campaign_too(self):
        # Not just closed windows: an event whose day has gone must stop taking
        # applications.
        import inspect

        src = inspect.getsource(server._expire_stale_campaigns)
        assert "event_date" in src and "end_date" in src


class TestCampaignManagerRole:
    def test_the_role_exists_in_the_rbac(self):
        assert "campaign_manager" in server.Role.__args__

    def test_nobody_can_sign_themselves_up_as_one(self):
        # It can read creators' phone numbers — an admin makes the account.
        assert set(server.RegisterInput.model_fields["role"].annotation.__args__) == {
            "creator",
            "brand",
        }
        for model in (server.OtpRequestInput, server.OtpVerifyInput):
            allowed = model.model_fields["role"].annotation
            assert "campaign_manager" not in str(allowed)

    def test_managers_sign_in_with_a_password_like_admins(self):
        import inspect

        src = inspect.getsource(server.login)
        assert '"admin", "campaign_manager"' in src

    def test_a_manager_only_reaches_their_own_campaigns(self):
        import inspect

        src = inspect.getsource(server._managed_campaign_or_404)
        assert "manager_id" in src
        # 404 rather than 403, the same shape as brand ownership: the existence
        # of other campaigns leaks nothing. (The docstring says so too, so only
        # the raised statuses are checked.)
        raised = [ln for ln in src.splitlines() if "status_code=" in ln]
        assert raised
        assert all("404" in ln for ln in raised)

    @pytest.mark.parametrize(
        "fn_name",
        ["list_managed_campaigns", "list_campaign_slots", "create_campaign_slot",
         "delete_campaign_slot"],
    )
    def test_the_manager_endpoints_are_role_guarded(self, fn_name):
        import inspect

        src = inspect.getsource(getattr(server, fn_name))
        assert 'require_roles("campaign_manager", "admin")' in src

    def test_assignment_is_the_admins_alone(self):
        import inspect

        src = inspect.getsource(server.assign_campaign_manager)
        assert 'require_roles("admin")' in src
        # The snapshot is the point: the brand and the creators see these, and
        # they must not change under them if the manager edits their account.
        for field in ("manager_name", "manager_phone", "manager_email"):
            assert field in src

    def test_assignment_is_audited_and_the_manager_told(self):
        import inspect

        src = inspect.getsource(server.assign_campaign_manager)
        assert '"campaign.assign_manager"' in src
        assert "manager_assigned" in src


class TestSlots:
    def test_a_slot_has_to_end_after_it_starts(self):
        with pytest.raises(Exception):
            server.SlotPayload(
                starts_at="2026-09-01T12:00:00Z",
                ends_at="2026-09-01T11:00:00Z",
                capacity=4,
            )

    def test_a_slot_holds_at_least_one_person(self):
        with pytest.raises(Exception):
            server.SlotPayload(starts_at="2026-09-01T12:00:00Z", capacity=0)

    def test_an_event_slot_needs_no_end_time(self):
        payload = server.SlotPayload(starts_at="2026-09-01T12:00:00Z", capacity=4)
        assert payload.ends_at is None

    def test_booking_claims_the_seat_atomically(self):
        # The check and the increment are one operation, so two creators after
        # the last place resolve inside the database rather than both winning.
        import inspect

        src = inspect.getsource(server.book_slot)
        assert "find_one_and_update" in src
        assert '"$expr": {"$lt": ["$booked_count", "$capacity"]}' in src
        assert '"$inc": {"booked_count": 1}' in src

    def test_a_lost_race_is_a_409_not_a_double_booking(self):
        import inspect

        src = inspect.getsource(server.book_slot)
        assert "just filled up" in src

    def test_a_claimed_seat_is_given_back_if_the_collaboration_moved(self):
        import inspect

        src = inspect.getsource(server.book_slot)
        assert '"$inc": {"booked_count": -1}' in src

    def test_booking_is_the_step_out_of_commercial_agreed(self):
        import inspect

        src = inspect.getsource(server.book_slot)
        assert '"commercial_agreed"' in src
        assert '"slot_booked"' in src

    def test_reverting_out_of_slot_booked_frees_the_seat(self):
        import inspect

        src = inspect.getsource(server.revert_collaboration)
        assert 'current == "slot_booked"' in src
        assert '"$inc": {"booked_count": -1}' in src

    def test_cancelling_frees_the_seat_too(self):
        import inspect

        src = inspect.getsource(server.cancel_collaboration)
        assert "campaign_slots" in src
        assert '"$inc": {"booked_count": -1}' in src

    def test_a_slot_with_bookings_cannot_be_deleted(self):
        import inspect

        src = inspect.getsource(server.delete_campaign_slot)
        assert '"booked_count": 0' in src, "the delete needs a precondition"
        assert "409" in src

    def test_an_event_slot_must_sit_on_the_event_day(self):
        import inspect

        src = inspect.getsource(server.create_campaign_slot)
        assert "event_date" in src and ".date()" in src

    def test_a_table_window_must_sit_inside_the_campaigns_dates(self):
        import inspect

        src = inspect.getsource(server.create_campaign_slot)
        assert "start_date" in src and "end_date" in src


class TestCoordinationDetailsAreEarned:
    def test_only_creators_actually_on_the_campaign_see_them(self):
        # Applying is not being on it — a staff phone number is not applicant
        # information.
        assert "applied" not in server._ONBOARD_COLLAB_STATES
        assert "verified" not in server._ONBOARD_COLLAB_STATES
        assert "accepted" in server._ONBOARD_COLLAB_STATES
        assert "closed" in server._ONBOARD_COLLAB_STATES

    def test_the_public_serializer_leaks_neither_venue_nor_manager(self):
        import inspect

        src = inspect.getsource(server._serialize_campaign)
        for field in ("venue_address", "manager_phone", "manager_email", "on_site_contact"):
            assert field not in src, f"{field} must not reach the open campaign feed"

    def test_the_detail_view_gates_the_coordination_block(self):
        import inspect

        src = inspect.getsource(server.get_campaign)
        assert "_ONBOARD_COLLAB_STATES" in src
        assert "coordination" in src

    def test_creators_never_see_the_managers_email(self):
        # Name and phone are for coordinating on the day; the email is internal.
        import inspect

        src = inspect.getsource(server.get_campaign)
        block = src.split('payload["coordination"] = {')[1][:400]
        assert "manager_phone" in block
        assert "manager_email" not in block

    def test_the_slot_list_is_gated_the_same_way(self):
        import inspect

        src = inspect.getsource(server.list_slots_for_creator)
        assert "_ONBOARD_COLLAB_STATES" in src
