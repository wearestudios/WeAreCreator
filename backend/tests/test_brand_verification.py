"""Backend tests for document-based brand representative verification.

Before this, anyone could sign up, type any business name and be one admin
click from the creator directory. The click still exists — but now there is
something to click on: legal entity, registered address, GST, the person
asking and on what authority, and at least one document proving the business
is real.

The half that matters most is the gating. An unverified brand may draft and
may fix its own profile; it may not see, contact or notify a single creator.
These check that endpoint by endpoint, because "we check on publish" was
exactly the hole.
"""
import os
import uuid

import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ORIGIN = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")

# A real PDF and a real PNG, so the magic-byte check has something honest to
# accept. The third is a Windows executable header — the thing the check exists
# to keep out.
PDF = b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd8e40000000049454e44ae426082"
)
NOT_A_DOCUMENT = b"MZ\x90\x00\x03\x00\x00\x00this is an executable"


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
    """A brand that has signed up and done nothing else."""
    s = requests.Session()
    _, user = _register(s, "brand")
    return s, user["id"]


@pytest.fixture
def creator(admin):
    """A verified creator, so there is somebody for a brand to try to reach."""
    s = requests.Session()
    _, user = _register(s, "creator")
    pipeline.complete_creator_profile(s)
    pipeline.verify_creator(admin, user["id"])
    return s, user["id"]


def _full_details(**overrides):
    body = {
        "business_name": f"Third Wave {uuid.uuid4().hex[:5]}",
        "legal_entity_name": "Third Wave Coffee Roasters Private Limited",
        "business_type": "private_limited",
        "category": "fnb",
        "areas": ["Indiranagar"],
        "registered_address": "12 Church Street, Bengaluru 560001",
        "gst_number": "29ABCDE1234F1Z5",
        "website": "thirdwavecoffee.in",
        "instagram_handle": "@thirdwavecoffee",
        "contact_person_name": "Riya Menon",
        "contact_person_designation": "Marketing Manager",
        "contact_email": "riya@thirdwavecoffee.in",
    }
    body.update(overrides)
    return body


def _upload(session, doc_type="gst_certificate", content=PDF, name="gst.pdf", mime="application/pdf"):
    return session.post(
        f"{BASE_URL}/brand/verification/documents",
        data={"doc_type": doc_type},
        files={"file": (name, content, mime)},
    )


def _ready_to_submit(session):
    """Details in, one document up — everything but the submit."""
    r = session.put(f"{BASE_URL}/brand/profile", json=_full_details())
    assert r.status_code == 200, r.text
    assert _upload(session).status_code == 200
    return r.json()


def _fully_verified(session, admin_session, user_id):
    _ready_to_submit(session)
    assert session.post(f"{BASE_URL}/brand/verification/submit").status_code == 200
    r = admin_session.post(f"{BASE_URL}/admin/brands/{user_id}/verify")
    assert r.status_code == 200, r.text


# ---------- 1. The business details ----------

class TestBrandDetails:
    def test_the_new_fields_round_trip(self, brand):
        bs, _ = brand
        r = bs.put(f"{BASE_URL}/brand/profile", json=_full_details())
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["legal_entity_name"] == "Third Wave Coffee Roasters Private Limited"
        assert p["business_type"] == "private_limited"
        assert p["gst_number"] == "29ABCDE1234F1Z5"
        assert p["contact_person_designation"] == "Marketing Manager"
        assert p["website"].startswith("https://")  # scheme added for us
        assert p["instagram_handle"] == "thirdwavecoffee"  # @ stripped

    def test_a_later_save_does_not_wipe_an_earlier_one(self, brand):
        bs, _ = brand
        bs.put(f"{BASE_URL}/brand/profile", json=_full_details())
        p = bs.put(f"{BASE_URL}/brand/profile", json={"areas": ["Koramangala"]}).json()
        assert p["legal_entity_name"] == "Third Wave Coffee Roasters Private Limited"
        assert p["areas"] == ["Koramangala"]

    def test_a_malformed_gstin_is_refused(self, brand):
        bs, _ = brand
        r = bs.put(f"{BASE_URL}/brand/profile", json={"gst_number": "NOPE"})
        assert r.status_code == 422, r.text

    def test_gst_is_optional(self, brand):
        bs, _ = brand
        r = bs.put(f"{BASE_URL}/brand/profile", json=_full_details(gst_number=None))
        assert r.status_code == 200, r.text
        assert r.json()["gst_number"] is None

    def test_the_profile_says_what_is_still_missing(self, brand):
        bs, _ = brand
        v = bs.get(f"{BASE_URL}/brand/verification").json()
        missing = {row["field"] for row in v["missing_fields"]}
        assert {"legal_entity_name", "registered_address", "contact_person_name"} <= missing
        assert v["can_submit"] is False
        assert v["state"] == "unsubmitted"


