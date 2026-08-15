"""Backend tests for /api/admin/* — verification, collaborations, payments, metrics."""
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


@pytest.fixture
def brand_2():
    """A second, unrelated brand — for asserting one brand's data stays its own."""
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email


def _complete_creator(s, handle_suffix=None):
    return pipeline.complete_creator_profile(s, suffix=handle_suffix)


def _vet(admin_session, email):
    """Approve the creator with this email and return their user id."""
    rows = admin_session.get(f"{BASE_URL}/admin/creators/pending").json()
    uid = next(x["user_id"] for x in rows if x["email"] == email)
    pipeline.verify_creator(admin_session, uid)
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
        assert row.get("verification_status") == "pending"

    def test_rejected_and_verified_not_in_pending(self, admin, creator):
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
    def test_approve_sets_verified_and_active_and_is_idempotent(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        rows = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        uid = next(x["user_id"] for x in rows if x["email"] == email)

        r1 = admin.post(f"{BASE_URL}/admin/creators/{uid}/approve")
        assert r1.status_code == 200
        assert r1.json()["verification_status"] == "verified"

        # /auth/me from creator session should now show status=active
        me = s.get(f"{BASE_URL}/auth/me")
        assert me.status_code == 200
        assert me.json().get("status") == "active"

        # Second call idempotent
        r2 = admin.post(f"{BASE_URL}/admin/creators/{uid}/approve")
        assert r2.status_code == 200
        assert r2.json()["verification_status"] == "verified"

    def test_reject_sets_rejected(self, admin, creator):
        s, _, email = creator
        _complete_creator(s)
        rows = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        uid = next(x["user_id"] for x in rows if x["email"] == email)
        r = admin.post(f"{BASE_URL}/admin/creators/{uid}/reject")
        assert r.status_code == 200
        assert r.json()["verification_status"] == "rejected"

    def test_approve_nonexistent_404(self, admin):
        # valid-looking ObjectId that shouldn't exist
        r = admin.post(f"{BASE_URL}/admin/creators/507f1f77bcf86cd799439011/approve")
        assert r.status_code == 404


# ---------- 4. Collaborations list ----------

def _seed_open_campaign(brand_session, admin_session):
    """A campaign creators can see. Goes through the real gates: the brand is
    verified, it drafts, submits, and an admin approves."""
    pipeline.setup_brand(brand_session, admin_session)
    body = {
        "title": f"Camp-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
        "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
        "creators_needed": 3,
        "campaign_type": "personal_table",
        "start_date": "2025-03-01T00:00:00Z",
        "end_date": "2027-03-01T00:00:00Z",
        "status": "draft",
    }
    r = brand_session.post(f"{BASE_URL}/brand/campaigns", json=body)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    pipeline.submit_campaign(brand_session, cid)
    assert pipeline.approve_campaign(admin_session, cid) == "open"
    return cid, body["title"]


class TestCollabList:
    def test_list_shape(self, admin, brand, creator):
        bs, _ = brand
        cs, _, cemail = creator
        _complete_creator(cs)
        _vet(admin, cemail)
        cid, _ = _seed_open_campaign(bs, admin)
        ar = cs.post(f"{BASE_URL}/campaigns/{cid}/apply", json={
            "pitch": "hi there really keen", "quoted_rate": 5500,
        })
        assert ar.status_code in (200, 201), ar.text

        r = admin.get(f"{BASE_URL}/admin/collaborations")
        assert r.status_code == 200
        data = r.json()
        assert "by_state" in data and "total" in data
        for st in ["applied","verified","accepted","commercial_agreed","slot_booked",
                   "attended","content_submitted","content_approved","in_payment",
                   "closed","declined","cancelled"]:
            assert st in data["by_state"]
        applied = data["by_state"]["applied"]
        row = next((x for x in applied if x["creator"]["email"] == cemail), None)
        assert row is not None
        assert row["quoted_rate"] == 5500
        assert row["next_state"] == "verified"
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
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "verified")

        row = next(
            x
            for x in admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]["verified"]
            if x["id"] == collab_id
        )
        assert row["next_state"] == "accepted"
        assert row["next_owner"] == "brand"
        assert row["can_advance"] is False

        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "verified"},
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
        pipeline.verify_creator(admin, cuid)
        cid, _ = _seed_open_campaign(bs, admin)
        collab_id = pipeline.apply_to_campaign(cs, cid, quoted_rate=6000)

        # applied -> verified (admin)
        r = pipeline.step(admin, bs, collab_id, "verified")
        assert r["state"] == "verified"

        # verified -> accepted is the brand's, and the fee is recorded with it
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
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "verified")

        # The caller thinks it's still `applied`; it isn't.
        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/advance",
            json={"from_state": "applied"},
        )
        assert r.status_code == 409
        assert "already moved" in r.json()["detail"].lower()
        assert pipeline.current_state(admin, collab_id) == "verified"

    def test_payment_requires_creator_payout_details(self, admin, brand, creator):
        """We must not claim to have paid someone we have no way of paying."""
        bs, _ = brand
        cs, cuid, _ = creator
        # Same setup, minus the payout fields.
        pipeline.complete_creator_profile(cs, with_payout=False)
        pipeline.verify_creator(admin, cuid)
        cid, _ = _seed_open_campaign(bs, admin)
        collab_id = pipeline.apply_to_campaign(cs, cid)
        for state in ["verified", "accepted", "commercial_agreed", "slot_booked", "attended"]:
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
            admin, bs, cs, cuid, "verified"
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
            "verified_creators",
            "total_paid_out",
            "platform_revenue",
            "platform_fee_percent",
            "payouts_pending",
            "brand_receivable",
            "creators_pending_review",
            "brands_unverified",
            "applicants_awaiting_verification",
        ]:
            assert k in d, f"missing metric {k}"
        assert isinstance(d["open_campaigns"], int)
        assert isinstance(d["verified_creators"], int)
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
        pipeline.verify_creator(admin, cuid)

        r = admin.get(f"{BASE_URL}/admin/audit", params={"limit": 50})
        assert r.status_code == 200
        rows = r.json()
        entry = next(
            (x for x in rows if x["action"] == "creator.verified"), None
        )
        assert entry is not None, "verification decision left no audit trail"
        assert entry["actor_role"] == "admin"
        assert entry["before"]["verification_status"] == "pending"
        assert entry["after"]["verification_status"] == "verified"
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
        # The default now returns every brand, so the verification queue has to
        # be asked for explicitly.
        queue = {"unverified_only": True}
        rows = admin.get(f"{BASE_URL}/admin/brands", params=queue).json()
        row = next((x for x in rows if x["email"] == bemail), None)
        assert row is not None, "a new brand should be waiting for verification"
        assert row["verified"] is False

        r = admin.post(f"{BASE_URL}/admin/brands/{row['user_id']}/verify")
        assert r.status_code == 200
        assert r.json()["verified"] is True

        rows2 = admin.get(f"{BASE_URL}/admin/brands", params=queue).json()
        assert not any(x["email"] == bemail for x in rows2)

        # …but it's still on the full roster.
        everyone = admin.get(f"{BASE_URL}/admin/brands").json()
        listed = next(x for x in everyone if x["email"] == bemail)
        assert listed["verified"] is True

    def test_brand_endpoints_are_admin_only(self, creator, brand, anon):
        cs, _, _ = creator
        bs, _ = brand
        assert anon.get(f"{BASE_URL}/admin/brands").status_code == 401
        assert cs.get(f"{BASE_URL}/admin/brands").status_code == 403
        assert bs.get(f"{BASE_URL}/admin/brands").status_code == 403


