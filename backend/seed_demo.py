#!/usr/bin/env python3
"""Wipe the demo database and fill it with a marketplace that makes sense.

    ALLOW_OTP_SIMULATION=true python seed_demo.py --yes

**What was wrong with the old seed.** `seed_personas.py` made seven accounts
and one campaign. That is enough to sign in and not enough to look at: every
list was empty, the health panel had nothing to be unhealthy about, the
reliability band said "new" for everybody because nobody had ever finished
anything, and you could not tell a screen that was working from one that was
broken. Half the bugs this product has shipped were invisible on data that
thin.

So this seeds an operation with a history. Five brands across every
verification state, twelve creators with real profiles and reliability records
earned from real collaborations, fifteen campaigns across every status, and
collaborations sitting at **every state in `COLLAB_STATE_ORDER` and all five
terminal exits** — with the slots, invitations, questions, notes, ratings,
performance readings, payments, invoices, one live dispute and one live
takedown that hang off them.

Every persona phone number `seed_personas.py` documented still works, and this
file supersedes it.

## The three fences, and why the third one exists

1. `_simulation_allowed()` — the same gate the OTP log uses. These accounts
   sign in by WhatsApp code, and without simulation you could not read one, so
   they would be unusable anyway. The gate and the usefulness are one fact.
2. `_is_production()` — which reads an **unset** `APP_ENV` as production, the
   safe direction for a script whose first act is a delete.
3. **It says what it is about to destroy and waits to be told to.** The first
   two fences are about the environment; this one is about the person. A
   mistyped `DB_NAME` passes both of the others, and "delete all test data" is
   only ever one character away from deleting somebody's real one.

It names the collections it clears rather than dropping the database, so the
list is reviewable in the diff and anything else in there survives.

**A script, not an endpoint.** A route that mints pre-verified accounts with
known phone numbers is a backdoor whether or not it is guarded, and it would
sit in the route table in production one misconfiguration from reachable.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import server  # noqa: E402  (env has to load first)

# Deterministic, so two runs produce the same numbers and a screenshot taken
# last week still matches. Randomness in a fixture is a diff nobody can read.
random.seed(20260101)

NOW = datetime.now(timezone.utc)


def ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def ahead(days: float) -> datetime:
    return NOW + timedelta(days=days)


# Every collection the app writes to. Listed rather than discovered, so adding
# one to `server.py` and forgetting it here shows up as data that survives a
# wipe — which is exactly the confusing state this script exists to end.
#
# `otp_codes` is included: a code issued against a phone number that no longer
# exists is litter, and leaving it means the first login after a reseed can
# hit a stale hourly-limit counter.
WIPED = (
    "users",
    "creator_profiles",
    "brand_profiles",
    "brand_documents",
    "campaigns",
    "campaign_slots",
    "campaign_invitations",
    "campaign_questions",
    "campaign_templates",
    "collaborations",
    # Pitches taken before a creator was verified. Their own collection
    # rather than a state on `collaborations` — see `_hold_application`.
    "held_applications",
    "collaboration_notes",
    "collaboration_ratings",
    "content_performance",
    "creator_lists",
    "payments",
    "deletion_requests",
    "notifications",
    "audit_log",
    "otp_codes",
    "instagram_connections",
    "instagram_oauth_states",
    "instagram_stats_cache",
    # Operator settings go too: a reset should put the SLA targets, the
    # verification validity, the payment terms and the reschedule limit back to
    # the defaults in the code. Keeping them would mean a fresh database
    # quietly running on last month's argument.
    "platform_settings",
    # And the counters, or the first seeded brand is BRD-0043 because of a
    # database that no longer exists.
    "reference_counters",
)

# Fake numbers in an obviously-patterned block, so a real one can never be
# mistaken for a seeded one — and `+9199000000` in a production database is a
# self-announcing bug.
def phone(n: int) -> str:
    return f"+9199000000{n:02d}"


# ---------------------------------------------------------------------------
# The cast
# ---------------------------------------------------------------------------

# Neighbourhoods people actually name when they say where a shoot is.
AREAS = ["Indiranagar", "Koramangala", "Jayanagar", "Whitefield", "HSR Layout",
         "Malleshwaram", "Church Street"]

BRANDS = [
    {
        "key": "thirdwave",
        "phone": phone(4),
        "manager": "Riya Nair",
        "designation": "Marketing lead",
        "business": "Thirdwave Coffee",
        "category": "fnb",
        "area": "Indiranagar",
        "tagline": "Third-wave coffee, four rooms in Bengaluru.",
        "about": (
            "We roast in Jayanagar and pour in four rooms across the city. "
            "We work with creators who actually drink coffee and can tell a "
            "washed Ethiopian from a natural one on camera."
        ),
        # Verified, active, runs its own campaigns. The default happy path.
        "state": "verified",
        "verified_days_ago": 40,
        "content_types": ["reel", "story"],
        "preferred_follower_tier": "mid",
        "typical_budget_band": "5k_15k",
        "outlets": [
            {"name": "Indiranagar", "address": "1102, 12th Main, Indiranagar",
             "area": "Indiranagar", "city": "Bengaluru"},
            {"name": "Church Street", "address": "42 Church Street",
             "area": "Church Street", "city": "Bengaluru"},
        ],
    },
    {
        "key": "copperclay",
        "phone": phone(5),
        "manager": "Sam Iyer",
        "designation": "Founder",
        "business": "Copper & Clay",
        "category": "fnb",
        "area": "Koramangala",
        "tagline": "South Indian small plates, natural wine.",
        "about": "Eighteen seats in Koramangala. Menu changes every Tuesday.",
        # Documents in, waiting on us. Exercises the verification gate and the
        # brand review queue.
        "state": "pending_verification",
        "content_types": ["reel"],
        "preferred_follower_tier": "micro",
        "typical_budget_band": "under_5k",
        "outlets": [],
    },
    {
        "key": "blume",
        "phone": phone(8),
        "manager": "Nikhil Bose",
        "designation": "Brand manager",
        "business": "Blume Skincare",
        "category": "beauty",
        "area": "HSR Layout",
        "tagline": "Barrier-first skincare, made in Bengaluru.",
        "about": (
            "Six products, no ten-step routine. We hand our campaigns to the "
            "WeAre team because we would rather make the serum than run a "
            "shortlist."
        ),
        # Verified, hands campaigns to us, and owes us money — so the invoice
        # block and its override have somewhere to be seen.
        "state": "verified",
        "verified_days_ago": 120,
        "owes": True,
        "content_types": ["reel", "static_post"],
        "preferred_follower_tier": "macro",
        "typical_budget_band": "15k_40k",
        "outlets": [],
    },
    {
        "key": "permitroom",
        "phone": phone(9),
        "manager": "Aarti Desai",
        "designation": "Head of marketing",
        "business": "The Permit Room",
        "category": "fnb",
        "area": "Church Street",
        "tagline": "Bar snacks and a very short cocktail list.",
        "about": "A room off Church Street. Loud on Fridays, quiet on Tuesdays.",
        # Rejected once, fixed it, verified on the second attempt — so the
        # resubmission counter and the previous reason have a real record.
        "state": "verified",
        "verified_days_ago": 15,
        "resubmissions": 1,
        "previous_reason": (
            "The GST certificate was for a different entity to the one named "
            "on the profile. Upload the one matching The Permit Room."
        ),
        "content_types": ["reel", "story", "video"],
        "preferred_follower_tier": "mid",
        "typical_budget_band": "5k_15k",
        "outlets": [
            {"name": "Church Street", "address": "7 Church Street", "area": "Church Street",
             "city": "Bengaluru"},
        ],
    },
    {
        "key": "loomroom",
        "phone": phone(10),
        "manager": "Farah Sheikh",
        "designation": "Owner",
        "business": "The Loom Room",
        "category": "fashion",
        "area": "Jayanagar",
        "tagline": "Handloom, cut for people who sit down at desks.",
        "about": "Two racks and a tailor. Everything is made after you order it.",
        # Turned down and still turned down. The rejected state needs an
        # occupant or the brand reviews queue has only one shape in it.
        "state": "rejected",
        "reason": (
            "The shop & establishment licence has expired. Send a current one "
            "and we'll look again straight away."
        ),
        "content_types": [],
        "preferred_follower_tier": "any",
        "typical_budget_band": "under_5k",
        "outlets": [],
    },
]

# `history` is what this creator's finished work should add up to, and the
# collaborations below are written to match — a reliability panel whose numbers
# do not come from rows anybody can open is a panel nobody trusts twice.
CREATORS = [
    {
        "key": "ana", "phone": phone(1), "name": "Ana Kulkarni",
        "handle": "ana.eats", "followers": 42000, "er": 4.6,
        "area": "Indiranagar", "niches": ["fnb", "lifestyle"],
        "genres": ["food", "reviews"], "platforms": ["instagram"],
        "rate": 8000, "payout": "upi", "state": "verified",
        "verified_days_ago": 60,
        "about": "I eat out four nights a week and film two of them.",
        "blurb": "Verified, strong record. The default creator for a happy path.",
    },
    {
        "key": "bo", "phone": phone(2), "name": "Bo Sharma",
        "handle": None, "followers": None, "er": None,
        "area": "Koramangala", "niches": [], "genres": [],
        "platforms": ["instagram"], "rate": None, "payout": None,
        "state": "incomplete",
        "blurb": "Signed up, profile half-built. Tests the builder and the apply gate.",
    },
    {
        "key": "cal", "phone": phone(3), "name": "Cal Mehta",
        "handle": "cal.builds", "followers": 9200, "er": 5.1,
        "area": "HSR Layout", "niches": ["tech"], "genres": ["reviews"],
        "platforms": ["instagram", "youtube"], "rate": 5000, "payout": "bank",
        "state": "pending", "submitted_days_ago": 4,
        "about": "Gadget reviews, mostly in Kannada.",
        "blurb": "Submitted for review. Sits in the admin creator queue.",
    },
    {
        "key": "diya", "phone": phone(11), "name": "Diya Fernandes",
        "handle": "diya.pours", "followers": 128000, "er": 3.2,
        "area": "Church Street", "niches": ["fnb", "nightlife"],
        "genres": ["food", "cocktails"], "platforms": ["instagram", "youtube"],
        "rate": 22000, "payout": "bank", "state": "verified",
        "verified_days_ago": 200,
        "about": "Cocktails, and the people who make them.",
        "blurb": "Macro tier. Use to see the follower bands and the report.",
    },
    {
        "key": "eshan", "phone": phone(12), "name": "Eshan Rai",
        "handle": "eshan.frames", "followers": 6400, "er": 7.8,
        "area": "Malleshwaram", "niches": ["photography", "lifestyle"],
        "genres": ["photo essays"], "platforms": ["instagram"],
        "rate": 3500, "payout": "upi", "state": "verified",
        "verified_days_ago": 5,
        "blurb": "Micro tier, verified last week, no history yet — the `new` band.",
    },
    {
        "key": "farida", "phone": phone(13), "name": "Farida Qureshi",
        "handle": "farida.wears", "followers": 31000, "er": 4.1,
        "area": "Jayanagar", "niches": ["fashion"], "genres": ["styling"],
        "platforms": ["instagram"], "rate": 9000, "payout": "upi",
        "state": "verified", "verified_days_ago": 340,
        # 25 days left of a 365-day validity: the warning window, so the
        # revalidation prompt has somewhere to appear.
        "blurb": "Verification runs out in 25 days. Shows the revalidation prompt.",
    },
    {
        "key": "gaurav", "phone": phone(14), "name": "Gaurav Menon",
        "handle": "gaurav.trails", "followers": 18500, "er": 3.9,
        "area": "Whitefield", "niches": ["travel", "fitness"],
        "genres": ["vlogs"], "platforms": ["instagram", "youtube"],
        "rate": 7000, "payout": "bank", "state": "verified",
        "verified_days_ago": 400,
        # Past 365 days with no confirmation: lapsed, and blocked from applying.
        "blurb": "Verification lapsed. Cannot apply until they confirm.",
    },
    {
        "key": "hema", "phone": phone(15), "name": "Hema Prakash",
        "handle": "hema.cooks", "followers": 54000, "er": 5.4,
        "area": "Indiranagar", "niches": ["fnb"], "genres": ["home cooking"],
        "platforms": ["instagram"], "rate": 11000, "payout": "upi",
        "state": "verified", "verified_days_ago": 90, "pending_review": True,
        "pending_review_fields": ["payout_account_number", "instagram_handle"],
        "blurb": "Edited their bank details — verified, but re-checked before new work.",
    },
    {
        "key": "irfan", "phone": phone(16), "name": "Irfan Baig",
        "handle": "irfan.rides", "followers": 22000, "er": 2.8,
        "area": "Koramangala", "niches": ["automotive"], "genres": ["reviews"],
        "platforms": ["instagram"], "rate": 6500, "payout": "upi",
        "state": "verified", "verified_days_ago": 150, "no_shows": 3,
        "blurb": "Three no-shows. Raises the suspension prompt in the admin queue.",
    },
    {
        "key": "jaya", "phone": phone(17), "name": "Jaya Anand",
        "handle": "jaya.reads", "followers": 8800, "er": 6.2,
        "area": "Malleshwaram", "niches": ["books", "lifestyle"],
        "genres": ["reviews"], "platforms": ["instagram"], "rate": 4000,
        "payout": "upi", "state": "suspended",
        "suspension_reason": "Passed a brand's brief to a competitor before it went live.",
        "blurb": "Suspended, with a reason. Cannot apply or book; history intact.",
    },
    {
        "key": "kabir", "phone": phone(18), "name": "Kabir Shetty",
        "handle": "kabir.lifts", "followers": 67000, "er": 4.4,
        "area": "HSR Layout", "niches": ["fitness", "wellness"],
        "genres": ["training"], "platforms": ["instagram", "youtube"],
        "rate": 14000, "payout": "bank", "state": "verified",
        "verified_days_ago": 220,
        "about": "Strength coaching, and what I actually eat.",
        "blurb": "Verified, mid-macro. The other half of most two-creator campaigns.",
    },
    {
        "key": "lata", "phone": phone(19), "name": "Lata Bhat",
        "handle": "lata.makes", "followers": 15200, "er": 5.9,
        "area": "Jayanagar", "niches": ["crafts", "home"],
        "genres": ["making"], "platforms": ["instagram"], "rate": 5500,
        "payout": "upi", "state": "rejected",
        "rejection_reason": (
            "The Instagram account did not match the name on the profile. "
            "Fix that and submit again."
        ),
        "blurb": "Turned down. Tests the rejected state and the way back.",
    },
]

STAFF = [
    {"key": "manager", "phone": phone(6), "name": "Priya Rao",
     "role": "campaign_manager",
     "blurb": "Runs shoots. Roster, daysheet, slot confirmations, check-in."},
    {"key": "team", "phone": phone(7), "name": "Devika Rao",
     "role": "weare_team",
     "blurb": "Console scoped to Thirdwave and Blume. No directory, no health, no audit."},
]


# ---------------------------------------------------------------------------
# Writing it
# ---------------------------------------------------------------------------


async def wipe(db) -> dict:
    """Clear the collections listed above, reporting what went."""
    removed = {}
    for name in WIPED:
        n = await db[name].count_documents({})
        if n:
            await db[name].delete_many({})
            removed[name] = n
    return removed


async def _account(p: dict, role: str, now: datetime):
    # A brand row names the *person*, because that is what the login belongs
    # to: a brand has exactly one, captured at registration.
    display = p.get("name") or p["manager"]
    doc = {
        "name": display,
        "role": role,
        "phone": p["phone"],
        "email": f"{p['key']}@seed.local",
        "status": "suspended" if p.get("state") == "suspended" else "active",
        # No password: these are OTP logins. Staff could have one, and giving
        # them a known one would be the backdoor this file exists to avoid.
        "password_hash": None,
        "created_at": now - timedelta(days=p.get("joined_days_ago", 120)),
        "updated_at": now,
    }
    if p.get("state") == "suspended":
        doc["suspension_reason"] = p["suspension_reason"]
        doc["suspended_at"] = ago(12)
    if role == "brand_manager":
        doc["manager_name"] = p["manager"]
        doc["manager_designation"] = p["designation"]
        doc["manager_email"] = f"{p['key']}@seed.local"
    uid = (await server.db.users.insert_one(doc)).inserted_id
    if role == "brand_manager":
        # `_brand_scope` reads this on every brand request, and the partial
        # unique index on it is what makes one login per brand a constraint
        # rather than a rule to remember.
        await server.db.users.update_one({"_id": uid}, {"$set": {"brand_id": uid}})
    return uid


async def seed_brands(now: datetime) -> dict:
    out = {}
    for b in BRANDS:
        uid = await _account(b, "brand_manager", now)
        verified = b["state"] == "verified"
        doc = {
            "user_id": uid,
            "reference": await server._next_reference("brand"),
            "business_name": b["business"],
            "legal_entity_name": f"{b['business']} Private Limited",
            "business_type": "private_limited",
            "category": b["category"],
            "city": "Bengaluru",
            "areas": [b["area"]],
            "tagline": b["tagline"],
            "about": b["about"],
            "outlets": b["outlets"],
            "registered_address": f"{b['area']}, Bengaluru 560001",
            "gst_number": f"29AAAAA{1000 + len(out)}A1Z5",
            "website": f"https://{b['key']}.example",
            "contact_person_name": b["manager"],
            "contact_person_designation": b["designation"],
            "contact_email": f"{b['key']}@seed.local",
            "contact_phone": b["phone"],
            # What they are looking for, so the suggestions panel ranks on a
            # stated preference rather than inferring one from a fee.
            "content_types": b["content_types"],
            "preferred_follower_tier": b["preferred_follower_tier"],
            "typical_budget_band": b["typical_budget_band"],
            "verified": verified,
            "verification_state": b["state"],
            **server._state_stamp(b["state"], now, field="verification_state"),
            "submitted_for_verification_at": ago(b.get("verified_days_ago", 6) + 2),
            "created_at": ago(b.get("verified_days_ago", 30) + 10),
        }
        if verified:
            doc["verified_at"] = ago(b["verified_days_ago"])
        if b.get("resubmissions"):
            doc["verification_resubmissions"] = b["resubmissions"]
            doc["previous_verification_reason"] = b["previous_reason"]
        if b["state"] == "rejected":
            doc["verification_reason"] = b["reason"]
        oid = (await server.db.brand_profiles.insert_one(doc)).inserted_id

        # Papers on file for anybody who has actually submitted. The row is
        # what a reviewer opens; the file itself is not seeded, because
        # `PRIVATE_UPLOAD_DIR` holding a fake GST certificate is a fake GST
        # certificate on somebody's disk.
        if b["state"] in ("pending_verification", "verified", "rejected"):
            await server.db.brand_documents.insert_one({
                "brand_id": uid,
                "kind": "gst_certificate",
                "original_name": f"{b['key']}-gst.pdf",
                "stored_name": None,
                "content_type": "application/pdf",
                "size": 184_320,
                "uploaded_at": ago(b.get("verified_days_ago", 6) + 2),
            })
        out[b["key"]] = {"user_id": uid, "profile_id": oid, **b}
    return out


async def seed_creators(now: datetime) -> dict:
    out = {}
    for c in CREATORS:
        uid = await _account(c, "creator", now)
        status = {
            "verified": "verified", "suspended": "verified",
            "pending": "pending", "incomplete": "pending", "rejected": "rejected",
        }[c["state"]]

        doc = {
            "user_id": uid,
            "reference": await server._next_reference("creator"),
            "name": c["name"],
            "email": f"{c['key']}@seed.local",
            "phone": c["phone"],
            "city": "Bengaluru",
            "address": c["area"],
            "niches": c["niches"],
            "genres": c["genres"],
            "platforms": c["platforms"],
            "verification_status": status,
            **server._state_stamp(status, now, field="verification_status"),
            "pending_review": bool(c.get("pending_review")),
            "created_at": ago(c.get("verified_days_ago", 30) + 14),
            "updated_at": now,
        }
        if c["state"] != "incomplete":
            doc.update({
                "instagram_handle": c["handle"],
                "instagram_profile_url": f"https://instagram.com/{c['handle']}",
                "follower_count": c["followers"],
                "follower_count_self_reported": c["followers"],
                "engagement_rate": c["er"],
                "base_rate": c["rate"],
                "about": c.get("about"),
                "full_address": f"{random.randint(2, 90)} {c['area']} Main Road, "
                                f"{c['area']}, Bengaluru 5600{random.randint(10, 99)}",
                # The pin and the label are two different things: one gets
                # printed on a delivery, the other gets navigated to.
                "location_lat": round(12.90 + random.random() * 0.15, 6),
                "location_lng": round(77.55 + random.random() * 0.15, 6),
                "profile_image_url": None,
                "submitted_for_review_at": ago(c.get("submitted_days_ago", 45)),
            })
            if "youtube" in c["platforms"]:
                doc["youtube_url"] = f"https://youtube.com/@{c['handle']}"
        if c["state"] in ("verified", "suspended"):
            doc["verified_at"] = ago(c.get("verified_days_ago", 90))
        if c["state"] == "rejected":
            doc["verification_reason"] = c["rejection_reason"]
        if c.get("pending_review"):
            doc["pending_review_fields"] = c["pending_review_fields"]

        # Payout details on everybody who could plausibly be paid. Not on the
        # half-finished profile: a PAN is not the price of being looked at, and
        # that persona exists to show the gate.
        if c.get("payout") == "upi":
            doc.update({"payout_method": "upi", "payout_upi": f"{c['key']}@okhdfcbank",
                        "pan": f"AAAP{c['key'][0].upper()}{random.randint(1000, 9999)}A"})
        elif c.get("payout") == "bank":
            doc.update({
                "payout_method": "bank",
                "payout_account_name": c["name"],
                "payout_account_number": f"5010012{random.randint(100000, 999999)}",
                "payout_ifsc": "HDFC0001234",
                "pan": f"AAAP{c['key'][0].upper()}{random.randint(1000, 9999)}A",
            })
        await server.db.creator_profiles.insert_one(doc)
        out[c["key"]] = {"user_id": uid, **c}
    return out


async def seed_staff(now: datetime, brands: dict) -> dict:
    out = {}
    for s in STAFF:
        uid = await _account(s, s["role"], now)
        out[s["key"]] = {"user_id": uid, **s}
    # A scoped console with no brands on it is correctly empty and
    # indistinguishable from a broken one, which is the exact confusion this
    # file exists to prevent. Two brands rather than one, so the brand filter
    # has something to filter.
    await server.db.users.update_one(
        {"_id": out["team"]["user_id"]},
        {"$set": {"assigned_brand_ids": [brands["thirdwave"]["user_id"],
                                         brands["blume"]["user_id"]]}},
    )
    return out


# --- campaigns --------------------------------------------------------------

def _campaign(brand, *, title, brief, items, budget, category, area,
              needed, ctype, status, **kw) -> dict:
    """A campaign shaped exactly like one the form posts.

    Deliberately through `_resolve_deliverables`, so the counted items and the
    sentence beside them can never describe different asks — the same resolver
    the create and edit routes share.
    """
    return {
        "brand_id": brand["user_id"],
        "title": title,
        "brief": brief,
        **server._resolve_deliverables(items, None, True),
        "budget_per_creator": float(budget),
        "compensation_type": kw.pop("compensation_type", "fixed"),
        "category": category,
        "area": area,
        "city": "Bengaluru",
        "creators_needed": needed,
        "campaign_type": ctype,
        "execution_owner": kw.pop("execution_owner", "brand"),
        "visibility": kw.pop("visibility", "public"),
        "requires_draft_approval": kw.pop("requires_draft_approval", True),
        "restricted_days": kw.pop("restricted_days", []),
        "shoot_windows": kw.pop("shoot_windows", []),
        "venue_address": kw.pop("venue_address", None),
        "venue_instructions": kw.pop("venue_instructions", None),
        "on_site_contact": kw.pop("on_site_contact", None),
        "status": status,
        **server._state_stamp(status, NOW, field="status"),
        "created_at": kw.pop("created_at", ago(20)),
        **kw,
    }


async def seed_campaigns(brands: dict, staff: dict) -> dict:
    """Fifteen briefs across every status the product can be in.

    The point of the spread is that no console screen is empty and no filter
    returns nothing: a status with no occupant is a tab you cannot tell from a
    broken query.
    """
    tw, cc, bl, pr = brands["thirdwave"], brands["copperclay"], brands["blume"], brands["permitroom"]
    mgr = staff["manager"]
    mgr_contact = {
        "manager_id": mgr["user_id"], "manager_name": mgr["name"],
        "manager_phone": mgr["phone"], "manager_email": "manager@seed.local",
    }
    brand_contact = lambda b: {  # noqa: E731 — a table, not a function worth naming
        "manager_id": b["user_id"], "manager_name": b["manager"],
        "manager_phone": b["phone"], "manager_email": f"{b['key']}@seed.local",
    }

    specs = [
        # --- Thirdwave: the brand that runs its own work -------------------
        ("tw_brunch", _campaign(
            tw, title="Weekend brunch, Indiranagar",
            brief=("Two hours on a Saturday or Sunday morning. Order what you "
                   "want off the brunch menu, film the room while it is full, "
                   "and tell people what the filter coffee is actually like."),
            items=[{"type": "reel", "quantity": 1}, {"type": "story", "quantity": 3}],
            budget=8000, category="fnb", area="Indiranagar", needed=3,
            ctype="personal_table", status="open",
            start_date=ago(6), end_date=ahead(24),
            venue_address="1102, 12th Main, Indiranagar, Bengaluru 560038",
            venue_instructions="Ask for Riya at the counter. Parking is on 12th Main.",
            on_site_contact="Riya Nair",
            # Not during Friday or Saturday service; mornings and afternoons only.
            restricted_days=[4], shoot_windows=[{"preset": "brunch"}],
            **brand_contact(tw), created_at=ago(18),
        )),
        ("tw_roastery", _campaign(
            tw, title="Roastery tour, Jayanagar",
            brief=("A morning at the roastery watching a batch go through. "
                   "We want the smell of it on camera, which is harder than "
                   "it sounds."),
            items=[{"type": "reel", "quantity": 1}, {"type": "youtube_short", "quantity": 1}],
            budget=12000, category="fnb", area="Jayanagar", needed=2,
            ctype="group_event", status="in_progress",
            event_date=ago(9), start_date=ago(12), end_date=ago(5),
            venue_address="Thirdwave Roastery, 30th Cross, Jayanagar",
            **mgr_contact, execution_owner="weare", created_at=ago(30),
        )),
        ("tw_winter", _campaign(
            tw, title="Winter menu launch",
            brief="One evening, the whole new menu, eight people in the room.",
            items=[{"type": "reel", "quantity": 1}, {"type": "story", "quantity": 5}],
            budget=15000, category="fnb", area="Church Street", needed=4,
            ctype="launch", status="completed",
            event_date=ago(52), start_date=ago(60), end_date=ago(50),
            **mgr_contact, execution_owner="weare", created_at=ago(75),
        )),
        ("tw_draft", _campaign(
            tw, title="Cold brew, summer",
            brief="Not written properly yet — placeholder while we decide the dates.",
            items=[{"type": "reel", "quantity": 1}],
            budget=6000, category="fnb", area="Indiranagar", needed=2,
            ctype="personal_table", status="draft",
            # Untouched for over a month, so the stale-draft flag has an
            # occupant and the health panel can say so.
            created_at=ago(41), updated_at=ago(38),
            **brand_contact(tw),
        )),
        ("tw_private", _campaign(
            tw, title="Founders' table (invite only)",
            brief=("A small sitting with the founders. We are asking four "
                   "people directly rather than opening it."),
            items=[{"type": "reel", "quantity": 1}, {"type": "static_post", "quantity": 1}],
            budget=18000, category="fnb", area="Indiranagar", needed=2,
            ctype="group_event", status="open", visibility="private",
            event_date=ahead(11), start_date=ahead(9), end_date=ahead(13),
            **brand_contact(tw), created_at=ago(4),
        )),

        # --- Blume: hands everything to WeAre ------------------------------
        ("bl_serum", _campaign(
            bl, title="Barrier serum, everyday routine",
            brief=("Two weeks with the serum, then tell people honestly "
                   "whether your skin changed. We would rather have a "
                   "lukewarm review than a scripted one."),
            items=[{"type": "reel", "quantity": 1}, {"type": "static_post", "quantity": 2}],
            budget=25000, category="beauty", area="HSR Layout", needed=2,
            ctype="personal_table", status="in_progress",
            start_date=ago(21), end_date=ahead(7),
            execution_owner="weare", requires_draft_approval=False,
            **mgr_contact, created_at=ago(28),
        )),
        ("bl_spf", _campaign(
            bl, title="SPF 50, for people who forget",
            brief="One reel. The whole point is that it does not leave a cast.",
            items=[{"type": "reel", "quantity": 1}],
            budget=20000, category="beauty", area="HSR Layout", needed=3,
            ctype="personal_table", status="open",
            # Four days out and two of three seats unfilled: the underfill
            # check needs a real campaign to be worried about.
            start_date=ahead(4), end_date=ahead(18),
            execution_owner="weare", **mgr_contact, created_at=ago(9),
        )),
        ("bl_paused", _campaign(
            bl, title="Cleanser refill pouches",
            brief="Paused while the packaging is redone.",
            items=[{"type": "reel", "quantity": 1}],
            budget=15000, category="beauty", area="HSR Layout", needed=2,
            ctype="personal_table", status="paused",
            paused_from_status="open",
            pause_reason="Packaging is being redone; back in about three weeks.",
            start_date=ago(3), end_date=ahead(20),
            execution_owner="weare", **mgr_contact, created_at=ago(16),
        )),

        # --- The Permit Room ------------------------------------------------
        ("pr_cocktails", _campaign(
            pr, title="Six cocktails, one evening",
            brief=("The new list, start to finish, with the bartender "
                   "explaining two of them. Loud room — bring a mic."),
            items=[{"type": "reel", "quantity": 1}, {"type": "video", "quantity": 1}],
            budget=0, category="fnb", area="Church Street", needed=2,
            ctype="launch", status="open", compensation_type="negotiated",
            event_date=ahead(6), start_date=ahead(4), end_date=ahead(8),
            venue_address="7 Church Street, Bengaluru 560001",
            restricted_days=[0, 1], shoot_windows=[{"preset": "evening"}],
            **brand_contact(pr), created_at=ago(7),
        )),
        ("pr_review", _campaign(
            pr, title="Tuesday quiz night",
            brief="Quiet night, we want it busier. Two creators, low key.",
            items=[{"type": "story", "quantity": 4}],
            budget=4000, category="fnb", area="Church Street", needed=2,
            ctype="group_event", status="pending_review",
            event_date=ahead(15), start_date=ahead(14), end_date=ahead(16),
            submitted_for_review_at=ago(2),
            **brand_contact(pr), created_at=ago(2),
        )),
        ("pr_barter", _campaign(
            pr, title="Bar snacks tasting (barter)",
            brief=("Dinner for two off the snack menu in exchange for a reel. "
                   "No fee — WeAre arranged this one directly."),
            items=[{"type": "reel", "quantity": 1}],
            budget=3000, category="fnb", area="Church Street", needed=2,
            ctype="personal_table", status="open", compensation_type="barter",
            start_date=ago(2), end_date=ahead(26),
            **brand_contact(pr), created_at=ago(5),
        )),
        ("pr_closed", _campaign(
            pr, title="Reopening week",
            brief="Ran in the spring. Kept for the numbers.",
            items=[{"type": "reel", "quantity": 1}, {"type": "story", "quantity": 2}],
            budget=9000, category="fnb", area="Church Street", needed=2,
            ctype="launch", status="closed",
            closed_reason="Ran and finished.",
            event_date=ago(96), start_date=ago(100), end_date=ago(94),
            showcase=True, **brand_contact(pr), created_at=ago(110),
        )),

        # --- Copper & Clay: unverified, so nothing may reach a creator ------
        ("cc_draft", _campaign(
            cc, title="Tuesday menu change",
            brief=("A new menu every week and nobody knows. Drafted while we "
                   "wait on verification."),
            items=[{"type": "reel", "quantity": 1}, {"type": "story", "quantity": 2}],
            budget=5000, category="fnb", area="Koramangala", needed=2,
            ctype="personal_table", status="draft",
            **brand_contact(cc), created_at=ago(3),
        )),
        ("cc_review", _campaign(
            cc, title="Natural wine evening",
            brief="Six bottles, twelve people, one long table.",
            items=[{"type": "reel", "quantity": 1}],
            budget=6000, category="fnb", area="Koramangala", needed=3,
            ctype="group_event", status="pending_review",
            event_date=ahead(21), start_date=ahead(19), end_date=ahead(22),
            # Submitted six days ago against a 24-hour target: overdue, loudly,
            # which is what the escalation list is for.
            submitted_for_review_at=ago(6),
            **brand_contact(cc), created_at=ago(6),
        )),
        ("tw_rejected", _campaign(
            tw, title="Coffee and crypto",
            brief="Turned down at review.",
            items=[{"type": "reel", "quantity": 1}],
            budget=8000, category="fnb", area="Indiranagar", needed=1,
            ctype="personal_table", status="rejected",
            review_reason=("Off-brief for the platform — we don't run financial "
                           "promotions. Everything else about it was fine."),
            reviewed_at=ago(11), **brand_contact(tw), created_at=ago(13),
        )),
    ]

    out = {}
    for key, doc in specs:
        doc["reference"] = await server._next_reference("campaign")
        doc.setdefault("updated_at", NOW)
        oid = (await server.db.campaigns.insert_one(doc)).inserted_id
        out[key] = {"_id": oid, **doc}
    return out


# --- collaborations, and everything that hangs off one ----------------------

async def _collab(campaign, creator, state, *, days_ago, **kw) -> dict:
    """One application, at a state, with the clock set to when it got there.

    **`state_since` is written, not left to default.** Without it every
    seeded row reads as having entered its state the moment the seeder ran, so
    the whole platform looks like it started waiting this morning and nothing
    is ever overdue — which is the one thing the ageing display exists to show.
    """
    doc = {
        "campaign_id": campaign["_id"],
        "creator_id": creator["user_id"],
        "reference": await server._next_reference("collaboration"),
        "pitch": kw.pop("pitch", "Happy to do this one — it's the kind of thing I post anyway."),
        "quoted_rate": float(kw.pop("quoted_rate", creator.get("rate") or 5000)),
        "agreed_amount": kw.pop("agreed_amount", None),
        "content_url": None,
        "content_urls": [],
        "scheduled_at": kw.pop("scheduled_at", None),
        "state": state,
        **server._state_stamp(state, ago(days_ago)),
        "active": state not in server.TERMINAL_COLLAB_STATES,
        "created_at": ago(kw.pop("applied_days_ago", days_ago + 3)),
        **kw,
    }
    doc["_id"] = (await server.db.collaborations.insert_one(doc)).inserted_id
    return doc


async def _payment(collab, *, state="pending", invoice="pending", paid_days_ago=None,
                   tds=None, frozen=False, creator_profile=None):
    agreed = float(collab.get("agreed_amount") or 0)
    fee = round(agreed * server.platform_fee_percent() / 100, 2)
    doc = {
        "collaboration_id": collab["_id"],
        "agreed_amount": agreed,
        "platform_fee": fee,
        "fee_percent": server.platform_fee_percent(),
        "creator_payout": agreed,
        "brand_invoice_amount": round(agreed + fee, 2),
        "brand_invoice_state": invoice,
        # The snapshot, not the live profile: what matters for accounting is
        # where the money actually went, not where it would go today.
        "payout_snapshot": {
            "method": (creator_profile or {}).get("payout"),
            "upi": f"{(creator_profile or {}).get('key')}@okhdfcbank"
            if (creator_profile or {}).get("payout") == "upi" else None,
            "account_name": (creator_profile or {}).get("name")
            if (creator_profile or {}).get("payout") == "bank" else None,
        },
        "state": state,
        "frozen": frozen,
        "created_at": ago((paid_days_ago or 5) + 4),
        "updated_at": NOW,
    }
    if state == "paid":
        doc["paid_at"] = ago(paid_days_ago or 3)
        doc["payment_reference"] = f"UTR{random.randint(10**11, 10**12 - 1)}"
        # Three states, not two: `None` is "nobody has said", which is a
        # different fact from "no withholding applies".
        doc["tds_applicable"] = tds is not None
        doc["tds_amount"] = float(tds) if tds else None
        doc["net_paid"] = round(agreed - float(tds or 0), 2)
    if invoice == "sent":
        sent = ago(paid_days_ago or 20)
        doc["invoice_sent_at"] = sent
        doc["invoice_due_at"] = sent + timedelta(days=await server.payment_terms_days())
    if invoice == "settled":
        doc["invoice_settled_at"] = ago(paid_days_ago or 2)
    await server.db.payments.insert_one(doc)
    return doc


async def _note(collab, campaign, author, body, *, days_ago=2, role="brand_manager"):
    await server.db.collaboration_notes.insert_one({
        "collaboration_id": collab["_id"],
        "campaign_id": campaign["_id"],
        "brand_id": campaign["brand_id"],
        "author_id": author["user_id"],
        "author_name": author.get("name") or author.get("manager"),
        "author_role": role,
        "body": body,
        "created_at": ago(days_ago),
    })


async def _rating(collab, campaign, side, score, note, by):
    await server.db.collaboration_ratings.insert_one({
        "collaboration_id": collab["_id"],
        "campaign_id": campaign["_id"],
        "creator_id": collab["creator_id"],
        "brand_id": campaign["brand_id"],
        "side": side,
        "score": score,
        "note": note,
        "by_id": by["user_id"],
        "by_name": by.get("name") or by.get("manager"),
        "created_at": ago(2),
        "updated_at": ago(2),
    })


async def _performance(collab, *, reach, likes, comments, saves=None, views=None,
                       by=None, days_ago=3):
    """A reading, with `None` where we genuinely could not read it.

    Never zero for an unknown: a post with no saves and a post whose saves we
    could not see are different, and averaging the second as zero makes a
    campaign look worse than it was.
    """
    await server.db.content_performance.insert_one({
        "collaboration_id": collab["_id"],
        "campaign_id": collab["campaign_id"],
        "creator_id": collab["creator_id"],
        "reach": reach, "impressions": None, "views": views,
        "likes": likes, "comments": comments, "saves": saves,
        "captured_at": ago(days_ago),
        "source": "manual",
        "captured_by": (by or {}).get("user_id"),
        "captured_by_name": (by or {}).get("name"),
        "content_url": (collab.get("content_urls") or [None])[0],
        "created_at": ago(days_ago),
        "updated_at": ago(days_ago),
    })


async def seed_work(brands, creators, campaigns, staff):
    """The collaborations, and the paper each one leaves behind.

    Every state in `COLLAB_STATE_ORDER` has at least one occupant, and so does
    every terminal exit. A ladder with empty rungs is a ladder nobody can test
    a transition against.
    """
    mgr, team = staff["manager"], staff["team"]
    tw, bl, pr = brands["thirdwave"], brands["blume"], brands["permitroom"]
    C = creators
    made = {}

    # --- The live brunch campaign: a board with something on every rung ----
    brunch = campaigns["tw_brunch"]
    made["applied"] = await _collab(
        brunch, C["eshan"], "applied", days_ago=1,
        pitch="I shoot mornings anyway and I live ten minutes away.",
        quoted_rate=3500,
    )
    made["verified"] = await _collab(
        # Four days at `verified` against a 72-hour target: overdue, so the
        # escalation list and the brand's own age badge have a real row.
        brunch, C["hema"], "verified", days_ago=4,
        pitch="Filter coffee is the thing I get asked about most.",
        quoted_rate=11000,
    )
    made["accepted"] = await _collab(
        brunch, C["kabir"], "accepted", days_ago=2, quoted_rate=14000,
    )
    made["commercial"] = await _collab(
        brunch, C["ana"], "commercial_agreed", days_ago=3,
        quoted_rate=8000, agreed_amount=8000.0, agreed_at=ago(3),
        agreed_by=tw["user_id"],
    )
    await _note(made["commercial"], brunch, tw, "Agreed ₹8,000. Same as the last two she did for us.",
                days_ago=3)

    # --- Slots, and a booking still waiting on an answer --------------------
    slots = []
    for offset, cap in ((3, 2), (5, 2), (9, 3)):
        starts = (NOW + timedelta(days=offset)).replace(
            hour=5, minute=30, second=0, microsecond=0)  # 11:00 IST
        slots.append((await server.db.campaign_slots.insert_one({
            "campaign_id": brunch["_id"],
            "starts_at": starts,
            "ends_at": starts + timedelta(hours=2),
            "capacity": cap,
            "booked_count": 0,
            "created_by": mgr["user_id"],
            "created_at": ago(6),
            "updated_at": ago(6),
        })).inserted_id)

    made["booked_unconfirmed"] = await _collab(
        brunch, C["diya"], "slot_booked", days_ago=1,
        quoted_rate=22000, agreed_amount=20000.0, agreed_at=ago(4),
        slot_id=slots[0], scheduled_at=ahead(3),
        # Booked and waiting on an answer: `slot_confirmed_at` absent is what
        # tells the manager's SlotAnswer band there is something to do.
        slot_booked_at=ago(1),
    )
    await server.db.campaign_slots.update_one(
        {"_id": slots[0]}, {"$set": {"booked_count": 1}})

    made["booked_confirmed"] = await _collab(
        brunch, C["farida"], "slot_booked", days_ago=2,
        quoted_rate=9000, agreed_amount=9000.0, agreed_at=ago(5),
        slot_id=slots[1], scheduled_at=ahead(5),
        slot_booked_at=ago(2), slot_confirmed_at=ago(2),
    )
    await server.db.campaign_slots.update_one(
        {"_id": slots[1]}, {"$set": {"booked_count": 1}})

    # --- The roastery campaign, mid-flight ---------------------------------
    roast = campaigns["tw_roastery"]
    made["attended"] = await _collab(
        roast, C["gaurav"], "attended", days_ago=9,
        quoted_rate=7000, agreed_amount=12000.0, agreed_at=ago(14),
        scheduled_at=ago(9), checked_in_at=ago(9), checked_in_by=mgr["user_id"],
        check_in_method="manual",
    )
    made["draft_submitted"] = await _collab(
        roast, C["ana"], "draft_submitted", days_ago=5,
        quoted_rate=8000, agreed_amount=12000.0, agreed_at=ago(16),
        scheduled_at=ago(9), checked_in_at=ago(9),
        draft_url="https://drive.example/unlisted/roastery-cut-2",
        draft_submitted_at=ago(5), draft_revision_count=1,
    )
    made["draft_approved"] = await _collab(
        roast, C["kabir"], "draft_approved", days_ago=2,
        quoted_rate=14000, agreed_amount=12000.0, agreed_at=ago(16),
        scheduled_at=ago(9), checked_in_at=ago(9),
        draft_url="https://drive.example/unlisted/roastery-cut-1",
        draft_submitted_at=ago(4), draft_approved_at=ago(2),
    )

    # --- Blume, weare-run, with a dispute on it ----------------------------
    serum = campaigns["bl_serum"]
    made["content_submitted"] = await _collab(
        serum, C["diya"], "content_submitted", days_ago=6,
        quoted_rate=22000, agreed_amount=25000.0, agreed_at=ago(18),
        scheduled_at=ago(14), checked_in_at=ago(14),
        content_url="https://instagram.com/p/seed-serum-diya",
        content_urls=["https://instagram.com/p/seed-serum-diya"],
        # The argument: delivered, and the brand will not approve it.
        dispute={
            "state": "open",
            "reason": ("They asked for changes twice after approving the draft, "
                       "and now say they won't pay because the caption doesn't "
                       "mention the price. The brief didn't ask for a price."),
            "raised_by_id": C["diya"]["user_id"],
            "raised_by_name": C["diya"]["name"],
            "raised_by_role": "creator",
            "raised_at": ago(2),
        },
    )
    await _payment(made["content_submitted"], frozen=True,
                   creator_profile=C["diya"])
    await _note(made["content_submitted"], serum, mgr,
                "Reading both sides. Draft approval is in the audit trail — "
                "the caption ask came after it.", days_ago=1, role="campaign_manager")

    made["content_approved"] = await _collab(
        serum, C["kabir"], "content_approved", days_ago=4,
        quoted_rate=14000, agreed_amount=25000.0, agreed_at=ago(20),
        scheduled_at=ago(16), checked_in_at=ago(16),
        content_url="https://instagram.com/p/seed-serum-kabir",
        content_urls=["https://instagram.com/p/seed-serum-kabir"],
        content_approved_at=ago(4),
    )
    await _payment(made["content_approved"], invoice="sent", paid_days_ago=4,
                   creator_profile=C["kabir"])
    await _performance(made["content_approved"], reach=88400, likes=6120,
                       comments=214, saves=901, by=mgr)

    # --- Winter menu: finished work, so reliability has something to read ---
    winter = campaigns["tw_winter"]
    finished = [
        ("ana", 15000, 52, 3, True),
        ("kabir", 15000, 51, 2, True),
        ("diya", 18000, 50, 5, False),   # delivered late
        ("farida", 12000, 49, 1, True),
    ]
    for i, (key, amount, days, delay, on_time) in enumerate(finished):
        collab = await _collab(
            winter, C[key], "closed", days_ago=days - delay,
            quoted_rate=C[key]["rate"], agreed_amount=float(amount),
            agreed_at=ago(days + 6), scheduled_at=ago(days),
            checked_in_at=ago(days),
            content_url=f"https://instagram.com/p/seed-winter-{key}",
            content_urls=[f"https://instagram.com/p/seed-winter-{key}"],
            content_approved_at=ago(days - delay - 1),
            **({} if on_time else {"content_overdue": True}),
            applied_days_ago=days + 12,
        )
        await _payment(collab, state="paid", invoice="settled",
                       paid_days_ago=days - delay - 2,
                       tds=round(amount * 0.02) if i == 0 else None,
                       creator_profile=C[key])
        await _performance(
            collab,
            reach=[41200, 62800, 154000, 28900][i],
            likes=[3010, 4402, 9880, 2140][i],
            comments=[142, 96, 402, 61][i],
            # Unknown on one of them, deliberately: an em dash on a report is
            # the honest rendering of a number nobody could read.
            saves=[418, None, 1204, 289][i],
            by=mgr, days_ago=days - delay - 1,
        )
        await _rating(collab, winter, "runner", [5, 5, 3, 4][i],
                      ["Turned up early, sent the cut the same night.",
                       "Reliable, as always.",
                       "The work was good; it was four days late and we had to chase.",
                       "Fine. Nothing to flag."][i], mgr)
        await _rating(collab, winter, "creator", [5, 4, 4, 5][i],
                      ["Well organised, paid on time.",
                       "Good brief. The venue was busier than described.",
                       "Payment took a while.",
                       "Easy one."][i], C[key])

    # --- Reopening week: more history, and a live takedown -----------------
    reopen = campaigns["pr_closed"]
    made["takedown"] = await _collab(
        reopen, C["ana"], "closed", days_ago=88,
        quoted_rate=8000, agreed_amount=9000.0, agreed_at=ago(101),
        scheduled_at=ago(96), checked_in_at=ago(96),
        content_url="https://instagram.com/p/seed-reopen-ana",
        content_urls=["https://instagram.com/p/seed-reopen-ana"],
        content_approved_at=ago(92), applied_days_ago=104,
        takedown={
            "state": "requested",
            "reason_code": "factual_error",
            "detail": ("The reel says the kitchen is open till 1am. It's 11pm on "
                       "weekdays and we're getting people turning up at midnight."),
            "requested_by_id": pr["user_id"],
            "requested_by_name": pr["manager"],
            "requested_by_role": "brand_manager",
            "requested_at": ago(1),
            "respond_by": ahead(1),
        },
    )
    await _payment(made["takedown"], state="paid", invoice="settled",
                   paid_days_ago=88, creator_profile=C["ana"])

    made["takedown_done"] = await _collab(
        reopen, C["farida"], "closed", days_ago=90,
        quoted_rate=9000, agreed_amount=9000.0, agreed_at=ago(101),
        scheduled_at=ago(96), checked_in_at=ago(96),
        content_url="https://instagram.com/p/seed-reopen-farida",
        content_urls=["https://instagram.com/p/seed-reopen-farida"],
        content_approved_at=ago(94), applied_days_ago=104,
        takedown={
            "state": "actioned", "reason_code": "rights",
            "detail": "The track on it isn't cleared for commercial use.",
            "requested_by_id": pr["user_id"], "requested_by_name": pr["manager"],
            "requested_by_role": "brand_manager",
            "requested_at": ago(30), "respond_by": ago(28),
            "response_note": "Taken down and reposted without the audio.",
            "responded_at": ago(29),
        },
    )
    await _payment(made["takedown_done"], state="paid", invoice="settled",
                   paid_days_ago=90, creator_profile=C["farida"])

    # --- In payment, and a resolved dispute behind it ----------------------
    made["in_payment"] = await _collab(
        campaigns["bl_paused"], C["hema"], "in_payment", days_ago=8,
        quoted_rate=11000, agreed_amount=15000.0, agreed_at=ago(22),
        scheduled_at=ago(18), checked_in_at=ago(18),
        content_url="https://instagram.com/p/seed-cleanser-hema",
        content_urls=["https://instagram.com/p/seed-cleanser-hema"],
        content_approved_at=ago(8),
        dispute={
            "state": "resolved",
            "reason": "Two of the three stories never went up.",
            "raised_by_id": bl["user_id"], "raised_by_name": bl["manager"],
            "raised_by_role": "runner", "raised_at": ago(11),
            "resolution": "partial_release", "resolution_amount": 10000.0,
            "resolution_note": ("One story was posted and archived within the "
                                "hour, which is not a delivery. Two of three "
                                "at ₹10,000, agreed with both sides."),
            "resolved_by_name": "Admin", "resolved_at": ago(9),
        },
    )
    await _payment(made["in_payment"], invoice="sent", paid_days_ago=8,
                   creator_profile=C["hema"])

    # --- Blume's overdue invoice, which is what blocks them publishing -----
    made["overdue_invoice"] = await _collab(
        campaigns["bl_serum"], C["ana"], "closed", days_ago=34,
        quoted_rate=8000, agreed_amount=25000.0, agreed_at=ago(48),
        scheduled_at=ago(42), checked_in_at=ago(42),
        content_url="https://instagram.com/p/seed-serum-ana",
        content_urls=["https://instagram.com/p/seed-serum-ana"],
        content_approved_at=ago(36), applied_days_ago=52,
    )
    paid = await _payment(made["overdue_invoice"], state="paid",
                          paid_days_ago=34, creator_profile=C["ana"])
    # Issued 30 days ago on 14-day terms: sixteen days past due.
    await server.db.payments.update_one(
        {"collaboration_id": made["overdue_invoice"]["_id"]},
        {"$set": {"brand_invoice_state": "sent",
                  "invoice_sent_at": ago(30),
                  "invoice_due_at": ago(16)}},
    )

    # --- The four exits, which are not steps -------------------------------
    made["declined"] = await _collab(
        brunch, C["irfan"], "declined", days_ago=6,
        pitch="Not really my area but happy to try.",
        exit_reason="Automotive audience — not the fit we're after for brunch.",
        applied_days_ago=8,
    )
    made["withdrawn"] = await _collab(
        campaigns["pr_cocktails"], C["eshan"], "withdrawn", days_ago=3,
        quoted_rate=3500,
        exit_reason="I'm out of town that week — sorry, should have checked the dates.",
        withdrawn_at=ago(3), applied_days_ago=5,
    )
    made["cancelled"] = await _collab(
        campaigns["tw_roastery"], C["irfan"], "cancelled", days_ago=11,
        quoted_rate=6500, agreed_amount=12000.0, agreed_at=ago(20),
        scheduled_at=ago(9),
        exit_reason="Venue moved the roast day and the creator could not make the new one.",
        cancelled_by_id=tw["user_id"], cancelled_by_name=tw["manager"],
        cancelled_by_role="brand_manager", cancelled_at=ago(11),
        # Two days' notice on a shoot they had already blocked out.
        days_of_notice=2, kill_fee=4000.0, applied_days_ago=26,
    )
    await _payment(made["cancelled"], creator_profile=C["irfan"])
    await server.db.payments.update_one(
        {"collaboration_id": made["cancelled"]["_id"]},
        {"$set": {"is_kill_fee": True, "creator_payout": 4000.0,
                  "agreed_amount": 4000.0}},
    )
    made["expired"] = await _collab(
        campaigns["tw_winter"], C["eshan"], "expired", days_ago=48,
        quoted_rate=3500,
        exit_reason="The campaign started and this application was never answered.",
        applied_days_ago=64,
    )

    # --- Irfan's no-shows, which is what raises the suspension prompt ------
    for i, key in enumerate(("tw_winter", "pr_closed", "tw_roastery")):
        await _collab(
            campaigns[key], C["irfan"], "cancelled", days_ago=40 + i * 18,
            quoted_rate=6500, agreed_amount=6000.0, agreed_at=ago(50 + i * 18),
            scheduled_at=ago(42 + i * 18),
            no_show_reported=True, no_show_reported_at=ago(42 + i * 18),
            exit_reason="Did not turn up and did not answer.",
            cancelled_by_role="admin", cancelled_at=ago(41 + i * 18),
            applied_days_ago=58 + i * 18,
        )

    # A reschedule on the record, so the count is not always zero.
    await server.db.collaborations.update_one(
        {"_id": made["booked_confirmed"]["_id"]},
        {"$set": {"reschedule_count": 1}},
    )
    return made


# --- everything else a screen reads -----------------------------------------

async def seed_invitations(brands, creators, campaigns, staff):
    """Asked, and not yet answered — which is a state the boards used to
    have no way to show at all."""
    tw, C = brands["thirdwave"], creators
    private, brunch = campaigns["tw_private"], campaigns["tw_brunch"]
    rows = [
        # Open, inside the seven-day window: shows on the creator's dashboard
        # with both answers on the row.
        (private, C["ana"], "sent", 2, "You've done three of ours. This one is smaller and better paid."),
        (private, C["diya"], "sent", 2, None),
        (private, C["kabir"], "sent", 5, None),
        # Lapsed: past `respond_by`, so it reads as history rather than
        # offering an Accept that would 404.
        (brunch, C["farida"], "sent", 12, None),
        # The message never landed. Still an invitation, and still visible.
        (brunch, C["hema"], "send_failed", 3, None),
    ]
    for campaign, creator, state, days, note in rows:
        await server.db.campaign_invitations.insert_one({
            "campaign_id": campaign["_id"],
            "creator_id": creator["user_id"],
            "brand_id": campaign["brand_id"],
            "invited_by": tw["user_id"],
            "note": note,
            "state": state,
            "respond_by": ago(days) + timedelta(days=server.INVITATION_RESPONSE_DAYS),
            "delivered_on_whatsapp": state == "sent",
            "whatsapp_mode": "simulated" if state == "sent" else None,
            "error": None if state == "sent" else "Number not on WhatsApp",
            "created_at": ago(days),
            "updated_at": ago(days),
        })


async def seed_questions(brands, creators, campaigns, staff):
    """Threads with the creator as a party — not the work notes, which they
    never see. One answered, one still waiting, on both kinds of campaign."""
    tw, bl = brands["thirdwave"], brands["blume"]
    mgr, C = staff["manager"], creators
    brunch, serum = campaigns["tw_brunch"], campaigns["bl_serum"]

    async def thread(campaign, creator, question, answer=None, *, days, by=None,
                     side=None):
        await server.db.campaign_questions.insert_one({
            "campaign_id": campaign["_id"], "creator_id": creator["user_id"],
            "brand_id": campaign["brand_id"], "author_id": creator["user_id"],
            "author_name": creator["name"], "from_creator": True,
            "author_side": None, "body": question, "created_at": ago(days),
        })
        if answer:
            await server.db.campaign_questions.insert_one({
                "campaign_id": campaign["_id"], "creator_id": creator["user_id"],
                "brand_id": campaign["brand_id"],
                "author_id": by["user_id"],
                "author_name": by.get("name") or by.get("manager"),
                "from_creator": False, "author_side": side,
                "body": answer, "created_at": ago(days) + timedelta(hours=5),
            })

    await thread(
        brunch, C["eshan"],
        "Is there parking near the Indiranagar room on a Sunday morning?",
        "There's paid parking on 12th Main, about fifty metres down. It fills "
        "by 10 so come a bit early.",
        days=3, by=tw, side="brand",
    )
    # Unanswered, and old enough to be in the admin's action queue.
    await thread(
        brunch, C["hema"],
        "Can I bring someone to shoot for me, or does it have to be just me?",
        days=4,
    )
    await thread(
        serum, C["diya"],
        "Do you want the routine filmed over the two weeks or just at the end?",
        "Over the two weeks if you can — the change is the story. Rough phone "
        "clips are fine for the middle.",
        days=9, by=mgr, side="weare",
    )
    # On a weare-run brief and unanswered: goes to our team, and the brand
    # never sees the thread at all.
    await thread(
        serum, C["kabir"],
        "Is the serum fragrance-free? I have a viewer who always asks.",
        days=2,
    )


async def seed_lists_and_templates(brands, creators, campaigns, staff):
    tw, C = brands["thirdwave"], creators
    await server.db.creator_lists.insert_one({
        "owner_id": tw["user_id"], "owner_kind": "brand",
        "brand_id": tw["user_id"],
        "name": "Worked well at launches",
        "creator_ids": [C["ana"]["user_id"], C["kabir"]["user_id"],
                        C["diya"]["user_id"]],
        "created_at": ago(30), "updated_at": ago(6),
    })
    # WeAre's own list belongs to the operation, not to whoever typed it:
    # "creators who are good at launch nights" is operational knowledge.
    await server.db.creator_lists.insert_one({
        "owner_id": server._WEARE_LIST_OWNER, "owner_kind": "weare",
        "brand_id": None,
        "name": "Reliable on a weeknight",
        "creator_ids": [C["ana"]["user_id"], C["farida"]["user_id"],
                        C["hema"]["user_id"]],
        "created_at": ago(45), "updated_at": ago(10),
    })

    brunch = campaigns["tw_brunch"]
    await server.db.campaign_templates.insert_one({
        "owner_id": tw["user_id"], "brand_id": tw["user_id"],
        "name": "Monthly brunch sitting",
        # The brief, and deliberately none of the dates — a template that
        # carried them would brief a day that has passed.
        "brief_fields": server._brief_fields_of(brunch),
        "used_count": 4,
        "created_at": ago(60), "updated_at": ago(18),
    })


async def seed_notifications(creators, brands, campaigns, work, staff):
    """A handful, so the bell is not permanently empty — and so the relative
    times on the panel have something to be relative to."""
    C = creators
    rows = [
        (C["ana"]["user_id"], "slot_confirmed", "Your slot is confirmed",
         "Thirdwave Coffee confirmed Saturday 11:00.", "/dashboard", 1, True),
        (C["diya"]["user_id"], "dispute_raised", "We're looking at it",
         "Blume Skincare — WeAre has the dispute and will come back to you.",
         "/dashboard", 2, False),
        (C["ana"]["user_id"], "takedown_requested", "A post needs taking down",
         "The Permit Room: something in it is factually wrong.", "/dashboard", 1, False),
        (C["hema"]["user_id"], "profile_recheck", "We're taking another look",
         "You changed your bank details, so we'll re-check before new work.",
         "/profile", 6, True),
        (brands["thirdwave"]["user_id"], "new_applicant", "A creator applied",
         "Eshan Rai applied to “Weekend brunch, Indiranagar”.",
         "/brand/campaigns", 1, False),
    ]
    for uid, event, title, body, link, days, read in rows:
        await server.db.notifications.insert_one({
            "user_id": uid, "event": event, "title": title, "body": body,
            "link": link, "read": read, "created_at": ago(days),
        })


async def seed_audit(brands, creators, campaigns, work, staff):
    """Enough lines that the log and every collaboration timeline read as a
    history rather than a blank panel.

    Written directly rather than through `audit()`, because these describe
    things that happened weeks ago and the helper stamps now.
    """
    tw, bl = brands["thirdwave"], brands["blume"]
    mgr = staff["manager"]
    admin = {"user_id": None, "name": "WeAre (seeded)", "role": "admin"}
    rows = [
        (tw, "campaign.create", "campaign", campaigns["tw_brunch"]["_id"], 18),
        (admin, "campaign.approve", "campaign", campaigns["tw_brunch"]["_id"], 17),
        (admin, "brand.verify", "brand", tw["user_id"], 40),
        (admin, "brand.verify", "brand", bl["user_id"], 120),
        (mgr, "collaboration.advance", "collaboration",
         work["attended"]["_id"], 9),
        (mgr, "collaboration.check_in", "collaboration",
         work["attended"]["_id"], 9),
        (tw, "collaboration.accept", "collaboration", work["accepted"]["_id"], 2),
        (admin, "collaboration.dispute_resolved", "collaboration",
         work["in_payment"]["_id"], 9),
        (tw, "collaboration.takedown_requested", "collaboration",
         work["takedown"]["_id"], 1),
    ]
    for actor, action, subject_type, subject_id, days in rows:
        await server.db.audit_log.insert_one({
            "actor_id": actor.get("user_id"),
            "actor_name": actor.get("name") or actor.get("manager"),
            "actor_role": actor.get("role", "brand_manager"),
            "action": action,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "before": None, "after": None, "note": None,
            "created_at": ago(days),
        })


async def seed_invoice_override(brands):
    """Blume owes us money, and nobody has waived it — so they meet the block.

    Left off deliberately rather than pre-granted: the override is the thing
    worth seeing somebody use, and a database where it is already on shows the
    escape hatch and never the wall.
    """
    await server.db.brand_profiles.update_one(
        {"user_id": brands["blume"]["user_id"]},
        {"$set": {"invoice_override": False}},
    )


async def seed_deletion_request(creators):
    """One person exercising the right, blocked by nothing, waiting on us."""
    await server.db.deletion_requests.insert_one({
        "user_id": creators["lata"]["user_id"],
        "role": "creator",
        "name": creators["lata"]["name"],
        "state": "requested",
        "reason": "I'm not doing brand work any more.",
        "requested_at": ago(3),
        "created_at": ago(3),
        "updated_at": ago(3),
    })


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

BANNER = """
  This will DELETE every row in {n} collections of

      {db}   at   {url}

  and replace them with demo data. Nothing here is recoverable.
