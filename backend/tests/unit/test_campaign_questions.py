"""Creator questions on a campaign.

A creator reading a brief had no way to ask anything short of applying and
hoping. `campaign_questions` is that channel: one thread per (campaign,
creator), asked from the campaign page, answered by whoever runs the campaign.

Three rules hold it up.

**It is not the work notes.** `collaboration_notes` stays the internal paper
trail creators never see. Questions are the opposite shape — the creator is a
party to the thread — and the two collections never mix.

**One creator's thread is invisible to every other creator.** The creator route
takes no creator_id at all: the thread it reads is the session's.

**Who answers follows `execution_owner`.** The brand's manager reads and
answers on a brand-run campaign; on a weare-run one the brand does not see the
thread at all — a creator asking "our team" a question has not agreed to the
brand reading it. Notification routing mirrors `apply_to_campaign` exactly.

Most of this file runs the real handlers against an in-memory Mongo, for the
reason the export leak-tests do.
"""
import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
Q = server.QuestionPayload


def source(fn):
    return inspect.getsource(fn)


def _world():
    """A brand-run and a weare-run campaign from one verified brand, plus a
    creator, a bystander creator, the brand's manager, a WeAre manager, a
    rival brand and an admin."""
    server.db = AsyncMongoMockClient()["t"]
    now = datetime.now(timezone.utc)
    w = {"now": now}

    async def build():
        w["brand_uid"] = ObjectId()
        w["manager_uid"] = ObjectId()
        w["rival_uid"] = ObjectId()
        await server.db.users.insert_many([
            {"_id": w["brand_uid"], "role": "brand_manager", "name": "Priya"},
            {"_id": w["manager_uid"], "role": "campaign_manager", "name": "Rohan"},
            {"_id": w["rival_uid"], "role": "brand_manager", "name": "Rival"},
        ])
        await server.db.brand_profiles.insert_one(
            {"user_id": w["brand_uid"], "business_name": "Blue Tokai", "verified": True}
        )
        base = {
            "brand_id": w["brand_uid"], "status": "open", "title": "Brunch launch",
            "budget_per_creator": 8000, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 3, "created_at": now,
            "event_date": now + timedelta(days=30),
        }
        w["brand_run"] = (
            await server.db.campaigns.insert_one(
                {**base, "execution_owner": "brand", "manager_id": w["brand_uid"]}
            )
        ).inserted_id
        w["weare_run"] = (
            await server.db.campaigns.insert_one(
                {**base, "title": "Roastery tour", "execution_owner": "weare",
                 "manager_id": w["manager_uid"]}
            )
        ).inserted_id
        for key, name in (("creator_uid", "Asha"), ("bystander_uid", "Meera")):
            oid = ObjectId()
            w[key] = oid
            await server.db.users.insert_one({"_id": oid, "role": "creator", "name": name})
            await server.db.creator_profiles.insert_one(
                {"user_id": oid, "name": name, "verification_status": "verified",
                 # Planted for the leak test: these must never reach a
                 # brand-facing thread payload.
                 "phone": "+919812345678", "email": "asha@example.com",
                 "full_address": "14 Hidden Lane"}
            )

    asyncio.run(build())
    w["creator"] = {"_id": str(w["creator_uid"]), "role": "creator", "name": "Asha"}
    w["bystander"] = {"_id": str(w["bystander_uid"]), "role": "creator", "name": "Meera"}
    w["brand"] = {"_id": str(w["brand_uid"]), "role": "brand_manager", "brand_id": None}
    w["rival"] = {"_id": str(w["rival_uid"]), "role": "brand_manager", "brand_id": None}
    w["manager"] = {"_id": str(w["manager_uid"]), "role": "campaign_manager"}
    w["admin"] = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}
    return w


def _status(coro):
    try:
        asyncio.run(coro)
        return 200
    except HTTPException as e:
        return e.status_code


# --- The thread is the creator's own -----------------------------------------


def test_the_creator_route_takes_no_creator_id():
    """The thread it reads is the session's. Another creator's thread is not
    reachable from this route with any input at all."""
    for fn in (server.my_campaign_questions, server.ask_campaign_question):
        assert "creator_id" not in inspect.signature(fn).parameters
        assert 'ObjectId(user["_id"])' in source(fn)


def test_one_creator_never_sees_another_s_thread():
    w = _world()
    asyncio.run(
        server.ask_campaign_question(str(w["brand_run"]), Q(body="Parking?"), w["creator"])
    )
    theirs = asyncio.run(server.my_campaign_questions(str(w["brand_run"]), w["bystander"]))
    mine = asyncio.run(server.my_campaign_questions(str(w["brand_run"]), w["creator"]))

    assert len(mine["questions"]) == 1
    assert theirs["questions"] == []


