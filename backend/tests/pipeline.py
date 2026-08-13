"""Shared helpers for walking a collaboration through the pipeline.

The pipeline is no longer a single admin clicking Advance nine times: applying
requires a verified creator, and two of the steps belong to the brand. Every
integration test that needs a collaboration in a given state goes through here,
so the shape of the process lives in one place.
"""
import os
import uuid

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

# Steps an admin drives, and what each one needs.
_ADMIN_STEPS = {
    "verified": lambda **kw: {},
    "commercial_agreed": lambda agreed_amount=8500, **kw: {
        "agreed_amount": agreed_amount
    },
    "slot_booked": lambda scheduled_at="2026-09-01T10:00:00Z", **kw: {
        "scheduled_at": scheduled_at,
        "location_note": "Test venue",
    },
    "attended": lambda **kw: {},
    "in_payment": lambda platform_fee=None, **kw: (
        {} if platform_fee is None else {"platform_fee": platform_fee}
    ),
}

# Steps the brand owns. The admin advance endpoint refuses these by design.
_BRAND_STEPS = ("accepted", "content_approved")

# The happy path, in order.
PIPELINE = [
    "verified",
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "content_submitted",
    "content_approved",
    "in_payment",
    "closed",
]

PAYOUT_DETAILS = {
    "payout_upi": "testcreator@okhdfcbank",
    "payout_account_name": "Test Creator",
    "pan": "AAAPT1234C",
}


def complete_creator_profile(session, *, with_payout=True, suffix=None):
    """Submit a full creator profile so the account can be verified."""
    suf = suffix or uuid.uuid4().hex[:6]
    me = session.get(f"{BASE_URL}/auth/me").json()
    body = {
        "name": f"Creator {suf}",
        "instagram_handle": f"@c_{suf}",
        "instagram_profile_url": f"https://instagram.com/c_{suf}",
        "email": me.get("email"),
        "city": "Bengaluru",
        "address": "Indiranagar",
        "niches": ["cafe"],
        "follower_count": 12000,
        "base_rate": 5000,
    }
    if with_payout:
        body.update(PAYOUT_DETAILS)
    r = session.put(f"{BASE_URL}/creator/profile", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def verify_creator(admin_session, user_id):
    """Approve a creator so they can apply to briefs."""
    r = admin_session.post(f"{BASE_URL}/admin/creators/{user_id}/approve")
    assert r.status_code == 200, r.text
    assert r.json()["verification_status"] == "verified"
    return r.json()


def verify_brand(admin_session, user_id):
    r = admin_session.post(f"{BASE_URL}/admin/brands/{user_id}/verify")
    assert r.status_code == 200, r.text
    return r.json()


def seed_open_campaign(brand_session, *, creators_needed=3, budget=5000):
    brand_session.put(
        f"{BASE_URL}/brand/profile",
        json={
            "business_name": f"Br-{uuid.uuid4().hex[:5]}",
            "category": "fnb",
            "areas": ["Indiranagar"],
        },
    )
    r = brand_session.post(
        f"{BASE_URL}/brand/campaigns",
        json={
            "title": f"Camp-{uuid.uuid4().hex[:6]}",
            "brief": "b",
            "deliverables": "d",
            "budget_per_creator": budget,
            "category": "fnb",
            "area": "Indiranagar",
            "creators_needed": creators_needed,
            # Far enough out that the expiry sweep leaves it alone.
            "start_date": "2026-09-01T00:00:00Z",
            "end_date": "2027-01-01T00:00:00Z",
            "status": "open",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def apply_to_campaign(creator_session, campaign_id, *, quoted_rate=5500):
    r = creator_session.post(
        f"{BASE_URL}/campaigns/{campaign_id}/apply",
        json={"pitch": "eager to collaborate with you all", "quoted_rate": quoted_rate},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def current_state(admin_session, collab_id):
    board = admin_session.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
    for state, rows in board.items():
        if any(row["id"] == collab_id for row in rows):
            return state
    raise AssertionError(f"collaboration {collab_id} not found on the board")


def step(admin_session, brand_session, collab_id, to_state, **kwargs):
    """Take one step, routing brand-owned transitions to the brand endpoints."""
    if to_state in _BRAND_STEPS:
        assert brand_session is not None, (
            f"'{to_state}' is the brand's step — pass a brand session"
        )
        path = "accept" if to_state == "accepted" else "approve_content"
        body = (
            {"agreed_amount": kwargs["agreed_amount"]}
            if to_state == "accepted" and "agreed_amount" in kwargs
            else {}
        )
        r = brand_session.post(
            f"{BASE_URL}/brand/collaborations/{collab_id}/{path}", json=body
        )
        assert r.status_code == 200, f"brand step {to_state} failed: {r.text}"
        return r.json()

    if to_state == "content_submitted":
        raise AssertionError(
            "content_submitted is the creator's step — call submit_content"
        )

    body = _ADMIN_STEPS[to_state](**kwargs)
    # from_state is the write precondition that stops a double advance.
    body["from_state"] = current_state(admin_session, collab_id)
    r = admin_session.post(
        f"{BASE_URL}/admin/collaborations/{collab_id}/advance", json=body
    )
    assert r.status_code == 200, f"admin step {to_state} failed: {r.text}"
    return r.json()


def submit_content(creator_session, collab_id, urls=None):
    r = creator_session.post(
        f"{BASE_URL}/creator/collaborations/{collab_id}/submit_content",
        json={"content_urls": urls or ["https://instagram.com/p/testpost"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def advance_to(admin_session, brand_session, creator_session, collab_id, target_state):
    """Walk a collaboration from `applied` to `target_state`."""
    assert target_state in PIPELINE, f"unknown target state {target_state}"
    for state in PIPELINE:
        if state == "content_submitted":
            submit_content(creator_session, collab_id)
        elif state == "closed":
            # Closing is a consequence of recording the payout, not a step.
            board = admin_session.get(f"{BASE_URL}/admin/collaborations").json()
            row = next(
                r
                for rows in board["by_state"].values()
                for r in rows
                if r["id"] == collab_id
            )
            r = admin_session.post(
                f"{BASE_URL}/admin/payments/{row['payment']['id']}/mark_paid",
                json={"payment_reference": f"UTR{uuid.uuid4().hex[:12].upper()}"},
            )
            assert r.status_code == 200, r.text
        else:
            step(admin_session, brand_session, collab_id, state)
        if state == target_state:
            return
    raise AssertionError(f"unreachable state {target_state}")


def make_collab_in_state(
    admin_session, brand_session, creator_session, creator_user_id, target_state,
    *, creators_needed=3,
):
    """End-to-end setup: verified creator applies to a live brief, then walks the
    pipeline to `target_state`. Returns (collab_id, campaign_id)."""
    complete_creator_profile(creator_session)
    verify_creator(admin_session, creator_user_id)
    campaign_id = seed_open_campaign(brand_session, creators_needed=creators_needed)
    collab_id = apply_to_campaign(creator_session, campaign_id)
    if target_state != "applied":
        advance_to(
            admin_session, brand_session, creator_session, collab_id, target_state
        )
    return collab_id, campaign_id
