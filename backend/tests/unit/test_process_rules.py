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
                    for marker in (
                        "for legacy in",
                        '"state": "vetted"',
                        "#",
                        "Migrated",
                        # The admin console groups applicants into applied /
                        # approved / rejected. That "approved" is a bucket of
                        # collaboration states, never a verification_status
                        # value, so it cannot cause the mismatch this guard is
                        # about — the marker keeps the exemption that narrow.
                        "_APPLICANT",
                    )
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
        # Read off `_claim_slot`: both booking routes go through it, so there
        # is one atomic claim rather than one per entry point.
        import inspect

        src = inspect.getsource(server._claim_slot)
        assert "find_one_and_update" in src
        assert '"$expr": {"$lt": ["$booked_count", "$capacity"]}' in src
        assert '"$inc": {"booked_count": 1}' in src

    def test_a_lost_race_is_a_409_not_a_double_booking(self):
        import inspect

        src = inspect.getsource(server._claim_slot)
        assert "just filled up" in src

    def test_a_claimed_seat_is_given_back_if_the_collaboration_moved(self):
        import inspect

        src = inspect.getsource(server._claim_slot)
        assert '"$inc": {"booked_count": -1}' in src

    def test_booking_is_the_step_out_of_commercial_agreed(self):
        import inspect

        src = inspect.getsource(server.book_slot) + inspect.getsource(server._claim_slot)
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
        # The rule lives in _validate_slot_times, which create and edit share —
        # a slot moved onto the wrong day is as wrong as one created there.
        import inspect

        src = inspect.getsource(server._validate_slot_times)
        assert "event_date" in src and ".date()" in src

    def test_a_table_window_must_sit_inside_the_campaigns_dates(self):
        import inspect

        src = inspect.getsource(server._validate_slot_times)
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


# ---------------------------------------------------------------------------
# The manager's operational endpoints. Everything here is scoped through the
# campaign: a manager touches a creator because they are running the day that
# creator is booked onto, not because of anything about the creator.
# ---------------------------------------------------------------------------


MANAGER_ENDPOINTS = [
    "create_slot",
    "update_slot",
    "delete_campaign_slot",
    "create_campaign_slot",
    "list_campaign_slots",
    "list_managed_campaigns",
    "campaign_roster",
    "campaign_daysheet",
    "check_in_creator",
    "mark_no_show",
    "reschedule_creator",
    "broadcast_to_campaign",
]


class TestManagerScoping:
    @pytest.mark.parametrize("fn_name", MANAGER_ENDPOINTS)
    def test_every_endpoint_is_role_guarded(self, fn_name):
        import inspect

        src = inspect.getsource(getattr(server, fn_name))
        assert 'require_roles("campaign_manager", "admin")' in src

    @pytest.mark.parametrize(
        "fn_name",
        ["campaign_roster", "campaign_daysheet", "broadcast_to_campaign",
         "list_campaign_slots", "create_campaign_slot"],
    )
    def test_campaign_endpoints_go_through_the_scope_check(self, fn_name):
        import inspect

        assert "_managed_campaign_or_404" in inspect.getsource(getattr(server, fn_name))

    @pytest.mark.parametrize(
        "fn_name", ["check_in_creator", "mark_no_show", "reschedule_creator"]
    )
    def test_collaboration_endpoints_scope_through_the_campaign(self, fn_name):
        import inspect

        assert "_managed_collab_or_404" in inspect.getsource(getattr(server, fn_name))

    @pytest.mark.parametrize("fn_name", ["update_slot", "delete_campaign_slot"])
    def test_slot_endpoints_scope_through_the_campaign(self, fn_name):
        import inspect

        src = inspect.getsource(getattr(server, fn_name))
        assert "_slot_or_404" in src or "_managed_campaign_or_404" in src

    def test_the_scope_helpers_404_rather_than_403(self):
        import inspect

        for fn in (server._managed_collab_or_404, server._slot_or_404):
            raised = [ln for ln in inspect.getsource(fn).splitlines() if "status_code=" in ln]
            assert raised and all("404" in ln for ln in raised)

    def test_a_slot_on_another_campaign_is_not_a_reschedule_target(self):
        import inspect

        src = inspect.getsource(server.reschedule_creator)
        assert 'target["campaign_id"] != campaign["_id"]' in src


class TestManagerAudit:
    @pytest.mark.parametrize(
        "fn_name,action",
        [
            ("update_slot", "slot.update"),
            ("delete_campaign_slot", "slot.delete"),
            ("create_campaign_slot", "slot.create"),
            ("check_in_creator", "collaboration.check_in"),
            ("mark_no_show", "collaboration.no_show"),
            ("reschedule_creator", "collaboration.reschedule"),
            ("broadcast_to_campaign", "campaign.broadcast"),
        ],
    )
    def test_each_action_is_logged_under_its_own_name(self, fn_name, action):
        import inspect

        assert f'"{action}"' in inspect.getsource(getattr(server, fn_name))

    def test_every_manager_mutation_writes_to_the_audit_log(self):
        import inspect
        import re as _re

        source = (server.ROOT_DIR / "server.py").read_text()
        blocks = _re.split(r"\n(?=@manager_router\.)", source)
        missing = []
        for b in blocks[1:]:
            m = _re.match(r'@manager_router\.(post|patch|put|delete)\("([^"]+)"\)', b)
            if not m:
                continue
            end = b.find("\n@")
            body = b[:end] if end > 0 else b
            fn = _re.search(r"async def (\w+)", b)
            # create_slot delegates to create_campaign_slot, which audits.
            if "await audit(" in body or "await create_campaign_slot(" in body:
                continue
            missing.append(f"{m.group(2)} ({fn.group(1) if fn else '?'})")
        assert not missing, f"manager mutations with no audit trail: {missing}"
        assert inspect.getsource(server.broadcast_to_campaign).count("await audit(") == 1