def test_asking_respects_campaign_visibility():
    """A private brief's question box answers the same 404 as its page."""
    w = _world()

    async def scenario():
        private = (
            await server.db.campaigns.insert_one(
                {"brand_id": w["brand_uid"], "status": "open", "title": "Secret",
                 "visibility": "private", "creators_needed": 2, "created_at": w["now"],
                 "event_date": w["now"] + timedelta(days=30)}
            )
        ).inserted_id
        return private

    private = asyncio.run(scenario())
    assert _status(
        server.ask_campaign_question(str(private), Q(body="hi"), w["creator"])
    ) == 404


def test_a_creator_on_the_campaign_can_ask_after_it_leaves_live():
    """Mid-shoot is when the questions come; a bystander is refused."""
    w = _world()

    async def scenario():
        await server.db.campaigns.update_one(
            {"_id": w["brand_run"]}, {"$set": {"status": "in_progress"}}
        )
        await server.db.collaborations.insert_one(
            {"campaign_id": w["brand_run"], "creator_id": w["creator_uid"],
             "active": True, "state": "accepted", "created_at": w["now"]}
        )

    asyncio.run(scenario())
    assert _status(
        server.ask_campaign_question(str(w["brand_run"]), Q(body="What time?"), w["creator"])
    ) == 200
    assert _status(
        server.ask_campaign_question(str(w["brand_run"]), Q(body="hi"), w["bystander"])
    ) == 409


# --- Who answers -------------------------------------------------------------


def test_the_staff_door_follows_execution_owner():
    w = _world()
    matrix = [
        (w["brand"], w["brand_run"], 200),
        (w["brand"], w["weare_run"], 404),  # the whole point
        (w["rival"], w["brand_run"], 404),
        (w["manager"], w["weare_run"], 200),
        (w["manager"], w["brand_run"], 404),
        (w["admin"], w["weare_run"], 200),
    ]
    for who, cid, want in matrix:
        got = _status(server.campaign_question_threads(str(cid), who))
        assert got == want, f"{who['role']} on {cid}: {got} != {want}"


def test_no_creator_role_on_any_staff_route():
    for fn in (server.campaign_question_threads, server.campaign_question_thread,
               server.answer_campaign_question):
        assert '"creator"' not in source(fn).split("Depends")[1].split(")")[0]


def test_an_answer_reaches_the_creator_with_the_side_word():
    """The creator is told who they are dealing with in the same two words
    execution_owner prints everywhere else — never a staff role name."""
    w = _world()
    asyncio.run(
        server.ask_campaign_question(str(w["brand_run"]), Q(body="Parking?"), w["creator"])
    )
    out = asyncio.run(
        server.answer_campaign_question(
            str(w["brand_run"]), str(w["creator_uid"]), Q(body="Yes."), w["brand"]
        )
    )
    assert out["author_side"] == "brand"

    thread = asyncio.run(server.my_campaign_questions(str(w["brand_run"]), w["creator"]))
    assert [q["author_side"] for q in thread["questions"]] == ["creator", "brand"]


def test_a_reply_into_a_void_is_refused():
    """Replying where nobody asked would start a thread the creator never
    opened — that is outreach, and outreach is the invite flow."""
    w = _world()
    assert _status(
        server.answer_campaign_question(
            str(w["brand_run"]), str(w["creator_uid"]), Q(body="hi"), w["admin"]
        )
    ) == 404


def test_the_thread_is_append_only():
    """No edit, no delete — a record that can be quietly rewritten is not a
    record, the same rule the work notes live by."""
    text = Path(server.__file__).read_text()

    assert "campaign_questions.update_one" not in text
    assert "campaign_questions.delete" not in text


def test_both_directions_are_audited():
    assert "campaign.question" in source(server.ask_campaign_question)
    assert "campaign.question_answered" in source(server.answer_campaign_question)
    for fn in (server.ask_campaign_question, server.answer_campaign_question):
        assert "_campaign_audit_context(campaign)" in source(fn)


# --- Notifications -----------------------------------------------------------


def test_a_question_is_routed_like_an_application():
    """weare-run → notify_weare_team (assigned manager, or every admin when
    unstaffed); brand-run → the brand's manager. The brand hears nothing about
    a weare-run thread."""
    w = _world()
    for cid in (w["brand_run"], w["weare_run"]):
        asyncio.run(
            server.ask_campaign_question(str(cid), Q(body="Parking?"), w["creator"])
        )

    async def read():
        return await server.db.notifications.find({"event": "campaign_question"}).to_list(50)

    notes = asyncio.run(read())
    recipients = {n["user_id"] for n in notes}
    assert w["brand_uid"] in recipients
    assert w["manager_uid"] in recipients
    assert not any(
        n["user_id"] == w["brand_uid"] and "Roastery" in (n.get("body") or "")
        for n in notes
    ), "the brand was told about a weare-run thread"


