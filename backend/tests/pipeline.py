"""Shared helpers for walking a collaboration through the pipeline.

The pipeline is no longer a single admin clicking Advance nine times: applying
requires a verified creator, and two of the steps belong to the brand. Every
integration test that needs a collaboration in a given state goes through here,
so the shape of the process lives in one place.
"""
import os
import uuid

# Read leniently so the unit suite can import this module to check the
# ownership tables below without a server. A real call against the
# placeholder fails on the first request, naming the variable.
BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL", "http://REACT_APP_BACKEND_URL-is-unset")
    .rstrip("/")
    + "/api"
)

# Who moves each step. Every state on a ladder is claimed by exactly one of
# these, and `check_ownership` fails loudly when that stops being true.
#
# This harness ran for a long time with `slot_booked` listed as an admin step
# after the server had made booking the creator's alone: the admin advance
# answered 409 and nothing past `commercial_agreed` was reachable from any
# integration test. The tables are what the server's own sets are checked
# against in `tests/unit/test_pipeline_ownership.py`, so the next ownership
# change fails there, in CI, rather than deep inside a run nobody gates on.

# Steps an admin drives through `/admin/collaborations/{id}/advance`, and what
# each one needs. `commercial_agreed` sends no amount by default: on a fixed
# brief the server resolves the fee from the budget and refuses any other
# figure, so a hardcoded number here is a 422 on every brief that is not
# priced at exactly that.
_ADMIN_STEPS = {
    "verified": lambda **kw: {},
    "commercial_agreed": lambda agreed_amount=None, **kw: (
        {} if agreed_amount is None else {"agreed_amount": agreed_amount}
    ),
    "attended": lambda **kw: {},
    "in_payment": lambda platform_fee=None, **kw: (
        {} if platform_fee is None else {"platform_fee": platform_fee}
    ),
}

# Steps whoever runs the campaign owns: the brand on a brand-run brief, WeAre
# on a weare-run one (every brand-posted brief, now). The admin advance
# endpoint refuses these on a brand-run brief by design, and on a weare-run
# one it would skip the disclosure check `approve_content` makes — so the
# harness always goes through the brand route, as the runner.
_BRAND_STEPS = ("accepted", "content_approved")

# Steps only the creator can take. The admin advance refuses `slot_booked`
# outright: nobody books on a creator's behalf.
_CREATOR_STEPS = ("slot_booked", "draft_submitted", "content_submitted")

# The draft review, decided by whoever `execution_owner` names.
_REVIEWER_STEPS = ("draft_approved",)

# Closing is a consequence of recording the payout, not an advance — but it is
# an admin's act, so it is claimed here rather than left unowned.
_PAYOUT_STEPS = ("closed",)

OWNERS = {
    "admin": tuple(_ADMIN_STEPS) + _PAYOUT_STEPS,
    "brand": _BRAND_STEPS,
    "creator": _CREATOR_STEPS,
    "reviewer": _REVIEWER_STEPS,
}

# The happy path on a campaign without the draft gate, in order, from the
# first step after `applied`. Mirrors `_collab_ladder` for a personal table;
# `ladder_for` refuses to walk a collaboration whose server ladder differs.
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

# The same path through the draft gate: the creator shows the work before it
# goes live, and the reviewer approves it, between attending and posting.
DRAFT_PIPELINE = [
    "verified",
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "draft_submitted",
    "draft_approved",
    "content_submitted",
    "content_approved",
    "in_payment",
    "closed",
]


def check_ownership(ladder):
    """Fail, naming the state, unless every step has exactly one owner."""
    problems = []
    for state in ladder:
        claimed_by = [who for who, states in OWNERS.items() if state in states]
        if not claimed_by:
            problems.append(f"'{state}' is claimed by nobody")
        elif len(claimed_by) > 1:
            problems.append(
                f"'{state}' is claimed by more than one owner: {', '.join(claimed_by)}"
            )
    if problems:
        raise AssertionError(
            "the pipeline harness disagrees with itself about who moves a "
            "collaboration — " + "; ".join(problems)
        )