class TestRosterAndDaysheet:
    def test_the_roster_is_who_the_brand_actually_took(self):
        # An applicant isn't on the roster: nobody is expecting them at a venue.
        assert "applied" not in server._ROSTER_STATES
        assert "verified" not in server._ROSTER_STATES
        assert "accepted" in server._ROSTER_STATES

    def test_it_carries_what_the_manager_needs_on_the_day(self):
        import inspect

        src = inspect.getsource(server._roster_rows)
        for field in ("phone", "instagram_handle", "slot_time", "attendance"):
            assert f'"{field}"' in src

    def test_attendance_collapses_nine_states_into_three_answers(self):
        import inspect

        src = inspect.getsource(server._roster_rows)
        for word in ('"expected"', '"attended"', '"no_show"'):
            assert word in src

    def test_the_roster_is_one_pipeline_not_a_query_per_creator(self):
        import inspect

        src = inspect.getsource(server._roster_rows)
        assert src.count("$lookup") == 3
        assert "for r in rows" in src

    def test_the_daysheet_uses_a_real_csv_writer(self):
        # A creator called "Priya, Rao" would silently become two columns
        # under a hand-rolled join.
        import inspect

        src = inspect.getsource(server.campaign_daysheet)
        assert "csv.writer" in src
        assert "text/csv" in src
        assert "attachment; filename=" in src


class TestOnTheDayTransitions:
    def test_check_in_only_from_slot_booked(self):
        import inspect

        src = inspect.getsource(server.check_in_creator)
        assert 'current != "slot_booked"' in src
        assert '{"_id": collab["_id"], "state": "slot_booked"}' in src, (
            "the write needs a precondition"
        )

    def test_check_in_lands_on_attended(self):
        import inspect

        assert '"state": "attended"' in inspect.getsource(server.check_in_creator)

    def test_a_no_show_needs_a_note(self):
        assert server.NoShowPayload.model_fields["note"].is_required()
        with pytest.raises(Exception):
            server.NoShowPayload(note="")

    def test_a_no_show_flags_rather_than_cancels(self):
        # The manager knows who was in the room; whether anything is owed is
        # the admin's call with the money in front of them.
        import inspect

        src = inspect.getsource(server.mark_no_show)
        assert "no_show_reported" in src
        assert '"state": "cancelled"' not in src
        assert "next_step" in src

    def test_the_no_show_flag_feeds_the_admin_path(self):
        import inspect

        src = inspect.getsource(server.mark_no_show)
        assert "creator_no_show" in src, "the note has to point at the cancel type"
        # And the admin's cancel is what suppresses the settlement question.
        cancel = inspect.getsource(server.cancel_collaboration)
        assert 'cancellation_type != "creator_no_show"' in cancel

    def test_reschedule_claims_the_new_seat_before_freeing_the_old(self):
        # The other order would free their place and then discover the target
        # is full, leaving the creator with neither.
        import inspect

        src = inspect.getsource(server.reschedule_creator)
        claim = src.index('"$inc": {"booked_count": 1}')
        release = src.index('"$inc": {"booked_count": -1}, "$set": {"updated_at": now}')
        assert claim < release

    def test_reschedule_uses_the_same_atomic_claim_as_booking(self):
        import inspect

        src = inspect.getsource(server.reschedule_creator)
        assert '"$expr": {"$lt": ["$booked_count", "$capacity"]}' in src

    def test_a_failed_reschedule_gives_the_seat_back(self):
        import inspect

        src = inspect.getsource(server.reschedule_creator)
        assert src.count('"$inc": {"booked_count": -1}') >= 2


class TestSlotEditing:
    def test_capacity_cannot_shrink_below_what_is_booked(self):
        import inspect

        src = inspect.getsource(server.update_slot)
        assert "booked" in src and "409" in src

    def test_moving_a_slot_moves_the_people_on_it(self):
        # Otherwise their collaborations keep pointing at the old hour.
        import inspect

        src = inspect.getsource(server.update_slot)
        assert "collaborations.update_many" in src
        assert '"scheduled_at": starts' in src

    def test_an_edit_is_validated_against_the_campaign_like_a_create(self):
        import inspect

        assert "_validate_slot_times" in inspect.getsource(server.update_slot)
        assert "_validate_slot_times" in inspect.getsource(server.create_campaign_slot)

    def test_an_empty_edit_is_refused(self):
        import inspect

        assert "Nothing to update" in inspect.getsource(server.update_slot)

    def test_both_create_routes_land_on_one_implementation(self):
        import inspect

        assert "await create_campaign_slot(" in inspect.getsource(server.create_slot)


class TestBroadcast:
    def test_it_uses_the_sender_with_the_simulation_fallback(self):
        import inspect

        src = inspect.getsource(server.broadcast_to_campaign)
        assert "notify_over_utility_template" in src

    def test_one_bad_number_does_not_swallow_the_rest(self):
        import inspect

        src = inspect.getsource(server.broadcast_to_campaign)
        assert "for row in audience" in src
        assert '"results"' in src and '"failed"' in src

    def test_it_only_messages_people_still_expected(self):
        import inspect

        src = inspect.getsource(server.broadcast_to_campaign)
        assert 'r["attendance"] == "expected"' in src

    def test_an_empty_audience_is_a_409_not_a_silent_success(self):
        import inspect

        src = inspect.getsource(server.broadcast_to_campaign)
        assert "Nobody is confirmed" in src

    def test_a_message_is_required(self):
        with pytest.raises(Exception):
            server.BroadcastPayload(message="")