def test_an_answer_notifies_the_creator_with_a_link_back():
    w = _world()
    asyncio.run(
        server.ask_campaign_question(str(w["brand_run"]), Q(body="Parking?"), w["creator"])
    )
    asyncio.run(
        server.answer_campaign_question(
            str(w["brand_run"]), str(w["creator_uid"]), Q(body="Yes."), w["brand"]
        )
    )

    async def read():
        return await server.db.notifications.find_one(
            {"user_id": w["creator_uid"], "event": "question_answered"}
        )

    note = asyncio.run(read())
    assert note and note.get("link") == f"/campaigns/{w['brand_run']}"


def test_both_events_are_wired_for_whatsapp():
    """In NOTIFY_EVENTS, and documented in .env.example — the env-docs test
    holds the second half, this pins the first."""
    assert "campaign_question" in server.NOTIFY_EVENTS
    assert "question_answered" in server.NOTIFY_EVENTS


# --- The queue ---------------------------------------------------------------


def test_unanswered_means_the_last_word_is_the_creator_s():
    w = _world()
    asyncio.run(
        server.ask_campaign_question(str(w["weare_run"]), Q(body="Parking?"), w["creator"])
    )
    rows = asyncio.run(server.unanswered_questions(w["admin"]))
    assert [r["campaign_title"] for r in rows] == ["Roastery tour"]

    asyncio.run(
        server.answer_campaign_question(
            str(w["weare_run"]), str(w["creator_uid"]), Q(body="On-site."), w["manager"]
        )
    )
    assert asyncio.run(server.unanswered_questions(w["admin"])) == []


def test_a_follow_up_reopens_the_thread():
    """Answered once is not answered forever."""
    w = _world()
    asyncio.run(
        server.ask_campaign_question(str(w["weare_run"]), Q(body="Parking?"), w["creator"])
    )
    asyncio.run(
        server.answer_campaign_question(
            str(w["weare_run"]), str(w["creator_uid"]), Q(body="On-site."), w["manager"]
        )
    )
    asyncio.run(
        server.ask_campaign_question(str(w["weare_run"]), Q(body="And charging?"), w["creator"])
    )
    rows = asyncio.run(server.unanswered_questions(w["admin"]))
    assert len(rows) == 1 and rows[0]["body"] == "And charging?"


def test_the_queue_is_console_only_and_scoped_to_what_the_caller_runs():
    """It is a queue of work, and work belongs to whoever runs the campaign —
    so a WeAre team member gets theirs. **Scoped in the query, not on the
    rows**: the cap below is applied after the sort, so filtering afterwards
    would shorten a scoped queue to whatever survived somebody else's
    hundred."""
    src = source(server.unanswered_questions)

    assert "require_roles(*CONSOLE_ROLES)" in src
    assert "_console_campaign_query(user)" in src
    assert "find({})" not in src


# --- What a brand may read ---------------------------------------------------


def test_planted_contact_details_never_reach_a_thread_payload():
    """The thread's creator block goes through _brand_visible_creator; run
    with recognisable values planted and search the output."""
    w = _world()
    asyncio.run(
        server.ask_campaign_question(str(w["brand_run"]), Q(body="Parking?"), w["creator"])
    )
    out = asyncio.run(server.campaign_question_threads(str(w["brand_run"]), w["brand"]))
    flat = str(out)

    for value in ("+919812345678", "asha@example.com", "14 Hidden Lane"):
        assert value not in flat, f"{value} leaked into a brand-facing thread"


def test_questions_never_touch_the_work_notes():
    """The two collections are different audiences and must never mix — a
    creator-readable route that reads collaboration_notes is the leak this
    separation exists to prevent."""
    for fn in (server.my_campaign_questions, server.ask_campaign_question,
               server.campaign_question_threads, server.campaign_question_thread,
               server.answer_campaign_question, server.unanswered_questions):
        assert "collaboration_notes" not in source(fn)


def test_the_application_page_is_told_whether_to_show_the_thread():
    """`questions_enabled`, decided server-side — false for a brand reading a
    weare-run application, so the shared screen never asks who is looking."""
    assert "questions_enabled" in source(server.get_application)
    assert "_question_staff_may_see(campaign, user)" in source(server.get_application)


# --- The frontend ------------------------------------------------------------


def frontend(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def test_the_creator_asks_from_the_campaign_page():
    src = frontend("pages", "CampaignDetail.jsx")

    assert "CampaignQuestions" in src


def test_the_application_page_carries_the_thread_behind_the_flag():
    src = frontend("components", "application", "ApplicationDetail.jsx")

    assert "QuestionThread" in src
    assert "questions_enabled" in src


def test_the_queue_has_a_question_lane():
    src = frontend("components", "admin", "ActionQueue.jsx")

    assert "/questions/unanswered" in src
    assert '"question"' in src


def test_the_thread_component_never_asks_the_role():
    for name in ("CampaignQuestions.jsx", "QuestionThread.jsx"):
        src = frontend("components", "questions", name)
        for smell in ('role === "admin"', "user?.role", "user.role"):
            assert smell not in src, f"{name} branches on role"