# ---------- 9. Creator oversight ----------

class TestCreatorRoster:
    """GET /admin/creators — the roster, as opposed to the work queues."""

    def test_admin_only(self, creator, brand, anon):
        cs, _, _ = creator
        bs, _ = brand
        assert anon.get(f"{BASE_URL}/admin/creators").status_code == 401
        assert cs.get(f"{BASE_URL}/admin/creators").status_code == 403
        assert bs.get(f"{BASE_URL}/admin/creators").status_code == 403

    def test_lists_creators_of_every_verification_status(self, admin, creator):
        """The queues only show people waiting on us; this shows everyone."""
        cs, cuid, cemail = creator
        _complete_creator(cs)

        # Still pending — present.
        rows = admin.get(f"{BASE_URL}/admin/creators", params={"page_size": 100}).json()
        assert "creators" in rows and "total" in rows
        assert any(x["email"] == cemail for x in rows["creators"])

        # Verified — still present, unlike /creators/pending.
        pipeline.verify_creator(admin, cuid)
        after = admin.get(f"{BASE_URL}/admin/creators", params={"page_size": 100}).json()
        row = next(x for x in after["creators"] if x["email"] == cemail)
        assert row["verification_status"] == "verified"
        assert row["user_id"] == cuid

        pending = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        assert not any(x["email"] == cemail for x in pending)

    def test_row_carries_money_and_campaign_counts(self, admin, brand, creator):
        bs, _ = brand
        cs, cuid, cemail = creator
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "in_payment")

        row = next(
            x
            for x in admin.get(
                f"{BASE_URL}/admin/creators", params={"q": cemail, "page_size": 100}
            ).json()["creators"]
            if x["user_id"] == cuid
        )
        # Money in flight is committed, not earned — nothing has been paid yet.
        assert row["total_earned"] == 0
        assert row["committed"] > 0
        assert row["campaigns_completed"] == 0
        assert row["collaborations_ongoing"] == 1

        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        payment = next(
            x["payment"] for x in board["in_payment"] if x["id"] == collab_id
        )
        admin.post(
            f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
            json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"},
        )

        after = next(
            x
            for x in admin.get(
                f"{BASE_URL}/admin/creators", params={"q": cemail, "page_size": 100}
            ).json()["creators"]
            if x["user_id"] == cuid
        )
        assert after["total_earned"] == payment["creator_payout"]
        assert after["campaigns_completed"] == 1
        assert after["collaborations_ongoing"] == 0
        assert after["committed"] == 0

    def test_search_matches_name_handle_and_phone(self, admin, creator):
        cs, cuid, _ = creator
        suffix = uuid.uuid4().hex[:6]
        profile = pipeline.complete_creator_profile(cs, suffix=suffix)
        me = cs.get(f"{BASE_URL}/auth/me").json()

        def ids_for(term):
            r = admin.get(
                f"{BASE_URL}/admin/creators", params={"q": term, "page_size": 100}
            )
            assert r.status_code == 200, r.text
            return {x["user_id"] for x in r.json()["creators"]}

        assert cuid in ids_for(profile["name"])
        assert cuid in ids_for(profile["instagram_handle"])
        if me.get("phone"):
            assert cuid in ids_for(me["phone"])
        assert cuid not in ids_for(f"nobody-{uuid.uuid4().hex}")

    def test_filters_by_status_niche_and_city(self, admin, creator):
        cs, cuid, _ = creator
        pipeline.complete_creator_profile(cs)  # city Bengaluru, niche cafe
        pipeline.verify_creator(admin, cuid)

        def ids(params):
            r = admin.get(f"{BASE_URL}/admin/creators", params={**params, "page_size": 100})
            assert r.status_code == 200, r.text
            return {x["user_id"] for x in r.json()["creators"]}

        assert cuid in ids({"verification_status": "verified"})
        assert cuid not in ids({"verification_status": "rejected"})
        assert cuid in ids({"niche": "cafe"})
        assert cuid in ids({"niche": "CAFE"})  # case-insensitive
        assert cuid not in ids({"niche": "nonexistent-niche"})
        assert cuid in ids({"city": "Bengaluru"})
        # `area` is accepted as an alias — creators carry a city, not an area.
        assert cuid in ids({"area": "Bengaluru"})
        assert cuid not in ids({"city": "Atlantis"})

    def test_rejects_an_unknown_status(self, admin):
        r = admin.get(f"{BASE_URL}/admin/creators", params={"verification_status": "vetted"})
        assert r.status_code == 422

    def test_pagination_does_not_repeat_or_drop_rows(self, admin):
        first = admin.get(
            f"{BASE_URL}/admin/creators", params={"page": 1, "page_size": 3}
        ).json()
        assert first["page"] == 1 and first["page_size"] == 3
        assert len(first["creators"]) <= 3
        if first["total"] > 3:
            second = admin.get(
                f"{BASE_URL}/admin/creators", params={"page": 2, "page_size": 3}
            ).json()
            ids1 = {c["user_id"] for c in first["creators"]}
            ids2 = {c["user_id"] for c in second["creators"]}
            assert not (ids1 & ids2), "pages overlap"
            assert first["pages"] >= 2