class TestManagerNotifications:
    @pytest.mark.parametrize(
        "event", ["manager_slot_booked", "manager_slot_released", "campaign_broadcast"]
    )
    def test_the_events_are_declared(self, event):
        assert event in server.NOTIFY_EVENTS

    def test_booking_tells_the_manager(self):
        import inspect

        assert "notify_campaign_manager" in inspect.getsource(server._claim_slot)

    @pytest.mark.parametrize(
        "fn_name", ["revert_collaboration", "cancel_collaboration"]
    )
    def test_freeing_a_seat_tells_the_manager(self, fn_name):
        import inspect

        assert "_tell_manager_a_seat_freed" in inspect.getsource(getattr(server, fn_name))

    def test_an_unassigned_campaign_is_not_an_error(self):
        # A campaign with no manager has nobody to tell, and that must not
        # fail the booking that triggered it.
        import inspect

        src = inspect.getsource(server.notify_campaign_manager)
        assert "if not manager_id:" in src
        assert "return" in src


# ---------------------------------------------------------------------------
# Dashboard aggregation. Five requests used to fill the console's landing view,
# which meant five spinners and five chances for one slow query to make the
# page look broken.
# ---------------------------------------------------------------------------


class TestApplicantBuckets:
    def test_every_collaboration_state_lands_in_exactly_one_bucket(self):
        seen = []
        for _, states in server._APPLICANT_BUCKETS:
            seen.extend(states)
        every = set(server.COLLAB_STATE_ORDER) | set(server.TERMINAL_COLLAB_STATES)
        assert set(seen) == every, "a state in no bucket disappears from the console"
        assert len(seen) == len(set(seen)), "a state in two buckets is double-counted"

    def test_approved_means_accepted_and_beyond(self):
        approved = set(server._APPLICANT_APPROVED_STATES)
        assert "accepted" in approved
        # A finished collaboration is still a yes.
        assert "closed" in approved
        for not_yet in ("applied", "verified"):
            assert not_yet not in approved

    def test_rejected_covers_both_exits(self):
        rejected = dict(server._APPLICANT_BUCKETS)["rejected"]
        assert set(rejected) == {"declined", "cancelled"}

    def test_completed_is_reported_separately_from_approved(self):
        # "How many finished" is a different question from "how many were
        # taken on", so it is its own accumulator even though it is a subset.
        expr = server._bucket_counts_expr()
        assert set(expr) == {"applied", "approved", "rejected", "completed"}

    def test_the_counters_are_aggregation_accumulators_not_python_loops(self):
        expr = server._bucket_counts_expr()
        for value in expr.values():
            assert "$sum" in value
            assert "$cond" in value["$sum"]


