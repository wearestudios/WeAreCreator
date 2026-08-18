"""Campaign visibility: public briefs and invite-only ones.

"public" is the shop window — every verified creator can find it, and it may be
promoted to the open internet. "private" is invite-only: never in browse,
search, suggestions, the share page, the sitemap or the filter options, and
only creators holding an invitation (or an application that predates the flip)
can read or pitch. Enforced server-side on every campaign read and on apply —
the UI's pills and pickers are a courtesy on top.

Half of this file *runs* the handlers against an in-memory Mongo rather than
reading their source, for the reason the export leak-tests do: source-reading
catches the mistake somebody makes on purpose; running the code catches the
private brief that arrives through a query nobody remembered was a listing.

The other change here is the creator feed's order: "most relevant first",
scored by `score_campaign_for_creator` against the creator's own profile. It is
the mirror of `score_creator_for_campaign` — same vocabulary, pointed the other
way — and it deliberately knows nothing about money, so a barter brief ranks on
fit exactly like a paid one instead of sinking to the bottom of every feed.
"""
import asyncio
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def source(fn):
    return inspect.getsource(fn)


# --- The model ---------------------------------------------------------------


def test_two_visibilities_and_no_third():
    assert server.CAMPAIGN_VISIBILITIES == ("public", "private")


def test_absent_reads_as_public():
    """Campaigns predate the field and were all findable."""
    assert server._campaign_visibility({}) == "public"
    assert server._campaign_visibility({"visibility": None}) == "public"
    assert server._campaign_visibility({"visibility": "sekrit"}) == "public"
    assert server._campaign_visibility({"visibility": "private"}) == "private"


def test_the_public_filter_is_ne_not_equality():
    """The pre-migration trap, again: an equality test on "public" matches
    nothing written before the field existed. Same as execution_owner and
    showcase."""
    assert server.PUBLIC_CAMPAIGN_QUERY == {"visibility": {"$ne": "private"}}


def test_the_brand_sets_it_at_post_time_and_can_change_it():
    assert server.PostCampaignPayload.model_fields["visibility"].default == "public"
    assert "visibility" in server.UpdateCampaignPayload.model_fields


def test_creating_a_campaign_writes_it():
    assert '"visibility": payload.visibility' in source(server.create_brand_campaign)


@pytest.mark.parametrize(
    "fn", ["_serialize_campaign", "_serialize_brand_campaign", "list_all_campaigns"]
)
def test_every_campaign_row_carries_it(fn):
    """The owner's console prints one of two words on every row, and a creator
    who can see a private brief is told it is invite-only."""
    assert "_campaign_visibility" in source(getattr(server, fn))


# --- The doors, run rather than read -----------------------------------------


def _world():
    """A verified brand, one public and one private live brief, and three
    creators: a stranger, one invited, one already applied."""
    server.db = AsyncMongoMockClient()["t"]
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=30)
    w = {"now": now}
    w["brand_id"] = ObjectId()

    async def build():
        await server.db.brand_profiles.insert_one(
            {"user_id": w["brand_id"], "business_name": "Blue Tokai", "verified": True}
        )
        base = {
            "brand_id": w["brand_id"], "status": "open", "budget_per_creator": 8000,
            "compensation_type": "fixed", "category": "fnb", "area": "Indiranagar",
            "city": "Bengaluru", "creators_needed": 3, "created_at": now,
            "event_date": future,
        }
        w["public_id"] = (
            await server.db.campaigns.insert_one({**base, "title": "Public brief"})
        ).inserted_id
        w["private_id"] = (
            await server.db.campaigns.insert_one(
                {**base, "title": "Private tasting", "visibility": "private"}
            )
        ).inserted_id
        for key in ("stranger", "invited", "applicant"):
            oid = ObjectId()
            w[key] = oid
            await server.db.users.insert_one({"_id": oid, "role": "creator", "name": key})
            await server.db.creator_profiles.insert_one(
                {"user_id": oid, "verification_status": "verified"}
            )
        await server.db.campaign_invitations.insert_one(
            {"campaign_id": w["private_id"], "creator_id": w["invited"], "created_at": now}
        )
        await server.db.collaborations.insert_one(
            {"campaign_id": w["private_id"], "creator_id": w["applicant"],
             "active": True, "state": "applied", "created_at": now}
        )

    asyncio.run(build())
    return w


def _as(oid, role="creator"):
    return {"_id": str(oid), "role": role, "name": "x"}


def _titles(resp):
    return [r["title"] for r in json.loads(resp.body)]