class TestCreatorDetail:
    """GET /admin/creators/{id} — one creator's whole history."""

    def test_admin_only(self, creator, brand, anon):
        cs, cuid, _ = creator
        bs, _ = brand
        assert anon.get(f"{BASE_URL}/admin/creators/{cuid}").status_code == 401
        assert cs.get(f"{BASE_URL}/admin/creators/{cuid}").status_code == 403
        assert bs.get(f"{BASE_URL}/admin/creators/{cuid}").status_code == 403

    def test_unknown_and_malformed_ids_404(self, admin):
        assert admin.get(f"{BASE_URL}/admin/creators/not-an-id").status_code == 404
        assert admin.get(
            f"{BASE_URL}/admin/creators/507f1f77bcf86cd799439011"
        ).status_code == 404

    def test_a_brand_is_not_a_creator(self, admin, brand):
        """The id is a user id, so it has to be checked against the role."""
        bs, bemail = brand
        bs.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "X", "category": "fnb", "areas": ["Indiranagar"],
        })
        row = next(
            x for x in admin.get(f"{BASE_URL}/admin/brands").json()
            if x["email"] == bemail
        )
        assert admin.get(f"{BASE_URL}/admin/creators/{row['user_id']}").status_code == 404

    def test_fixed_paths_still_win_over_the_id_route(self, admin):
        """/creators/pending must not be read as a creator id."""
        for path in ("pending", "changed", "incomplete"):
            r = admin.get(f"{BASE_URL}/admin/creators/{path}")
            assert r.status_code == 200, f"/creators/{path} -> {r.status_code}"
            assert isinstance(r.json(), list), f"/creators/{path} returned the detail shape"

    def test_groups_collaborations_and_totals_the_money(self, admin, brand, creator):
        bs, _ = brand
        cs, cuid, _ = creator

        # One paid through to closed…
        done_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "in_payment")
        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        payment = next(x["payment"] for x in board["in_payment"] if x["id"] == done_id)
        admin.post(
            f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
            json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"},
        )

        # …one mid-flight…
        ongoing_campaign = pipeline.seed_open_campaign(bs, admin)
        ongoing_id = pipeline.apply_to_campaign(cs, ongoing_campaign)
        pipeline.step(admin, bs, ongoing_id, "verified")
        pipeline.step(admin, bs, ongoing_id, "accepted", agreed_amount=4000)

        # …and one still waiting on a decision.
        open_campaign = pipeline.seed_open_campaign(bs, admin)
        open_id = pipeline.apply_to_campaign(cs, open_campaign)

        r = admin.get(f"{BASE_URL}/admin/creators/{cuid}")
        assert r.status_code == 200, r.text
        d = r.json()

        assert d["creator"]["user_id"] == cuid
        assert d["creator"]["payout_ready"] is True

        groups = d["collaborations"]
        assert {c["id"] for c in groups["completed"]} == {done_id}
        assert {c["id"] for c in groups["ongoing"]} == {ongoing_id}
        assert {c["id"] for c in groups["applied"]} == {open_id}

        # Each row carries enough to read without another request.
        for row in groups["completed"] + groups["ongoing"] + groups["applied"]:
            assert row["campaign_title"], "campaign_title missing"
            assert row["brand_name"], "brand_name missing"
            assert "agreed_amount" in row
            assert row["state"]

        totals = d["totals"]
        assert totals["lifetime_earned"] == payment["creator_payout"]
        assert totals["committed"] == 4000
        assert totals["campaigns_completed"] == 1
        assert totals["collaborations_ongoing"] == 1
        assert totals["applications_open"] == 1

    def test_declined_collaborations_are_kept_not_dropped(self, admin, brand, creator):
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "verified")
        bs.post(
            f"{BASE_URL}/brand/collaborations/{collab_id}/decline",
            json={"reason": "Different audience this time"},
        )

        d = admin.get(f"{BASE_URL}/admin/creators/{cuid}").json()
        ended = d["collaborations"]["ended"]
        row = next(x for x in ended if x["id"] == collab_id)
        assert row["state"] == "declined"
        assert row["exit_reason"] == "Different audience this time"
        # And it isn't miscounted as work.
        assert d["totals"]["collaborations_ongoing"] == 0
        assert d["totals"]["campaigns_completed"] == 0

    def test_a_creator_with_no_history_reads_cleanly(self, admin, creator):
        cs, cuid, _ = creator
        _complete_creator(cs)
        d = admin.get(f"{BASE_URL}/admin/creators/{cuid}").json()
        assert d["collaborations"] == {
            "completed": [], "ongoing": [], "applied": [], "ended": []
        }
        assert d["totals"]["lifetime_earned"] == 0
        assert d["totals"]["committed"] == 0


