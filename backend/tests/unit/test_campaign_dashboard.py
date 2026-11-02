"""The results dashboard: per-post data, its history, and the block it draws.

The verification the brief asked for is the first class: a campaign of nine
creators and eleven posts, where **the totals equal the sum of the posts** and
**reels plus carousels equal total views** — asserted, not eyeballed. Then the
Instagram half (one unsupported metric never blanks a post, thumbnails refresh
with the numbers), the six-hourly schedule and its freeze, the history the
chart is drawn from, and the brand allow-list.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

NOW = datetime.now(timezone.utc)
LOOP = asyncio.new_event_loop()


def run(body):
    async def go():
        db = AsyncMongoMockClient()["dashboard"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


PLANTED = {
    "phone": "+919812345678", "email": "creator.private@example.com",
    "full_address": "42 Secret Lane", "location_lat": 12.97161, "pan": "ABCDE1234F",
    "payout_upi": "someone@okhdfc", "payout_account_number": "918273645500",
}

# Nine creators, eleven posts: two creators posted twice. (name, [(format, views,
# reach, likes, comments, shares, saves, days_ago_posted)]).
CREATORS = [
    ("Aditi Rao", [("reel", 98000, 61000, 4100, 210, 880, 640, 10)]),
    ("Kiran M", [("reel", 76000, 50500, 3300, 160, 410, 390, 9),
                 ("carousel", 21000, 16000, 1200, 70, 90, 260, 6)]),
    ("Priya S", [("reel", 64000, 41000, 2800, 120, 300, 280, 9)]),
    ("Rahul T", [("carousel", 18000, 14000, 900, 40, 60, 200, 8)]),
    ("Tanvi K", [("reel", 52000, 36000, 2500, 110, 260, 240, 8),
                 ("reel", 31000, 22000, 1400, 60, 120, 150, 3)]),
    ("Meera J", [("carousel", 15000, 11000, 800, 30, 50, 170, 7)]),
    ("Arjun N", [("reel", 44000, 30000, 1900, 90, 200, 180, 7)]),
    ("Sana Q", [("reel", 39000, 27000, 1700, 80, 150, 160, 5)]),
    ("Vikram P", [("carousel", 12000, 9000, 600, 25, 30, 120, 4)]),
]


async def seed(db, *, creators=CREATORS, live=True, manual_for=()):
    """The brief's verification campaign. Readings land through the real
    recorder, so the post rows, the snapshots and the per-delivery rollup are
    the ones production writes."""
    brand = ObjectId()
    await db.users.insert_one({"_id": brand, "role": "brand_manager", "name": "Toit", "brand_id": brand})
    campaign = {
        "_id": ObjectId(), "brand_id": brand, "title": "Weekend brunch launch",
        "status": "in_progress", "created_at": NOW - timedelta(days=20),
        "start_date": NOW - timedelta(days=12), "end_date": NOW - timedelta(days=2),
        "category": "fnb", "campaign_type": "personal_table", "compensation_type": "fixed",
        "budget_per_creator": 15000, "execution_owner": "brand",
        "deliverable_items": [{"type": "reel", "quantity": 1}],
    }
    await db.campaigns.insert_one(campaign)
    collabs = []
    for i, (name, posts) in enumerate(creators):
        creator, cid = ObjectId(), ObjectId()
        await db.users.insert_one({"_id": creator, "role": "creator", "name": name, **PLANTED})
        await db.creator_profiles.insert_one(
            {"user_id": creator, "name": name, "verification_status": "verified",
             "instagram_handle": f"creator{i}", **PLANTED}
        )
        urls = [f"https://www.instagram.com/{'reel' if p[0] == 'reel' else 'p'}/C{i}x{j}/"
                for j, p in enumerate(posts)]
        collab = {
            "_id": cid, "campaign_id": campaign["_id"], "creator_id": creator,
            "state": "content_approved" if live else "slot_booked",
            "agreed_at": NOW - timedelta(days=15), "agreed_amount": 15000.0,
            "content_urls": urls if live else [],
            "content_submitted_at": NOW - timedelta(days=posts[0][7]),
            "updated_at": NOW - timedelta(days=1),
        }
        await db.collaborations.insert_one(collab)
        collabs.append(collab)
        if not live:
            continue
        for j, (fmt, views, reach, likes, comments, shares, saves, ago) in enumerate(posts):
            key = server._permalink_key(urls[j])
            source = "manual" if name in manual_for else "instagram"
            # Two readings per post: a first look, then the latest. The chart
            # is drawn from both; the totals from the latest only.
            for frac, when in ((0.6, NOW - timedelta(days=ago) + timedelta(hours=12)),
                               (1.0, NOW - timedelta(hours=2))):
                await server._record_post_reading(
                    collab, key,
                    {"views": int(views * frac), "reach": int(reach * frac), "likes": int(likes * frac),
                     "comments": int(comments * frac), "shares": int(shares * frac), "saves": int(saves * frac)},
                    source=source, captured_at=when,
                    meta={"permalink": urls[j], "media_type": fmt,
                          "posted_at": NOW - timedelta(days=ago),
                          "thumbnail_url": f"https://cdn.example/{key}.jpg",
                          "carousel_count": 4 if fmt == "carousel" else None},
                )
            await server._rollup_collab_performance(collab)
    user = {"_id": str(brand), "role": "brand_manager", "name": "Toit", "brand_id": str(brand)}
    return {"user": user, "campaign": campaign, "id": str(campaign["_id"]), "collabs": collabs}


def dashboard_of(w):
    return server.brand_campaign_analytics(w["id"], w["user"])


# ---------------------------------------------------------------------------
# 1. The verification campaign: nine creators, eleven posts
# ---------------------------------------------------------------------------


class TestNineCreatorsElevenPosts:
    @pytest.fixture(scope="class")
    def data(self):
        async def body(db):
            w = await seed(db)
            return await dashboard_of(w)

        return run(body)["dashboard"]

    def test_the_shape(self, data):
        assert data["creators"]["total"] == 9 and data["creators"]["posted"] == 9
        assert data["posts"]["live"] == 11 and len(data["posts"]["items"]) == 11

    @pytest.mark.parametrize("metric,key", [
        ("views", "views"), ("reach", "reach_sum"), ("likes", "likes"),
        ("comments", "comments"), ("shares", "shares"), ("saves", "saves"),
    ])
    def test_totals_equal_the_sum_of_the_posts(self, data, metric, key):
        expected = sum(p[{"reach": 2}.get(metric, {"views": 1, "likes": 3, "comments": 4,
                                                   "shares": 5, "saves": 6}.get(metric, 0))]
                       for _, posts in CREATORS for p in posts)
        assert data["totals"][key] == expected
        assert data["totals"][key] == sum(p[metric] for p in data["posts"]["items"])

    def test_reels_plus_carousels_equal_total_views(self, data):
        by = {f["format"]: f for f in data["by_format"]}
        assert set(by) == {"reel", "carousel"}
        assert by["reel"]["views"] + by["carousel"]["views"] == data["totals"]["views"]
        assert by["reel"]["posts"] == 7 and by["carousel"]["posts"] == 4

    def test_engagement_rate_is_interactions_over_reach(self, data):
        t = data["totals"]
        assert t["interactions"] == t["likes"] + t["comments"] + t["shares"] + t["saves"]
        assert t["engagement_rate"] == round(t["interactions"] / t["reach_sum"] * 100, 2)

    def test_views_by_creator_are_summed_and_sorted(self, data):
        rows = data["by_creator"]
        assert [r["views"] for r in rows] == sorted((r["views"] for r in rows), reverse=True)
        tanvi = next(r for r in rows if r["name"] == "Tanvi K")
        assert tanvi["views"] == 52000 + 31000 and tanvi["posts"] == 2
        assert sum(r["views"] for r in rows) == data["totals"]["views"]

    def test_the_wall_is_sorted_by_views_and_carries_what_a_tile_needs(self, data):
        items = data["posts"]["items"]
        assert [p["views"] for p in items] == sorted((p["views"] for p in items), reverse=True)
        top = items[0]
        assert top["creator_name"] == "Aditi Rao" and top["media_type"] == "reel"
        assert top["permalink"].startswith("https://www.instagram.com/reel/")
        assert top["thumbnail_url"].startswith("https://cdn.example/")
        carousel = next(p for p in items if p["media_type"] == "carousel")
        assert carousel["carousel_count"] == 4

    def test_the_timeseries_is_cumulative_and_ends_at_the_total(self, data):
        series = data["timeseries"]
        assert series, "no chart"
        views = [d["views"] for d in series]
        assert views == sorted(views), "cumulative views never go down"
        assert views[-1] == data["totals"]["views"]

    def test_reels_are_marked_on_the_day_they_went_live(self, data):
        names = [m["name"] for m in data["markers"]]
        assert "Aditi Rao" in names and "Rahul T" not in names, "carousels are not marked"
        assert len(data["markers"]) == 7

    def test_no_contact_field_or_value_reaches_the_dashboard(self, data):
        blob = json.dumps(data, default=str)
        for value in PLANTED.values():
            assert str(value) not in blob, value
        for key in server.BRAND_FORBIDDEN_CREATOR_FIELDS:
            assert f'"{key}"' not in blob, key


# ---------------------------------------------------------------------------
# 2. Empty and part-live
# ---------------------------------------------------------------------------


class TestEmptyAndPartLive:
    def test_before_anything_is_live_there_are_people_and_no_zeros(self):
        async def body(db):
            w = await seed(db, live=False)
            return (await dashboard_of(w))["dashboard"]

        data = run(body)
        assert data["posts"]["live"] == 0 and data["creators"]["posted"] == 0
        assert all(v is None for v in data["totals"].values()), data["totals"]
        assert {c["status"] for c in data["creators"]["list"]} == {"Shoot booked"}
        assert data["timeseries"] == [] and data["by_format"] == []

    def test_part_live_totals_cover_live_posts_only(self):
        async def body(db):
            w = await seed(db)
            # Two creators have not posted yet.
            for collab in w["collabs"][:2]:
                await db.collaborations.update_one(
                    {"_id": collab["_id"]}, {"$set": {"state": "slot_booked"}}
                )
            return (await dashboard_of(w))["dashboard"]

        data = run(body)
        live_posts = [p for _, posts in CREATORS[2:] for p in posts]
        assert data["posts"]["live"] == len(live_posts)
        assert data["totals"]["views"] == sum(p[1] for p in live_posts)
        assert data["creators"]["posted"] == 7 and data["creators"]["total"] == 9
        assert data["posts"]["total"] >= data["posts"]["live"]

    def test_a_reading_entered_by_hand_says_so(self):
        async def body(db):
            w = await seed(db, manual_for=("Sana Q",))
            return (await dashboard_of(w))["dashboard"]

        items = run(body)["posts"]["items"]
        sana = next(p for p in items if p["creator_name"] == "Sana Q")
        assert sana["source"] == "manual"
        assert {p["source"] for p in items if p["creator_name"] != "Sana Q"} == {"instagram"}


# ---------------------------------------------------------------------------
# 3. The history the chart is drawn from
# ---------------------------------------------------------------------------


class TestHistory:
    def test_snapshots_are_appended_never_overwritten(self):
        async def body(db):
            w = await seed(db, creators=CREATORS[:1])
            return await db.performance_snapshots.count_documents({}), await db.post_performance.count_documents({})

        snapshots, posts = run(body)
        assert posts == 1 and snapshots == 2

    def test_the_latest_reading_on_or_before_a_day_is_carried_forward(self):
        d0 = datetime(2026, 10, 1, 6, tzinfo=timezone.utc)
        posts = [{"key": "a", "posted_day": d0.astimezone(server.SHOOT_TZ).date()},
                 {"key": "b", "posted_day": None}]
        snaps = [
            {"post_key": "a", "captured_at": d0, "metrics": {"views": 100}},
            {"post_key": "a", "captured_at": d0 + timedelta(days=3), "metrics": {"views": 400}},
            {"post_key": "b", "captured_at": d0 + timedelta(days=1), "metrics": {"views": 50}},
        ]
        series = server._cumulative_views(posts, snaps, (d0 + timedelta(days=10)).date())
        assert [d["views"] for d in series] == [100, 150, 150, 450]

    def test_a_manual_reading_merges_rather_than_erases(self):
        async def body(db):
            w = await seed(db, creators=CREATORS[:1])
            collab = w["collabs"][0]
            await server._record_performance(
                collab, server.PerformancePayload(likes=5000), {"_id": str(ObjectId()), "name": "Ops"}
            )
            return await db.post_performance.find_one({"collaboration_id": collab["_id"]})

        row = run(body)
        assert row["likes"] == 5000 and row["views"] == 98000, "views from Instagram survive"
        assert row["source"] == "manual"

    def test_old_readings_are_backfilled_into_posts(self):
        async def body(db):
            collab = {"_id": ObjectId(), "campaign_id": ObjectId(), "creator_id": ObjectId(),
                      "content_urls": ["https://www.instagram.com/reel/OLD1/"]}
            await db.collaborations.insert_one(collab)
            await db.content_performance.insert_one(
                {"collaboration_id": collab["_id"], "campaign_id": collab["campaign_id"],
                 "views": 1200, "reach": 900, "source": "manual",
                 "content_url": collab["content_urls"][0], "captured_at": NOW - timedelta(days=30)}
            )
            first = await server.backfill_post_performance()
            again = await server.backfill_post_performance()
            row = await db.post_performance.find_one({})
            return first, again, row, await db.performance_snapshots.count_documents({})

        first, again, row, snaps = run(body)
        assert (first, again) == (1, 0), "idempotent"
        assert row["post_key"] == "OLD1" and row["views"] == 1200 and snaps == 1


# ---------------------------------------------------------------------------
# 4. Instagram: one unsupported metric never blanks a post
# ---------------------------------------------------------------------------


def fake_graph(*, refuse_set=True, refuse=("saved",), thumb="https://cdn.ig/new.jpg", fail_media=False):
    """A stand-in for `_instagram_get`: a media list, and insights that refuse
    the whole set when it contains a metric this media type lacks — which is
    what Instagram does."""
    calls = []

    async def get(path, params):
        calls.append((path, dict(params)))
        if path.endswith("/me/media"):
            if fail_media:
                raise HTTPException(status_code=502, detail="Instagram is having a moment")
            return {"data": [
                {"id": "m1", "permalink": "https://www.instagram.com/reel/C0x0/",
                 "media_type": "VIDEO", "media_product_type": "REELS",
                 "timestamp": (NOW - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S+0000"),
                 "thumbnail_url": thumb},
            ]}
        asked = params["metric"].split(",")
        if any(m in refuse for m in asked) and (len(asked) > 1 or refuse_set):
            raise HTTPException(status_code=502, detail="(#100) metric not supported for this media")
        values = {"views": 9000, "reach": 7000, "likes": 400, "comments": 30, "shares": 55, "saved": 20}
        return {"data": [{"name": m, "values": [{"value": values[m]}]} for m in asked]}

    return get, calls


@pytest.fixture
def instagram_on(monkeypatch):
    monkeypatch.setattr(server, "instagram_configured", lambda: True)
    monkeypatch.setattr(server, "_decrypt_token", lambda _: "token")


async def connected_collab(db):
    creator, campaign = ObjectId(), ObjectId()
    await db.instagram_connections.insert_one({"user_id": creator, "status": "connected", "access_token": "x"})
    collab = {"_id": ObjectId(), "campaign_id": campaign, "creator_id": creator,
              "state": "content_approved", "content_urls": ["https://www.instagram.com/reel/C0x0/"],
              "updated_at": NOW}
    await db.collaborations.insert_one(collab)
    await db.campaigns.insert_one({"_id": campaign, "brand_id": ObjectId()})
    return collab


class TestInstagram:
    def test_one_unsupported_metric_costs_that_metric_not_the_post(self, monkeypatch, instagram_on):
        get, calls = fake_graph()
        monkeypatch.setattr(server, "_instagram_get", get)

        async def body(db):
            collab = await connected_collab(db)
            posts, reason = await server._fetch_instagram_posts(collab)
            return posts, reason

        posts, reason = run(body)
        assert reason is None and len(posts) == 1
        post = posts[0]
        assert post["metrics"] == {"views": 9000, "reach": 7000, "likes": 400, "comments": 30, "shares": 55}
        assert post["unsupported"] == ["saves"]
        insight_calls = [c for c in calls if c[0].endswith("/insights")]
        assert len(insight_calls) == 1 + 6, "the set, then one metric at a time"

    def test_the_set_is_chosen_per_media_type(self):
        assert "saves" not in server._IG_METRICS_BY_FORMAT["story"]
        assert "shares" in server._IG_METRICS_BY_FORMAT["reel"]
        assert server._post_format({"media_type": "CAROUSEL_ALBUM", "media_product_type": "FEED"}) == "carousel"
        assert server._post_format({"media_type": "VIDEO", "media_product_type": "REELS"}) == "reel"
        assert server._post_format({"media_type": "IMAGE", "media_product_type": "STORY"}) == "story"

    def test_calls_are_pinned_to_a_graph_version(self, monkeypatch, instagram_on):
        get, calls = fake_graph(refuse=())
        monkeypatch.setattr(server, "_instagram_get", get)
        run(lambda db: connected_collab(db))

        async def body(db):
            return await server._fetch_instagram_posts(await connected_collab(db))

        run(body)
        assert all(path.startswith(f"/{server.INSTAGRAM_MEDIA_API_VERSION}/") for path, _ in calls)

    def test_the_thumbnail_is_refreshed_with_the_numbers(self, monkeypatch, instagram_on):
        get, _ = fake_graph(refuse=(), thumb="https://cdn.ig/fresh.jpg")
        monkeypatch.setattr(server, "_instagram_get", get)

        async def body(db):
            collab = await connected_collab(db)
            await db.post_performance.insert_one(
                {"collaboration_id": collab["_id"], "post_key": "C0x0",
                 "thumbnail_url": "https://cdn.ig/expired.jpg"}
            )
            posts, _ = await server._fetch_instagram_posts(collab)
            await server._record_instagram_posts(collab, posts)
            return await db.post_performance.find_one({"post_key": "C0x0"})

        row = run(body)
        assert row["thumbnail_url"] == "https://cdn.ig/fresh.jpg" and row["thumbnail_fetched_at"]

    def test_a_carousel_is_shown_by_its_first_child_with_a_count(self):
        thumb, count = server._post_thumbnail(
            {"children": {"data": [{"media_url": "https://a/1.jpg"}, {"media_url": "https://a/2.jpg"}]}}
        )
        assert thumb == "https://a/1.jpg" and count == 2


# ---------------------------------------------------------------------------
# 5. Every six hours, until a fortnight, then frozen; backing off on errors
# ---------------------------------------------------------------------------


class TestRefreshSchedule:
    def test_a_refresh_schedules_the_next_one_six_hours_out(self, monkeypatch, instagram_on):
        get, _ = fake_graph(refuse=())
        monkeypatch.setattr(server, "_instagram_get", get)

        async def body(db):
            collab = await connected_collab(db)
            report = await server.refresh_post_insights()
            again = await server.refresh_post_insights()
            return report, again, await db.collaborations.find_one({"_id": collab["_id"]})

        report, again, collab = run(body)
        assert report["refreshed"] == 1 and again["considered"] == 0, "not due again yet"
        next_at = server._as_utc(collab["insights_refresh"]["next_at"])
        assert timedelta(hours=5, minutes=59) < next_at - NOW < timedelta(hours=6, minutes=5)
        assert "frozen_at" not in collab["insights_refresh"]

    def test_a_post_older_than_a_fortnight_is_frozen(self, monkeypatch, instagram_on):
        get, _ = fake_graph(refuse=())

        async def old(path, params):
            data = await get(path, params)
            if path.endswith("/me/media"):
                data["data"][0]["timestamp"] = (NOW - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%S+0000")
            return data

        monkeypatch.setattr(server, "_instagram_get", old)

        async def body(db):
            collab = await connected_collab(db)
            await server.refresh_post_insights()
            later = await server.refresh_post_insights()
            return later, await db.collaborations.find_one({"_id": collab["_id"]})

        later, collab = run(body)
        assert collab["insights_refresh"]["frozen_at"]
        assert later["considered"] == 0, "a frozen post is never read again"

    def test_a_failure_backs_off_rather_than_retrying_every_pass(self, monkeypatch, instagram_on):
        get, _ = fake_graph(fail_media=True)
        monkeypatch.setattr(server, "_instagram_get", get)

        async def body(db):
            collab = await connected_collab(db)
            report = await server.refresh_post_insights()
            return report, await db.collaborations.find_one({"_id": collab["_id"]})

        report, collab = run(body)
        state = collab["insights_refresh"]
        assert report["failed"] == 1 and state["failures"] == 1
        assert server._as_utc(state["next_at"]) - NOW >= timedelta(minutes=59)

    def test_off_when_instagram_is_not_configured(self):
        assert run(lambda db: server.refresh_post_insights())["skipped"] == "not configured"

    def test_the_cadence_constants(self):
        assert server.POST_REFRESH_HOURS == 6 and server.POST_FREEZE_DAYS == 14
        assert server.POST_REFRESH_CALLS_PER_CREATOR < 200


# ---------------------------------------------------------------------------
# 6. Doors
# ---------------------------------------------------------------------------


class TestDoors:
    def test_an_admin_sees_the_same_dashboard(self):
        async def body(db):
            w = await seed(db, creators=CREATORS[:3])
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "Ops"}
            mine = (await dashboard_of(w))["dashboard"]
            theirs = (await server.brand_campaign_analytics(w["id"], admin))["dashboard"]
            return mine, theirs

        mine, theirs = run(body)
        assert mine == theirs

    def test_another_brand_gets_a_404(self):
        async def body(db):
            w = await seed(db, creators=CREATORS[:1])
            stranger = {"_id": str(ObjectId()), "role": "brand_manager", "brand_id": str(ObjectId())}
            with pytest.raises(HTTPException) as err:
                await server.brand_campaign_analytics(w["id"], stranger)
            return err.value.status_code

        assert run(body) == 404

    def test_the_last_campaign_delta_is_against_one_campaign(self):
        async def body(db):
            w = await seed(db, creators=CREATORS[:3])
            earlier = {"_id": ObjectId(), "brand_id": w["campaign"]["brand_id"], "title": "Diwali",
                       "status": "closed", "created_at": NOW - timedelta(days=90)}
            await db.campaigns.insert_one(earlier)
            await db.content_performance.insert_one(
                {"collaboration_id": ObjectId(), "campaign_id": earlier["_id"], "views": 100000, "reach": 1}
            )
            return (await dashboard_of(w))["dashboard"]["versus_last_campaign"]

        delta = run(body)
        total = 98000 + 76000 + 21000 + 64000
        assert delta["title"] == "Diwali" and delta["views"] == 100000
        assert delta["change_percent"] == round((total - 100000) / 100000 * 100, 1)