def test_browse_hides_a_private_brief_from_a_stranger():
    w = _world()
    titles = _titles(asyncio.run(server.list_campaigns(user=_as(w["stranger"]))))

    assert titles == ["Public brief"]


def test_browse_shows_it_through_both_doors():
    """An invitation, or an application that predates the brand flipping the
    brief private — going private must not vanish it from people already on it."""
    w = _world()

    assert "Private tasting" in _titles(
        asyncio.run(server.list_campaigns(user=_as(w["invited"])))
    )
    assert "Private tasting" in _titles(
        asyncio.run(server.list_campaigns(user=_as(w["applicant"])))
    )


def test_admins_see_everything():
    w = _world()
    titles = _titles(
        asyncio.run(server.list_campaigns(user={"_id": str(ObjectId()), "role": "admin"}))
    )

    assert "Private tasting" in titles


def test_the_detail_read_is_a_404_not_a_403():
    """Whether the campaign exists is itself what the privacy protects — the
    same reasoning as _own_campaign_or_404."""
    w = _world()
    with pytest.raises(HTTPException) as e:
        asyncio.run(server.get_campaign(str(w["private_id"]), _as(w["stranger"])))

    assert e.value.status_code == 404


def test_the_detail_read_opens_for_the_invited_and_the_applied():
    w = _world()
    for who in ("invited", "applicant"):
        out = asyncio.run(server.get_campaign(str(w["private_id"]), _as(w[who])))
        assert out["title"] == "Private tasting"
        assert out["visibility"] == "private", "the page needs the word for its pill"


def test_apply_refuses_a_stranger_and_takes_an_invitee():
    w = _world()
    payload = server.ApplyPayload(pitch="Love this brief", quoted_rate=5000)
    with pytest.raises(HTTPException) as e:
        asyncio.run(
            server.apply_to_campaign(str(w["private_id"]), payload, _as(w["stranger"]))
        )
    assert e.value.status_code == 404

    out = asyncio.run(
        server.apply_to_campaign(str(w["private_id"]), payload, _as(w["invited"]))
    )
    assert out


def test_the_share_page_404s_a_private_brief():
    """A private brief has no public page at all — not a login wall."""
    w = _world()

    class Req:
        base_url = "https://api.example/"

    with pytest.raises(HTTPException) as e:
        asyncio.run(server.public_campaign_page(str(w["private_id"]), Req()))
    assert e.value.status_code == 404
    # And the public one still serves.
    resp = asyncio.run(server.public_campaign_page(str(w["public_id"]), Req()))
    assert resp.status_code == 200


def test_no_public_internet_surface_lists_it():
    """The sitemap, the landing preview and the brand page's shelf — the three
    places a stranger with no account could otherwise read the title."""
    w = _world()

    class Req:
        base_url = "https://api.example/"

    sitemap = asyncio.run(server.public_sitemap()).body.decode()
    assert str(w["private_id"]) not in sitemap
    assert str(w["public_id"]) in sitemap

    preview = asyncio.run(server.public_campaign_preview())
    assert "Private tasting" not in [c["title"] for c in preview["campaigns"]]
    assert preview["total_open"] == 1

    page = asyncio.run(server.public_brand_page(str(w["brand_id"]), Req())).body.decode()
    assert "Private tasting" not in page


def test_the_filter_options_do_not_leak_its_neighbourhood():
    """A private brief's area showing up as a dropdown option announces its
    existence to everyone the privacy is for."""
    w = _world()

    async def scenario():
        await server.db.campaigns.update_one(
            {"_id": w["private_id"]}, {"$set": {"area": "Sadashivanagar"}}
        )
        return await server.campaign_filters(user=_as(w["stranger"]))

    options = asyncio.run(scenario())
    assert "Sadashivanagar" not in options["areas"]


def test_suggestions_never_volunteer_a_private_brief():
    """A recommendation is a disclosure."""
    assert "PUBLIC_CAMPAIGN_QUERY" in source(server._suggested_campaigns)


def test_a_money_filter_says_nothing_about_barter():
    """A barter brief keeps its vestigial budget, so before this a "₹5k–15k"
    filter surfaced a barter stay whose leftover number happened to be 5000."""
    w = _world()

    async def scenario():
        await server.db.campaigns.insert_one(
            {"brand_id": w["brand_id"], "title": "Barter stay", "status": "open",
             "compensation_type": "barter", "budget_per_creator": 5000,
             "category": "fnb", "area": "Indiranagar", "creators_needed": 2,
             "created_at": w["now"], "event_date": w["now"] + timedelta(days=30)}
        )
        with_money = _titles(
            await server.list_campaigns(user=_as(w["stranger"]), budget_min=4000, budget_max=15000)
        )
        without = _titles(await server.list_campaigns(user=_as(w["stranger"])))
        return with_money, without

    with_money, without = asyncio.run(scenario())
    assert "Barter stay" not in with_money
    assert "Barter stay" in without, "unfiltered, barter is on the feed"