class TestMetricsOversight:
    def test_gmv_campaign_counts_and_action_queue_present(self, admin):
        d = admin.get(f"{BASE_URL}/admin/metrics").json()
        for k in ["gmv", "campaigns_by_status", "campaigns_total",
                  "awaiting_admin_action", "awaiting_breakdown"]:
            assert k in d, f"missing {k}"

        # Every campaign status is zero-filled, so a caller never has to guard.
        for status in ["draft", "upcoming", "open", "in_progress", "completed", "closed"]:
            assert status in d["campaigns_by_status"]
            assert isinstance(d["campaigns_by_status"][status], int)
        assert d["campaigns_total"] == sum(d["campaigns_by_status"].values())

        # The headline number is always explainable by its parts.
        assert d["awaiting_admin_action"] == sum(d["awaiting_breakdown"].values())

    def test_gmv_is_payouts_plus_our_margin(self, admin, brand, creator):
        before = admin.get(f"{BASE_URL}/admin/metrics").json()
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "in_payment")
        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        payment = next(x["payment"] for x in board["in_payment"] if x["id"] == collab_id)
        admin.post(
            f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
            json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"},
        )

        after = admin.get(f"{BASE_URL}/admin/metrics").json()
        expected = payment["creator_payout"] + payment["platform_fee"]
        assert after["gmv"] == pytest.approx(before["gmv"] + expected, abs=0.01)
        assert after["gmv"] == pytest.approx(
            after["total_paid_out"] + after["platform_revenue"], abs=0.01
        )

    def test_action_queue_counts_a_new_applicant(self, admin, brand, creator):
        before = admin.get(f"{BASE_URL}/admin/metrics").json()
        bs, _ = brand
        cs, cuid, _ = creator
        pipeline.make_collab_in_state(admin, bs, cs, cuid, "applied")

        after = admin.get(f"{BASE_URL}/admin/metrics").json()
        assert (
            after["awaiting_breakdown"]["applicants_to_verify"]
            >= before["awaiting_breakdown"]["applicants_to_verify"] + 1
        )
        assert after["awaiting_admin_action"] > before["awaiting_admin_action"]


