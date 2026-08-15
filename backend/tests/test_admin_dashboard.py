"""Backend tests for the console's aggregation endpoints.

Five requests used to fill the admin landing view. These cover the single call
that replaced them, the campaign scope, and the per-campaign applicant
breakdown — mostly by building a known set of collaborations and asserting the
numbers land in the right buckets.
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
    s = requests.Session()
    _register(s, "brand")
    return s


@pytest.fixture
def creator():
    s = requests.Session()
    _, user = _register(s, "creator")
    return s, user["id"]


def _new_creator(admin):
    """A verified creator with their own session."""
    s = requests.Session()
    _, user = _register(s, "creator")
    pipeline.complete_creator_profile(s)
    pipeline.verify_creator(admin, user["id"])
    return s, user["id"]


@pytest.fixture
def campaign(admin, brand):
    """A live campaign with room for several creators."""
    return pipeline.seed_open_campaign(brand, admin, creators_needed=10)


def _dashboard(admin, **params):
    r = admin.get(f"{BASE_URL}/admin/dashboard", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _applicants(admin, campaign_id):
    r = admin.get(f"{BASE_URL}/admin/campaigns/{campaign_id}/applicants")
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 1. Guards and shape ----------

class TestDashboardAccess:
    def test_admin_only(self, anon, brand, creator):
        cs, _ = creator
        assert anon.get(f"{BASE_URL}/admin/dashboard").status_code == 401
        assert brand.get(f"{BASE_URL}/admin/dashboard").status_code == 403
        assert cs.get(f"{BASE_URL}/admin/dashboard").status_code == 403

    def test_it_answers_in_one_call(self, admin):
        out = _dashboard(admin)
        for block in ("campaigns", "awaiting", "totals", "campaign_summary"):
            assert block in out, f"the console needs {block} without a second request"

    def test_campaign_statuses_are_zero_filled(self, admin):
        out = _dashboard(admin)["campaigns"]
        for status in ("draft", "pending_review", "upcoming", "open", "in_progress",
                       "paused", "completed", "closed"):
            assert isinstance(out[status], int), f"{status} must always be present"
        assert out["live"] == out["open"]
        assert out["total"] >= out["open"]

    def test_the_queues_are_all_present_and_sum_to_the_headline(self, admin):
        out = _dashboard(admin)
        for queue in ("creators_to_review", "campaigns_to_review", "brands_to_verify",
                      "collaborations_to_move", "payouts_to_record"):
            assert queue in out["awaiting"]
        assert out["awaiting_total"] == sum(out["awaiting"].values())

    def test_the_totals_are_all_present(self, admin):
        totals = _dashboard(admin)["totals"]
        for key in ("gmv", "total_paid_out", "active_creators", "active_brands"):
            assert key in totals

    def test_a_bad_campaign_scope_is_422_and_an_unknown_one_404(self, admin):
        assert admin.get(f"{BASE_URL}/admin/dashboard",
                         params={"campaign_id": "not-an-id"}).status_code == 422
        assert admin.get(
            f"{BASE_URL}/admin/dashboard",
            params={"campaign_id": "507f1f77bcf86cd799439011"},
        ).status_code == 404


# ---------- 2. The numbers ----------

class TestDashboardCounts:
    def test_a_new_campaign_shows_up_in_the_status_counts(self, admin, brand):
        before = _dashboard(admin)["campaigns"]["open"]
        pipeline.seed_open_campaign(brand, admin)
        assert _dashboard(admin)["campaigns"]["open"] == before + 1

    def test_a_submitted_campaign_lands_in_the_review_queue(self, admin, brand):
        before = _dashboard(admin)["awaiting"]["campaigns_to_review"]
        pipeline.setup_brand(brand, admin)
        r = brand.post(f"{BASE_URL}/brand/campaigns", json={
            "title": f"Q-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
            "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 2, "campaign_type": "launch",
            "event_date": "2027-09-01T00:00:00Z", "status": "draft",
        })
        pipeline.submit_campaign(brand, r.json()["id"])

        out = _dashboard(admin)
        assert out["awaiting"]["campaigns_to_review"] == before + 1
        assert out["campaigns"]["pending_review"] >= 1

    def test_an_applicant_lands_in_the_collaborations_queue(self, admin, brand, campaign):
        before = _dashboard(admin)["awaiting"]["collaborations_to_move"]
        cs, _ = _new_creator(admin)
        pipeline.apply_to_campaign(cs, campaign)
        assert _dashboard(admin)["awaiting"]["collaborations_to_move"] == before + 1

    def test_a_payout_waiting_shows_in_the_queue_and_the_totals(self, admin, brand, creator):
        cs, cuid = creator
        before = _dashboard(admin)
        collab_id, _ = pipeline.make_collab_in_state(admin, brand, cs, cuid, "in_payment")

        mid = _dashboard(admin)
        assert mid["awaiting"]["payouts_to_record"] == (
            before["awaiting"]["payouts_to_record"] + 1
        )
        assert mid["totals"]["payouts_pending"] > before["totals"]["payouts_pending"]

        # Recording it moves the money from pending into GMV.
        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        payment = next(x["payment"] for x in board["in_payment"] if x["id"] == collab_id)
        admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
                   json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"})

        after = _dashboard(admin)
        assert after["totals"]["total_paid_out"] > before["totals"]["total_paid_out"]
        assert after["totals"]["gmv"] > before["totals"]["gmv"]
        assert after["awaiting"]["payouts_to_record"] == (
            before["awaiting"]["payouts_to_record"]
        )

    def test_a_refund_takes_the_money_back_out_of_gmv(self, admin, brand, creator):
        cs, cuid = creator
        before = _dashboard(admin)["totals"]["gmv"]
        collab_id, _ = pipeline.make_collab_in_state(admin, brand, cs, cuid, "in_payment")
        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        payment = next(x["payment"] for x in board["in_payment"] if x["id"] == collab_id)
        admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
                   json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"})
        assert _dashboard(admin)["totals"]["gmv"] > before

        admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/refund",
                   json={"reason": "Paid the wrong account"})
        assert _dashboard(admin)["totals"]["gmv"] == pytest.approx(before, abs=0.01)

    def test_a_working_creator_counts_as_active(self, admin, brand, creator):
        cs, cuid = creator
        before = _dashboard(admin)["totals"]["active_creators"]
        # Applying is not working; being taken on is.
        pipeline.make_collab_in_state(admin, brand, cs, cuid, "applied")
        assert _dashboard(admin)["totals"]["active_creators"] == before

        collab_id, _ = pipeline.make_collab_in_state(admin, brand, cs, cuid, "accepted")
        assert _dashboard(admin)["totals"]["active_creators"] == before + 1

    def test_a_brand_running_something_counts_as_active(self, admin, brand):
        before = _dashboard(admin)["totals"]["active_brands"]
        pipeline.seed_open_campaign(brand, admin)
        assert _dashboard(admin)["totals"]["active_brands"] == before + 1


# ---------- 3. The per-campaign summary ----------

class TestCampaignSummary:
    def test_a_campaign_appears_with_its_type_and_dates(self, admin, brand):
        pipeline.setup_brand(brand, admin)
        r = brand.post(f"{BASE_URL}/brand/campaigns", json={
            "title": f"Sum-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
            "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 4, "campaign_type": "launch",
            "event_date": "2027-09-01T00:00:00Z", "status": "draft",
        })
        cid = r.json()["id"]
        pipeline.submit_campaign(brand, cid)
        pipeline.approve_campaign(admin, cid)

        row = next(c for c in _dashboard(admin, limit=200)["campaign_summary"]
                   if c["id"] == cid)
        assert row["campaign_type"] == "launch"
        assert row["event_date"]
        assert row["start_date"] is None, "a launch carries a day, not a window"
        assert row["creators_needed"] == 4
        assert row["brand_name"]

    def test_the_buckets_count_what_actually_happened(self, admin, brand, campaign):
        # One still applied, one taken on, one turned away.
        waiting, _ = _new_creator(admin)
        pipeline.apply_to_campaign(waiting, campaign)

        taken, _ = _new_creator(admin)
        accepted_id = pipeline.apply_to_campaign(taken, campaign)
        pipeline.step(admin, brand, accepted_id, "verified")
        pipeline.step(admin, brand, accepted_id, "accepted")

        turned_away, _ = _new_creator(admin)
        declined_id = pipeline.apply_to_campaign(turned_away, campaign)
        admin.post(f"{BASE_URL}/admin/collaborations/{declined_id}/decline",
                   json={"reason": "Not the right fit"})

        row = next(c for c in _dashboard(admin, limit=200)["campaign_summary"]
                   if c["id"] == campaign)
        assert row["applied"] == 1
        assert row["approved"] == 1
        assert row["rejected"] == 1
        assert row["completed"] == 0

    def test_the_list_is_bounded_and_says_when_it_is_cut(self, admin):
        out = _dashboard(admin, limit=1)
        assert len(out["campaign_summary"]) <= 1
        assert "summary_truncated" in out


# ---------- 4. Scoping to one campaign ----------

class TestCampaignScope:
    def test_it_narrows_to_the_one_campaign(self, admin, brand, campaign):
        # A second campaign that must not appear in the scoped numbers.
        other = pipeline.seed_open_campaign(brand, admin)

        out = _dashboard(admin, campaign_id=campaign)
        assert out["scoped_to_campaign"] == campaign
        ids = {c["id"] for c in out["campaign_summary"]}
        assert ids == {campaign}
        assert other not in ids
        assert out["campaigns"]["total"] == 1

    def test_only_that_campaigns_collaborations_are_counted(self, admin, brand, campaign):
        other = pipeline.seed_open_campaign(brand, admin)
        mine, _ = _new_creator(admin)
        theirs, _ = _new_creator(admin)
        pipeline.apply_to_campaign(mine, campaign)
        pipeline.apply_to_campaign(theirs, other)

        out = _dashboard(admin, campaign_id=campaign)
        assert out["awaiting"]["collaborations_to_move"] == 1

    def test_platform_wide_queues_read_zero_when_scoped(self, admin, brand, campaign):
        # There is always some creator waiting somewhere; scoped to a campaign
        # that number is not this campaign's business.
        out = _dashboard(admin, campaign_id=campaign)
        assert out["awaiting"]["creators_to_review"] == 0
        assert out["awaiting"]["brands_to_verify"] == 0

    def test_the_money_narrows_too(self, admin, brand, creator):
        cs, cuid = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, brand, cs, cuid, "in_payment"
        )
        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        payment = next(x["payment"] for x in board["in_payment"] if x["id"] == collab_id)
        admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
                   json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"})

        scoped = _dashboard(admin, campaign_id=campaign_id)["totals"]
        assert scoped["total_paid_out"] == pytest.approx(payment["creator_payout"], abs=0.01)
        assert scoped["collaborations_paid"] == 1

        # And the unscoped view is at least that much.
        assert _dashboard(admin)["totals"]["total_paid_out"] >= scoped["total_paid_out"]


# ---------- 5. The applicant breakdown ----------

class TestAdminApplicants:
    def test_admin_only(self, anon, brand, creator, campaign):
        cs, _ = creator
        path = f"{BASE_URL}/admin/campaigns/{campaign}/applicants"
        assert anon.get(path).status_code == 401
        assert cs.get(path).status_code == 403
        # Not even the brand that owns it — they have their own board.
        assert brand.get(path).status_code == 403

    def test_it_groups_into_three(self, admin, brand, campaign):
        waiting, _ = _new_creator(admin)
        pipeline.apply_to_campaign(waiting, campaign)

        taken, _ = _new_creator(admin)
        accepted_id = pipeline.apply_to_campaign(taken, campaign)
        pipeline.step(admin, brand, accepted_id, "verified")
        pipeline.step(admin, brand, accepted_id, "accepted")

        turned_away, _ = _new_creator(admin)
        declined_id = pipeline.apply_to_campaign(turned_away, campaign)
        admin.post(f"{BASE_URL}/admin/collaborations/{declined_id}/decline",
                   json={"reason": "Not this time"})

        out = _applicants(admin, campaign)
        assert len(out["applied"]) == 1
        assert len(out["approved"]) == 1
        assert len(out["rejected"]) == 1
        assert out["counts"] == {"applied": 1, "approved": 1, "rejected": 1}
        assert out["total"] == 3

    def test_each_entry_carries_what_the_console_renders(self, admin, brand, campaign):
        cs, _ = _new_creator(admin)
        pipeline.apply_to_campaign(cs, campaign, quoted_rate=7777)

        entry = _applicants(admin, campaign)["applied"][0]
        for field in ("name", "instagram_handle", "follower_count", "quoted_rate",
                      "agreed_amount", "state", "profile_image_url", "creator_id"):
            assert field in entry, f"missing {field}"
        assert entry["quoted_rate"] == 7777
        assert entry["state"] == "applied"

    def test_an_agreed_amount_shows_once_it_exists(self, admin, brand, campaign):
        cs, _ = _new_creator(admin)
        collab_id = pipeline.apply_to_campaign(cs, campaign)
        pipeline.step(admin, brand, collab_id, "verified")
        pipeline.step(admin, brand, collab_id, "accepted")
        pipeline.step(admin, brand, collab_id, "commercial_agreed", agreed_amount=6543)

        entry = next(e for e in _applicants(admin, campaign)["approved"]
                     if e["collaboration_id"] == collab_id)
        assert entry["agreed_amount"] == 6543
        assert entry["state"] == "commercial_agreed"

    def test_a_finished_collaboration_is_still_approved(self, admin, brand, creator):
        cs, cuid = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, brand, cs, cuid, "closed"
        )
        out = _applicants(admin, campaign_id)
        assert any(e["collaboration_id"] == collab_id for e in out["approved"])
        assert not any(e["collaboration_id"] == collab_id for e in out["rejected"])

    def test_a_cancelled_collaboration_is_rejected(self, admin, brand, creator):
        cs, cuid = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, brand, cs, cuid, "slot_booked"
        )
        admin.post(f"{BASE_URL}/admin/collaborations/{collab_id}/cancel", json={
            "reason": "Venue flooded", "cancellation_type": "brand_cancelled",
        })
        out = _applicants(admin, campaign_id)
        entry = next(e for e in out["rejected"] if e["collaboration_id"] == collab_id)
        assert entry["state"] == "cancelled"
        assert "flooded" in (entry["exit_reason"] or "")

    def test_it_carries_the_campaign_header(self, admin, brand, campaign):
        out = _applicants(admin, campaign)["campaign"]
        assert out["id"] == campaign
        assert out["title"]
        assert out["brand_name"]
        assert out["creators_needed"] >= 1
        assert "spots_left" in out

    def test_an_empty_campaign_answers_with_empty_groups(self, admin, brand, campaign):
        out = _applicants(admin, campaign)
        assert out["total"] == 0
        assert out["applied"] == [] and out["approved"] == [] and out["rejected"] == []

    def test_unknown_campaign_is_404(self, admin):
        for cid in ("507f1f77bcf86cd799439011", "not-an-id"):
            assert admin.get(
                f"{BASE_URL}/admin/campaigns/{cid}/applicants"
            ).status_code == 404

    def test_it_reaches_a_closed_campaign(self, admin, brand, campaign):
        cs, _ = _new_creator(admin)
        pipeline.apply_to_campaign(cs, campaign)
        admin.post(f"{BASE_URL}/admin/campaigns/{campaign}/close",
                   json={"reason": "Brand went quiet"})
        # The brand's own board is a decision screen; this one still answers.
        assert _applicants(admin, campaign)["total"] == 1
