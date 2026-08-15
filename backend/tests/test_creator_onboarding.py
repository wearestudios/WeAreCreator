"""Backend tests for the restructured creator onboarding.

Signup used to ask for a profile's worth of detail before anybody had seen the
product, and every stub row it created landed in the vetting queue where no
admin could make a decision about it. Signup is now a name and a number; the
profile is built afterwards over as many sittings as it takes; and an explicit
submission — only possible at 100% — is what asks us to look.

These cover the seams: that a partial save doesn't wipe what came before, that
completeness follows the platforms a creator actually posts on, that submitting
is gated on being finished, that applying is gated on being verified whatever
the UI does, and that the 3-day nudge fires once.
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
def brand():
    s = requests.Session()
    _register(s, "brand")
    return s


@pytest.fixture
def creator():
    """A brand-new creator: name and number only, nothing else filled in."""
    s = requests.Session()
    _, user = _register(s, "creator")
    return s, user["id"]


def _complete_body(session, **overrides):
    """Everything the builder asks an Instagram creator for."""
    suf = uuid.uuid4().hex[:6]
    me = session.get(f"{BASE_URL}/auth/me").json()
    body = {
        "genres": ["food"],
        "platforms": ["instagram"],
        "city": "Bengaluru",
        "full_address": "42 12th Main, Indiranagar, Bengaluru 560038",
        "email": me.get("email") or f"c-{suf}@example.com",
        "niches": ["cafe"],
        "base_rate": 5000,
        "instagram_handle": f"@c_{suf}",
        "instagram_profile_url": f"https://instagram.com/c_{suf}",
    }
    body.update(overrides)
    return body


def _fill_completely(session):
    """Take a creator to 100%, photo included."""
    r = session.put(f"{BASE_URL}/creator/profile", json=_complete_body(session))
    assert r.status_code == 200, r.text
    # The photo saves on its own route, so it needs its own call.
    files = {"file": ("me.png", _PNG, "image/png")}
    r = session.post(f"{BASE_URL}/creator/profile/image", files=files)
    assert r.status_code == 200, r.text
    return r.json()


# The smallest valid PNG, so the upload has something real to accept.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd8e40000000049454e44ae426082"
)


# ---------- 1. Signup asks for almost nothing ----------

class TestSignupIsNameAndNumber:
    def test_a_fresh_creator_has_an_empty_profile(self, creator):
        cs, _ = creator
        profile = cs.get(f"{BASE_URL}/creator/profile").json()
        assert profile["name"]  # from signup
        for field in ("instagram_handle", "city", "full_address", "youtube_url", "base_rate"):
            assert profile[field] in (None, ""), field
        assert profile["niches"] == []
        assert profile["genres"] == []
        assert profile["platforms"] == []

    def test_a_fresh_creator_is_not_in_the_vetting_queue(self, admin, creator):
        # The whole reason this was restructured: a stub nobody can decide on
        # is not a queue item.
        cs, user_id = creator
        queue = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        assert all(row["user_id"] != user_id for row in queue)

    def test_completeness_starts_low_and_names_everything(self, creator):
        cs, _ = creator
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        assert data["percent"] == 0
        assert data["complete"] is False
        assert {"genres", "platforms", "city", "email"} <= {
            row["field"] for row in data["missing"]
        }


# ---------- 2. The profile builder saves partially ----------

class TestPartialSaves:
    def test_one_field_at_a_time_is_accepted(self, creator):
        cs, _ = creator
        r = cs.put(f"{BASE_URL}/creator/profile", json={"city": "Bengaluru"})
        assert r.status_code == 200, r.text
        assert r.json()["city"] == "Bengaluru"

    def test_a_later_save_does_not_wipe_an_earlier_one(self, creator):
        # The builder is filled in over several sittings; each step sends only
        # its own fields.
        cs, _ = creator
        cs.put(f"{BASE_URL}/creator/profile", json={"city": "Bengaluru"})
        cs.put(f"{BASE_URL}/creator/profile", json={"genres": ["food", "travel"]})
        profile = cs.put(
            f"{BASE_URL}/creator/profile", json={"platforms": ["instagram"]}
        ).json()
        assert profile["city"] == "Bengaluru"
        assert profile["genres"] == ["food", "travel"]
        assert profile["platforms"] == ["instagram"]

    def test_an_explicit_null_clears_a_field(self, creator):
        cs, _ = creator
        cs.put(f"{BASE_URL}/creator/profile", json={"city": "Bengaluru"})
        profile = cs.put(f"{BASE_URL}/creator/profile", json={"city": None}).json()
        assert profile["city"] is None

    def test_an_empty_body_changes_nothing(self, creator):
        cs, _ = creator
        before = cs.put(f"{BASE_URL}/creator/profile", json=_complete_body(cs)).json()
        after = cs.put(f"{BASE_URL}/creator/profile", json={}).json()
        for field in ("city", "email", "instagram_handle", "niches", "genres", "base_rate"):
            assert after[field] == before[field], field

    def test_payout_details_survive_a_save_that_did_not_mention_them(self, creator):
        cs, _ = creator
        cs.put(f"{BASE_URL}/creator/profile", json=pipeline.PAYOUT_DETAILS)
        profile = cs.put(f"{BASE_URL}/creator/profile", json={"city": "Pune"}).json()
        assert profile["payout_upi"] == pipeline.PAYOUT_DETAILS["payout_upi"]
        assert profile["pan"] == pipeline.PAYOUT_DETAILS["pan"]
        assert profile["payout_ready"] is True

    def test_saving_never_puts_anybody_in_the_queue(self, admin, creator):
        cs, user_id = creator
        _fill_completely(cs)
        queue = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        assert all(row["user_id"] != user_id for row in queue), (
            "a saved profile is not a submitted one"
        )

    def test_a_youtube_link_round_trips(self, creator):
        cs, _ = creator
        profile = cs.put(
            f"{BASE_URL}/creator/profile",
            json={"platforms": ["youtube"], "youtube_url": "https://youtube.com/@someone"},
        ).json()
        assert profile["youtube_url"] == "https://youtube.com/@someone"

    def test_a_link_that_is_not_youtube_is_refused(self, creator):
        cs, _ = creator
        r = cs.put(f"{BASE_URL}/creator/profile", json={"youtube_url": "https://vimeo.com/x"})
        assert r.status_code == 422, r.text


# ---------- 3. Completeness ----------

class TestCompleteness:
    def test_it_climbs_as_fields_are_filled(self, creator):
        cs, _ = creator
        start = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        cs.put(f"{BASE_URL}/creator/profile", json={"city": "Bengaluru", "genres": ["food"]})
        later = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        assert later["percent"] > start["percent"]

    def test_an_instagram_creator_reaches_a_hundred(self, creator):
        cs, _ = creator
        _fill_completely(cs)
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        assert data["percent"] == 100, data["missing"]
        assert data["complete"] is True

    def test_a_youtube_creator_is_asked_for_the_channel(self, creator):
        cs, _ = creator
        _fill_completely(cs)
        cs.put(
            f"{BASE_URL}/creator/profile",
            json={"platforms": ["instagram", "youtube"]},
        )
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        assert data["complete"] is False
        assert "youtube_url" in {row["field"] for row in data["missing"]}

    def test_adding_the_channel_completes_them_again(self, creator):
        cs, _ = creator
        _fill_completely(cs)
        cs.put(
            f"{BASE_URL}/creator/profile",
            json={
                "platforms": ["instagram", "youtube"],
                "youtube_url": "https://youtube.com/@someone",
            },
        )
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        assert data["complete"] is True

    def test_payout_details_are_not_part_of_it(self, creator):
        # A PAN must not be the price of being looked at.
        cs, _ = creator
        _fill_completely(cs)
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        assert data["complete"] is True
        assert cs.get(f"{BASE_URL}/creator/profile").json()["payout_ready"] is False


# ---------- 4. Submitting for review ----------

class TestSubmitForReview:
    def test_an_unfinished_profile_is_refused_and_told_why(self, creator):
        cs, _ = creator
        cs.put(f"{BASE_URL}/creator/profile", json={"city": "Bengaluru"})
        r = cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        assert r.status_code == 409, r.text
        assert "Still needed" in r.text

    def test_a_finished_profile_is_accepted(self, creator):
        cs, _ = creator
        _fill_completely(cs)
        r = cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        assert r.status_code == 200, r.text
        assert r.json()["verification_status"] == "pending"
        assert r.json()["submitted_for_review_at"]

    def test_submitting_is_what_puts_them_in_the_queue(self, admin, creator):
        cs, user_id = creator
        _fill_completely(cs)
        cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        queue = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        assert any(row["user_id"] == user_id for row in queue)

    def test_an_edit_after_submitting_keeps_them_in_the_queue(self, admin, creator):
        cs, user_id = creator
        _fill_completely(cs)
        cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        cs.put(f"{BASE_URL}/creator/profile", json={"base_rate": 7000})
        queue = admin.get(f"{BASE_URL}/admin/creators/pending").json()
        assert any(row["user_id"] == user_id for row in queue)

    def test_a_verified_creator_is_refused(self, admin, creator):
        cs, user_id = creator
        _fill_completely(cs)
        cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        pipeline.verify_creator(admin, user_id)
        r = cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        assert r.status_code == 409, r.text
        assert "already verified" in r.text.lower()

    def test_a_rejected_creator_can_fix_and_resubmit(self, admin, creator):
        cs, user_id = creator
        _fill_completely(cs)
        cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        r = admin.post(
            f"{BASE_URL}/admin/creators/{user_id}/reject",
            json={"reason": "Handle didn't match the profile."},
        )
        assert r.status_code == 200, r.text

        cs.put(f"{BASE_URL}/creator/profile", json={"instagram_handle": "@fixed.handle"})
        r = cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        assert r.status_code == 200, r.text
        # The old verdict must not still be on screen next to a fresh request.
        assert cs.get(f"{BASE_URL}/creator/profile").json()["verification_status"] == "pending"

    def test_it_lands_in_the_audit_log(self, admin, creator):
        cs, _ = creator
        _fill_completely(cs)
        cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        rows = admin.get(
            f"{BASE_URL}/admin/audit", params={"action": "creator.submit_for_review"}
        ).json()
        assert rows

    def test_the_creator_gets_a_confirmation(self, creator):
        cs, _ = creator
        _fill_completely(cs)
        cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        events = [
            n["event"] for n in cs.get(f"{BASE_URL}/notifications").json()["notifications"]
        ]
        assert "profile_submitted" in events


# ---------- 5. Gating ----------

class TestBrowsingIsOpenApplyingIsNot:
    def test_an_unverified_creator_can_browse(self, brand, admin, creator):
        cs, _ = creator
        pipeline.seed_open_campaign(brand, admin)
        r = cs.get(f"{BASE_URL}/campaigns")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_an_unverified_creator_can_open_a_brief(self, brand, admin, creator):
        cs, _ = creator
        cid = pipeline.seed_open_campaign(brand, admin)
        assert cs.get(f"{BASE_URL}/campaigns/{cid}").status_code == 200

    def test_applying_is_refused_server_side(self, brand, admin, creator):
        cs, _ = creator
        cid = pipeline.seed_open_campaign(brand, admin)
        r = cs.post(
            f"{BASE_URL}/campaigns/{cid}/apply",
            json={"pitch": "I would love this one", "quoted_rate": 5000},
        )
        assert r.status_code == 403, r.text

    def test_someone_still_building_is_told_what_is_left(self, brand, admin, creator):
        cs, _ = creator
        cs.put(f"{BASE_URL}/creator/profile", json={"platforms": ["instagram"]})
        cid = pipeline.seed_open_campaign(brand, admin)
        r = cs.post(
            f"{BASE_URL}/campaigns/{cid}/apply",
            json={"pitch": "I would love this one", "quoted_rate": 5000},
        )
        assert r.status_code == 403
        assert "Finish your profile" in r.text
        assert "Instagram handle" in r.text

    def test_someone_waiting_on_us_is_told_that_instead(self, brand, admin, creator):
        cs, _ = creator
        _fill_completely(cs)
        cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        cid = pipeline.seed_open_campaign(brand, admin)
        r = cs.post(
            f"{BASE_URL}/campaigns/{cid}/apply",
            json={"pitch": "I would love this one", "quoted_rate": 5000},
        )
        assert r.status_code == 403
        assert "with the WeAre team" in r.text

    def test_a_verified_creator_may_apply(self, brand, admin, creator):
        cs, user_id = creator
        _fill_completely(cs)
        cs.post(f"{BASE_URL}/creator/profile/submit-for-review")
        pipeline.verify_creator(admin, user_id)
        cid = pipeline.seed_open_campaign(brand, admin)
        r = cs.post(
            f"{BASE_URL}/campaigns/{cid}/apply",
            json={"pitch": "I would love this one", "quoted_rate": 5000},
        )
        assert r.status_code in (200, 201), r.text


# ---------- 6. The nudge ----------

class TestProfileNudge:
    def test_a_fresh_signup_is_not_chased(self, admin, creator):
        # Three days, not three minutes. Somebody who signed up an hour ago is
        # not stalled, they're busy.
        cs, _ = creator
        report = admin.post(f"{BASE_URL}/admin/jobs/creator-nudges").json()
        assert report["sent"] == 0
        events = [
            n["event"] for n in cs.get(f"{BASE_URL}/notifications").json()["notifications"]
        ]
        assert "profile_nudge" not in events

    def test_a_manual_run_is_allowed_and_audited(self, admin):
        r = admin.post(f"{BASE_URL}/admin/jobs/creator-nudges")
        assert r.status_code == 200, r.text
        assert set(r.json()) == {"considered", "sent", "skipped", "failed"}
        rows = admin.get(
            f"{BASE_URL}/admin/audit", params={"action": "job.creator_nudges"}
        ).json()
        assert rows

    def test_running_it_twice_never_double_sends(self, admin):
        # The claim is the write, so a second pass finds nothing left to claim.
        first = admin.post(f"{BASE_URL}/admin/jobs/creator-nudges").json()
        second = admin.post(f"{BASE_URL}/admin/jobs/creator-nudges").json()
        assert second["sent"] == 0, (first, second)

    def test_only_an_admin_can_run_it(self, brand, creator):
        cs, _ = creator
        assert cs.post(f"{BASE_URL}/admin/jobs/creator-nudges").status_code == 403
        assert brand.post(f"{BASE_URL}/admin/jobs/creator-nudges").status_code == 403