"""


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yes", action="store_true",
                    help="Skip the confirmation. For CI and containers.")
    ap.add_argument("--keep", action="store_true",
                    help="Seed without wiping. Only sensible on an empty database.")
    args = ap.parse_args(argv)

    if not server._simulation_allowed():
        print(
            "Refusing to run.\n\n"
            "These accounts sign in by OTP, and without simulation mode you\n"
            "could not read the code — so they would be unusable anyway.\n\n"
            "  ALLOW_OTP_SIMULATION=true python seed_demo.py --yes\n",
            file=sys.stderr,
        )
        return 1
    # Belt and braces, and not the same check: `_simulation_allowed` returns
    # true for an explicit ALLOW_OTP_SIMULATION whatever APP_ENV says, so on
    # its own it would let `APP_ENV=production ALLOW_OTP_SIMULATION=true` wipe
    # a live database. This one reads an unset APP_ENV as production.
    if server._is_production():
        print(
            "Refusing to run: this looks like production.\n\n"
            "APP_ENV must be one of dev|development|local|test. An unset one\n"
            "reads as production on purpose — for a script whose first act is\n"
            "a delete, that is the safe direction to guess in.\n",
            file=sys.stderr,
        )
        return 1

    import os

    if not args.keep:
        counts = {n: await server.db[n].count_documents({}) for n in WIPED}
        total = sum(counts.values())
        print(BANNER.format(n=len(WIPED), db=os.environ.get("DB_NAME", "?"),
                            url=os.environ.get("MONGO_URL", "?")))
        if total:
            for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                if n:
                    print(f"      {n:>6}  {name}")
            print()
        else:
            print("      (all empty already)\n")
        if not args.yes:
            # **The person, not the environment.** A mistyped DB_NAME passes
            # both fences above.
            if not sys.stdin.isatty():
                print("Refusing to wipe without --yes when there is nobody to ask.",
                      file=sys.stderr)
                return 1
            if input("  Type the database name to confirm: ").strip() != os.environ.get("DB_NAME"):
                print("\n  Not confirmed. Nothing was deleted.")
                return 1
        removed = await wipe(server.db)
        print(f"  Cleared {sum(removed.values())} documents.\n")

    brands = await seed_brands(NOW)
    creators = await seed_creators(NOW)
    staff = await seed_staff(NOW, brands)
    campaigns = await seed_campaigns(brands, staff)
    work = await seed_work(brands, creators, campaigns, staff)
    await seed_invitations(brands, creators, campaigns, staff)
    await seed_questions(brands, creators, campaigns, staff)
    await seed_lists_and_templates(brands, creators, campaigns, staff)
    await seed_notifications(creators, brands, campaigns, work, staff)
    await seed_audit(brands, creators, campaigns, work, staff)
    await seed_invoice_override(brands)
    await seed_deletion_request(creators)

    counts = {
        "brands": len(brands), "creators": len(creators), "staff": len(staff),
        "campaigns": len(campaigns),
        "collaborations": await server.db.collaborations.count_documents({}),
        "payments": await server.db.payments.count_documents({}),
    }
    print("  Seeded: " + ", ".join(f"{v} {k}" for k, v in counts.items()) + "\n")

    print("Sign in at /login with the number, then read the OTP from the log:\n")
    print("  docker compose logs -f api | grep -i 'simulation mode'\n")
    everyone = (
        [(c["phone"], c["name"], c.get("blurb", "")) for c in CREATORS]
        + [(b["phone"], f"{b['manager']} — {b['business']}",
            f"Brand, {b['state'].replace('_', ' ')}.") for b in BRANDS]
        + [(s["phone"], s["name"], s["blurb"]) for s in STAFF]
    )
    width = max(len(p) for p, _, _ in everyone)
    for p, name, blurb in everyone:
        print(f"  {p:<{width}}  {name}")
        if blurb:
            print(f"  {'':<{width}}  {blurb}")
    print("\n  Admin signs in at /admin/login with ADMIN_EMAIL / ADMIN_PASSWORD.")
    print("  These numbers are fake and must never reach production.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