# At import, so a bad edit to the tables fails every test that uses them
# rather than one step deep inside whichever test happened to reach it.
check_ownership(PIPELINE)
check_ownership(DRAFT_PIPELINE)

# A slot inside the seeded campaign's window (2025-01-01 → 2027-01-01): a
# Tuesday from 10:00 to 18:00 IST, and a time inside it for a personal table,
# where the creator names when they will arrive.
_SLOT_STARTS = "2026-12-01T04:30:00Z"
_SLOT_ENDS = "2026-12-01T12:30:00Z"
_SLOT_ARRIVAL = "2026-12-01T06:30:00Z"

# The smallest valid PNG, so the photo upload has something real to accept.
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd8e40000000049454e44ae426082"
)

PAYOUT_DETAILS = {
    "payout_upi": "testcreator@okhdfcbank",
    "payout_account_name": "Test Creator",
    "pan": "AAAPT1234C",
}


def complete_creator_profile(session, *, with_payout=True, suffix=None, submit=True):
    """Fill a creator profile in and hand it to the team.

    Saving and submitting are separate acts now — a saved profile sits with the
    creator, and only `/creator/profile/submit-for-review` puts them in the
    vetting queue. Almost every caller wants a creator an admin can approve, so
    this does both; pass `submit=False` to stop at the save.

    The body is everything completeness asks an Instagram creator for, minus
    the photo (its own endpoint), so submitting is accepted.
    """
    suf = suffix or uuid.uuid4().hex[:6]
    me = session.get(f"{BASE_URL}/auth/me").json()
    body = {
        "name": f"Creator {suf}",
        "instagram_handle": f"@c_{suf}",
        "instagram_profile_url": f"https://instagram.com/c_{suf}",
        "email": me.get("email"),
        "city": "Bengaluru",
        "address": "Indiranagar",
        "full_address": f"{suf} 12th Main, Indiranagar, Bengaluru 560038",
        "niches": ["cafe"],
        "genres": ["food"],
        "platforms": ["instagram"],
        "follower_count": 12000,
        "base_rate": 5000,
    }
    if with_payout:
        body.update(PAYOUT_DETAILS)
    r = session.put(f"{BASE_URL}/creator/profile", json=body)
    assert r.status_code == 200, r.text
    profile = r.json()

    if submit:
        # The photo is the last thing completeness wants, and it has its own
        # route because a file upload is a different kind of write.
        files = {"file": ("me.png", _TINY_PNG, "image/png")}
        img = session.post(f"{BASE_URL}/creator/profile/image", files=files)
        assert img.status_code == 200, img.text
        sub = session.post(f"{BASE_URL}/creator/profile/submit-for-review")
        # 409 means they were already verified, which is not a failure here.
        assert sub.status_code in (200, 409), sub.text
        profile = session.get(f"{BASE_URL}/creator/profile").json()
    return profile


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


def user_id_of(session):
    r = session.get(f"{BASE_URL}/auth/me")
    assert r.status_code == 200, r.text
    return r.json()["id"]


def setup_brand(brand_session, admin_session, *, business_name=None):
    """Give a brand a profile and get it verified.

    An unverified brand can only draft, so every test that needs a live campaign
    needs this first.
    """
    r = brand_session.put(
        f"{BASE_URL}/brand/profile",
        json={
            "business_name": business_name or f"Br-{uuid.uuid4().hex[:5]}",
            "category": "fnb",
            "areas": ["Indiranagar"],
        },
    )
    assert r.status_code == 200, r.text
    uid = user_id_of(brand_session)
    verify_brand(admin_session, uid)
    return uid