class TestDashboardEndpoint:
    def test_it_is_admin_only(self):
        import inspect

        for fn in (server.admin_dashboard, server.admin_campaign_applicants):
            assert 'require_roles("admin")' in inspect.getsource(fn)

    def test_it_takes_an_optional_campaign_scope(self):
        params = __import__("inspect").signature(server.admin_dashboard).parameters
        assert "campaign_id" in params
        assert params["campaign_id"].default is None

    def test_a_bad_campaign_id_is_a_422_and_a_missing_one_a_404(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert "422" in src and "404" in src

    def test_the_collections_are_read_with_facets_not_loops(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        # One aggregation per collection, each answering several questions.
        assert src.count('"$facet"') >= 3
        assert "find_one({" not in src.replace(
            'if not await db.campaigns.find_one({"_id": scoped_oid}):', ""
        ), "the scope check is the only single-document read"

    def test_there_is_no_per_campaign_query(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        # The per-campaign counts come from one grouped pass, keyed afterwards.
        assert '"$group": {"_id": "$campaign_id"' in src
        assert "per_campaign.get(" in src

    def test_campaign_statuses_are_zero_filled(self):
        # A caller must never have to guard for a missing key.
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert "{s: 0 for s in CampaignStatus.__args__}" in src

    def test_live_is_an_alias_for_open(self):
        # The creator feed calls it live; the console should agree.
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert '"live": campaigns_by_status.get("open", 0)' in src

    def test_every_queue_the_console_shows_is_counted(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        for queue in (
            "creators_to_review",
            "campaigns_to_review",
            "brands_to_verify",
            "collaborations_to_move",
            "payouts_to_record",
        ):
            assert f'"{queue}"' in src

    def test_the_headline_number_is_the_sum_of_the_queues(self):
        # So it can always be explained by pointing at a row.
        import inspect

        assert '"awaiting_total": sum(awaiting.values())' in inspect.getsource(
            server.admin_dashboard
        )

    def test_active_creators_means_working_not_signed_up(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert '"active_creators"' in src
        assert "_APPLICANT_APPROVED_STATES" in src

    def test_active_brands_means_running_something(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert "ACTIVE_CAMPAIGN_STATUSES" in src
        assert '"$group": {"_id": "$brand_id"}' in src

    def test_gmv_is_payouts_plus_our_margin(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert '"gmv": round(total_paid + platform_revenue, 2)' in src

    def test_refunded_money_is_not_counted_as_paid(self):
        # The facet matches "paid" exactly, so a clawed-back payout drops out.
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert '{"$match": {"state": "paid"}}' in src

    def test_scoping_narrows_the_money_through_the_collaborations(self):
        # Payments hang off collaborations, not campaigns, so a campaign scope
        # has to name that campaign's collaborations first.
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert '"collaboration_id": {"$in":' in src

    def test_platform_wide_queues_read_zero_when_scoped(self):
        # Creator and brand vetting are not about any one campaign; reporting
        # the global number next to one campaign's stats would be a lie.
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert "if scoped_oid:" in src
        assert "creators_to_review = 0" in src

    def test_the_summary_list_is_bounded_and_says_so(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        assert '"$limit": limit' in src
        assert '"summary_truncated"' in src

    def test_the_summary_carries_whichever_dates_the_type_has(self):
        import inspect

        src = inspect.getsource(server.admin_dashboard)
        for field in ("event_date", "start_date", "end_date", "campaign_type"):
            assert f'"{field}"' in src


class TestAdminApplicantsEndpoint:
    def test_it_is_one_pipeline_with_the_joins(self):
        import inspect

        src = inspect.getsource(server.admin_campaign_applicants)
        assert src.count("$lookup") == 3
        assert src.count("db.collaborations.aggregate") == 1

    def test_it_groups_into_the_three_buckets(self):
        import inspect

        src = inspect.getsource(server.admin_campaign_applicants)
        assert "_APPLICANT_BUCKETS" in src
        assert "break" in src, "a collaboration lands in the first matching bucket only"

    def test_each_entry_carries_what_the_console_renders(self):
        import inspect

        src = inspect.getsource(server.admin_campaign_applicants)
        for field in (
            "profile_image_url",
            "instagram_handle",
            "follower_count",
            "quoted_rate",
            "agreed_amount",
            "state",
        ):
            assert f'"{field}"' in src

    def test_it_reaches_any_campaign_not_just_one_brands(self):
        # The brand's own board stops at its own campaigns; this is the admin's
        # read of anything, including campaigns that ended.
        import inspect

        src = inspect.getsource(server.admin_campaign_applicants)
        assert "_admin_campaign_or_404" in src
        assert "_own_campaign_or_404" not in src

    def test_the_counts_match_the_lists(self):
        import inspect

        src = inspect.getsource(server.admin_campaign_applicants)
        assert '"counts": {name: len(rows_) for name, rows_ in groups.items()}' in src


# ---------------------------------------------------------------------------
# The creator's own side: their profile, their slots, their dashboard. Slots
# and the manager tooling shipped before the creator could see either, so a
# creator sat at commercial_agreed with no way forward — these guard the route
# out of it.
# ---------------------------------------------------------------------------


class TestCreatorProfileFields:
    def test_genres_and_niches_are_separate_questions(self):
        # A brand filters the directory on niches and briefs against genres.
        # Collapsing them into one list breaks whichever of the two it isn't.
        fields = server.CreatorProfileUpdate.model_fields
        assert "niches" in fields and "genres" in fields

    def test_the_neighbourhood_and_the_postal_address_are_separate(self):
        fields = server.CreatorProfileUpdate.model_fields
        assert "address" in fields and "full_address" in fields

    def test_nothing_is_required_to_save(self):
        # The builder is filled in over several sittings, so a save that
        # demanded the whole thing would mean nobody ever saved.
        for name, field in server.CreatorProfileUpdate.model_fields.items():
            assert not field.is_required(), f"{name} blocks a partial save"

    def test_platforms_is_a_closed_list(self):
        assert set(server.CreatorPlatform.__args__) == {"instagram", "youtube"}

    def test_a_platform_we_do_not_run_on_is_refused(self):
        with pytest.raises(Exception):
            server.CreatorProfileUpdate(
                name="A",
                instagram_handle="a",
                instagram_profile_url="https://instagram.com/a",
                email="a@b.com",
                address="Indiranagar",
                platforms=["tiktok"],
            )

    def test_the_profile_response_carries_the_new_fields(self):
        import inspect

        src = inspect.getsource(server._serialize_creator_profile)
        for field in ("genres", "platforms", "full_address"):
            assert f'"{field}"' in src

    def test_the_dashboard_shows_a_creator_their_own_email(self):
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        assert '"email"' in src

    def test_platforms_are_deduped_on_write(self):
        import inspect

        assert "dict.fromkeys(payload.platforms)" in inspect.getsource(
            server.update_creator_profile
        )

    def test_genres_are_stored_lowercase_like_niches(self):
        # Matching is done on these, and "Food" never matching "food" would
        # quietly empty every suggestion list.
        import inspect

        src = inspect.getsource(server.update_creator_profile)
        assert "g.strip().lower() for g in payload.genres" in src


class TestProfileCompleteness:
    def test_an_empty_profile_is_zero_and_lists_everything(self):
        result = server._profile_completeness({})
        assert result["percent"] == 0
        assert len(result["missing"]) == result["total"]
        assert result["complete"] is False

    def test_a_full_profile_is_a_hundred_with_nothing_missing(self):
        profile = {field: "x" for field, _ in server._PROFILE_COMPLETENESS_FIELDS}
        result = server._profile_completeness(profile)
        assert result["percent"] == 100
        assert result["missing"] == []
        assert result["complete"] is True

    def test_an_empty_list_counts_as_missing(self):
        # `niches: []` is not an answer, and treating it as one would tell a
        # creator they were done while brands couldn't find them.
        result = server._profile_completeness({"niches": [], "genres": []})
        missing = {row["field"] for row in result["missing"]}
        assert {"niches", "genres"} <= missing

    def test_every_missing_entry_names_a_field_and_a_label(self):
        for row in server._profile_completeness({})["missing"]:
            assert row["field"] and row["label"]

    def test_the_payout_fields_are_not_counted(self):
        # Bank details are needed before we can pay somebody, not before we can
        # look at them. Counting them here would make a PAN the price of being
        # reviewed at all, since submitting for review requires 100%.
        fields = {field for field, _ in server._PROFILE_COMPLETENESS_FIELDS}
        assert not ({"payout_upi", "pan", "gstin"} & fields)

    def test_the_new_profile_fields_are_counted(self):
        fields = {field for field, _ in server._PROFILE_COMPLETENESS_FIELDS}
        assert {"genres", "platforms", "full_address"} <= fields


class TestCreatorNextAction:
    def test_an_agreed_fee_puts_the_ball_with_the_creator(self):
        action = server._creator_next_action(
            {"state": "commercial_agreed"}, {"campaign_type": "launch"}, True
        )
        assert action["action"] == "book_slot"
        assert action["waiting_on"] == "you"

    def test_a_personal_table_asks_for_a_time_not_a_slot(self):
        action = server._creator_next_action(
            {"state": "commercial_agreed"}, {"campaign_type": "personal_table"}, True
        )
        assert "window" in action["label"]

    @pytest.mark.parametrize(
        "state,expected",
        [
            ("slot_booked", "attend"),
            ("attended", "submit_content"),
            ("content_submitted", "resubmit_content"),
        ],
    )
    def test_each_step_names_what_the_creator_does(self, state, expected):
        assert server._creator_next_action({"state": state}, {}, True)["action"] == expected

    def test_waiting_on_us_is_said_plainly(self):
        action = server._creator_next_action({"state": "accepted"}, {}, True)
        assert action["action"] is None
        assert action["waiting_on"] == "weare"

    def test_missing_payout_details_outrank_the_reassuring_message(self):
        # This is the one place a creator blocks their own money without being
        # told, so it has to win over "payment is being processed".
        action = server._creator_next_action({"state": "in_payment"}, {}, False)
        assert action["action"] == "add_payout_details"
        assert action["waiting_on"] == "you"

    def test_with_payout_details_there_is_nothing_to_do(self):
        action = server._creator_next_action({"state": "content_approved"}, {}, True)
        assert action["action"] is None

    def test_every_active_state_gets_an_answer(self):
        for state in server._CREATOR_ACTIVE_STATES:
            action = server._creator_next_action({"state": state}, {}, True)
            assert action["label"], f"{state} leaves the creator with no next step"


class TestCreatorSlotBooking:
    def test_the_creator_route_reuses_the_shared_claim(self):
        # A second copy of an atomic claim is a second chance to get it wrong.
        import inspect

        assert "_claim_slot" in inspect.getsource(server.creator_book_slot)
        assert "find_one_and_update" not in inspect.getsource(server.creator_book_slot)

    def test_booking_opens_only_once_the_fee_is_agreed(self):
        import inspect

        src = inspect.getsource(server.creator_book_slot)
        assert '"commercial_agreed"' in src
        assert "409" in src

    def test_another_campaigns_slot_is_not_a_slot(self):
        import inspect

        src = inspect.getsource(server.creator_book_slot)
        assert 'slot["campaign_id"] != collab["campaign_id"]' in src

    def test_a_personal_table_requires_a_time_inside_the_window(self):
        import inspect

        src = inspect.getsource(server.creator_book_slot)
        assert '"personal_table"' in src
        assert "preferred < starts" in src and "preferred > ends" in src

    def test_a_fixed_time_campaign_refuses_a_chosen_time(self):
        # Everyone arrives together on a launch; one creator writing their own
        # time would put them at the venue alone.
        import inspect

        src = inspect.getsource(server.creator_book_slot)
        assert "elif payload.preferred_time is not None:" in src

    def test_somebody_elses_collaboration_is_a_404(self):
        import inspect

        src = inspect.getsource(server._own_collab_or_404)
        assert '"creator_id": ObjectId(user["_id"])' in src
        # Only the raises, not the docstring — which explains why it is not a 403.
        codes = [ln for ln in src.splitlines() if "status_code=" in ln]
        assert codes and all("404" in ln for ln in codes)

    def test_the_slot_list_is_gated_on_being_on_the_campaign(self):
        import inspect

        src = inspect.getsource(server.list_creator_slots)
        assert "_ONBOARD_COLLAB_STATES" in src
        assert 'detail="Campaign not found"' in src

    def test_the_slot_list_says_which_one_is_theirs(self):
        import inspect

        src = inspect.getsource(server.list_creator_slots)
        assert '"is_mine"' in src
        assert '"booked_slot_id"' in src

    def test_an_invitation_is_surfaced_but_not_required(self):
        # A creator who applied off the open list is just as much on the
        # campaign as one who was invited.
        import inspect

        src = inspect.getsource(server.list_creator_slots)
        assert "campaign_invitations" in src
        assert '"invited"' in src

    def test_a_full_slot_is_marked_rather_than_hidden(self):
        import inspect

        assert '"is_full"' in inspect.getsource(server.list_creator_slots)


class TestCreatorSlotCancellation:
    def test_there_is_a_cutoff(self):
        assert server.SLOT_CANCEL_CUTOFF_HOURS > 0

    def test_inside_the_cutoff_is_a_409(self):
        import inspect

        src = inspect.getsource(server.creator_cancel_slot)
        assert "SLOT_CANCEL_CUTOFF_HOURS" in src
        assert "409" in src

    def test_cancelling_returns_them_to_commercial_agreed(self):
        # They are still on the campaign and still owed a place — just not
        # that one. Leaving the campaign is a different decision.
        import inspect

        src = inspect.getsource(server.creator_cancel_slot)
        assert '"state": "commercial_agreed"' in src

    def test_the_booking_is_cleared_not_left_dangling(self):
        import inspect

        src = inspect.getsource(server.creator_cancel_slot)
        assert '"$unset": {"slot_id": "", "scheduled_at": "", "preferred_time": ""}' in src

    def test_the_collaboration_moves_before_the_seat_is_released(self):
        # The other order would put the place on sale while the creator still
        # held it.
        import inspect

        src = inspect.getsource(server.creator_cancel_slot)
        assert src.index("db.collaborations.find_one_and_update") < src.index(
            "db.campaign_slots.update_one"
        )

    def test_the_release_is_written_with_a_precondition(self):
        import inspect

        src = inspect.getsource(server.creator_cancel_slot)
        assert '"state": "slot_booked", "slot_id": slot_oid' in src
        assert '{"$gt": 0}' in src

    def test_the_manager_is_told(self):
        import inspect

        assert "_tell_manager_a_seat_freed" in inspect.getsource(server.creator_cancel_slot)

    def test_it_is_audited(self):
        import inspect

        src = inspect.getsource(server.creator_cancel_slot)
        assert '"collaboration.cancel_slot"' in src


class TestCreatorDashboardEarnings:
    def test_refunded_and_cancelled_money_is_counted_nowhere(self):
        # "cancelled" is a payout that never happens; "refunded" is one clawed
        # back. Either one in a total has the creator waiting on nothing.
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        assert 'p.get("state") == "paid"' in src
        assert 'p.get("state") == "pending"' in src

    def test_both_figures_are_net_of_the_platform_fee(self):
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        assert "creator_payout" in src
        assert "compute_fee(float(agreed))" in src

    def test_an_agreed_fee_with_no_payment_row_yet_still_counts_as_pending(self):
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        assert "if c[\"_id\"] in payment_by_collab" in src

    def test_an_ended_collaboration_is_not_pending_money(self):
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        assert 'c.get("state") in COLLAB_GROUP_ENDED' in src

    def test_campaigns_completed_means_closed(self):
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        assert "COLLAB_GROUP_COMPLETED" in src


class TestCreatorDashboardGrouping:
    def test_every_state_lands_in_exactly_one_group(self):
        # Nothing may drop out of a creator's own record.
        groups = (
            set(server._CREATOR_ACTIVE_STATES)
            | set(server.COLLAB_GROUP_COMPLETED)
            | set(server.COLLAB_GROUP_ENDED)
            | set(server.COLLAB_GROUP_APPLIED)
        )
        assert groups == set(server.COLLAB_STATE_ORDER) | set(server.COLLAB_GROUP_ENDED)

    def test_waiting_to_be_paid_is_active_not_completed(self):
        assert "in_payment" in server._CREATOR_ACTIVE_STATES
        assert "in_payment" not in server.COLLAB_GROUP_COMPLETED

    def test_an_active_row_carries_the_venue_and_the_manager(self):
        # This is the view a creator opens on the way to a venue, so it cannot
        # need a second request to be useful.
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        for field in ("manager_name", "manager_phone", "venue_address", "venue_instructions"):
            assert f'"{field}"' in src

    def test_an_active_row_carries_the_booked_time_and_the_next_step(self):
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        assert '"slot_starts_at"' in src
        assert "_creator_next_action" in src


class TestSuggestedCampaigns:
    def test_only_live_campaigns_are_suggested(self):
        import inspect

        src = inspect.getsource(server._suggested_campaigns)
        assert "LIVE_CAMPAIGN_STATUSES" in src

    def test_campaigns_already_applied_to_are_excluded(self):
        import inspect

        src = inspect.getsource(server._suggested_campaigns)
        assert '"_id": {"$nin": list(exclude_ids)}' in src

    def test_the_exclusion_covers_every_collaboration_not_just_open_ones(self):
        import inspect

        src = inspect.getsource(server.get_creator_dashboard)
        assert '{c["campaign_id"] for c in collabs}' in src

    def test_a_blank_profile_gets_no_suggestions_rather_than_random_ones(self):
        import inspect

        src = inspect.getsource(server._suggested_campaigns)
        assert "if not (niches or genres or places):" in src

    def test_every_suggestion_says_why(self):
        import inspect

        src = inspect.getsource(server._suggested_campaigns)
        assert '"match_reason"' in src
        assert "reasons.append" in src

    def test_a_campaign_matching_nothing_is_not_suggested(self):
        import inspect

        src = inspect.getsource(server._suggested_campaigns)
        assert "if reasons:" in src

    def test_niches_genres_and_place_are_all_matched(self):
        import inspect

        src = inspect.getsource(server._suggested_campaigns)
        assert "in niches" in src and "in genres" in src and "in places" in src

    def test_the_list_is_bounded(self):
        import inspect

        src = inspect.getsource(server._suggested_campaigns)
        assert "scored[:limit]" in src


# ---------------------------------------------------------------------------
# Onboarding. Signup used to ask for a profile's worth of detail before anyone
# had seen the product, and the vetting queue filled with stubs nobody could
# decide on. Signup is now a name and a number; the profile is built after, at
# whatever pace, and an explicit submission is what asks us to look.
# ---------------------------------------------------------------------------


class TestSignupAsksForAlmostNothing:
    def test_the_signup_payloads_carry_only_identity(self):
        # role picks which product you get and accept_terms is consent we have
        # to be able to evidence. Anything else belongs in the profile builder.
        allowed = {"phone", "purpose", "name", "role", "accept_terms", "code"}
        for model in (server.OtpRequestInput, server.OtpVerifyInput):
            assert set(model.model_fields) <= allowed, sorted(set(model.model_fields) - allowed)

    def test_signup_needs_a_name_and_a_role_and_nothing_more(self):
        import inspect

        src = inspect.getsource(server.request_otp)
        assert "Name and role are required to sign up." in src

    def test_the_profile_stub_starts_empty(self):
        # A half-guessed stub would show up as progress the creator never made.
        import inspect

        src = inspect.getsource(server.verify_otp)
        start = src.index("db.creator_profiles.insert_one")
        block = src[start : start + 1200]
        for field in ("instagram_handle", "email", "city", "genres", "platforms"):
            assert f'"{field}"' in block
        assert '"verification_status": "pending"' in block


class TestProfileSavesPartially:
    def test_every_field_is_optional(self):
        for name, field in server.CreatorProfileUpdate.model_fields.items():
            assert not field.is_required(), f"{name} blocks a partial save"

    def test_only_the_keys_that_were_sent_are_written(self):
        # An omitted key means "leave it alone"; an explicit null means "clear
        # it". A builder saving one step at a time depends on the difference.
        import inspect

        src = inspect.getsource(server.update_creator_profile)
        assert "payload.model_fields_set" in src
        assert src.count('in sent:') >= 10

    def test_payout_fields_respect_a_partial_save_too(self):
        import inspect

        src = inspect.getsource(server._clean_payout_fields)
        assert "only" in src and "wanted(" in src

    def test_saving_no_longer_puts_anybody_in_the_queue(self):
        # This is the whole point: saving and submitting are separate acts.
        import inspect

        src = inspect.getsource(server.update_creator_profile)
        assert 'update["pending_review"] = bool(existing.get("submitted_for_review_at"))' in src

    def test_a_verified_creator_still_stays_live_while_edits_are_reviewed(self):
        import inspect

        src = inspect.getsource(server.update_creator_profile)
        assert "material_fields" in src
        assert '"name", "instagram_handle", "city"' in src


class TestYoutubeLink:
    @pytest.mark.parametrize(
        "raw",
        [
            "https://youtube.com/@someone",
            "https://www.youtube.com/channel/UCabc123",
            "youtube.com/c/SomeChannel",
            "https://youtu.be/abc123",
        ],
    )
    def test_a_real_channel_link_is_kept(self, raw):
        assert server._clean_youtube_url(raw)

    def test_a_bare_link_gets_a_scheme(self):
        assert server._clean_youtube_url("youtube.com/@someone").startswith("https://")

    @pytest.mark.parametrize("raw", ["https://vimeo.com/someone", "not a url", "https://youtube.evil.com/@x"])
    def test_anything_else_is_refused(self, raw):
        # A brand clicks this to decide whether to book somebody; a link that
        # goes nowhere costs the creator the booking and they never find out.
        with pytest.raises(HTTPException) as exc:
            server._clean_youtube_url(raw)
        assert exc.value.status_code == 422

    def test_blank_clears_it(self):
        assert server._clean_youtube_url("") is None
        assert server._clean_youtube_url(None) is None


class TestCompletenessFollowsThePlatforms:
    def _full(self, platforms):
        profile = {field: "x" for field, _ in server._PROFILE_COMPLETENESS_FIELDS}
        profile["platforms"] = platforms
        for p in platforms:
            for field, _ in server._PLATFORM_COMPLETENESS_FIELDS[p]:
                profile[field] = "x"
        return profile

    def test_an_instagram_creator_is_never_asked_for_a_youtube_link(self):
        # Otherwise they could never reach 100%, and so could never submit for
        # review at all.
        result = server._profile_completeness(self._full(["instagram"]))
        assert result["complete"] is True
        assert result["percent"] == 100

    def test_a_youtube_creator_is_asked_for_the_channel(self):
        profile = self._full(["youtube"])
        profile.pop("youtube_url")
        missing = {r["field"] for r in server._profile_completeness(profile)["missing"]}
        assert "youtube_url" in missing

    def test_someone_on_both_is_asked_for_both(self):
        fields = {f for f, _ in server._completeness_fields_for({"platforms": ["instagram", "youtube"]})}
        assert {"instagram_handle", "instagram_profile_url", "youtube_url"} <= fields

    def test_naming_no_platform_can_never_be_complete(self):
        # platforms is itself a required field, so an empty list is missing one.
        result = server._profile_completeness({})
        assert result["complete"] is False
        assert "platforms" in {r["field"] for r in result["missing"]}

    def test_the_percentage_is_out_of_what_this_creator_was_asked(self):
        profile = self._full(["instagram"])
        profile.pop("city")
        result = server._profile_completeness(profile)
        assert result["total"] == len(server._PROFILE_COMPLETENESS_FIELDS) + 2
        assert result["filled"] == result["total"] - 1


class TestTheBuilderIsToldWhereItStands:
    def test_the_profile_read_carries_completeness(self):
        # So the builder's submit button and the server's gate can never
        # disagree about what "done" means.
        import inspect

        assert "_profile_completeness" in inspect.getsource(server.get_creator_profile)


class TestSubmitForReview:
    def test_it_is_the_only_creator_path_that_stamps_the_submission(self):
        # Writes only — a query filtering on the field is not a write. If a
        # second path could stamp it, a half-built profile could reach the
        # vetting queue again, which is the thing this restructure removes.
        import inspect

        src = server.ROOT_DIR.joinpath("server.py").read_text()
        writers = [
            line.strip()
            for line in src.splitlines()
            if '"submitted_for_review_at": now' in line
        ]
        # This endpoint, and the campaign-review equivalent on brands.
        assert len(writers) == 2, writers
        assert '"submitted_for_review_at": now' in inspect.getsource(
            server.submit_profile_for_review
        )

    def test_it_refuses_an_unfinished_profile(self):
        import inspect

        src = inspect.getsource(server.submit_profile_for_review)
        assert 'completeness["complete"]' in src
        assert "409" in src

    def test_the_refusal_names_what_is_missing(self):
        import inspect

        src = inspect.getsource(server.submit_profile_for_review)
        assert 'row["label"] for row in completeness["missing"]' in src

    def test_an_already_verified_creator_is_refused(self):
        import inspect

        src = inspect.getsource(server.submit_profile_for_review)
        assert 'status == "verified"' in src

    def test_a_resubmission_clears_the_old_rejection_reason(self):
        import inspect

        src = inspect.getsource(server.submit_profile_for_review)
        assert '"verification_reason": None' in src

    def test_it_is_audited_and_confirmed_to_the_creator(self):
        import inspect

        src = inspect.getsource(server.submit_profile_for_review)
        assert '"creator.submit_for_review"' in src
        assert "notify(" in src


class TestVettingQueueShowsOnlySubmittedProfiles:
    def test_the_queue_reads_the_shared_query(self):
        import inspect

        assert "_AWAITING_REVIEW_QUERY" in inspect.getsource(server.list_pending_creators)

    def test_the_query_is_submission_not_a_guess_at_one(self):
        assert server._AWAITING_REVIEW_QUERY["verification_status"] == "pending"
        assert "submitted_for_review_at" in server._AWAITING_REVIEW_QUERY
        assert "instagram_handle" not in server._AWAITING_REVIEW_QUERY

    def test_the_badge_counts_the_same_rows_the_queue_shows(self):
        import inspect

        for fn in (server.admin_metrics, server.admin_dashboard):
            assert "_AWAITING_REVIEW_QUERY" in inspect.getsource(fn)

    def test_the_longest_wait_is_first(self):
        import inspect

        assert '.sort("submitted_for_review_at", 1)' in inspect.getsource(
            server.list_pending_creators
        )


class TestApplyingIsGatedServerSide:
    def test_the_endpoint_checks_verification_itself(self):
        import inspect

        src = inspect.getsource(server.apply_to_campaign)
        assert 'verification_status") != "verified"' in src
        assert "403" in src

    def test_browsing_is_not_gated(self):
        # A creator deciding whether this is worth finishing a profile for has
        # to be able to see what is on offer.
        import inspect

        src = inspect.getsource(server.list_campaigns)
        assert "verification_status" not in src

    def test_someone_still_building_is_told_what_is_left(self):
        message = server._why_you_cannot_apply({"platforms": ["instagram"]})
        assert "Finish your profile" in message
        assert "Instagram handle" in message

    def test_someone_waiting_on_us_is_told_that_instead(self):
        message = server._why_you_cannot_apply(
            {"verification_status": "pending", "submitted_for_review_at": "2026-08-01T00:00:00Z"}
        )
        assert "with the WeAre team" in message
        assert "Finish your profile" not in message

    def test_a_rejected_creator_gets_the_reason_back(self):
        message = server._why_you_cannot_apply(
            {"verification_status": "rejected", "verification_reason": "Handle didn't match."}
        )
        assert "Handle didn't match." in message
        assert "submit it again" in message

    def test_a_rejection_with_no_reason_still_says_what_to_do(self):
        message = server._why_you_cannot_apply({"verification_status": "rejected"})
        assert "submit it again" in message


class TestProfileNudge:
    def test_it_waits_three_days_by_default(self, monkeypatch):
        monkeypatch.delenv("PROFILE_NUDGE_AFTER_DAYS", raising=False)
        assert server._nudge_after_days() == 3

    def test_the_wait_is_configurable_and_never_zero(self, monkeypatch):
        monkeypatch.setenv("PROFILE_NUDGE_AFTER_DAYS", "7")
        assert server._nudge_after_days() == 7
        monkeypatch.setenv("PROFILE_NUDGE_AFTER_DAYS", "0")
        assert server._nudge_after_days() == 1

    def test_nonsense_falls_back_rather_than_crashing_startup(self, monkeypatch):
        monkeypatch.setenv("PROFILE_NUDGE_AFTER_DAYS", "soon")
        assert server._nudge_after_days() == 3

    def test_the_loop_can_be_turned_off(self, monkeypatch):
        # So a deployment with its own scheduler can drive the endpoint instead
        # without two things chasing the same people.
        monkeypatch.setenv("PROFILE_NUDGE_INTERVAL_SECONDS", "0")
        assert server._nudge_interval_seconds() == 0

    def test_the_send_is_claimed_before_it_is_made(self):
        # The stamp is the claim, under a filter that only matches while it is
        # absent — so a race produces one message and a failed send still counts
        # as used up. Chasing twice is how you get muted.
        import inspect

        src = inspect.getsource(server.nudge_stale_creator_profiles)
        assert '"onboarding_nudge_sent_at": {"$exists": False}' in src
        assert "find_one_and_update" in src
        claim = src.index("find_one_and_update")
        assert src.index("_send_aisensy_utility") > claim

    def test_it_only_chases_people_who_actually_stalled(self):
        import inspect

        src = inspect.getsource(server.nudge_stale_creator_profiles)
        assert '"created_at": {"$lte": cutoff}' in src
        assert '"verification_status": "pending"' in src
        assert '"submitted_for_review_at": {"$in": [None, False]}' in src

    def test_a_finished_but_unsubmitted_profile_is_left_alone(self):
        import inspect

        src = inspect.getsource(server.nudge_stale_creator_profiles)
        assert 'completeness["complete"]' in src
        assert "continue" in src

    def test_it_reuses_the_utility_helper_and_its_simulation_fallback(self):
        import inspect

        src = inspect.getsource(server.nudge_stale_creator_profiles)
        assert "_send_aisensy_utility" in src
        assert 'mode == "simulation"' in src

    def test_one_bad_send_does_not_take_the_batch(self):
        import inspect

        src = inspect.getsource(server.nudge_stale_creator_profiles)
        assert "except HTTPException" in src and "except Exception" in src

    def test_a_failed_pass_never_kills_the_loop(self):
        import inspect

        src = inspect.getsource(server._nudge_loop)
        assert "except asyncio.CancelledError" in src
        assert "raise" in src
        assert "except Exception" in src

    def test_the_message_names_what_is_missing(self):
        import inspect

        src = inspect.getsource(server.nudge_stale_creator_profiles)
        assert 'completeness["missing"][:3]' in src

    def test_it_lands_in_the_creators_notifications_too(self):
        # WhatsApp can fail; the in-app record is what survives it.
        import inspect

        src = inspect.getsource(server.nudge_stale_creator_profiles)
        assert "record_notification" in src
        assert '"profile_nudge"' in src

    def test_the_event_is_declared(self):
        assert "profile_nudge" in server.NOTIFY_EVENTS
        assert "profile_submitted" in server.NOTIFY_EVENTS

    def test_a_manual_run_goes_through_the_same_function(self):
        import inspect

        src = inspect.getsource(server.run_creator_nudges)
        assert "nudge_stale_creator_profiles()" in src
        assert "audit(" in src