def test_the_and_clauses_never_clobber_each_other():
    """The city filter, the keyword search and the visibility cut all want a
    slot in $and. One assignment among the appends silently drops whatever came
    before it — so there must be no bare assignment left."""
    src = source(server.list_campaigns)

    assert 'query["$and"] =' not in src
    assert src.count('query.setdefault("$and", [])') >= 3


def test_visibility_is_a_cut_not_a_filter():
    """It is applied for creators inside the handler, not offered as a query
    parameter anyone could unset."""
    params = inspect.signature(server.list_campaigns).parameters

    assert "visibility" not in params
    assert "_visible_campaign_ids_for_creator" in source(server.list_campaigns)


# --- Most relevant first -----------------------------------------------------


def test_the_scorer_is_pure():
    src = source(server.score_campaign_for_creator)

    assert "await" not in src and "db." not in src


def test_an_unknown_creator_scores_everything_zero():
    """Which makes the sort fall through to recency — the old order, and the
    right one for somebody we know nothing about."""
    campaign = {"category": "fnb", "area": "Indiranagar", "city": "Bengaluru"}

    assert server.score_campaign_for_creator(campaign, None) == 0.0
    assert server.score_campaign_for_creator(campaign, {}) == 0.0


def test_fit_is_niches_city_and_neighbourhood():
    campaign = {"category": "fnb", "area": "Indiranagar", "city": "Bengaluru",
                "title": "Brunch launch", "brief": "", "deliverables": ""}
    # Three matched terms ("cafes"/"food" via the fnb synonyms, "brunch" from
    # the title) is where the work signal saturates, so this is full marks.
    profile = {"niches": ["cafes", "brunch"], "genres": ["food"], "city": "Bengaluru",
               "address": "Indiranagar"}
    full = server.score_campaign_for_creator(campaign, profile)
    away = server.score_campaign_for_creator(
        {**campaign, "city": "Mumbai", "area": "Bandra"}, profile
    )

    assert full > away
    assert full == sum(server.CREATOR_FEED_WEIGHTS.values())


def test_a_long_tag_list_saturates():
    """Two matches beat one; five are not five times stronger."""
    campaign = {"category": "fnb", "area": "", "city": "Mumbai",
                "title": "cafes food brunch dessert coffee", "brief": "", "deliverables": ""}
    three = server.score_campaign_for_creator(
        campaign, {"niches": ["cafes", "food", "brunch"]}
    )
    five = server.score_campaign_for_creator(
        campaign, {"niches": ["cafes", "food", "brunch", "dessert", "coffee"]}
    )

    assert three == five == server.CREATOR_FEED_WEIGHTS["work_match"]


def test_the_scorer_knows_nothing_about_money():
    """Or "most relevant" quietly becomes "paid first" and barter sinks — the
    invisible version of the bug where it was missing outright."""
    import ast, textwrap

    # The docstring says *why* money is absent, so the check reads the code
    # body, not the prose.
    tree = ast.parse(textwrap.dedent(source(server.score_campaign_for_creator)))
    fn = tree.body[0]
    body = ast.unparse(fn.body[1:] if isinstance(fn.body[0], ast.Expr) else fn.body)

    assert "budget" not in body
    assert "compensation" not in body


def test_barter_ranks_on_fit_like_anything_else():
    profile = {"niches": ["cafes"], "city": "Bengaluru", "address": "Indiranagar"}
    base = {"category": "fnb", "area": "Indiranagar", "city": "Bengaluru",
            "title": "cafes", "brief": "", "deliverables": ""}

    assert server.score_campaign_for_creator(
        {**base, "compensation_type": "barter"}, profile
    ) == server.score_campaign_for_creator(
        {**base, "compensation_type": "fixed", "budget_per_creator": 50000}, profile
    )