def submit_campaign(brand_session, campaign_id):
    """Hand a draft to us for review. (The route is still called `publish`.)"""
    r = brand_session.post(f"{BASE_URL}/brand/campaigns/{campaign_id}/publish")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_review"
    return r.json()


def approve_campaign(admin_session, campaign_id):
    """Publish a reviewed campaign. This is the only route to the creator feed."""
    r = admin_session.post(f"{BASE_URL}/admin/campaigns/{campaign_id}/approve")
    assert r.status_code == 200, r.text
    return r.json()["status"]


def seed_open_campaign(
    brand_session, admin_session, *, creators_needed=3, budget=5000, brand_ready=False,
    requires_draft_approval=None, requires_slot_confirmation=None,
):
    """A campaign creators can actually see, through the real gates.

    Campaigns no longer go live because the payload said so: the brand drafts,
    submits, and an admin approves. Pass `brand_ready=True` if the caller has
    already set up and verified the brand.

    The two `requires_*` flags are sent only when given, so the server's own
    defaults apply otherwise. Note the draft gate's default is *off* for a
    brand-posted brief, because every one of those is weare-run — pass
    `requires_draft_approval=True` to get the draft ladder.
    """
    if not brand_ready:
        setup_brand(brand_session, admin_session)

    gates = {}
    if requires_draft_approval is not None:
        gates["requires_draft_approval"] = requires_draft_approval
    if requires_slot_confirmation is not None:
        gates["requires_slot_confirmation"] = requires_slot_confirmation

    r = brand_session.post(
        f"{BASE_URL}/brand/campaigns",
        json={
            **gates,
            "title": f"Camp-{uuid.uuid4().hex[:6]}",
            "brief": "b",
            "deliverables": "d",
            "budget_per_creator": budget,
            "category": "fnb",
            "area": "Indiranagar",
            "creators_needed": creators_needed,
            # A window that already opened, so approval lands on "open" rather
            # than "upcoming"; far enough out that the expiry sweep leaves it.
            "campaign_type": "personal_table",
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2027-01-01T00:00:00Z",
            "status": "draft",
        },
    )
    assert r.status_code == 200, r.text
    campaign_id = r.json()["id"]

    submit_campaign(brand_session, campaign_id)
    status = approve_campaign(admin_session, campaign_id)
    assert status == "open", f"expected an open campaign, got {status}"
    return campaign_id


def apply_to_campaign(creator_session, campaign_id, *, quoted_rate=5500):
    r = creator_session.post(
        f"{BASE_URL}/campaigns/{campaign_id}/apply",
        json={"pitch": "eager to collaborate with you all", "quoted_rate": quoted_rate},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]




def collab_detail(admin_session, collab_id):
    """The admin's view of one collaboration: state, slot, payment, ladder."""
    r = admin_session.get(f"{BASE_URL}/admin/collaborations/{collab_id}")
    assert r.status_code == 200, r.text
    return r.json()


def current_state(admin_session, collab_id):
    return collab_detail(admin_session, collab_id)["collaboration"]["state"]


def campaign_of(admin_session, collab_id):
    """The campaign a collaboration belongs to, as the admin console reads it."""
    campaign_id = collab_detail(admin_session, collab_id)["collaboration"]["campaign"]["id"]
    r = admin_session.get(f"{BASE_URL}/admin/campaigns/{campaign_id}")
    assert r.status_code == 200, r.text
    return r.json()["campaign"]


def runner_session(campaign, admin_session, brand_session):
    """Whoever runs the campaign, which decides who takes the brand-owned steps.

    On a weare-run brief the brand cannot even see an application until we
    have agreed a fee — the accept route answers it 404 — so the runner is us.
    """
    if campaign.get("execution_owner") == "brand":
        assert brand_session is not None, "a brand-run campaign needs a brand session"
        return brand_session
    return admin_session