# ---------- 2. Documents ----------

class TestDocuments:
    def test_a_pdf_is_accepted(self, brand):
        bs, _ = brand
        r = _upload(bs)
        assert r.status_code == 200, r.text
        assert r.json()["doc_type"] == "gst_certificate"
        assert r.json()["mime"] == "application/pdf"

    def test_a_photo_of_a_licence_is_accepted(self, brand):
        bs, _ = brand
        r = _upload(bs, doc_type="fssai_licence", content=PNG, name="licence.png", mime="image/png")
        assert r.status_code == 200, r.text
        assert r.json()["mime"] == "image/png"

    def test_something_that_is_not_a_document_is_refused(self, brand):
        bs, _ = brand
        r = _upload(bs, content=NOT_A_DOCUMENT, name="payload.pdf")
        assert r.status_code == 422, r.text

    def test_a_lying_content_type_does_not_help(self, brand):
        # The extension and the declared mime are the client's; the bytes are not.
        bs, _ = brand
        r = _upload(bs, content=NOT_A_DOCUMENT, name="gst.pdf", mime="application/pdf")
        assert r.status_code == 422, r.text

    def test_an_empty_file_is_refused(self, brand):
        bs, _ = brand
        assert _upload(bs, content=b"").status_code == 422

    def test_several_documents_are_allowed(self, brand):
        bs, _ = brand
        assert _upload(bs, doc_type="gst_certificate").status_code == 200
        assert _upload(bs, doc_type="shop_establishment_licence").status_code == 200
        v = bs.get(f"{BASE_URL}/brand/verification").json()
        assert v["document_count"] == 2

    def test_the_brand_can_see_what_it_sent(self, brand):
        bs, _ = brand
        _upload(bs, name="my-gst-certificate.pdf")
        doc = bs.get(f"{BASE_URL}/brand/verification").json()["documents"][0]
        assert doc["original_name"] == "my-gst-certificate.pdf"
        assert doc["doc_label"] == "GST certificate"
        assert doc["status"] == "submitted"

    def test_the_response_never_carries_a_path_or_a_url(self, brand):
        bs, _ = brand
        body = _upload(bs).text
        assert "stored_name" not in body
        assert "/uploads/" not in body
        assert ".pdf" in body  # the label they gave it, which is fine

    def test_a_document_can_be_replaced_before_verification(self, brand):
        bs, _ = brand
        doc_id = _upload(bs).json()["id"]
        assert bs.delete(f"{BASE_URL}/brand/verification/documents/{doc_id}").status_code == 200
        assert bs.get(f"{BASE_URL}/brand/verification").json()["document_count"] == 0
        assert _upload(bs).status_code == 200

    def test_another_brands_document_is_a_404(self, brand):
        bs, _ = brand
        doc_id = _upload(bs).json()["id"]
        other = requests.Session()
        _register(other, "brand")
        r = other.delete(f"{BASE_URL}/brand/verification/documents/{doc_id}")
        assert r.status_code == 404, r.text

    def test_creators_and_anonymous_callers_cannot_upload(self, creator):
        cs, _ = creator
        assert _upload(cs).status_code == 403
        assert requests.post(f"{BASE_URL}/brand/verification/documents").status_code == 401


# ---------- 3. Submitting ----------