# ---------- 10. Campaign and brand oversight ----------

class TestCampaignOversight:
    """GET /admin/campaigns — the creator feed hides closed and draft briefs;
    the admin has to be able to see them."""

    def test_admin_only(self, creator, brand, anon):
        cs, _, _ = creator
        bs, _ = brand
        assert anon.get(f"{BASE_URL}/admin/campaigns").status_code == 401
        assert cs.get(f"{BASE_URL}/admin/campaigns").status_code == 403
        assert bs.get(f"{BASE_URL}/admin/campaigns").status_code == 403

    def _seed(self, bs, admin=None, status="open", **overrides):
        bs.put(f"{BASE_URL}/brand/profile", json={
            "business_name": f"Br-{uuid.uuid4().hex[:5]}",
            "category": "fnb", "areas": ["Indiranagar"],
        })
        # A campaign only reaches "open" through review, so a live one needs a
        # verified brand and an admin approval.
        if status == "open":
            assert admin is not None, "seeding an open campaign needs an admin session"
            pipeline.verify_brand(admin, pipeline.user_id_of(bs))
        body = {
            "title": f"Oversight-{uuid.uuid4().hex[:6]}", "brief": "b",
            "deliverables": "d", "budget_per_creator": 5000, "category": "fnb",
            "area": "Indiranagar", "creators_needed": 2, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        }
        body.update(overrides)
        r = bs.post(f"{BASE_URL}/brand/campaigns", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        if status == "open":
            pipeline.submit_campaign(bs, out["id"])
            assert pipeline.approve_campaign(admin, out["id"]) == "open"
            out["status"] = "open"
        return out

    def _ids(self, admin, **params):
        r = admin.get(f"{BASE_URL}/admin/campaigns", params={"page_size": 100, **params})
        assert r.status_code == 200, r.text
        return {c["id"] for c in r.json()["campaigns"]}

    def test_shows_draft_and_closed_which_the_feed_hides(self, admin, brand, creator):
        bs, _ = brand
        cs, cuid, _ = creator
        draft = self._seed(bs, status="draft")
        live = self._seed(bs, admin, status="open")
        bs.post(f"{BASE_URL}/brand/campaigns/{live['id']}/close", json={"reason": "done"})

        visible = self._ids(admin)
        assert draft["id"] in visible, "draft campaigns must be visible to an admin"
        assert live["id"] in visible, "closed campaigns must be visible to an admin"

        # And the creator feed is unchanged — still only live briefs.
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        feed = {c["id"] for c in cs.get(f"{BASE_URL}/campaigns").json()}
        assert draft["id"] not in feed
        assert live["id"] not in feed

    def test_filter_by_status_and_brand(self, admin, brand, brand_2):
        bs, _ = brand
        bs2, _ = brand_2
        mine_draft = self._seed(bs, status="draft")
        mine_open = self._seed(bs, admin, status="open")
        theirs = self._seed(bs2, admin, status="open")

        drafts = self._ids(admin, status="draft")
        assert mine_draft["id"] in drafts
        assert mine_open["id"] not in drafts

        row = next(
            c for c in admin.get(
                f"{BASE_URL}/admin/campaigns",
                params={"page_size": 100, "status": "draft"},
            ).json()["campaigns"] if c["id"] == mine_draft["id"]
        )
        by_brand = self._ids(admin, brand_id=row["brand_id"])
        assert mine_draft["id"] in by_brand and mine_open["id"] in by_brand
        assert theirs["id"] not in by_brand

    def test_rejects_unknown_status_brand_and_date_field(self, admin):
        assert admin.get(
            f"{BASE_URL}/admin/campaigns", params={"status": "archived"}
        ).status_code == 422
        assert admin.get(
            f"{BASE_URL}/admin/campaigns", params={"brand_id": "not-an-id"}
        ).status_code == 422
        assert admin.get(
            f"{BASE_URL}/admin/campaigns", params={"date_field": "whenever"}
        ).status_code == 422

    def test_date_range_filters(self, admin, brand):
        bs, _ = brand
        c = self._seed(bs, admin, status="open")
        # A window that ends before anything was created excludes it…
        assert c["id"] not in self._ids(admin, date_to="2020-01-01T00:00:00Z")
        # …and one that starts before now includes it.
        assert c["id"] in self._ids(admin, date_from="2020-01-01T00:00:00Z")

    def test_row_carries_brand_name_and_its_creators(self, admin, brand, creator):
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, bs, cs, cuid, "commercial_agreed"
        )

        row = next(
            c for c in admin.get(
                f"{BASE_URL}/admin/campaigns", params={"page_size": 100}
            ).json()["campaigns"] if c["id"] == campaign_id
        )
        assert row["brand_name"], "brand name missing"
        who = next(x for x in row["creators"] if x["collaboration_id"] == collab_id)
        assert who["creator_id"] == cuid
        assert who["name"]
        assert who["state"] == "commercial_agreed"
        assert who["agreed_amount"] == 8500
        assert row["filled_slots"] >= 1

    def test_declined_creators_are_still_listed(self, admin, brand, creator):
        """"who are or were part of it" — a decline is part of the history."""
        bs, _ = brand
        cs, cuid, _ = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, bs, cs, cuid, "verified"
        )
        bs.post(f"{BASE_URL}/brand/collaborations/{collab_id}/decline", json={})

        row = next(
            c for c in admin.get(
                f"{BASE_URL}/admin/campaigns", params={"page_size": 100}
            ).json()["campaigns"] if c["id"] == campaign_id
        )
        who = next(x for x in row["creators"] if x["collaboration_id"] == collab_id)
        assert who["state"] == "declined"
        # …but not counted as filling a slot.
        assert row["filled_slots"] == 0

    def test_pagination(self, admin):
        first = admin.get(
            f"{BASE_URL}/admin/campaigns", params={"page": 1, "page_size": 2}
        ).json()
        assert first["page"] == 1 and first["page_size"] == 2
        assert len(first["campaigns"]) <= 2
        if first["total"] > 2:
            second = admin.get(
                f"{BASE_URL}/admin/campaigns", params={"page": 2, "page_size": 2}
            ).json()
            ids1 = {c["id"] for c in first["campaigns"]}
            ids2 = {c["id"] for c in second["campaigns"]}
            assert not (ids1 & ids2), "pages overlap"


