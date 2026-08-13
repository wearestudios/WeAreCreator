"""Backend tests for /api/admin/* — vetting, collaborations, payments, metrics."""
import os
import uuid
import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


def _rand_email(role):
    # Server lower-cases emails on register.
    return f"test_{role}-{uuid.uuid4().hex[:10]}@example.com"


def _register(session, role):
    email = _rand_email(role)
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role,
    })
    assert r.status_code == 200, r.text
    return email, r.json()


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def admin():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture
def anon():
    return requests.Session()


@pytest.fixture
def creator():
    s = requests.Session()
    email, user = _register(s, "creator")
    return s, user.get("id") or user.get("user_id") or user.get("_id"), email


@pytest.fixture
def brand():
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email


def _complete_creator(s, handle_suffix=None):
    return pipeline.complete_creator_profile(s, suffix=handle_suffix)


def _vet(admin_session, email):
    """Approve the creator with this email and return their user id."""
    rows = admin_session.get(f"{BASE_URL}/admin/creators/pending").json()
    uid = next(x["user_id"] for x in rows if x["email"] == email)
    pipeline.vet_creator(admin_session, uid)
    return uid


# ---------- 1. Auth guards ----------
ADMIN_ENDPOINTS = [
    ("GET", "/admin/creators/pending"),
    ("GET", "/admin/collaborations"),
    ("GET", "/admin/metrics"),
]


class TestAdminAuth:
    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_anonymous_401(self, anon, method, path):
        r = anon.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 401, f"{path} -> {r.status_code}"

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_creator_403(self, creator, method, path):
        s, _, _ = creator
        r = s.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 403, f"{path} -> {r.status_code}"

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_brand_403(self, brand, method, path):
        s, _ = brand
        r = s.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 403, f"{path} -> {r.status_code}"

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_admin_200(self, admin, method, path):
        r = admin.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code}"


# ---------- 2. Pending creators list ----------

