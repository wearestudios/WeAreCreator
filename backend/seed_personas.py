#!/usr/bin/env python3
"""One signed-in-able account per persona, for testing before AiSensy is live.

Creators, brands and campaign managers sign in by WhatsApp OTP only. Until
AiSensy is configured there is no way into any of those accounts — so this
seeds them, and simulation mode prints the code to the server log instead of
sending it.

    ALLOW_OTP_SIMULATION=true python seed_personas.py

**A script, not an endpoint, deliberately.** An HTTP route that mints
pre-verified accounts with known phone numbers is a backdoor whether or not it
is guarded, and it would sit in the route table in production being one
misconfiguration away from reachable. A script cannot be called over the
network at all.

It refuses to run unless OTP simulation is permitted — the same gate the login
codes use. That is not belt-and-braces, it is the honest condition: without
simulation you could not read the OTP, so these accounts would be unusable
anyway. The gate and the usefulness are the same fact.

Idempotent, keyed on phone. Re-run it after a wipe, or to reset a persona that
you have pushed into a state you no longer want.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

import server  # noqa: E402  (env has to load first)


# Numbers in an obviously-patterned block, so a real one can never be mistaken
# for a seeded one — and so `+9199000000` in a production database is a
# self-announcing bug. They must never exist outside a laptop.
def phone(n: int) -> str:
    return f"+9199000000{n:02d}"


PERSONAS = [
    {
        "key": "creator-verified",
        "phone": phone(1),
        "name": "Ana Kulkarni (verified creator)",
        "role": "creator",
        "blurb": "Verified. Can apply to briefs, book slots, submit content.",
    },
    {
        "key": "creator-new",
        "phone": phone(2),
        "name": "Bo Sharma (half-finished creator)",
        "role": "creator",
        "blurb": "Signed up, profile incomplete. Use to test the builder and the apply gate.",
    },
    {
        "key": "creator-pending",
        "phone": phone(3),
        "name": "Cal Mehta (awaiting review)",
        "role": "creator",
        "blurb": "Submitted for review. Sits in the admin creator queue.",
    },
    {
        "key": "brand-verified",
        "phone": phone(4),
        "name": "Riya Nair",
        "role": "brand_manager",
        "business": "Thirdwave Coffee (verified)",
        "blurb": "Verified brand. Can publish, invite, see the directory and applicants.",
    },
    {
        "key": "brand-unverified",
        "phone": phone(5),
        "name": "Sam Iyer",
        "role": "brand_manager",
        "business": "Copper & Clay (unverified)",
        "blurb": "Submitted documents, not yet verified. Use to test the gate.",
    },
    {
        "key": "manager",
        "phone": phone(6),
        "name": "Priya Rao (WeAre manager)",
        "role": "campaign_manager",
        "blurb": "Staff. Gets the roster, daysheet and check-in screen for assigned campaigns.",
    },
    {
        "key": "team",
        "phone": phone(7),
        "name": "Devika Rao (WeAre team)",
        "role": "weare_team",
        "blurb": (
            "Staff. The admin console scoped to Thirdwave Coffee — no creator "
            "directory, no health, no audit, and every list ends at that brand."
        ),
    },
]


async def _user(p: dict, now: datetime):
    """Insert or update the account, keyed on phone."""
    doc = {
        "name": p["name"],
        "role": p["role"],
        "phone": p["phone"],
        "status": "active",
        # No password: these are OTP logins. A campaign manager is staff and
        # could have one, but giving it a known password would be the backdoor
        # this file exists to avoid.
        "password_hash": None,
        "updated_at": now,
    }
    if p["role"] == "brand_manager":
        doc["manager_name"] = p["name"]
    existing = await server.db.users.find_one({"phone": p["phone"]})
    if existing:
        await server.db.users.update_one({"_id": existing["_id"]}, {"$set": doc})
        uid = existing["_id"]
    else:
        doc["email"] = f"{p['key']}@seed.local"
        doc["created_at"] = now
        uid = (await server.db.users.insert_one(doc)).inserted_id
    if p["role"] == "brand_manager":
        # `_brand_scope` reads this on every brand request.
        await server.db.users.update_one({"_id": uid}, {"$set": {"brand_id": uid}})
    return uid


async def _creator_profile(p: dict, uid, now: datetime):
    base = {
        "user_id": uid,
        "name": p["name"],
        "email": f"{p['key']}@seed.local",
        "updated_at": now,
    }
    if p["key"] == "creator-verified":
        base.update(
            {
                "verification_status": "verified",
                "verified_at": now,
                "instagram_handle": "ana.eats",
                "instagram_profile_url": "https://instagram.com/ana.eats",
                "follower_count": 42000,
                "follower_count_self_reported": 42000,
                "city": "Bengaluru",
                "full_address": "12 Someplace, Indiranagar, Bengaluru 560038",
                "niches": ["fnb", "lifestyle"],
                "genres": ["food", "reviews"],
                "platforms": ["instagram"],
                "base_rate": 8000,
                # Payout details, so this persona can be walked all the way to
                # `in_payment` without hitting the payout_ready floor.
                "payout_upi": "ana@seedupi",
                "payout_account_name": p["name"],
                "pan": "AAAPA0000A",
                "submitted_for_review_at": now - timedelta(days=20),
            }
        )
    elif p["key"] == "creator-new":
        # Deliberately thin: this is the persona for testing the profile
        # builder and `_why_you_cannot_apply`.
        base.update(
            {
                "verification_status": "pending",
                "city": "Bengaluru",
                "platforms": ["instagram"],
            }
        )
    else:  # creator-pending
        base.update(
            {
                "verification_status": "pending",
                "instagram_handle": "cal.builds",
                "instagram_profile_url": "https://instagram.com/cal.builds",
                "follower_count": 9000,
                "follower_count_self_reported": 9000,
                "city": "Bengaluru",
                "full_address": "3 Elsewhere Rd, Koramangala, Bengaluru 560034",
                "niches": ["tech"],
                "genres": ["reviews"],
                "platforms": ["instagram"],
                "base_rate": 5000,
                # What puts them in the queue — see `_AWAITING_REVIEW_QUERY`.
                "submitted_for_review_at": now - timedelta(days=4),
            }
        )
    await server.db.creator_profiles.update_one(
        {"user_id": uid},
        {"$set": base, "$setOnInsert": {"created_at": now, "pending_review": False}},
        upsert=True,
    )


async def _brand_profile(p: dict, uid, now: datetime):
    verified = p["key"] == "brand-verified"
    await server.db.brand_profiles.update_one(
        {"user_id": uid},
        {
            "$set": {
                "user_id": uid,
                "business_name": p["business"],
                "legal_entity_name": f"{p['business']} Private Limited",
                "business_type": "private_limited",
                "category": "fnb",
                "areas": ["Indiranagar"],
                "registered_address": "1 Test Street, Bengaluru 560001",
                "contact_person_name": p["name"],
                "contact_person_designation": "Marketing lead",
                "contact_email": f"{p['key']}@seed.local",
                "contact_phone": p["phone"],
                "verified": verified,
                "verification_state": "verified" if verified else "pending_verification",
                "submitted_for_verification_at": now - timedelta(days=5),
                **({"verified_at": now} if verified else {}),
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


async def main() -> int:
    if not server._simulation_allowed():
        print(
            "Refusing to run.\n\n"
            "These accounts sign in by OTP, and without simulation mode you\n"
            "could not read the code — so they would be unusable anyway.\n\n"
            "  ALLOW_OTP_SIMULATION=true python seed_personas.py\n",
            file=sys.stderr,
        )
        return 1

    now = datetime.now(timezone.utc)
    made = []
    for p in PERSONAS:
        uid = await _user(p, now)
        if p["role"] == "creator":
            await _creator_profile(p, uid, now)
        elif p["role"] == "brand_manager":
            await _brand_profile(p, uid, now)
        made.append((p, uid))

    # Give the manager something to manage, and the verified brand something
    # to look at — otherwise both personas land on an empty screen and you
    # cannot tell "working" from "broken".
    manager = next(u for p, u in made if p["key"] == "manager")
    brand = next(u for p, u in made if p["key"] == "brand-verified")
    manager_p = next(p for p, _ in made if p["key"] == "manager")

    # And put the team member on the verified brand, or their console is
    # correctly empty and indistinguishable from a broken one — which is the
    # exact confusion this file exists to prevent.
    team = next(u for p, u in made if p["key"] == "team")
    await server.db.users.update_one(
        {"_id": team}, {"$addToSet": {"assigned_brand_ids": brand}}
    )
    existing = await server.db.campaigns.find_one({"brand_id": brand, "title": {"$regex": "^Seed:"}})
    if not existing:
        await server.db.campaigns.insert_one(
            {
                "brand_id": brand,
                "title": "Seed: weekend brunch reel",
                "brief": "A seeded brief so the manager and brand screens have something on them.",
                # Structured, and the sentence derived from it — the same
                # shape a brief posted through the form takes.
                **server._resolve_deliverables(
                    [
                        {"type": "reel", "quantity": 1},
                        {"type": "story", "quantity": 3},
                    ],
                    None,
                    True,
                ),
                "budget_per_creator": 8000,
                "compensation_type": "fixed",
                "category": "fnb",
                "area": "Indiranagar",
                "creators_needed": 3,
                "campaign_type": "personal_table",
                "start_date": now + timedelta(days=2),
                "end_date": now + timedelta(days=30),
                "manager_id": manager,
                "manager_name": manager_p["name"],
                "manager_phone": manager_p["phone"],
                "manager_email": "manager@seed.local",
                "status": "open",
                "created_at": now,
                "updated_at": now,
            }
        )

    print("\nSeeded personas — sign in at /login with the number, then read the")
    print("OTP from the server log (it is never sent while AiSensy is unset):\n")
    print("  docker compose logs -f api | grep -i 'simulation mode'\n")
    width = max(len(p["phone"]) for p in PERSONAS)
    for p in PERSONAS:
        print(f"  {p['phone']:<{width}}  {p['name']}")
        print(f"  {'':<{width}}  {p['blurb']}\n")
    print("  Admin signs in at /admin/login with ADMIN_EMAIL / ADMIN_PASSWORD.\n")
    print("These numbers are fake and must never reach production.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