def ensure_slot(admin_session, campaign_id):
    """A slot with room on it, created the way a manager creates one."""
    r = admin_session.post(
        f"{BASE_URL}/manager/campaigns/{campaign_id}/slots",
        json={"starts_at": _SLOT_STARTS, "ends_at": _SLOT_ENDS, "capacity": 5},
    )
    assert r.status_code in (200, 201), f"creating a slot failed: {r.text}"
    return r.json()["id"]


def book_slot(admin_session, brand_session, creator_session, collab_id):
    """Book a slot the way a creator does, then have it answered if it must be.

    The creator lists the slots on their campaign and takes one through the
    route `SlotPicker` uses. On a personal table they also name the time they
    will arrive. If the campaign asks for the booking handshake, whoever runs
    it confirms through `_answer_slot_request`'s route — the manager route on
    a weare-run brief, the brand route on a brand-run one.
    """
    assert creator_session is not None, "'slot_booked' is the creator's step — pass a creator session"
    campaign = campaign_of(admin_session, collab_id)

    r = creator_session.get(f"{BASE_URL}/creator/campaigns/{campaign['id']}/slots")
    assert r.status_code == 200, f"listing slots failed: {r.text}"
    listing = r.json()
    open_slots = [s for s in listing.get("slots", []) if not s.get("is_full")]
    if open_slots:
        slot_id = open_slots[0]["id"]
    else:
        slot_id = ensure_slot(admin_session, campaign["id"])

    body = {"slot_id": slot_id}
    if campaign.get("campaign_type") == "personal_table":
        body["preferred_time"] = _SLOT_ARRIVAL
    r = creator_session.post(
        f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot", json=body
    )
    assert r.status_code == 200, f"creator booking failed: {r.text}"

    if campaign.get("requires_slot_confirmation"):
        runner = runner_session(campaign, admin_session, brand_session)
        prefix = "brand" if campaign.get("execution_owner") == "brand" else "manager"
        r = runner.post(f"{BASE_URL}/{prefix}/collaborations/{collab_id}/slot/confirm")
        assert r.status_code == 200, f"confirming the booking failed: {r.text}"
    return r.json()


def submit_draft(creator_session, collab_id, url="https://drive.example.com/draft.mp4"):
    """Show the work before it goes live — the unlisted-link door."""
    r = creator_session.post(
        f"{BASE_URL}/drafts/{collab_id}/link", json={"draft_url": url}
    )
    assert r.status_code == 200, f"submitting the draft failed: {r.text}"
    return r.json()


def approve_draft(reviewer_session, collab_id):
    """Approve the draft, confirming on the record that it carries the label."""
    r = reviewer_session.post(
        f"{BASE_URL}/drafts/{collab_id}/approve", json={"disclosure_confirmed": True}
    )
    assert r.status_code == 200, f"approving the draft failed: {r.text}"
    return r.json()


def step(admin_session, brand_session, collab_id, to_state, **kwargs):
    """Take one step, routing each transition to whoever owns it.

    Creator and reviewer steps raise with a pointer to their helper, the way
    `content_submitted` always has: they need a different session and a
    different route, and a silent wrong route is how this file broke before.
    """
    if to_state in _BRAND_STEPS:
        campaign = campaign_of(admin_session, collab_id)
        runner = runner_session(campaign, admin_session, brand_session)
        if to_state == "accepted":
            path = "accept"
            body = (
                {"agreed_amount": kwargs["agreed_amount"]}
                if "agreed_amount" in kwargs
                else {}
            )
        else:
            # The second disclosure checkpoint; the route refuses without it.
            path, body = "approve_content", {"disclosure_confirmed": True}
        r = runner.post(f"{BASE_URL}/brand/collaborations/{collab_id}/{path}", json=body)
        assert r.status_code == 200, f"runner step {to_state} failed: {r.text}"
        return r.json()

    if to_state == "slot_booked":
        raise AssertionError(
            "slot_booked is the creator's step — call book_slot (the admin "
            "advance refuses it: nobody books on a creator's behalf)"
        )
    if to_state == "draft_submitted":
        raise AssertionError("draft_submitted is the creator's step — call submit_draft")
    if to_state == "draft_approved":
        raise AssertionError("draft_approved is the reviewer's step — call approve_draft")
    if to_state == "content_submitted":
        raise AssertionError(
            "content_submitted is the creator's step — call submit_content"
        )
    if to_state not in _ADMIN_STEPS:
        raise AssertionError(f"no owner in the harness for '{to_state}'")

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