class TestSubmit:
    def test_incomplete_details_are_refused_and_named(self, brand):
        bs, _ = brand
        _upload(bs)
        r = bs.post(f"{BASE_URL}/brand/verification/submit")
        assert r.status_code == 409, r.text
        assert "Legal entity name" in r.text

    def test_no_documents_is_refused_and_says_which_are_accepted(self, brand):
        bs, _ = brand
        bs.put(f"{BASE_URL}/brand/profile", json=_full_details())
        r = bs.post(f"{BASE_URL}/brand/verification/submit")
        assert r.status_code == 409, r.text
        assert "GST certificate" in r.text

    def test_a_complete_submission_is_accepted(self, brand):
        bs, _ = brand
        _ready_to_submit(bs)
        r = bs.post(f"{BASE_URL}/brand/verification/submit")
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "pending_verification"
        assert r.json()["submitted_at"]

    def test_submitting_is_what_puts_them_in_the_queue(self, admin, brand):
        bs, user_id = brand
        _ready_to_submit(bs)
        queue = admin.get(f"{BASE_URL}/admin/brands/pending").json()
        assert all(row["user_id"] != user_id for row in queue), (
            "an unsubmitted brand is not a queue item"
        )
        bs.post(f"{BASE_URL}/brand/verification/submit")
        queue = admin.get(f"{BASE_URL}/admin/brands/pending").json()
        assert any(row["user_id"] == user_id for row in queue)

    def test_an_already_verified_brand_cannot_resubmit(self, admin, brand):
        bs, user_id = brand
        _fully_verified(bs, admin, user_id)
        r = bs.post(f"{BASE_URL}/brand/verification/submit")
        assert r.status_code == 409, r.text


# ---------- 4. The admin review ----------

