"""The AI brief writer: two lines in, a filled form out, and the rules in code.

The model is scripted (`FakeProvider`) and **deliberately misbehaves** in most
of these — invents a fee, a creator count, a date last week, an address, picks
barter — because the point is that the code holds each rule whatever the model
does. The route is driven against a mock database: it never creates a
campaign, counts ten drafts a day including failures, gives up at twenty
seconds, and with AI off the brand profile says so and the route refuses.
"""
from __future__ import annotations

import asyncio
import json
import typing
from datetime import date, timedelta

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import ai
import brief_writer as bw
import server
from fake_ai import FakeProvider, ai_on

TODAY = date(2026, 11, 2)  # a Monday
LOOP = asyncio.new_event_loop()


def run(body):
    async def go():
        db = AsyncMongoMockClient()["brief_writer"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    async def boom(self, **_):
        raise AssertionError(f"a test reached the real {self.name} provider")

    monkeypatch.setattr(ai.GeminiProvider, "complete", boom)
    monkeypatch.setattr(ai.AnthropicProvider, "complete", boom)
    monkeypatch.delenv("AI_ENABLED", raising=False)
    yield
    ai.use_provider(None)


def draft(**kw):
    return bw.BriefDraft.model_validate_json(json.dumps(kw))


def final(text, **kw):
    return bw.finalise(draft(**kw), text, today=TODAY, venue=kw.pop("_venue", None))


# ---------------------------------------------------------------------------
# 1. The literals are the server's
# ---------------------------------------------------------------------------


def test_the_mirrored_literals_are_the_servers():
    assert set(bw.CAMPAIGN_TYPES) == set(typing.get_args(server.CampaignType))
    assert set(bw.CATEGORIES) == set(typing.get_args(server.CATEGORY_LITERAL))
    assert set(bw.DELIVERABLE_TYPES) == set(server.DELIVERABLE_TYPES)
    assert bw.DISCLOSURE in server.DISCLOSURE_LABELS


def test_unknown_enum_values_are_dropped_not_mapped():
    d = draft(campaign_type="pop_up", category="crypto",
              deliverable_items=[{"type": "tiktok", "quantity": 2}, {"type": "Reel", "quantity": 1}])
    assert d.campaign_type is None and d.category is None
    assert [i.model_dump() for i in d.deliverable_items] == [{"type": "reel", "quantity": 1}]


# ---------------------------------------------------------------------------
# 2. No invented numbers
# ---------------------------------------------------------------------------


def test_numbers_survive_only_when_the_brand_typed_them():
    out = final(
        "Weekend brunch launch, 4 creators, 6k each",
        budget_per_creator=6000, total_budget=24000, creators_needed=4, revisions_included=2,
    )
    f = out["fields"]
    assert f["budget_per_creator"] == 6000 and f["creators_needed"] == 4
    assert "total_budget" not in f, "4 × 6k is arithmetic, not something the brand said"
    assert "revisions_included" not in f
    assert any("total_budget" in d for d in out["dropped"])


@pytest.mark.parametrize("text,value", [
    ("budget ₹8,000 per creator", 8000),
    ("8k per creator", 8000),
    ("₹1,20,000 for the whole thing", 120000),
    ("1.5L total for the whole thing", 150000),
])
def test_indian_number_forms_are_read(text, value):
    assert bw.stated(value, bw.input_numbers(text))


def test_a_spelled_out_thousand_is_not_read_and_so_is_dropped():
    """"eight thousand" is not a number the reader knows — the safe direction:
    the fee is left for the brand to type rather than guessed."""
    out = final("eight thousand per creator", budget_per_creator=8000)
    assert "budget_per_creator" not in out["fields"]


def test_a_written_field_with_an_invented_number_is_a_problem():
    d = draft(title="Brunch launch", brief="Get 10,000 views and 3 reels at our new menu launch.")
    problems = bw.text_problems(d, "brunch launch, need reels")
    assert any("10,000" in p for p in problems)
    assert any("'3'" in p for p in problems)
    assert bw.text_problems(draft(brief="Two reels at the launch."), "launch, 2 reels") == []


def test_non_english_output_is_a_problem():
    d = draft(brief="ಹೊಸ ಮೆನು ಲಾಂಚ್")
    assert bw.text_problems(d, "naya menu launch") != []


# ---------------------------------------------------------------------------
# 3. Dates
# ---------------------------------------------------------------------------


def test_a_date_in_the_past_is_dropped():
    out = final("launch on the 28th", campaign_type="launch", event_date="2026-10-28")
    assert "event_date" not in out["fields"]


def test_a_date_the_brand_never_mentioned_is_dropped():
    out = final("brunch launch, two reels", campaign_type="launch", event_date="2026-11-14")
    assert "event_date" not in out["fields"]


def test_a_relative_date_is_kept_and_its_time_needs_an_hour_in_the_text():
    out = final("launch this saturday 7pm", campaign_type="launch", event_date="2026-11-07", event_time="19:00")
    assert out["fields"]["event_date"] == "2026-11-07" and out["fields"]["event_time"] == "19:00"
    out2 = final("launch this saturday", campaign_type="launch", event_date="2026-11-07", event_time="19:00")
    assert "event_time" not in out2["fields"]


def test_a_relative_word_reaches_a_fortnight_and_no_further():
    near = final("any evening next week", campaign_type="personal_table",
                 start_date="2026-11-09", end_date="2026-11-13")
    assert near["fields"]["start_date"] == "2026-11-09"
    far = final("any evening next week", campaign_type="personal_table",
                start_date="2026-11-09", end_date="2026-12-29")
    assert "end_date" not in far["fields"]


def test_a_date_more_than_a_year_out_is_dropped():
    far = TODAY + timedelta(days=400)
    out = final(f"launch on {far.day}", campaign_type="launch", event_date=far.isoformat())
    assert "event_date" not in out["fields"]


def test_only_the_dates_the_type_has():
    out = final("tasting window 10th to 20th", campaign_type="personal_table",
                event_date="2026-11-10", start_date="2026-11-10", end_date="2026-11-20")
    assert "event_date" not in out["fields"]
    assert out["fields"]["start_date"] == "2026-11-10" and out["fields"]["end_date"] == "2026-11-20"


# ---------------------------------------------------------------------------
# 4. Disclosure, compensation, venue: code, not model
# ---------------------------------------------------------------------------


def test_disclosure_is_added_by_code_whatever_the_model_says():
    out = final("brunch reels, skip the #ad please", brief_dos=["Show the food"], mandatory_hashtags=["toitbrunch"])
    f = out["fields"]
    assert f["required_disclosure"] == "paid_partnership"
    assert f["mandatory_hashtags"] == ["#toitbrunch", "#ad"]
    assert f["brief_dos"][-1] == bw.DISCLOSURE_DO


def test_compensation_defaults_to_paid():
    assert final("4 creators, 6k each")["fields"]["compensation_type"] == "fixed"


@pytest.mark.parametrize("text", [
    "barter collab, free dinner for two",
    "complimentary stay for one night in exchange for a reel",
    "free meal for 3 creators, no fee",
])
def test_barter_is_never_selected_and_is_said(text):
    out = final(text)
    assert out["fields"]["compensation_type"] is None
    assert any("barter" in n.lower() for n in out["notices"])


def test_the_model_cannot_choose_compensation_or_a_venue():
    d = bw.BriefDraft.model_validate_json(json.dumps({
        "title": "Launch", "compensation_type": "barter", "venue_address": "Somewhere invented",
    }))
    out = bw.finalise(d, "launch with 2 reels", today=TODAY,
                      venue={"venue_address": "Toit, 298 100 Feet Road", "area": "Indiranagar"})
    assert out["fields"]["compensation_type"] == "fixed"
    assert out["fields"]["venue_address"] == "Toit, 298 100 Feet Road"


def test_a_delivery_gets_no_venue():
    out = bw.finalise(draft(campaign_type="delivery"), "send 5 hampers", today=TODAY,
                      venue={"venue_address": "Toit", "area": "Indiranagar"})
    assert "venue_address" not in out["fields"]


# ---------------------------------------------------------------------------
# 5. The route, driven
# ---------------------------------------------------------------------------


async def brand(db, **profile):
    uid = ObjectId()
    await db.brand_profiles.insert_one({"user_id": uid, "category": "fnb", **profile})
    return {"_id": str(uid), "role": "brand_manager", "brand_id": str(uid), "name": "Toit"}


def reply(**kw):
    return json.dumps({"title": "Weekend brunch launch", "brief": "Creators join our brunch launch.",
                       "campaign_type": "launch", "category": "fnb",
                       "deliverable_items": [{"type": "reel", "quantity": 1}], **kw})


def test_ai_off_is_a_supported_state():
    async def body(db):
        user = await brand(db)
        status = await server._brief_writer_status(ObjectId(user["_id"]))
        with pytest.raises(HTTPException) as exc:
            await server.draft_brief(server.BriefWriterPayload(text="brunch launch, 2 reels"), user=user)
        return status, exc.value

    status, exc = run(body)
    assert status == {"available": False}
    assert exc.status_code == 503 and exc.detail["code"] == "ai_off"


def test_a_draft_fills_fields_and_creates_no_campaign():
    fake = FakeProvider(reply(budget_per_creator=6000, creators_needed=4))

    async def body(db):
        user = await brand(db, outlets=[{"name": "Toit", "address": "298 100 Feet Road", "area": "Indiranagar"}])
        with ai_on(fake, GEMINI_API_KEY="k"):
            out = await server.draft_brief(
                server.BriefWriterPayload(text="Brunch launch, 4 creators at 6k each, call 9876543210"), user=user)
        return out, await db.campaigns.count_documents({})

    out, campaigns = run(body)
    f = out["fields"]
    assert campaigns == 0, "a draft never creates a campaign"
    assert f["budget_per_creator"] == 6000 and f["creators_needed"] == 4
    assert f["venue_address"] == "Toit, 298 100 Feet Road" and f["area"] == "Indiranagar"
    assert out["remaining"] == bw.DRAFTS_PER_DAY - 1
    sent = fake.sent()
    assert "9876543210" not in sent, "redact_for_ai runs on the description"
    assert "DATA-" in fake.calls[0]["user"], "the description goes as data"


def test_an_invented_number_in_the_prose_gets_one_retry_then_fails_closed():
    bad = reply(brief="Get 50,000 views at our launch.")
    good = reply(brief="Creators join our launch.")

    async def body(db, replies):
        user = await brand(db)
        with ai_on(FakeProvider(*replies), GEMINI_API_KEY="k"):
            try:
                return await server.draft_brief(server.BriefWriterPayload(text="brunch launch, reels"), user=user)
            except HTTPException as exc:
                return exc

    ok = run(lambda db: body(db, [bad, good]))
    assert ok["fields"]["brief"] == "Creators join our launch."
    failed = run(lambda db: body(db, [bad, bad]))
    assert isinstance(failed, HTTPException) and failed.detail["code"] == "draft_failed"
    assert failed.detail["message"] == "Couldn't draft this — fill it in below."


def test_ten_drafts_a_day_counting_failures():
    replies = [ai.ProviderError("provider_error")] * 4 + [reply()] * 20

    async def body(db):
        user = await brand(db)
        codes = []
        with ai_on(FakeProvider(*replies), GEMINI_API_KEY="k", AI_ACCOUNT_TASK_DAILY_LIMIT="100"):
            for _ in range(bw.DRAFTS_PER_DAY + 1):
                try:
                    await server.draft_brief(server.BriefWriterPayload(text="brunch launch, reels"), user=user)
                    codes.append(200)
                except HTTPException as exc:
                    codes.append(exc.detail.get("code"))
            status = await server._brief_writer_status(ObjectId(user["_id"]))
        return codes, status

    codes, status = run(body)
    assert codes[-1] == "draft_limit"
    assert len(codes) == bw.DRAFTS_PER_DAY + 1 and codes.count("draft_limit") == 1
    assert codes.count("draft_failed") >= 1, "a failed attempt is one of the ten"
    assert status["remaining"] == 0


def test_twenty_seconds_then_the_brand_fills_it_in(monkeypatch):
    monkeypatch.setattr(bw, "TIMEOUT_S", 0.05)

    class Slow(FakeProvider):
        async def complete(self, **kw):
            await asyncio.sleep(1)
            return await super().complete(**kw)

    async def body(db):
        user = await brand(db)
        with ai_on(Slow(reply()), GEMINI_API_KEY="k"):
            with pytest.raises(HTTPException) as exc:
                await server.draft_brief(server.BriefWriterPayload(text="brunch launch, reels"), user=user)
        return exc.value

    exc = run(body)
    assert exc.status_code == 503 and exc.detail["reason"] == "timeout"


def test_the_brand_profile_says_whether_to_show_it():
    async def body(db):
        user = await brand(db)
        with ai_on(FakeProvider(), GEMINI_API_KEY="k"):
            return await server._brief_writer_status(ObjectId(user["_id"]))

    assert run(body) == {"available": True, "limit": 10, "remaining": 10}
    assert "_brief_writer_status" in __import__("inspect").getsource(server.get_brand_profile)