def mark_paid(admin_session, collab_id):
    """Record the payout, which is what closes the collaboration."""
    payment = collab_detail(admin_session, collab_id)["payment"]
    assert payment, "no payment row to mark paid — is the collaboration in_payment?"
    r = admin_session.post(
        f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
        json={"payment_reference": f"UTR{uuid.uuid4().hex[:12].upper()}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def ladder_for(admin_session, collab_id):
    """The harness ladder this collaboration walks, chosen from the server's.

    The server ships `_collab_ladder(campaign)` as `state_order`; this picks
    the harness ladder that matches it and refuses to guess otherwise — a
    campaign type whose ladder has delivery or venue steps the harness does
    not know is a gap to fill here, not one to walk past.
    """
    server = collab_detail(admin_session, collab_id)["state_order"]
    for ladder in (PIPELINE, DRAFT_PIPELINE):
        if server == ["applied"] + ladder:
            return ladder
    raise AssertionError(
        f"the server walks this collaboration through {server}, which matches "
        "neither PIPELINE nor DRAFT_PIPELINE — add the ladder to the harness"
    )


def walk(admin_session, brand_session, creator_session, collab_id):
    """Take each step on the collaboration's own ladder, yielding as it lands."""
    ladder = ladder_for(admin_session, collab_id)
    check_ownership(ladder)
    campaign = None
    for state in ladder:
        if state == "slot_booked":
            book_slot(admin_session, brand_session, creator_session, collab_id)
        elif state == "draft_submitted":
            submit_draft(creator_session, collab_id)
        elif state == "draft_approved":
            campaign = campaign or campaign_of(admin_session, collab_id)
            approve_draft(
                runner_session(campaign, admin_session, brand_session), collab_id
            )
        elif state == "content_submitted":
            submit_content(creator_session, collab_id)
        elif state == "closed":
            mark_paid(admin_session, collab_id)
        else:
            step(admin_session, brand_session, collab_id, state)
        yield state


def advance_to(admin_session, brand_session, creator_session, collab_id, target_state):
    """Walk a collaboration from `applied` to `target_state`.

    The ladder comes from the campaign, so a draft-gated campaign walks the
    draft steps and one without the gate does not.
    """
    ladder = ladder_for(admin_session, collab_id)
    assert target_state in ladder, (
        f"'{target_state}' is not on this collaboration's ladder: {ladder}"
    )
    for state in walk(admin_session, brand_session, creator_session, collab_id):
        if state == target_state:
            return
    raise AssertionError(f"unreachable state {target_state}")


def make_collab_in_state(
    admin_session, brand_session, creator_session, creator_user_id, target_state,
    *, creators_needed=3, requires_draft_approval=None, requires_slot_confirmation=None,
):
    """End-to-end setup: verified creator applies to a live brief, then walks the
    pipeline to `target_state`. Returns (collab_id, campaign_id)."""
    complete_creator_profile(creator_session)
    verify_creator(admin_session, creator_user_id)
    campaign_id = seed_open_campaign(
        brand_session, admin_session, creators_needed=creators_needed,
        requires_draft_approval=requires_draft_approval,
        requires_slot_confirmation=requires_slot_confirmation,
    )
    collab_id = apply_to_campaign(creator_session, campaign_id)
    if target_state != "applied":
        advance_to(
            admin_session, brand_session, creator_session, collab_id, target_state
        )
    return collab_id, campaign_id