class TestPendingCreators:
    def test_pending_list_shape_and_filter(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        # This creator (pending) should be listed
        r = admin.get(f"{BASE_URL}/admin/creators/pending")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        row = next((x for x in rows if x.get("email") == email), None)
        assert row is not None, f"pending creator {email} not found"
        for field in ["user_id", "name", "email", "instagram_handle",
                      "instagram_profile_url", "niches", "follower_count",
                      "base_rate", "address"]:
            assert field in row, f"missing field {field}"
        assert row.get("vetting_status") == "pending"

    def test_rejected_and_vetted_not_in_pending(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        # find uid
        rows = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        row = next(x for x in rows if x["email"] == email)
        uid = row["user_id"]
        # approve
        r = admin.post(f"{BASE_URL}/admin/creators/{uid}/approve")
        assert r.status_code == 200
        rows2 = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        assert not any(x["email"] == email for x in rows2)


# ---------- 3. Approve / Reject ----------

class TestApproveReject:
    def test_approve_sets_vetted_and_active_and_is_idempotent(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        rows = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        uid = next(x["user_id"] for x in rows if x["email"] == email)

        r1 = admin.post(f"{BASE_URL}/admin/creators/{uid}/approve")
        assert r1.status_code == 200
        assert r1.json()["vetting_status"] == "vetted"

        # /auth/me from creator session should now show status=active
        me = s.get(f"{BASE_URL}/auth/me")
        assert me.status_code == 200
        assert me.json().get("status") == "active"

        # Second call idempotent
        r2 = admin.post(f"{BASE_URL}/admin/creators/{uid}/approve")
        assert r2.status_code == 200
        assert r2.json()["vetting_status"] == "vetted"

    def test_reject_sets_rejected(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        rows = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        uid = next(x["user_id"] for x in rows if x["email"] == email)
        r = admin.post(f"{BASE_URL}/admin/creators/{uid}/reject")
        assert r.status_code == 200
        assert r.json()["vetting_status"] == "rejected"

    def test_approve_nonexistent_404(self, admin):
        # valid-looking ObjectId that shouldn't exist
        r = admin.post(f"{BASE_URL}/admin/creators/507f1f77bcf86cd799439011/approve")
        assert r.status_code == 404


# ---------- 4. Collaborations list ----------

def _seed_open_campaign(brand_session):
    brand_session.put(f"{BASE_URL}/brand/profile", json={
        "business_name": f"Br-{uuid.uuid4().hex[:5]}", "category": "fnb",
        "areas": ["Indiranagar"],
    })
    body = {
        "title": f"Camp-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
        "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
        "creators_needed": 3,
        "start_date": "2026-02-01T00:00:00Z", "end_date": "2026-03-01T00:00:00Z",
        "status": "open",
    }
    r = brand_session.post(f"{BASE_URL}/brand/campaigns", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"], body["title"]


class TestCollabList:
    def test_list_shape(self, admin, brand, creator):
        bs, _ = brand
        cs, _, cemail = creator
        _complete_creator(cs)
        _vet(admin, cemail)
        cid, _ = _seed_open_campaign(bs)
        ar = cs.post(f"{BASE_URL}/campaigns/{cid}/apply", json={
            "pitch": "hi there really keen", "quoted_rate": 5500,
        })
        assert ar.status_code in (200, 201), ar.text

        r = admin.get(f"{BASE_URL}/admin/collaborations")
        assert r.status_code == 200
        data = r.json()
        assert "by_state" in data and "total" in data
        for st in ["applied","vetted","accepted","commercial_agreed","slot_booked",
                   "attended","content_submitted","content_approved","in_payment",
                   "closed","declined","cancelled"]:
            assert st in data["by_state"]
        applied = data["by_state"]["applied"]
        row = next((x for x in applied if x["creator"]["email"] == cemail), None)
        assert row is not None
        assert row["quoted_rate"] == 5500
        assert row["next_state"] == "vetted"
        assert row["can_advance"] is True
        assert row["next_owner"] == "admin"
        for k in ["id", "state", "campaign", "brand_name", "creator", "payment"]:
            assert k in row
        assert row["campaign"]["title"]

    def test_accepting_is_flagged_as_the_brands_step(self, admin, brand, creator):
        """The admin console must not offer an Advance button for a decision the
        brand owns — and the API refuses it either way."""
        bs, _ = brand
        cs, cuid, cemail = creator
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "vetted")

        row = next(
            x
            for x in admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]["vetted"]
            if x["id"] == collab_id
        )
        assert row["next_state"] == "accepted"
        assert row["next_owner"] == "brand"
        assert row["can_advance"] is False

        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "vetted"},
        )
        assert r.status_code == 409
        assert "brand" in r.json()["detail"].lower()


# ---------- 5. State machine end-to-end ----------

class TestStateMachine:
    def test_full_pipeline_end_to_end(self, admin, brand, creator):
        """Applied → closed, with each step taken by whoever owns it."""
        bs, _ = brand
        cs, cuid, cemail = creator
        _complete_creator(cs)
        pipeline.vet_creator(admin, cuid)
        cid, _ = _seed_open_campaign(bs)
        collab_id = pipeline.apply_to_campaign(cs, cid, quoted_rate=6000)

        # applied -> vetted (admin)
        r = pipeline.step(admin, bs, collab_id, "vetted")
        assert r["state"] == "vetted"

        # vetted -> accepted is the brand's, and the fee is recorded with it
        r = pipeline.step(admin, bs, collab_id, "accepted", agreed_amount=8500)
        assert r["state"] == "accepted"
        assert r["agreed_amount"] == 8500

        # accepted -> commercial_agreed needs an amount
        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "accepted"},
        )
        assert r.status_code == 422
        assert "Agreed amount is required" in r.text

        r = pipeline.step(admin, bs, collab_id, "commercial_agreed", agreed_amount=8500)
        assert r["state"] == "commercial_agreed"
        assert r["agreed_amount"] == 8500

        # slot_booked requires an actual slot
        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "commercial_agreed"},
        )
        assert r.status_code == 422
        assert "date and time" in r.json()["detail"].lower()

        r = pipeline.step(admin, bs, collab_id, "slot_booked")
        assert r["state"] == "slot_booked"
        assert r["scheduled_at"], "the slot must carry a time"

        assert pipeline.step(admin, bs, collab_id, "attended")["state"] == "attended"

        # content_submitted is the creator's step
        sr = pipeline.submit_content(cs, collab_id)
        assert sr["state"] == "content_submitted"

        # approval is the brand's
        ar = pipeline.step(admin, bs, collab_id, "content_approved")
        assert ar["state"] == "content_approved"

        # in_payment: the fee comes from config, no hand-typed number needed
        r = pipeline.step(admin, bs, collab_id, "in_payment")
        assert r["state"] == "in_payment"

        all_c = admin.get(f"{BASE_URL}/admin/collaborations").json()
        row = next(x for x in all_c["by_state"]["in_payment"] if x["id"] == collab_id)
        pay = row["payment"]
        assert pay is not None
        assert pay["agreed_amount"] == 8500
        assert pay["creator_payout"] == 8500
        assert pay["platform_fee"] > 0
        # The brand is invoiced the creator's fee plus our margin.
        assert pay["brand_invoice_amount"] == pytest.approx(
            8500 + pay["platform_fee"]
        )
        assert pay["state"] == "pending"

        # Recording a payout demands a reference you can reconcile.
        bad = admin.post(f"{BASE_URL}/admin/payments/{pay['id']}/mark_paid", json={})
        assert bad.status_code == 422

        mr = admin.post(
            f"{BASE_URL}/admin/payments/{pay['id']}/mark_paid",
            json={"payment_reference": "UTR402512345678"},
        )
        assert mr.status_code == 200, mr.text
        md = mr.json()
        assert md["state"] == "paid"
        assert md["paid_at"]
        assert md["payment_reference"] == "UTR402512345678"
        assert md["collaboration_id"] == collab_id

        # collab now closed
        all_c2 = admin.get(f"{BASE_URL}/admin/collaborations").json()
        assert any(x["id"] == collab_id for x in all_c2["by_state"]["closed"])

        # advancing from closed -> 409
        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "closed"},
        )
        assert r.status_code == 409

        # paying twice is refused
        again = admin.post(
            f"{BASE_URL}/admin/payments/{pay['id']}/mark_paid",
            json={"payment_reference": "UTR999"},
        )
        assert again.status_code == 409
        assert "already marked paid" in again.json()["detail"].lower()

    def test_stale_from_state_is_refused(self, admin, brand, creator):
        """A double-click used to skip a stage. The precondition stops it."""
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "vetted")

        # The caller thinks it's still `applied`; it isn't.
        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "applied"},
        )
        assert r.status_code == 409
        assert "already moved" in r.json()["detail"].lower()
        assert pipeline.current_state(admin, collab_id) == "vetted"

    def test_payment_requires_creator_payout_details(self, admin, brand, creator):
        """We must not claim to have paid someone we have no way of paying."""
        bs, _ = brand
        cs, cuid, _ = creator
        # Same setup, minus the payout fields.
        pipeline.complete_creator_profile(cs, with_payout=False)
        pipeline.vet_creator(admin, cuid)
        cid, _ = _seed_open_campaign(bs)
        collab_id = pipeline.apply_to_campaign(cs, cid)
        for state in ["vetted", "accepted", "commercial_agreed", "slot_booked", "attended"]:
            pipeline.step(admin, bs, collab_id, state)
        pipeline.submit_content(cs, collab_id)
        pipeline.step(admin, bs, collab_id, "content_approved")

        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "content_approved"},
        )
        assert r.status_code == 422
        assert "payout details" in r.json()["detail"].lower()

    def test_advance_from_in_payment_is_blocked_use_mark_paid(
        self, admin, brand, creator
    ):
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "in_payment")

        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "in_payment"},
        )
        assert r.status_code == 400
        assert "mark as paid" in r.json()["detail"].lower()

    def test_cancel_ends_a_collaboration_and_voids_its_payment(
        self, admin, brand, creator
    ):
        """There was no way out of the pipeline at all before this."""
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, bs, cs, cuid, "slot_booked"
        )

        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/cancel",
            json={"reason": "Creator couldn't make the slot"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "cancelled"

        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        row = next(x for x in board["cancelled"] if x["id"] == collab_id)
        assert row["exit_reason"] == "Creator couldn't make the slot"
        assert row["can_advance"] is False

        # A cancelled collaboration cannot be moved again.
        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/cancel", json={"reason": "again"}
        )
        assert r.status_code == 409