def test_relevance_orders_the_feed_and_recency_breaks_ties():
    w = _world()

    async def scenario():
        await server.db.creator_profiles.update_one(
            {"user_id": w["stranger"]},
            {"$set": {"niches": ["cafes"], "genres": ["food"], "city": "Bengaluru",
                      "address": "Indiranagar"}},
        )
        # Newer than everything, matching nothing this creator does.
        await server.db.campaigns.insert_one(
            {"brand_id": w["brand_id"], "title": "Mumbai retail brief", "status": "open",
             "category": "retail", "area": "Bandra", "city": "Mumbai",
             "budget_per_creator": 90000, "creators_needed": 2,
             "created_at": w["now"] + timedelta(hours=1),
             "event_date": w["now"] + timedelta(days=30)}
        )
        default = _titles(await server.list_campaigns(user=_as(w["stranger"])))
        newest = _titles(await server.list_campaigns(user=_as(w["stranger"]), sort="newest"))
        return default, newest

    default, newest = asyncio.run(scenario())
    assert default[0] == "Public brief", f"fit should beat freshness: {default}"
    assert newest[0] == "Mumbai retail brief", "the explicit sort still means what it says"


def test_pagination_and_the_count_survive_relevance():
    """Scored in Python, but still sliced by offset/limit with the matched
    total in the header — the contract the page was built on."""
    w = _world()
    resp = asyncio.run(server.list_campaigns(user=_as(w["stranger"]), limit=1, offset=0))

    assert len(json.loads(resp.body)) == 1
    assert resp.headers["X-Total-Count"] == "1"


# --- The frontend ------------------------------------------------------------


def frontend(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def test_the_live_pool_is_gone():
    """It summed budget_per_creator across the feed — a figure barter made a
    lie and nobody could act on."""
    src = frontend("pages", "Campaigns.jsx")

    assert "Live pool" not in src
    assert "totalBudget" not in src


def test_the_feed_defaults_to_relevance():
    src = frontend("pages", "Campaigns.jsx")

    assert 'useState("relevant")' in src
    assert '{ value: "relevant", label: "Most relevant first" }' in src
    assert 'sort !== "relevant"' in src, "the default travels as an absence"


def test_the_filters_still_start_unset():
    src = frontend("pages", "Campaigns.jsx")

    for state in ("city", "area", "category", "campaignType", "compensation"):
        assert f"const [{state}, set" in src


def test_the_words_mirror_the_backend_reader():
    """`campaignVisibility` treats absent as public exactly like
    `_campaign_visibility` — a pre-field campaign must not render a blank pill."""
    src = frontend("lib", "visibility.js")

    assert 'campaign?.visibility === "private" ? "private" : "public"' in src


def test_posting_offers_the_choice():
    src = frontend("pages", "PostCampaign.jsx")

    assert "VISIBILITY.picker" in src
    assert 'useState("public")' in src, "public unless the brand says otherwise"
    assert "visibility," in src, "and it rides the payload"


def test_the_choice_survives_an_edit_round_trip():
    """Opening a private brief to fix a typo must not silently flip it public."""
    src = frontend("pages", "PostCampaign.jsx")

    assert 'setVisibility(data.visibility === "private" ? "private" : "public")' in src


@pytest.mark.parametrize(
    "page",
    [("pages", "Campaigns.jsx"), ("pages", "CampaignDetail.jsx"),
     ("pages", "BrandDashboardView.jsx")],
)
def test_the_indicator_is_wherever_a_campaign_is_shown(page):
    assert "VISIBILITY.badge" in frontend(*page)


def test_the_owner_sees_a_word_on_every_row_not_only_private_ones():
    """A brand reading "Invite-only" on one row learns the vocabulary; a brand
    reading nothing on the others has to guess what the default is."""
    src = frontend("pages", "BrandDashboardView.jsx")

    assert '"Public"' in src


def test_the_admin_detail_names_it():
    src = frontend("components", "admin", "CampaignDetailPage.jsx")

    assert "visibilityLabel(campaign)" in src


def test_the_dev_dependency_is_declared():
    """These tests import mongomock_motor; an undeclared import is a suite that
    passes here and fails in CI."""
    dev = (Path(server.__file__).resolve().parent / "requirements-dev.txt").read_text()

    assert "mongomock-motor" in dev


def test_no_share_button_on_a_private_brief():
    """Its /c/{id} page 404s by design, so a share button would copy a dead
    link. Absent, not disabled — nothing to re-enable from devtools."""
    for page in (("pages", "Campaigns.jsx"), ("pages", "CampaignDetail.jsx")):
        src = frontend(*page)
        idx = src.index("<ShareButton")
        assert "isPrivate" in src[max(0, idx - 400):idx], f"{page[-1]} shares private briefs"
