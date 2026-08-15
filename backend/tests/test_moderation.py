"""Backend tests for the moderation gates.

Two things used to reach the public with nobody's approval: a brand that signed
itself up, and a campaign whose payload said "open". These tests are about the
gates, so most of them are about what *cannot* happen.
"""
import os
import uuid

import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


def _register(session, role):
    email = f"test_{role}-{uuid.uuid4().hex[:10]}@example.com"
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role,
    })
    assert r.status_code == 200, r.text
    return email, r.json()


@pytest.fixture
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def anon():
    return requests.Session()


@pytest.fixture
def brand():
    """A brand with a profile and no verification — the default state."""
    s = requests.Session()
    email, _ = _register(s, "brand")
    r = s.put(f"{BASE_URL}/brand/profile", json={
        "business_name": f"Mod-{uuid.uuid4().hex[:6]}",
        "category": "fnb", "areas": ["Indiranagar"],
    })
    assert r.status_code == 200, r.text
    return s, email, pipeline.user_id_of(s)


@pytest.fixture
def creator():
    s = requests.Session()
    email, user = _register(s, "creator")
    return s, user.get("id"), email


CAMPAIGN_BODY = {
    "brief": "b", "deliverables": "d", "budget_per_creator": 5000,
    "category": "fnb", "area": "Indiranagar", "creators_needed": 2,
}


def _draft(bs, **overrides):
    body = {
        "title": f"Mod-{uuid.uuid4().hex[:6]}", **CAMPAIGN_BODY,
        "status": "draft", **overrides,
    }
    r = bs.post(f"{BASE_URL}/brand/campaigns", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 1. Brand verification ----------

class TestBrandVerificationQueue:
    def test_admin_only(self, anon, brand, creator):
        bs, _, _ = brand
        cs, _, _ = creator
        assert anon.get(f"{BASE_URL}/admin/brands/pending").status_code == 401
        assert bs.get(f"{BASE_URL}/admin/brands/pending").status_code == 403
        assert cs.get(f"{BASE_URL}/admin/brands/pending").status_code == 403

    def test_a_new_brand_lands_in_the_queue_with_its_signup_details(self, admin, brand):
        _, email, uid = brand
        rows = admin.get(f"{BASE_URL}/admin/brands/pending").json()
        row = next((x for x in rows if x["user_id"] == uid), None)
        assert row, "a brand that just signed up must be waiting on us"
        assert row["verification_state"] == "pending"
        assert row["email"] == email
        for field in ("business_name", "category", "areas", "signed_up_at", "campaign_count"):
            assert field in row

    def test_verifying_takes_them_out_of_the_queue(self, admin, brand):
        _, _, uid = brand
        pipeline.verify_brand(admin, uid)
        rows = admin.get(f"{BASE_URL}/admin/brands/pending").json()
        assert not any(x["user_id"] == uid for x in rows)

    def test_a_rejected_brand_stays_visible_and_says_why(self, admin, brand):
        _, _, uid = brand
        r = admin.post(f"{BASE_URL}/admin/brands/{uid}/reject",
                       json={"reason": "Could not confirm the business address"})
        assert r.status_code == 200, r.text

        rows = admin.get(f"{BASE_URL}/admin/brands/pending").json()
        row = next(x for x in rows if x["user_id"] == uid)
        assert row["verification_state"] == "rejected"
        assert "address" in row["verification_reason"]

    def test_the_brand_can_see_why_it_was_refused(self, admin, brand):
        bs, _, uid = brand
        admin.post(f"{BASE_URL}/admin/brands/{uid}/reject",
                   json={"reason": "Send us your GST certificate"})
        profile = bs.get(f"{BASE_URL}/brand/profile").json()
        assert profile["verified"] is False
        assert "GST" in profile["verification_reason"]

    def test_a_rejection_needs_a_reason(self, admin, brand):
        _, _, uid = brand
        assert admin.post(f"{BASE_URL}/admin/brands/{uid}/reject", json={}).status_code == 422
        assert admin.post(f"{BASE_URL}/admin/brands/{uid}/reject",
                          json={"reason": "   "}).status_code == 422

    def test_approving_after_a_rejection_clears_the_reason(self, admin, brand):
        bs, _, uid = brand
        admin.post(f"{BASE_URL}/admin/brands/{uid}/reject", json={"reason": "Missing details"})
        pipeline.verify_brand(admin, uid)
        profile = bs.get(f"{BASE_URL}/brand/profile").json()
        assert profile["verified"] is True
        assert not profile["verification_reason"], "an approved brand is not still refused"

    def test_reject_unknown_brand_is_404(self, admin):
        r = admin.post(f"{BASE_URL}/admin/brands/507f1f77bcf86cd799439011/reject",
                       json={"reason": "nope"})
        assert r.status_code == 404
        assert admin.post(f"{BASE_URL}/admin/brands/not-an-id/reject",
                          json={"reason": "nope"}).status_code == 404

    def test_the_brand_is_told_on_whatsapp(self, admin, brand):
        _, _, uid = brand
        out = admin.post(f"{BASE_URL}/admin/brands/{uid}/reject",
                         json={"reason": "Please add your address"}).json()
        # Whether it lands depends on the environment; that it was attempted and
        # reported does not.
        assert "notification" in out
        assert set(out["notification"]) >= {"delivered", "mode", "error"}


# ---------- 2. An unverified brand cannot publish ----------

class TestUnverifiedBrandCannotPublish:
    def test_it_may_still_draft(self, brand):
        bs, _, _ = brand
        assert _draft(bs)["status"] == "draft"

    def test_it_cannot_submit_a_campaign_for_review(self, brand):
        bs, _, _ = brand
        r = bs.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "Too soon", **CAMPAIGN_BODY, "status": "pending_review",
        })
        assert r.status_code == 403, r.text
        assert "verif" in r.text.lower()

    def test_it_cannot_push_an_existing_draft_through(self, brand):
        bs, _, _ = brand
        draft = _draft(bs)
        r = bs.post(f"{BASE_URL}/brand/campaigns/{draft['id']}/publish")
        assert r.status_code == 403, r.text

    def test_verifying_unblocks_it(self, admin, brand):
        bs, _, uid = brand
        draft = _draft(bs)
        assert bs.post(f"{BASE_URL}/brand/campaigns/{draft['id']}/publish").status_code == 403
        pipeline.verify_brand(admin, uid)
        r = bs.post(f"{BASE_URL}/brand/campaigns/{draft['id']}/publish")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending_review"

    def test_rejecting_a_brand_pulls_its_briefs_out_of_the_queue(self, admin, brand):
        bs, _, uid = brand
        pipeline.verify_brand(admin, uid)
        draft = _draft(bs)
        pipeline.submit_campaign(bs, draft["id"])

        out = admin.post(f"{BASE_URL}/admin/brands/{uid}/reject",
                         json={"reason": "Business could not be confirmed"}).json()
        assert out["campaigns_returned_to_draft"] >= 1

        queue = {c["id"] for c in admin.get(f"{BASE_URL}/admin/campaigns/pending").json()}
        assert draft["id"] not in queue, "a refused brand's brief must leave the queue"