# ---------- 5b. Brand-owned decisions ----------

class TestBrandDecisions:
    def test_brand_declines_and_the_creator_can_apply_again(
        self, admin, brand, creator
    ):
        """A decline used to be impossible, and the unique index made it permanent."""
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, bs, cs, cuid, "vetted"
        )

        r = bs.post(
            f"{BASE_URL}/brand/collaborations/{collab_id}/decline",
            json={"reason": "Looking for a different audience"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "declined"

        # The slot is free again, and so is the creator.
        again = cs.post(
            f"{BASE_URL}/campaigns/{campaign_id}/apply",
            json={"pitch": "second time lucky, here's a new angle", "quoted_rate": 5000},
        )
        assert again.status_code in (200, 201), again.text

    def test_brand_sends_content_back_and_creator_resubmits(
        self, admin, brand, creator
    ):
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, _ = pipeline.make_collab_in_state(
            admin, bs, cs, cuid, "content_submitted"
        )

        r = bs.post(
            f"{BASE_URL}/brand/collaborations/{collab_id}/request_changes",
            json={"reason": "Please tag the venue in the caption"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "attended"

        # A change request without a note is useless to the creator.
        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        row = next(x for x in board["attended"] if x["id"] == collab_id)
        assert row["revision_note"] == "Please tag the venue in the caption"

        # The creator can resubmit without an admin unpicking the state.
        again = pipeline.submit_content(
            cs, collab_id, ["https://instagram.com/p/fixedpost"]
        )
        assert again["state"] == "content_submitted"
        assert again["content_urls"] == ["https://instagram.com/p/fixedpost"]


# ---------- 6. Metrics ----------

class TestAdminMetrics:
    def test_metrics_shape_and_types(self, admin):
        r = admin.get(f"{BASE_URL}/admin/metrics")
        assert r.status_code == 200
        d = r.json()
        for k in [
            "open_campaigns",
            "vetted_creators",
            "total_paid_out",
            "platform_revenue",
            "platform_fee_percent",
            "payouts_pending",
            "brand_receivable",
            "creators_pending_review",
            "brands_unverified",
            "applicants_awaiting_vetting",
        ]:
            assert k in d, f"missing metric {k}"
        assert isinstance(d["open_campaigns"], int)
        assert isinstance(d["vetted_creators"], int)
        assert isinstance(d["total_paid_out"], (int, float))
        assert isinstance(d["platform_revenue"], (int, float))

    def test_metrics_react_to_mark_paid(self, admin, brand, creator):
        before = admin.get(f"{BASE_URL}/admin/metrics").json()
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "in_payment")

        row = next(
            x
            for x in admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]["in_payment"]
            if x["id"] == collab_id
        )
        payout = row["payment"]["creator_payout"]
        fee = row["payment"]["platform_fee"]

        admin.post(
            f"{BASE_URL}/admin/payments/{row['payment']['id']}/mark_paid",
            json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"},
        )
        after = admin.get(f"{BASE_URL}/admin/metrics").json()
        assert after["total_paid_out"] >= before["total_paid_out"] + payout - 0.01
        # Revenue is now visible in our own console, not just payouts.
        assert after["platform_revenue"] >= before["platform_revenue"] + fee - 0.01


# ---------- 7. Audit trail ----------

class TestAuditLog:
    def test_every_decision_names_who_made_it(self, admin, brand, creator):
        cs, cuid, cemail = creator
        _complete_creator(cs)
        pipeline.vet_creator(admin, cuid)

        r = admin.get(f"{BASE_URL}/admin/audit", params={"limit": 50})
        assert r.status_code == 200
        rows = r.json()
        entry = next(
            (x for x in rows if x["action"] == "creator.vetted"), None
        )
        assert entry is not None, "vetting decision left no audit trail"
        assert entry["actor_role"] == "admin"
        assert entry["before"]["vetting_status"] == "pending"
        assert entry["after"]["vetting_status"] == "vetted"
        assert entry["created_at"]

    def test_audit_is_admin_only(self, creator, brand, anon):
        cs, _, _ = creator
        bs, _ = brand
        assert anon.get(f"{BASE_URL}/admin/audit").status_code == 401
        assert cs.get(f"{BASE_URL}/admin/audit").status_code == 403
        assert bs.get(f"{BASE_URL}/admin/audit").status_code == 403


# ---------- 8. Brand verification ----------

class TestBrandVerification:
    def test_unverified_brand_can_be_verified(self, admin, brand):
        bs, bemail = brand
        bs.put(
            f"{BASE_URL}/brand/profile",
            json={
                "business_name": f"Br-{uuid.uuid4().hex[:5]}",
                "category": "fnb",
                "areas": ["Indiranagar"],
            },
        )
        rows = admin.get(f"{BASE_URL}/admin/brands").json()
        row = next((x for x in rows if x["email"] == bemail), None)
        assert row is not None, "a new brand should be waiting for verification"
        assert row["verified"] is False

        r = admin.post(f"{BASE_URL}/admin/brands/{row['user_id']}/verify")
        assert r.status_code == 200
        assert r.json()["verified"] is True

        rows2 = admin.get(f"{BASE_URL}/admin/brands").json()
        assert not any(x["email"] == bemail for x in rows2)

    def test_brand_endpoints_are_admin_only(self, creator, brand, anon):
        cs, _, _ = creator
        bs, _ = brand
        assert anon.get(f"{BASE_URL}/admin/brands").status_code == 401
        assert cs.get(f"{BASE_URL}/admin/brands").status_code == 403
        assert bs.get(f"{BASE_URL}/admin/brands").status_code == 403