class TestAdminReview:
    def _submitted(self, bs, admin, user_id):
        _ready_to_submit(bs)
        bs.post(f"{BASE_URL}/brand/verification/submit")
        return next(
            r for r in admin.get(f"{BASE_URL}/admin/brands/pending").json()
            if r["user_id"] == user_id
        )

    def test_the_reviewer_sees_the_business_and_the_person(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        assert row["legal_entity_name"] == "Third Wave Coffee Roasters Private Limited"
        assert row["business_type"] == "private_limited"
        assert row["registered_address"].startswith("12 Church Street")
        assert row["contact_person_name"] == "Riya Menon"
        assert row["contact_person_designation"] == "Marketing Manager"

    def test_the_reviewer_sees_the_documents(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        assert len(row["documents"]) == 1
        assert row["documents"][0]["doc_type"] == "gst_certificate"

    def test_a_work_domain_is_distinguished_from_a_free_one(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        assert row["contact_email_is_free_domain"] is False

    def test_an_admin_can_read_the_document_back(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        doc_id = row["documents"][0]["id"]
        r = admin.get(f"{BASE_URL}/admin/brands/{user_id}/documents/{doc_id}")
        assert r.status_code == 200, r.text
        assert r.content.startswith(b"%PDF-")
        assert r.headers.get("cache-control") == "no-store"

    def test_the_brand_itself_cannot_use_the_admin_route(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        doc_id = row["documents"][0]["id"]
        assert bs.get(f"{BASE_URL}/admin/brands/{user_id}/documents/{doc_id}").status_code == 403

    def test_anonymous_callers_cannot(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        doc_id = row["documents"][0]["id"]
        r = requests.get(f"{BASE_URL}/admin/brands/{user_id}/documents/{doc_id}")
        assert r.status_code == 401, r.text

    def test_a_document_id_cannot_be_read_under_another_brand(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        doc_id = row["documents"][0]["id"]
        other = requests.Session()
        _, other_user = _register(other, "brand")
        r = admin.get(f"{BASE_URL}/admin/brands/{other_user['id']}/documents/{doc_id}")
        assert r.status_code == 404, r.text

    def test_nothing_serves_the_document_publicly(self, admin, brand):
        # The private directory is not mounted. Even the public upload prefix
        # with the same id must not find it.
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        doc_id = row["documents"][0]["id"]
        for path in (f"/uploads/{doc_id}", f"/uploads/{doc_id}.pdf"):
            assert requests.get(f"{ORIGIN}{path}").status_code in (403, 404)

    def test_approving_verifies_and_notifies(self, admin, brand):
        bs, user_id = brand
        self._submitted(bs, admin, user_id)
        r = admin.post(f"{BASE_URL}/admin/brands/{user_id}/verify")
        assert r.status_code == 200, r.text
        assert r.json()["verified"] is True
        assert r.json()["verification_state"] == "verified"
        assert "notification" in r.json()

    def test_rejecting_needs_a_reason(self, admin, brand):
        bs, user_id = brand
        self._submitted(bs, admin, user_id)
        assert admin.post(f"{BASE_URL}/admin/brands/{user_id}/reject", json={}).status_code == 422

    def test_a_rejection_tells_the_brand_exactly_what_to_fix(self, admin, brand):
        bs, user_id = brand
        self._submitted(bs, admin, user_id)
        reason = "The GST certificate is for a different entity than the one named."
        r = admin.post(f"{BASE_URL}/admin/brands/{user_id}/reject", json={"reason": reason})
        assert r.status_code == 200, r.text
        v = bs.get(f"{BASE_URL}/brand/verification").json()
        assert v["state"] == "rejected"
        assert v["verification_reason"] == reason

    def test_a_rejected_brand_can_fix_and_resubmit(self, admin, brand):
        bs, user_id = brand
        self._submitted(bs, admin, user_id)
        admin.post(f"{BASE_URL}/admin/brands/{user_id}/reject", json={"reason": "Illegible scan."})
        assert _upload(bs, doc_type="business_registration").status_code == 200
        r = bs.post(f"{BASE_URL}/brand/verification/submit")
        assert r.status_code == 200, r.text
        # The old verdict must not still be showing next to a fresh request.
        assert bs.get(f"{BASE_URL}/brand/verification").json()["verification_reason"] is None

    def test_one_document_can_be_rejected_on_its_own(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        doc_id = row["documents"][0]["id"]
        r = admin.post(
            f"{BASE_URL}/admin/brands/{user_id}/documents/{doc_id}/review",
            json={"status": "rejected", "reason": "Too blurred to read the GSTIN."},
        )
        assert r.status_code == 200, r.text
        doc = bs.get(f"{BASE_URL}/brand/verification").json()["documents"][0]
        assert doc["status"] == "rejected"
        assert doc["review_note"] == "Too blurred to read the GSTIN."

    def test_rejecting_a_document_needs_a_note(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        doc_id = row["documents"][0]["id"]
        r = admin.post(
            f"{BASE_URL}/admin/brands/{user_id}/documents/{doc_id}/review",
            json={"status": "rejected"},
        )
        assert r.status_code == 422, r.text

    def test_a_verified_brand_cannot_delete_its_evidence(self, admin, brand):
        bs, user_id = brand
        _fully_verified(bs, admin, user_id)
        doc_id = bs.get(f"{BASE_URL}/brand/verification").json()["documents"][0]["id"]
        r = bs.delete(f"{BASE_URL}/brand/verification/documents/{doc_id}")
        assert r.status_code == 409, r.text

    def test_it_is_all_audited(self, admin, brand):
        bs, user_id = brand
        row = self._submitted(bs, admin, user_id)
        admin.get(f"{BASE_URL}/admin/brands/{user_id}/documents/{row['documents'][0]['id']}")
        for action in ("brand.submit_for_verification", "brand.document_upload", "brand.document_view"):
            rows = admin.get(f"{BASE_URL}/admin/audit", params={"action": action}).json()
            assert rows, action


# ---------- 5. The gate ----------

class TestUnverifiedBrandCannotReachCreators:
    """Every route through which an unverified brand could see, contact or
    notify a creator. The old gate was on publish alone."""

    def test_it_cannot_browse_the_creator_directory(self, brand):
        bs, _ = brand
        r = bs.get(f"{BASE_URL}/brand/creators")
        assert r.status_code == 403, r.text
        assert "Verify your business" in r.text

    def test_it_cannot_read_the_directory_filters_either(self, brand):
        # The filter list is distinct cities and niches — small, but it is
        # still the creator base leaking out a side door.
        bs, _ = brand
        assert bs.get(f"{BASE_URL}/brand/creators/filters").status_code == 403

    def test_it_cannot_publish(self, brand):
        bs, _ = brand
        bs.put(f"{BASE_URL}/brand/profile", json=_full_details())
        r = bs.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "Launch night", "brief": "b", "deliverables": "d",
            "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 2, "campaign_type": "launch",
            "event_date": "2027-09-01T00:00:00Z", "status": "draft",
        })
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        assert bs.post(f"{BASE_URL}/brand/campaigns/{cid}/publish").status_code == 403

    def test_it_cannot_read_its_own_applicant_list(self, admin, brand, creator):
        # Reachable if a brand was verified, published, then unverified — the
        # applicants are still there and their names are still creator data.
        bs, user_id = brand
        cs, _ = creator
        _fully_verified(bs, admin, user_id)
        cid = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        pipeline.apply_to_campaign(cs, cid)
        assert bs.get(f"{BASE_URL}/brand/campaigns/{cid}/applicants").status_code == 200

        assert admin.post(f"{BASE_URL}/admin/brands/{user_id}/unverify").status_code == 200
        r = bs.get(f"{BASE_URL}/brand/campaigns/{cid}/applicants")
        assert r.status_code == 403, r.text

    @pytest.mark.parametrize(
        "path,body",
        [
            ("accept", {}),
            ("decline", {"reason": "Not this time"}),
            ("approve_content", {}),
            ("request_changes", {"reason": "Please reshoot"}),
        ],
    )
    def test_it_cannot_act_on_a_collaboration(self, admin, brand, creator, path, body):
        # Each of these notifies the creator — that is messaging them.
        bs, user_id = brand
        cs, creator_id = creator
        _fully_verified(bs, admin, user_id)
        cid = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        collab_id = pipeline.apply_to_campaign(cs, cid)
        assert admin.post(f"{BASE_URL}/admin/brands/{user_id}/unverify").status_code == 200

        r = bs.post(f"{BASE_URL}/brand/collaborations/{collab_id}/{path}", json=body)
        assert r.status_code == 403, r.text

    def test_it_can_still_draft(self, brand):
        # Drafting reaches nobody, and a brand needs something to submit.
        bs, _ = brand
        r = bs.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "Draft", "brief": "b", "deliverables": "d",
            "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 2, "campaign_type": "launch",
            "event_date": "2027-09-01T00:00:00Z", "status": "draft",
        })
        assert r.status_code == 200, r.text

    def test_it_can_still_fix_its_own_profile(self, admin, brand):
        # The only route from rejected to verified runs through here.
        bs, user_id = brand
        _ready_to_submit(bs)
        bs.post(f"{BASE_URL}/brand/verification/submit")
        admin.post(f"{BASE_URL}/admin/brands/{user_id}/reject", json={"reason": "Wrong entity."})
        r = bs.put(f"{BASE_URL}/brand/profile", json={"legal_entity_name": "Correct Entity Pvt Ltd"})
        assert r.status_code == 200, r.text

    def test_a_verified_brand_gets_everything_back(self, admin, brand, creator):
        bs, user_id = brand
        _fully_verified(bs, admin, user_id)
        assert bs.get(f"{BASE_URL}/brand/creators").status_code == 200
        assert bs.get(f"{BASE_URL}/brand/creators/filters").status_code == 200

    def test_the_refusal_says_which_state_they_are_in(self, admin, brand):
        bs, user_id = brand
        never = bs.get(f"{BASE_URL}/brand/creators").text
        assert "Verify your business" in never

        _ready_to_submit(bs)
        bs.post(f"{BASE_URL}/brand/verification/submit")
        waiting = bs.get(f"{BASE_URL}/brand/creators").text
        assert "with the WeAre team" in waiting

        admin.post(f"{BASE_URL}/admin/brands/{user_id}/reject", json={"reason": "Mismatch."})
        refused = bs.get(f"{BASE_URL}/brand/creators").text
        assert "Mismatch." in refused

    def test_another_brands_campaign_is_still_a_404_not_a_403(self, admin, brand, creator):
        # Ownership is checked before verification, so an unverified brand
        # probing ids learns nothing about what exists from the refusal.
        bs, user_id = brand
        cs, _ = creator
        owner = requests.Session()
        _register(owner, "brand")
        cid = pipeline.seed_open_campaign(owner, admin)
        pipeline.apply_to_campaign(cs, cid)
        assert bs.get(f"{BASE_URL}/brand/campaigns/{cid}/applicants").status_code == 404

    def test_contact_details_still_wait_for_an_accepted_collaboration(self, admin, brand, creator):
        # Verification is necessary, not sufficient — a verified brand still
        # doesn't get a phone number off the back of an application.
        bs, user_id = brand
        cs, _ = creator
        _fully_verified(bs, admin, user_id)
        cid = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        pipeline.apply_to_campaign(cs, cid)
        row = bs.get(f"{BASE_URL}/brand/campaigns/{cid}/applicants").json()["applicants"][0]
        assert row["creator"]["phone"] is None
        assert row["creator"]["email"] is None
