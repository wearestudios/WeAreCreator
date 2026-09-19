"""The go-to-market surface: pages a stranger can find, and one claim on them.

Two problems, and they are one problem. A search asset with no claim on it is a
page somebody leaves; a claim on a page nobody reaches is a claim nobody reads.
So this file covers both halves and the edges between them.

**Every page is driven and read back, never grepped.** A category page that
renders, carries valid structured data, and links to a case study is three
different facts, and only the last of them is worth anything on its own — the
edges are where search value compounds. So the tests render the real handlers
against a real mock database and parse what comes out, including the JSON-LD,
which is the one part of a page nobody ever looks at and therefore the one part
that silently rots.

**The sitemap is tested as a promise rather than as a list.** Listing a URL is
telling a crawler that a page exists; the test that matters is that every URL
in it actually serves, which is the failure `/for-brands` had for months in the
opposite direction. `TestTheSitemap` walks what it emits and asks the routes.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"
PUBLIC = FRONTEND.parent / "public"

LOOP = None


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


class Req:
    """Enough of a Request for `str(request.base_url)`."""

    base_url = "http://testserver/"


def run(body):
    async def go():
        db = AsyncMongoMockClient()["gtm"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return _loop().run_until_complete(go())


def guard_allows(fn, role):
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                guard = dep.dependency
                break
    else:
        raise AssertionError(f"{fn.__name__} declares no require_roles guard")

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    return _loop().run_until_complete(go())


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


NOW = datetime.now(timezone.utc)


async def seed(db, *, creators=30, city="Bengaluru"):
    """A world with creators, a case study and a published post behind it.

    **One city is deliberately below `SEO_CITY_FLOOR`.** Without it the floor
    tests cannot fail: every city in the fixture would qualify, so deleting the
    floor from the sitemap would change nothing and the test would pass on a
    broken build. Found by break-testing, which is the only way that shape of
    hole shows up — Kolkata gets a single creator and must never be listed.
    """
    for i in range(creators):
        await db.creator_profiles.insert_one(
            {
                "user_id": ObjectId(),
                "verification_status": "verified",
                "niches": ["cafe", "brunch"] if i % 2 else ["fashion", "styling"],
                "city": city if i < creators - 4 else "Mumbai",
            }
        )
    await db.creator_profiles.insert_one(
        {"user_id": ObjectId(), "verification_status": "verified",
         "niches": ["cafe"], "city": "Kolkata"}
    )
    await db.case_studies.insert_one(
        {
            "_id": ObjectId(),
            "slug": "toit-tasting",
            "status": "published",
            "title": "A tasting that filled three sittings",
            "brand_name": "Toit",
            "category": "fnb",
            "city": city,
            "published_at": NOW,
            "updated_at": NOW,
            "creator_ids": [],
            "results": {},
        }
    )
    await db.blog_posts.insert_one(
        {
            "_id": ObjectId(),
            "slug": "reel-rates-bengaluru",
            "status": "published",
            "title": "What a reel costs in Bengaluru",
            "summary": "Real numbers from briefs we actually ran this year.",
            "body": "## The short answer\n\nRates move with reach.\n\n- Micro\n- Mid",
            "category": "rate-benchmarks",
            "published_at": NOW,
            "updated_at": NOW,
        }
    )


def ld_of(html: str) -> list:
    """The JSON-LD graph, parsed. Raises if the page emits something a crawler
    would reject — which is the point: invalid structured data is worse than
    none, because it looks present."""
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert m, "no structured data on the page"
    data = json.loads(m.group(1))
    assert data.get("@context") == "https://schema.org"
    # **Both shapes are valid JSON-LD and both are in use.** The newer pages
    # emit an `@graph` so one script can hold the organisation, the page and
    # the breadcrumb; the case-study pages predate that and emit a single
    # typed object. Normalising here rather than rewriting a page that works
    # keeps this a test about what a crawler receives.
    return data["@graph"] if "@graph" in data else [data]


def types_of(html: str) -> set:
    return {b.get("@type") for b in ld_of(html)}


# ---------------------------------------------------------------------------
# 1. The promise
# ---------------------------------------------------------------------------


class TestTheClaim:
    def test_it_leads_with_the_thing_only_we_do(self):
        """Every competitor books a creator. The claim has to be about running
        the campaign or it is a claim anybody could make."""
        claim = server.CAMPAIGN_CLAIM.lower()
        assert "run the campaign" in claim
        assert "booking" in claim

    def test_it_is_sayable_in_one_breath(self):
        """A hero somebody can repeat back after one read. Twelve words is the
        outside of a breath; the real one is eight."""
        words = [w for w in re.split(r"\s+", server.CAMPAIGN_CLAIM) if w]
        assert len(words) <= 12, f"{len(words)} words"

    def test_there_are_exactly_three_proof_points(self):
        """Three is what fits under a headline and what a reader holds. A
        fourth is a list, and a list is something people skim."""
        assert len(server.CAMPAIGN_PROOF_POINTS) == 3

    def test_the_proof_points_are_the_three_that_were_asked_for(self):
        joined = " ".join(
            f"{a} {b}" for a, b in server.CAMPAIGN_PROOF_POINTS
        ).lower()
        assert "verified" in joined
        assert "agreed in writing" in joined or "in writing" in joined
        assert "fee" in joined and ("back" in joined or "refund" in joined)

    def test_the_positioning_survives_it(self):
        """The enemy is disorganisation, never agencies — and no claim the
        operation cannot back. Checked against the claim itself, because a new
        headline is exactly where an overclaim gets in."""
        blob = (
            server.CAMPAIGN_CLAIM
            + " "
            + " ".join(f"{a} {b}" for a, b in server.CAMPAIGN_PROOF_POINTS)
        ).lower()
        for banned in server._FORBIDDEN_MARKETING_PHRASES:
            assert banned not in blob, banned


# ---------------------------------------------------------------------------
# 2 & 3. Category and city pages
# ---------------------------------------------------------------------------


class TestCategoryPages:
    def test_every_taxonomy_group_gets_one(self):
        """**Derived from `CREATOR_TAXONOMY`, not listed.** A group added to
        the taxonomy has to get a page from that edit alone, or the page and
        the vocabulary drift and ten of fifteen groups have nowhere to land."""
        assert len(server.SEO_CATEGORIES) == len(server.CREATOR_TAXONOMY)
        labels = {c["label"] for c in server.SEO_CATEGORIES}
        assert labels == {label for label, _ in server.CREATOR_TAXONOMY}

    def test_every_one_has_hand_written_campaign_examples(self):
        """The fallback exists so a newly added group never 500s. It is not a
        licence to ship fifteen pages saying the same sentence with a noun
        swapped — a search engine reads those as one page.

        This is the test that catches the silent version of the bug: four keys
        were spelled `food-drink` against slugs of `food-and-drink` and every
        one of them fell through to the generic copy while rendering fine.
        """
        for cat in server.SEO_CATEGORIES:
            assert cat["slug"] in server._SEO_CATEGORY_CAMPAIGNS, cat["slug"]
            assert cat["campaign_kinds"], f"{cat['slug']} maps to no campaign kind"

    @pytest.mark.parametrize("slug", [c["slug"] for c in server.SEO_CATEGORIES])
    def test_each_page_renders_with_valid_structured_data(self, slug):
        async def body(db):
            await seed(db)
            return (await server.public_category_page(slug, Req())).body.decode()

        html = run(body)
        assert types_of(html) == {"Organization", "CollectionPage", "BreadcrumbList"}
        assert '<link rel="canonical"' in html
        assert "<title>" in html

    def test_the_page_carries_the_claim_and_its_proof(self):
        async def body(db):
            await seed(db)
            return (
                await server.public_category_page("food-and-drink", Req())
            ).body.decode()

        html = run(body)
        assert server.CAMPAIGN_CLAIM in html
        for label, _ in server.CAMPAIGN_PROOF_POINTS:
            assert label in html

    def test_the_indicative_count_is_rounded_down_and_absent_when_small(self):
        """"40+ creators" holding while the fortieth signs up is the point.
        "3 creators" is a number that argues against us, and silence beats it."""
        assert server._indicative(43) == "25+"
        assert server._indicative(250) == "250+"
        assert server._indicative(9) is None

    def test_it_routes_to_the_right_signup(self):
        """A page that ranks and ends taught somebody about us and sent them
        nowhere."""
        async def body(db):
            await seed(db)
            return (await server.public_category_page("fashion", Req())).body.decode()

        assert "/signup?role=brand" in run(body)

    def test_nothing_is_escaped_twice(self):
        """**`&amp;` on a page is a bug a test has to catch**, because it only
        shows up in a browser and it shows up as a page that looks broken.

        "Food & Drink" is a real taxonomy label, so every page for it runs the
        ampersand through escaping — and a caller that escapes before handing a
        value to a renderer that escapes again produces "Food &amp;amp; Drink"
        on screen. Found in a screenshot; pinned here.
        """
        async def body(db):
            await seed(db)
            return {
                "category": (
                    await server.public_category_page("food-and-drink", Req())
                ).body.decode(),
                "city": (
                    await server.public_city_page("bengaluru", Req())
                ).body.decode(),
            }

        for name, html in run(body).items():
            assert "&amp;amp;" not in html, f"{name} double-escapes an ampersand"
            assert "&amp;lt;" not in html, f"{name} double-escapes a bracket"

    def test_the_footer_sits_inside_the_page_gutter(self):
        """Outside `.wrap` it has no padding and runs to the viewport edge
        while everything above it is inset. Also caught in a browser."""
        async def body(db):
            await seed(db)
            return (
                await server.public_category_page("food-and-drink", Req())
            ).body.decode()

        html = run(body)
        wrap = html.index('<div class="wrap">')
        assert html.index("<footer") > wrap
        assert html.index("</footer>") < html.rindex("</div>")

    def test_an_unknown_category_is_a_404_rather_than_an_empty_page(self):
        async def body(db):
            with pytest.raises(HTTPException) as exc:
                await server.public_category_page("underwater-basket-weaving", Req())
            return exc.value.status_code

        assert run(body) == 404

    def test_the_title_and_description_are_written_for_intent(self):
        """Not for branding. A title that is the company name and nothing else
        ranks for the company name, which is the one search we do not need to
        win."""
        async def body(db):
            await seed(db)
            return (
                await server.public_category_page("food-and-drink", Req())
            ).body.decode()

        html = run(body)
        title = re.search(r"<title>(.*?)</title>", html, re.S).group(1).lower()
        desc = re.search(r'name="description" content="(.*?)"', html, re.S).group(1).lower()
        assert "creators" in title and "campaign" in title
        assert not title.startswith("weare"), "the brand is not the search intent"
        assert len(desc) > 80, "a description under ~80 chars is a wasted slot"
        assert len(desc) < 320


class TestCityPages:
    def test_bengaluru_renders_with_valid_structured_data(self):
        async def body(db):
            await seed(db)
            return (await server.public_city_page("bengaluru", Req())).body.decode()

        html = run(body)
        assert types_of(html) == {"Organization", "CollectionPage", "BreadcrumbList"}
        assert "Bengaluru" in html
        assert server.CAMPAIGN_CLAIM in html

    def test_a_city_with_nobody_behind_it_is_a_404(self):
        """**The interesting half.** A page ranking for a city we cannot serve
        costs more than not ranking: a brand arrives, finds nothing, and learns
        something about us. Below the floor the honest answer is the category
        page, which promises no location."""
        async def body(db):
            # Bengaluru 26, Mumbai 4, Kolkata 1 — the last is under the floor.
            await seed(db, creators=30)
            with pytest.raises(HTTPException) as exc:
                await server.public_city_page("kolkata", Req())
            return exc.value.status_code

        assert run(body) == 404

    def test_the_floor_is_the_same_one_the_sitemap_uses(self):
        """Listing a city whose page 404s is telling a crawler about a page we
        refuse to serve — and a soft 404 in a sitemap is worse than an absence,
        because it is a claim we then withdraw."""
        async def body(db):
            await seed(db, creators=30)
            sitemap = (await server.public_sitemap()).body.decode()
            listed = re.findall(r"<loc>([^<]*/creators-in/[^<]*)</loc>", sitemap)
            served = []
            for loc in listed:
                slug = loc.rsplit("/", 1)[-1]
                try:
                    await server.public_city_page(slug, Req())
                    served.append(slug)
                except HTTPException:
                    pass
            return listed, served

        listed, served = run(body)
        assert listed, "no city pages listed at all"
        assert len(served) == len(listed), "the sitemap lists a city page that 404s"

    def test_an_unknown_city_is_a_404(self):
        async def body(db):
            await seed(db)
            with pytest.raises(HTTPException) as exc:
                await server.public_city_page("atlantis", Req())
            return exc.value.status_code

        assert run(body) == 404


# ---------------------------------------------------------------------------
# 4. The FAQ
# ---------------------------------------------------------------------------


class TestTheFaq:
    def test_it_emits_a_faqpage_a_crawler_can_read(self):
        html = server._faq_page_html()
        graph = {b["@type"]: b for b in ld_of(html)}
        assert "FAQPage" in graph
        entities = graph["FAQPage"]["mainEntity"]
        assert len(entities) == len(server.FAQ_ENTRIES)
        for q in entities:
            assert q["@type"] == "Question"
            assert q["acceptedAnswer"]["@type"] == "Answer"
            assert q["name"].endswith("?"), q["name"]
            assert len(q["acceptedAnswer"]["text"]) > 40

    def test_it_answers_the_questions_that_were_asked_for(self):
        joined = " ".join(f"{q} {a}" for q, a in server.FAQ_ENTRIES).lower()
        for topic in (
            "cost",          # what it costs
            "verif",         # how creators are verified
            "paid",          # when creators get paid
            "fill",          # what happens if a campaign underfills
            "own",           # who owns the content
            "disclosure",    # how disclosure works
            "how long",      # how long a campaign takes
        ):
            assert topic in joined, topic

    def test_the_answers_match_what_the_code_actually_does(self):
        """**A FAQ that describes a flow we removed is worse than no FAQ**, for
        the reason `Legal.jsx` is held to the same standard: somebody reads it
        and believes it. Each of these is checked against the rule that
        implements it rather than against a memory of it.
        """
        answers = {q.lower(): a.lower() for q, a in server.FAQ_ENTRIES}

        cost = next(a for q, a in answers.items() if "cost" in q)
        assert "on top" in cost, "the commission is charged on top, never deducted"
        assert "never taken out" in cost or "100%" in cost

        fill = next(a for q, a in answers.items() if "fill" in q)
        # `_refund_reckoning`'s actual rule: rejected creators forfeit it.
        assert "turned down" in fill or "rejected" in fill

        contact = next(a for q, a in answers.items() if "directly" in q)
        assert "never" in contact
        for field in ("phone", "email", "address"):
            assert field in contact

        where = next(a for q, a in answers.items() if "operate" in q)
        assert "bengaluru" in where

    def test_it_makes_no_claim_the_operation_cannot_back(self):
        blob = " ".join(f"{q} {a}" for q, a in server.FAQ_ENTRIES).lower()
        for banned in server._FORBIDDEN_MARKETING_PHRASES:
            assert banned not in blob, banned


# ---------------------------------------------------------------------------
# 5. SEO foundations
# ---------------------------------------------------------------------------


def _all_findable_pages(db_seeded=True):
    """Render one of each findable page, for the checks that apply to all."""

    async def body(db):
        await seed(db)
        return {
            "category": (
                await server.public_category_page("food-and-drink", Req())
            ).body.decode(),
            "city": (await server.public_city_page("bengaluru", Req())).body.decode(),
            "faq": (await server.public_faq_page()).body.decode(),
            "blog": (await server.public_blog_index(Req())).body.decode(),
            "post": (
                await server.public_blog_post("reel-rates-bengaluru", Req())
            ).body.decode(),
            "work": (await server.public_work_index(Req())).body.decode(),
            "case_study": (
                await server.public_work_page("toit-tasting", Req())
            ).body.decode(),
        }

    return run(body)


class TestSeoFoundations:
    PAGES = None

    @classmethod
    def setup_class(cls):
        cls.PAGES = _all_findable_pages()

    @pytest.mark.parametrize(
        "name", ["category", "city", "faq", "blog", "post", "work", "case_study"]
    )
    def test_every_page_carries_a_canonical_and_a_card(self, name):
        html = self.PAGES[name]
        assert '<link rel="canonical"' in html, name
        for tag in (
            'property="og:title"',
            'property="og:description"',
            'property="og:image"',
            'name="twitter:card"',
            'name="description"',
        ):
            assert tag in html, f"{name} is missing {tag}"

    @pytest.mark.parametrize("name", ["category", "city", "faq", "blog", "post"])
    def test_the_structured_data_parses(self, name):
        """Invalid JSON-LD is worse than none: it looks present and is
        discarded, so nobody goes looking."""
        graph = ld_of(self.PAGES[name])
        assert graph
        for block in graph:
            assert block.get("@type"), block

    @pytest.mark.parametrize("name", ["category", "city", "faq", "blog", "post"])
    def test_every_page_states_the_organisation(self, name):
        assert "Organization" in types_of(self.PAGES[name]), name

    def test_the_organisation_block_is_the_same_company_everywhere(self):
        """Including in the static shell, which is the only thing a crawler
        reads on the React routes."""
        org = next(b for b in ld_of(self.PAGES["faq"]) if b["@type"] == "Organization")
        assert org["name"] == "WeAre Creators"
        shell = (PUBLIC / "index.html").read_text()
        m = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', shell, re.S
        )
        assert m, "the app shell states no organisation"
        assert json.loads(m.group(1))["name"] == org["name"]

    @pytest.mark.parametrize("name", ["category", "city", "faq", "blog", "post"])
    def test_india_is_stated_rather_than_guessed(self, name):
        html = self.PAGES[name]
        assert 'name="geo.region" content="IN-KA"' in html, name
        assert 'property="og:locale" content="en_IN"' in html, name

    def test_a_case_study_is_an_article(self):
        assert "Article" in types_of(self.PAGES["case_study"])

    def test_no_two_findable_pages_share_a_title(self):
        """One title for two pages makes two links preview identically, which
        is the whole reason they are separate pages."""
        titles = [
            re.search(r"<title>(.*?)</title>", html, re.S).group(1)
            for html in self.PAGES.values()
        ]
        assert len(set(titles)) == len(titles), titles

    def test_the_search_console_tag_is_wired_to_the_environment(self):
        """**Never committed**, the rule the Maps key already holds. With the
        variable unset the placeholder survives the build, which Google does
        not match — failing closed rather than claiming a property."""
        shell = (PUBLIC / "index.html").read_text()
        assert 'name="google-site-verification"' in shell
        assert "%REACT_APP_SEARCH_CONSOLE_TOKEN%" in shell

    def test_robots_names_the_findable_pages_and_hides_the_rest(self):
        body = run(lambda db: server.public_robots()).body.decode()
        for allowed in (
            server.CATEGORY_PATH,
            server.CITY_PATH,
            server.FAQ_PATH,
            server.BLOG_PATH,
            server.CASE_STUDY_PATH,
        ):
            assert f"Allow: {allowed}" in body, allowed
        for hidden in ("/admin", "/api/", "/dashboard", "/manager", "/brand/"):
            assert f"Disallow: {hidden}" in body, hidden
        assert "Sitemap:" in body

    def test_robots_leaves_the_public_brand_page_reachable(self):
        """The trailing slash on `/brand/` is load-bearing: prefixes match
        literally, so without it `/brands/{id}` — the public page, and the
        whole point — would be disallowed too."""
        body = run(lambda db: server.public_robots()).body.decode()
        assert "Disallow: /brand/\n" in body
        assert "Disallow: /brands" not in body


class TestTheSitemap:
    """A sitemap is a promise that each URL serves. Tested as one."""

    def _sitemap(self, **kw):
        async def body(db):
            await seed(db, **kw)
            return (await server.public_sitemap()).body.decode()

        return run(body)

    def test_it_is_well_formed_xml(self):
        import xml.etree.ElementTree as ET

        root = ET.fromstring(self._sitemap())
        assert root.tag.endswith("urlset")
        assert len(root), "an empty sitemap"

    def test_every_category_page_is_listed(self):
        xml = self._sitemap()
        for cat in server.SEO_CATEGORIES:
            assert f"{server.CATEGORY_PATH}/{cat['slug']}</loc>" in xml, cat["slug"]

    def test_the_faq_the_guides_and_the_work_are_listed(self):
        xml = self._sitemap()
        assert f"{server.FAQ_PATH}</loc>" in xml
        assert f"{server.BLOG_PATH}</loc>" in xml
        assert f"{server.BLOG_PATH}/reel-rates-bengaluru</loc>" in xml
        assert f"{server.CASE_STUDY_PATH}</loc>" in xml
        assert f"{server.CASE_STUDY_PATH}/toit-tasting</loc>" in xml

    def test_the_marketing_pages_are_still_listed(self):
        """Adding a surface must not quietly drop the one that was there."""
        xml = self._sitemap()
        for path in server.MARKETING_PATHS:
            if path == "/":
                continue
            assert f"{path}</loc>" in xml, path

    def test_a_draft_post_is_not_listed(self):
        async def body(db):
            await seed(db)
            await db.blog_posts.insert_one(
                {"_id": ObjectId(), "slug": "half-written", "status": "draft",
                 "title": "Half written", "summary": "x" * 20, "body": "y" * 30,
                 "category": "industry", "updated_at": NOW}
            )
            return (await server.public_sitemap()).body.decode()

        assert "half-written" not in run(body)

    def test_every_listed_page_of_ours_actually_serves(self):
        """**The promise, checked.** Listing a URL tells a crawler the page
        exists; nothing else here asks whether it does. A soft 404 in a sitemap
        is worse than an omission, because it is a claim we then withdraw.
        """
        async def body(db):
            await seed(db)
            xml = (await server.public_sitemap()).body.decode()
            locs = re.findall(r"<loc>([^<]+)</loc>", xml)
            broken = []
            for loc in locs:
                path = re.sub(r"^https?://[^/]+", "", loc) or "/"
                try:
                    if path.startswith(server.CATEGORY_PATH + "/"):
                        await server.public_category_page(path.rsplit("/", 1)[-1], Req())
                    elif path.startswith(server.CITY_PATH + "/"):
                        await server.public_city_page(path.rsplit("/", 1)[-1], Req())
                    elif path == server.FAQ_PATH:
                        await server.public_faq_page()
                    elif path == server.BLOG_PATH:
                        await server.public_blog_index(Req())
                    elif path.startswith(server.BLOG_PATH + "/"):
                        await server.public_blog_post(path.rsplit("/", 1)[-1], Req())
                    elif path == server.CASE_STUDY_PATH:
                        await server.public_work_index(Req())
                    elif path.startswith(server.CASE_STUDY_PATH + "/"):
                        await server.public_work_page(path.rsplit("/", 1)[-1], Req())
                except HTTPException:
                    broken.append(path)
            return locs, broken

        locs, broken = run(body)
        assert locs, "nothing listed"
        assert not broken, f"the sitemap lists pages that 404: {broken}"

    def test_the_deploy_proxies_every_findable_path(self):
        """**A rewrite that never reaches the backend is the silent failure
        `/for-brands` had for months** — the page answered with the SPA's
        catch-all and every link to it went nowhere. These paths are
        server-rendered precisely so a crawler can read them, which is worth
        nothing if the edge never routes there."""
        import json as _json

        vercel = _json.loads((FRONTEND.parent / "vercel.json").read_text())
        sources = {r["source"] for r in vercel["rewrites"]}
        for needed in (
            f"{server.CATEGORY_PATH}/:slug",
            f"{server.CITY_PATH}/:slug",
            server.FAQ_PATH,
            server.BLOG_PATH,
            f"{server.BLOG_PATH}/:slug",
            "/sitemap.xml",
            "/robots.txt",
        ):
            assert needed in sources, f"{needed} is not proxied to the backend"


# ---------------------------------------------------------------------------
# 6. The blog
# ---------------------------------------------------------------------------


class TestTheBlog:
    ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Ops"}

    def _payload(self, **kw):
        return server.BlogPostPayload(
            **{
                "title": "What a reel costs in Bengaluru",
                "summary": "Real numbers from the briefs we ran this year.",
                "body": "## The short answer\n\nRates move with reach.",
                "category": "rate-benchmarks",
                **kw,
            }
        )

    def test_publishing_is_admin_only(self):
        """A post is a claim on the open internet under the company's name.
        `weare_team` is scoped to brands, and a scoped role that can speak for
        the company is not a scope — the split case studies already make."""
        for fn in (server.admin_create_blog, server.admin_publish_blog,
                   server.admin_delete_blog):
            assert guard_allows(fn, "admin") is True
            for role in ("weare_team", "campaign_manager", *server.BRAND_ROLES):
                assert guard_allows(fn, role) is False, fn.__name__

    def test_a_new_post_is_a_draft_and_reaches_no_public_page(self):
        async def body(db):
            created = await server.admin_create_blog(self._payload(), self.ADMIN)
            index = (await server.public_blog_index(Req())).body.decode()
            return created, index

        created, index = run(body)
        assert created["status"] == "draft"
        assert "What a reel costs" not in index

    def test_publishing_puts_it_on_the_page(self):
        async def body(db):
            created = await server.admin_create_blog(self._payload(), self.ADMIN)
            await server.admin_publish_blog(created["id"], self.ADMIN)
            return (await server.public_blog_index(Req())).body.decode()

        assert "What a reel costs" in run(body)

    def test_republishing_does_not_move_the_date(self):
        """A correction is not a new piece of work, and a date that jumped
        would tell a reader the article is newer than it is — the rule case
        studies settled."""
        async def body(db):
            created = await server.admin_create_blog(self._payload(), self.ADMIN)
            first = await server.admin_publish_blog(created["id"], self.ADMIN)
            await server.admin_unpublish_blog(created["id"], self.ADMIN)
            again = await server.admin_publish_blog(created["id"], self.ADMIN)
            return first["published_at"], again["published_at"]

        first, again = run(body)
        assert first and first == again

    def test_a_published_post_cannot_be_deleted_outright(self):
        """The link may already be out there."""
        async def body(db):
            created = await server.admin_create_blog(self._payload(), self.ADMIN)
            await server.admin_publish_blog(created["id"], self.ADMIN)
            with pytest.raises(HTTPException) as exc:
                await server.admin_delete_blog(created["id"], self.ADMIN)
            still = await db.blog_posts.count_documents({})
            return exc.value, still

        err, still = run(body)
        assert err.status_code == 409
        assert err.detail["code"] == "post_published"
        assert still == 1, "the refusal has to actually refuse"

    def test_a_slug_clash_gets_a_suffix_rather_than_a_refusal(self):
        """A writer who has typed a whole article should not lose the save
        because somebody used that title two years ago."""
        async def body(db):
            a = await server.admin_create_blog(self._payload(), self.ADMIN)
            b = await server.admin_create_blog(self._payload(), self.ADMIN)
            return a["slug"], b["slug"]

        a, b = run(body)
        assert a != b and b.startswith(a)

    def test_an_unknown_category_is_refused(self):
        with pytest.raises(Exception):
            self._payload(category="thought-leadership")

    def test_the_body_escapes_before_it_formats(self):
        """**Escape first, then allow exactly two things.** A post cannot
        contain HTML however it is typed, which is the property a markdown
        dependency in the public render path would take away."""
        out = server._blog_body_html(
            '## Heading <script>alert(1)</script>\n\n'
            '<img src=x onerror=alert(1)>\n\n'
            "- one\n- two"
        )
        assert "<script>" not in out
        assert "<img" not in out
        assert "&lt;script&gt;" in out
        assert out.count("<li>") == 2
        assert "<h2>" in out

    def test_the_public_projection_names_every_key(self):
        """An allow-list built by naming keys, never a document with fields
        deleted from it — so a column added next month cannot reach a public
        page because nobody remembered to exclude it."""
        src = inspect.getsource(server._public_blog_post)
        assert "doc.copy()" not in src and "**doc" not in src
        out = server._public_blog_post(
            {"slug": "x", "title": "t", "internal_note": "not for the internet"}
        )
        assert "internal_note" not in out

    def test_a_post_emits_article_schema(self):
        async def body(db):
            await seed(db)
            return (
                await server.public_blog_post("reel-rates-bengaluru", Req())
            ).body.decode()

        html = run(body)
        graph = {b["@type"]: b for b in ld_of(html)}
        assert "Article" in graph
        art = graph["Article"]
        assert art["headline"]
        assert art["datePublished"]
        assert art["publisher"]["name"] == "WeAre Creators"
        assert art["mainEntityOfPage"]["@id"].endswith("/blog/reel-rates-bengaluru")

    def test_the_console_can_reach_all_of_it(self):
        """A route with no caller and a component with no mount are the same
        failure, and both have happened here."""
        panel = read("components", "admin", "Blog.jsx")
        assert "/admin/blog" in panel
        # The two state changes go through one `act(row, verb)` rather than two
        # near-copies, so the verbs are what to look for.
        for verb in ('"publish"', '"unpublish"'):
            assert verb in panel, verb
        assert "api.delete(`/admin/blog/" in panel
        assert "BlogRoute" in read("components", "admin", "routes.jsx")
        app = read("App.js")
        assert '<Route path="blog" element={<BlogRoute />} />' in app
        assert '"blog"' in read("components", "admin", "console", "Sidebar.jsx")


# ---------------------------------------------------------------------------
# 7. Analytics
# ---------------------------------------------------------------------------


class TestAnalytics:
    def test_the_five_funnel_steps_are_named(self):
        src = read("lib", "analytics.js")
        for step in (
            "landing",
            "brandSignupStarted",
            "campaignPosted",
            "creatorSignupStarted",
            "profileSubmitted",
        ):
            assert step in src, step

    def test_every_step_has_a_call_site(self):
        """**A funnel with an unfired step is a funnel with a hole in it**, and
        the hole reads as a drop-off rather than as a missing tag — which is
        the worst kind of wrong number, because somebody acts on it."""
        sites = {
            "landing": ("pages", "Landing.jsx"),
            "brandSignupStarted": ("pages", "Signup.jsx"),
            "creatorSignupStarted": ("pages", "Signup.jsx"),
            "campaignPosted": ("pages", "PostCampaign.jsx"),
            "profileSubmitted": ("pages", "CreatorOnboarding.jsx"),
        }
        for step, path in sites.items():
            src = read(*path)
            assert "FUNNEL" in src, f"{path[-1]} fires nothing"
            assert f"FUNNEL.{step}" in src, f"{step} has no call site"

    def test_the_container_id_comes_from_the_environment(self):
        """Never hardcoded — the rule the Maps key holds. With no id nothing is
        injected, so a developer build makes no third-party request."""
        src = read("lib", "analytics.js")
        assert "REACT_APP_GTM_ID" in src
        assert not re.search(r"GTM-[A-Z0-9]{5,}", src), "a container id is hardcoded"
        assert "if (!id" in src

    def test_no_personal_data_can_reach_a_tag(self):
        """**This one leaves the building**, which is a stronger reason than
        the one `errorLog.js` has. The filter is on the payload rather than on
        every call site remembering, because personal data gets into a tag by
        somebody spreading a record into it."""
        src = read("lib", "analytics.js")
        forbidden = re.search(r"const FORBIDDEN = /(.*?)/i", src)
        assert forbidden, "no redaction at all"
        pattern = forbidden.group(1)
        for field in ("phone", "email", "address", "upi", "ifsc", "pan", "name"):
            assert field in pattern, f"{field} is not filtered"
        # Objects are dropped whole: the key check only sees the top level.
        assert 'typeof value === "object"' in src

    def test_a_blocked_datalayer_never_breaks_a_signup(self):
        src = read("lib", "analytics.js")
        assert "catch" in src.split("export function track")[1].split("}")[0] or (
            "try {" in src.split("export function track")[1]
        )


# ---------------------------------------------------------------------------
# 8. Internal linking
# ---------------------------------------------------------------------------


class TestInternalLinking:
    """Search value compounds through the edges, not on any one page."""

    def test_a_case_study_links_to_its_category_and_its_city(self):
        async def body(db):
            await seed(db)
            return (await server.public_work_page("toit-tasting", Req())).body.decode()

        html = run(body)
        assert f'href="{server.CATEGORY_PATH}/food-and-drink"' in html
        assert f'href="{server.CITY_PATH}/bengaluru"' in html

    def test_a_category_page_links_back_to_case_studies(self):
        async def body(db):
            await seed(db)
            return (
                await server.public_category_page("food-and-drink", Req())
            ).body.decode()

        assert "/work/toit-tasting" in run(body)

    def test_a_category_page_links_to_the_cities_and_the_other_categories(self):
        async def body(db):
            await seed(db)
            return (
                await server.public_category_page("food-and-drink", Req())
            ).body.decode()

        html = run(body)
        assert f'{server.CITY_PATH}/bengaluru' in html
        # **The body only.** The canonical, `og:url` and the breadcrumb all name
        # this page by design — and the canonical uses `href` too, so a regex
        # over the whole document reads a page doing exactly the right thing as
        # a page linking to itself.
        body = html.split("<body", 1)[1]
        linked = set(re.findall(rf'href="{server.CATEGORY_PATH}/([\w-]+)"', body))
        assert len(linked) >= 5, "a category page that links nowhere is a dead end"
        assert "food-and-drink" not in linked, "a page should not link to itself"

    def test_a_city_page_links_to_categories_and_local_work(self):
        async def body(db):
            await seed(db)
            return (await server.public_city_page("bengaluru", Req())).body.decode()

        html = run(body)
        assert f"{server.CATEGORY_PATH}/" in html
        assert "/work/toit-tasting" in html

    def test_the_bridge_between_the_two_vocabularies_goes_one_way(self):
        """`CATEGORY_LITERAL` is what a campaign is; `CREATOR_TAXONOMY` is what
        a creator makes. The mapping picks a page for a case study and is never
        read backwards — a two-way map would be a second definition of what a
        campaign category is."""
        assert server._seo_category_for_campaign("fnb")["slug"] == "food-and-drink"
        assert server._seo_category_for_campaign(None) is None
        assert server._seo_category_for_campaign("not-a-category") is None
        # Nothing writes through it.
        for name in ("create_brand_campaign", "update_brand_campaign",
                     "admin_update_campaign"):
            assert "_seo_category_for_campaign" not in inspect.getsource(
                getattr(server, name)
            ), name

    @pytest.mark.parametrize(
        "renderer", ["category", "city", "faq", "blog", "post"]
    )
    def test_every_findable_page_routes_to_a_signup(self, renderer):
        pages = _all_findable_pages()
        assert "/signup?role=brand" in pages[renderer], renderer

    def test_every_findable_page_carries_the_shared_footer(self):
        """One link list, already drift-tested against `lib/siteNav.js`. Three
        copies is how a footer advertises a page that moved."""
        pages = _all_findable_pages()
        for name in ("category", "city", "faq", "blog", "post"):
            for _, links in server.FOOTER_COLUMNS:
                for label, href in links:
                    assert f'href="{href}"' in pages[name], f"{name}: {label}"