class TestBrandOversight:
    """GET /admin/brands — the roster, not just the verification queue."""

    def test_lists_verified_brands_too(self, admin, brand):
        bs, bemail = brand
        bs.put(f"{BASE_URL}/brand/profile", json={
            "business_name": f"Br-{uuid.uuid4().hex[:5]}",
            "category": "fnb", "areas": ["Indiranagar"],
        })
        row = next(
            x for x in admin.get(f"{BASE_URL}/admin/brands").json()
            if x["email"] == bemail
        )
        admin.post(f"{BASE_URL}/admin/brands/{row['user_id']}/verify")

        after = next(
            x for x in admin.get(f"{BASE_URL}/admin/brands").json()
            if x["email"] == bemail
        )
        assert after["verified"] is True
        for field in ["campaign_count", "active_campaign_count", "total_spend"]:
            assert field in after, f"missing {field}"

    def test_counts_and_spend(self, admin, brand, creator):
        bs, bemail = brand
        cs, cuid, _ = creator

        def row():
            return next(
                x for x in admin.get(f"{BASE_URL}/admin/brands").json()
                if x["email"] == bemail
            )

        collab_id, _ = pipeline.make_collab_in_state(admin, bs, cs, cuid, "in_payment")
        mid = row()
        assert mid["campaign_count"] >= 1
        assert mid["active_campaign_count"] >= 1
        assert mid["total_spend"] == 0, "nothing is spent until a payout is recorded"

        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        payment = next(x["payment"] for x in board["in_payment"] if x["id"] == collab_id)
        admin.post(
            f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
            json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"},
        )

        after = row()
        # Spend is what the brand pays: the creator's fee plus our margin.
        assert after["total_spend"] == pytest.approx(
            payment["creator_payout"] + payment["platform_fee"], abs=0.01
        )
        assert after["paid_collaborations"] >= 1

    def test_closed_campaigns_are_not_active(self, admin, brand):
        bs, bemail = brand
        bs.put(f"{BASE_URL}/brand/profile", json={
            "business_name": f"Br-{uuid.uuid4().hex[:5]}",
            "category": "fnb", "areas": ["Indiranagar"],
        })
        pipeline.verify_brand(admin, pipeline.user_id_of(bs))
        c = bs.post(f"{BASE_URL}/brand/campaigns", json={
            "title": f"C-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 1, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        }).json()
        pipeline.submit_campaign(bs, c["id"])
        assert pipeline.approve_campaign(admin, c["id"]) == "open"

        def active():
            return next(
                x for x in admin.get(f"{BASE_URL}/admin/brands").json()
                if x["email"] == bemail
            )["active_campaign_count"]

        before = active()
        bs.post(f"{BASE_URL}/brand/campaigns/{c['id']}/close", json={})
        assert active() == before - 1


# ---------- 8. Campaign invites ----------
class TestCampaignInvites:
    """POST /admin/campaigns/{id}/invite — sourcing is manual, so an admin picks
    creators and asks them. Nobody gets asked twice, and a partial send reads as
    a partial send."""

    def _campaign(self, bs, admin, **overrides):
        bs.put(f"{BASE_URL}/brand/profile", json={
            "business_name": f"Invite-Br-{uuid.uuid4().hex[:5]}",
            "category": "fnb", "areas": ["Indiranagar"],
        })
        pipeline.verify_brand(admin, pipeline.user_id_of(bs))
        body = {
            "title": f"Invite-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
            "budget_per_creator": 7500, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 3, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        }
        body.update(overrides)
        r = bs.post(f"{BASE_URL}/brand/campaigns", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        # Invites only go to live campaigns, so this has to clear review.
        pipeline.submit_campaign(bs, out["id"])
        out["status"] = pipeline.approve_campaign(admin, out["id"])
        return out

    def _verified_creator(self, admin):
        s = requests.Session()
        email, _ = _register(s, "creator")
        _complete_creator(s)
        uid = _vet(admin, email)
        return s, uid

    def _invite(self, admin, campaign_id, creator_ids, **body):
        return admin.post(
            f"{BASE_URL}/admin/campaigns/{campaign_id}/invite",
            json={"creator_ids": creator_ids, **body},
        )

    def test_admin_only(self, admin, brand, creator, anon):
        bs, _ = brand
        cs, cuid, _ = creator
        c = self._campaign(bs, admin)
        path = f"{BASE_URL}/admin/campaigns/{c['id']}/invite"
        body = {"creator_ids": [cuid]}
        assert anon.post(path, json=body).status_code == 401
        assert cs.post(path, json=body).status_code == 403
        # The brand owns the campaign and still cannot send on our behalf.
        assert bs.post(path, json=body).status_code == 403

    def test_invites_a_creator_and_records_it(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        cs, uid = self._verified_creator(admin)

        r = self._invite(admin, c["id"], [uid], note="Great fit for this one")
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["campaign_id"] == c["id"]
        assert len(out["results"]) == 1
        row = out["results"][0]
        assert row["creator_id"] == uid
        assert row["status"] in ("invited", "failed")
        # Either way the invitation exists — a failed send must be retryable
        # against a record, not vanish.
        assert row.get("invitation_id")

    def test_the_creator_sees_the_invite_in_app(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin, budget_per_creator=7500)
        cs, uid = self._verified_creator(admin)

        self._invite(admin, c["id"], [uid])

        notes = cs.get(f"{BASE_URL}/notifications").json()["notifications"]
        invite = next((n for n in notes if n["event"] == "campaign_invite"), None)
        assert invite, "the invite has to reach the creator even if WhatsApp doesn't"
        assert c["title"] in invite["body"]
        assert "7,500" in invite["body"], "the creator is told what it pays"
        assert invite["link"] == f"/campaigns/{c['id']}"

    def test_the_same_creator_is_never_invited_twice(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        cs, uid = self._verified_creator(admin)

        first = self._invite(admin, c["id"], [uid]).json()
        assert first["results"][0]["status"] != "already_invited"

        second = self._invite(admin, c["id"], [uid]).json()
        assert second["results"][0]["status"] == "already_invited"
        assert second["already_invited"] == 1
        assert second["invited"] == 0

        # And no second notification was raised.
        events = [
            n for n in cs.get(f"{BASE_URL}/notifications").json()["notifications"]
            if n["event"] == "campaign_invite"
        ]
        assert len(events) == 1

    def test_a_repeated_id_in_one_request_is_one_invite(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        cs, uid = self._verified_creator(admin)

        out = self._invite(admin, c["id"], [uid, uid, uid]).json()
        assert len(out["results"]) == 1, "a multi-select repeat must not multi-send"

    def test_the_same_creator_can_be_invited_to_a_different_campaign(self, admin, brand):
        bs, _ = brand
        one = self._campaign(bs, admin)
        two = self._campaign(bs, admin)
        cs, uid = self._verified_creator(admin)

        self._invite(admin, one["id"], [uid])
        out = self._invite(admin, two["id"], [uid]).json()
        assert out["results"][0]["status"] != "already_invited"

    def test_unverified_creators_are_refused_with_a_reason(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        s = requests.Session()
        _register(s, "creator")
        _complete_creator(s)
        uid = s.get(f"{BASE_URL}/auth/me").json()["id"]

        out = self._invite(admin, c["id"], [uid]).json()
        row = out["results"][0]
        assert row["status"] == "failed"
        # Only verified creators can apply, so the invite would be a dead end.
        assert "verified" in row["reason"].lower()
        assert out["invited"] == 0

    def test_a_brand_account_is_not_a_creator(self, admin, brand, brand_2):
        bs, _ = brand
        bs2, _ = brand_2
        c = self._campaign(bs, admin)
        their_id = bs2.get(f"{BASE_URL}/auth/me").json()["id"]

        row = self._invite(admin, c["id"], [their_id]).json()["results"][0]
        assert row["status"] == "failed"

    def test_a_partial_send_is_reported_per_creator(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        cs, good = self._verified_creator(admin)

        out = self._invite(admin, c["id"], [good, "not-an-object-id"]).json()
        assert len(out["results"]) == 2
        by_id = {r["creator_id"]: r for r in out["results"]}
        assert by_id["not-an-object-id"]["status"] == "failed"
        assert out["failed"] >= 1
        # The bad id must not have cost the good one its invite.
        assert by_id[good]["status"] in ("invited", "failed")
        assert by_id[good].get("invitation_id")

    def test_results_come_back_in_the_order_they_were_asked_for(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        _, a = self._verified_creator(admin)
        _, b = self._verified_creator(admin)

        out = self._invite(admin, c["id"], [b, a]).json()
        assert [r["creator_id"] for r in out["results"]] == [b, a]

    def test_counts_add_up_to_the_batch(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        _, a = self._verified_creator(admin)
        _, b = self._verified_creator(admin)
        self._invite(admin, c["id"], [b])  # b is already in

        out = self._invite(admin, c["id"], [a, b, "nonsense"]).json()
        assert out["invited"] + out["failed"] + out["already_invited"] == len(out["results"])
        assert out["already_invited"] == 1

    def test_unknown_campaign_is_404(self, admin, brand):
        _, uid = self._verified_creator(admin)
        assert self._invite(admin, "64b7f9a2c3d4e5f6a7b8c9d0", [uid]).status_code == 404
        assert self._invite(admin, "not-an-id", [uid]).status_code == 404

    def test_a_closed_campaign_cannot_be_invited_to(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        _, uid = self._verified_creator(admin)
        bs.post(f"{BASE_URL}/brand/campaigns/{c['id']}/close", json={"reason": "done"})

        r = self._invite(admin, c["id"], [uid])
        assert r.status_code == 409, r.text

    def test_an_empty_ask_is_rejected(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        assert self._invite(admin, c["id"], []).status_code == 422

    def test_the_invite_is_written_to_the_audit_log(self, admin, brand):
        bs, _ = brand
        c = self._campaign(bs, admin)
        _, uid = self._verified_creator(admin)
        self._invite(admin, c["id"], [uid], note="hand-picked")

        entries = admin.get(
            f"{BASE_URL}/admin/audit", params={"subject_type": "campaign", "limit": 200}
        ).json()
        mine = [
            e for e in entries
            if e["action"] == "campaign.invite" and e["subject_id"] == c["id"]
        ]
        assert mine, "a message sent to creators needs an author"
        assert mine[0]["note"] == "hand-picked"