# ---------- 3. Campaign moderation ----------

class TestCampaignReview:
    def _submitted(self, bs, admin, uid, **overrides):
        pipeline.verify_brand(admin, uid)
        draft = _draft(bs, **overrides)
        pipeline.submit_campaign(bs, draft["id"])
        return draft

    def test_admin_only(self, anon, brand, creator, admin):
        bs, _, uid = brand
        cs, _, _ = creator
        draft = self._submitted(bs, admin, uid)
        path = f"{BASE_URL}/admin/campaigns/{draft['id']}/approve"
        assert anon.post(path).status_code == 401
        assert cs.post(path).status_code == 403
        # Not even the brand that owns it.
        assert bs.post(path).status_code == 403
        assert anon.get(f"{BASE_URL}/admin/campaigns/pending").status_code == 401

    def test_a_submitted_campaign_is_invisible_to_creators(self, brand, creator, admin):
        bs, _, uid = brand
        cs, cuid, _ = creator
        draft = self._submitted(bs, admin, uid)

        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)

        feed = {c["id"] for c in cs.get(f"{BASE_URL}/campaigns").json()}
        assert draft["id"] not in feed, "a brief nobody has read must not reach creators"
        assert cs.get(f"{BASE_URL}/campaigns/{draft['id']}").status_code == 404

    def test_a_submitted_campaign_cannot_be_applied_to(self, brand, creator, admin):
        bs, _, uid = brand
        cs, cuid, _ = creator
        draft = self._submitted(bs, admin, uid)
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)

        r = cs.post(f"{BASE_URL}/campaigns/{draft['id']}/apply",
                    json={"pitch": "keen on this one please", "quoted_rate": 5000})
        assert r.status_code == 404

    def test_it_shows_up_in_the_review_queue(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)
        rows = admin.get(f"{BASE_URL}/admin/campaigns/pending").json()
        row = next((c for c in rows if c["id"] == draft["id"]), None)
        assert row, "a submitted brief has to appear on somebody's desk"
        assert row["brand_verified"] is True
        assert row["submitted_for_review_at"]
        for field in ("brief", "deliverables", "budget_per_creator", "brand_name"):
            assert field in row

    def test_approving_opens_it_and_creators_can_see_it(self, brand, creator, admin):
        bs, _, uid = brand
        cs, cuid, _ = creator
        draft = self._submitted(bs, admin, uid)

        r = admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/approve")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "open"

        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        feed = {c["id"] for c in cs.get(f"{BASE_URL}/campaigns").json()}
        assert draft["id"] in feed

    def test_a_future_start_date_lands_on_upcoming(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid, start_date="2027-06-01T00:00:00Z")
        assert admin.post(
            f"{BASE_URL}/admin/campaigns/{draft['id']}/approve"
        ).json()["status"] == "upcoming"

    def test_approving_clears_the_queue_entry(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)
        admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/approve")
        queue = {c["id"] for c in admin.get(f"{BASE_URL}/admin/campaigns/pending").json()}
        assert draft["id"] not in queue

    def test_approving_twice_is_refused(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)
        assert admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/approve").status_code == 200
        second = admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/approve")
        assert second.status_code == 409, second.text

    def test_a_draft_cannot_be_approved_without_being_submitted(self, brand, admin):
        bs, _, uid = brand
        pipeline.verify_brand(admin, uid)
        draft = _draft(bs)
        r = admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/approve")
        assert r.status_code == 409, r.text

    def test_an_unverified_brands_brief_cannot_be_approved(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)
        # The brand loses its verification while the brief sits in the queue.
        admin.post(f"{BASE_URL}/admin/brands/{uid}/unverify")
        r = admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/approve")
        assert r.status_code == 409, r.text
        assert "verify the brand" in r.text.lower()

    def test_rejecting_sends_it_back_with_the_reason(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)

        r = admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/reject",
                       json={"reason": "The deliverables are too vague"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "draft"

        row = next(c for c in bs.get(f"{BASE_URL}/brand/campaigns").json()
                   if c["id"] == draft["id"])
        assert row["status"] == "draft"
        assert "vague" in row["review_reason"]
        assert row["can_edit"] and row["can_publish"]

    def test_a_campaign_rejection_needs_a_reason(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)
        assert admin.post(
            f"{BASE_URL}/admin/campaigns/{draft['id']}/reject", json={}
        ).status_code == 422

    def test_a_rejected_brief_can_be_fixed_and_resubmitted(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)
        admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/reject",
                   json={"reason": "Say what the deliverables are"})

        assert bs.put(f"{BASE_URL}/brand/campaigns/{draft['id']}",
                      json={"deliverables": "1 reel and 3 stories"}).status_code == 200
        pipeline.submit_campaign(bs, draft["id"])

        row = next(c for c in admin.get(f"{BASE_URL}/admin/campaigns/pending").json()
                   if c["id"] == draft["id"])
        assert row["previous_review_reason"] is None, (
            "a resubmission starts clean rather than carrying the last refusal"
        )
        assert admin.post(
            f"{BASE_URL}/admin/campaigns/{draft['id']}/approve"
        ).json()["status"] == "open"

    def test_a_live_campaign_cannot_be_rejected(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)
        admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/approve")
        r = admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/reject",
                       json={"reason": "changed my mind"})
        assert r.status_code == 409, r.text
        assert "close" in r.text.lower()

    def test_unknown_campaign_is_404(self, admin):
        assert admin.post(
            f"{BASE_URL}/admin/campaigns/507f1f77bcf86cd799439011/approve"
        ).status_code == 404
        assert admin.post(f"{BASE_URL}/admin/campaigns/not-an-id/approve").status_code == 404

    def test_the_decisions_are_audited(self, brand, admin):
        bs, _, uid = brand
        approved = self._submitted(bs, admin, uid)
        admin.post(f"{BASE_URL}/admin/campaigns/{approved['id']}/approve")
        sent_back = self._submitted(bs, admin, uid)
        admin.post(f"{BASE_URL}/admin/campaigns/{sent_back['id']}/reject",
                   json={"reason": "Needs a clearer brief"})

        entries = admin.get(f"{BASE_URL}/admin/audit",
                            params={"subject_type": "campaign", "limit": 200}).json()
        actions = {(e["action"], e["subject_id"]) for e in entries}
        assert ("campaign.approve", approved["id"]) in actions
        assert ("campaign.reject", sent_back["id"]) in actions

    def test_the_brand_is_told_either_way(self, brand, admin):
        bs, _, uid = brand
        draft = self._submitted(bs, admin, uid)
        out = admin.post(f"{BASE_URL}/admin/campaigns/{draft['id']}/approve").json()
        assert set(out["notification"]) >= {"delivered", "mode", "error"}

        notes = bs.get(f"{BASE_URL}/notifications").json()["notifications"]
        assert any(n["event"] == "campaign_approved" for n in notes), (
            "the brand has to be told in-app even if WhatsApp is unreachable"
        )


# ---------- 4. Metrics ----------

class TestModerationMetrics:
    def test_the_review_queue_is_on_the_admin_desk_count(self, brand, admin):
        bs, _, uid = brand
        before = admin.get(f"{BASE_URL}/admin/metrics").json()
        pipeline.verify_brand(admin, uid)
        draft = _draft(bs)
        pipeline.submit_campaign(bs, draft["id"])

        after = admin.get(f"{BASE_URL}/admin/metrics").json()
        assert after["campaigns_pending_review"] == before["campaigns_pending_review"] + 1
        assert after["awaiting_breakdown"]["campaigns_to_review"] >= 1
        assert after["awaiting_admin_action"] > before["awaiting_admin_action"]
