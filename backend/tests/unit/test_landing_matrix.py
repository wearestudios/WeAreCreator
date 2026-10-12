"""The landing page matrix — /influencer-marketing/...

**The one rule this file exists to hold: a page is generated from live supply,
never from the enums.** Eight sectors times twenty cities plus the hubs is 189
URLs that are trivial to emit and would be a lie on most of them. A page
saying "fashion creators in Guwahati" is a page a brand lands on, posts a
brief from, and waits — and then the campaign fee comes back under
`REFUND_POLICY_TERMS`, because we advertised a brief as fillable that we could
not fill. The gate is the product promise, not an SEO preference.

So every test below is one way that could go wrong: a floor that is read but
not applied, a page that stays in the sitemap after its supply drops, a slug
that parses into the wrong cut, or a title two pages share.

The two the brief asked for by name — sitemap generation and schema validity —
are sections 4 and 5.
"""

import asyncio
import json
import re
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"

LOOP = None


def run(body):
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["landing"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


class Req:
    """The one thing the handler reads off the request."""

    base_url = "http://api.test/"


async def _creators(db, city, niche, n):
    for _ in range(n):
        await db.creator_profiles.insert_one(
            {
                "user_id": ObjectId(),
                "verification_status": "verified",
                "city": city,
                "niches": [niche],
            }
        )


async def _supply(db, plan):
    """`plan` is {city: {niche: count}}."""
    for city, niches in plan.items():
        for niche, n in niches.items():
            await _creators(db, city, niche, n)


# A shape like a real operation: deep in two cities, thin in a third, almost
# nothing in a fourth. Every floor test needs a fixture where the floors
# actually bite — one where everything passes cannot tell a working gate from
# a missing one.
PLAN = {
    "Bengaluru": {"food": 12, "fashion": 8, "fitness": 6},
    "Mumbai": {"fashion": 9, "food": 7, "lifestyle": 5},
    "Pune": {"food": 6, "fashion": 4},
    "Kochi": {"food": 2},
}


async def _pages(db, plan=None):
    await _supply(db, plan or PLAN)
    supply = await server._landing_supply()
    settings = await server.landing_page_settings()
    return server._landing_pages_from(supply, settings)


def _slugs(pages):
    return [server._landing_slug_for(p["sector"], p["city"]) for p in pages]


# --- 1. The slugs come from the two vocabularies ----------------------------


class TestNoThirdListOfCitiesOrSectors:
    def test_the_sector_slugs_are_derived_from_the_category_labels(self):
        """`CATEGORY_LABELS` is the display vocabulary; these are the same
        values in URL form. A hand-written map would be the second category
        list `lib/categories.js` exists to prevent."""
        assert set(server.SEO_SECTOR_SLUGS.values()) == set(server.CATEGORY_LABELS)
        assert server.SEO_SECTOR_SLUGS["food-drink"] == "fnb"
        assert server.SEO_SECTOR_SLUGS["real-estate"] == "real_estate"

    def test_the_city_slugs_are_derived_from_indian_cities(self):
        assert set(server.SEO_CITY_SLUGS.values()) == set(server.INDIAN_CITIES)
        assert server.SEO_CITY_SLUGS["delhi-ncr"] == "Delhi NCR"

    def test_a_category_added_to_the_enum_appears_here_by_itself(self):
        """The property that makes "no third list" true rather than asserted:
        the derivation runs over whatever the enum holds."""
        labels = dict(server.CATEGORY_LABELS)
        labels["pet_care"] = "Pet care"
        derived = {server._landing_slug(v): k for k, v in labels.items()}
        assert derived["pet-care"] == "pet_care"

    def test_the_brief_asked_for_sectors_this_product_does_not_have(self):
        """**A deliberate departure from the brief, recorded as one.**

        The brief asked for regulated-sector pages for finance, healthcare,
        education and alcohol. None of the four is in `CATEGORY_LITERAL`, so a
        page offering one could never match a real campaign, a real case study
        or a real creator — the drift the case-study vocabulary note records.
        The substance was kept where it genuinely applies to a sector we run:
        surrogate advertising under hospitality, the Drugs & Magic Remedies
        Act under wellness, RERA under real estate.
        """
        for absent in ("finance", "healthcare", "education", "alcohol"):
            assert absent not in server.CATEGORY_LABELS
            assert absent not in server.SEO_SECTOR_SLUGS
        rules = " ".join(" ".join(v) for v in server.SECTOR_RULES.values()).lower()
        assert "surrogate" in rules
        assert "magic remedies" in rules
        assert "rera" in rules

    def test_every_sector_with_a_rule_is_a_real_sector(self):
        for key in server.SECTOR_RULES:
            assert key in server.CATEGORY_LABELS, key


# --- 2. Reading a URL back into a cut ---------------------------------------


class TestTheSlugParsesIntoExactlyOneCut:
    @pytest.mark.parametrize(
        "slug,expected",
        [
            ("india", {"sector": None, "city": None}),
            ("mumbai", {"sector": None, "city": "Mumbai"}),
            ("delhi-ncr", {"sector": None, "city": "Delhi NCR"}),
            ("food-drink-india", {"sector": "fnb", "city": None}),
            ("food-drink-mumbai", {"sector": "fnb", "city": "Mumbai"}),
            ("real-estate-delhi-ncr", {"sector": "real_estate", "city": "Delhi NCR"}),
        ],
    )
    def test_all_four_shapes(self, slug, expected):
        assert server._parse_landing_slug(slug) == expected

    def test_both_vocabularies_contain_hyphens_and_it_still_resolves(self):
        """**The reason the parser matches the longest sector prefix.**

        Splitting on the first hyphen reads "real-estate-mumbai" as the sector
        "real" in the city "estate-mumbai". Both lists are closed, so matching
        the longest known sector and then requiring the remainder to be a
        known city is unambiguous.
        """
        assert server._parse_landing_slug("real-estate-delhi-ncr") == {
            "sector": "real_estate",
            "city": "Delhi NCR",
        }
        # And it does not greedily eat a city whose name starts like a sector.
        assert server._parse_landing_slug("travel-india") == {
            "sector": "travel",
            "city": None,
        }

    @pytest.mark.parametrize(
        "slug", ["", "nonsense", "real-estate-nowhere", "fnb-mumbai", "mumbai-food-drink", "india-food-drink"]
    )
    def test_anything_else_is_none(self, slug):
        """Including the enum *key* (`fnb`) rather than the slug, and the two
        halves the wrong way round — a URL somebody guesses is not a URL we
        answer."""
        assert server._parse_landing_slug(slug) is None

    def test_the_slug_round_trips(self):
        """One speller in each direction, so a link and the route it points at
        cannot disagree."""
        for sector in [None, *server.CATEGORY_LABELS]:
            for city in [None, *server.INDIAN_CITIES]:
                slug = server._landing_slug_for(sector, city)
                assert server._parse_landing_slug(slug) == {
                    "sector": sector,
                    "city": city,
                }, slug


# --- 3. Generated from supply, and the floors actually bite -----------------


class TestAPageExistsOnlyWhereTheSupplyDoes:
    def test_the_national_hub_always_exists(self):
        """The one page whose claim is about the operation rather than about a
        place we have to staff."""
        pages = run(lambda db: _pages(db, {"Kochi": {"food": 1}}))
        assert {"sector": None, "city": None} in pages

    def test_a_city_under_the_floor_gets_no_page(self):
        """Pune has ten verified creators against a floor of fifteen."""
        slugs = _slugs(run(_pages))
        assert "bengaluru" in slugs
        assert "mumbai" in slugs
        assert "pune" not in slugs
        assert "kochi" not in slugs

    def test_a_sector_city_page_needs_both_floors(self):
        """**Both, not either.** A sector can clear its own five in a city
        that has nowhere near fifteen creators overall — and a page for it
        would send a brand to a city we cannot staff for anything else."""
        slugs = _slugs(run(_pages))
        # Bengaluru clears 15; food clears 5 there.
        assert "food-drink-bengaluru" in slugs
        # Pune's food niche has 6 — over the sector floor — but Pune itself is
        # under the city floor, so the page does not exist.
        assert "food-drink-pune" not in slugs

    def test_a_sector_with_no_creators_in_a_city_gets_no_page(self):
        slugs = _slugs(run(_pages))
        assert "wellness-bengaluru" not in slugs
        assert "travel-mumbai" not in slugs

    def test_an_unverified_crowd_generates_nothing(self):
        """Supply means creators a brand can actually book. A city full of
        half-finished signups is not a city we can staff."""

        async def body(db):
            for _ in range(60):
                await db.creator_profiles.insert_one(
                    {"user_id": ObjectId(), "verification_status": "pending",
                     "city": "Jaipur", "niches": ["food"]}
                )
            supply = await server._landing_supply()
            return server._landing_pages_from(supply, await server.landing_page_settings())

        assert _slugs(run(body)) == ["india"]

    def test_the_stored_floors_are_applied_not_merely_read(self):
        """**The break this is aimed at**: a settings function nothing
        consults. Lowering the city floor to ten has to make Pune exist."""

        async def body(db):
            await db.platform_settings.update_one(
                {"_id": server._LANDING_SETTINGS_ID},
                {"$set": {"city_minimum": 10, "sector_minimum": 4}},
                upsert=True,
            )
            await _supply(db, PLAN)
            supply = await server._landing_supply()
            return server._landing_pages_from(supply, await server.landing_page_settings())

        slugs = _slugs(run(body))
        assert "pune" in slugs
        assert "food-drink-pune" in slugs
        # Kochi still has two, under even the lowered floor.
        assert "kochi" not in slugs

    def test_raising_the_floor_removes_pages(self):
        async def body(db):
            await db.platform_settings.update_one(
                {"_id": server._LANDING_SETTINGS_ID},
                # Above Bengaluru's 26, which is the deepest city in the
                # fixture — a floor that only removes the thin cities would
                # not tell a working gate from a partly working one.
                {"$set": {"city_minimum": 40}},
                upsert=True,
            )
            await _supply(db, PLAN)
            supply = await server._landing_supply()
            return server._landing_pages_from(supply, await server.landing_page_settings())

        assert _slugs(run(body)) == ["india"]

    def test_a_floor_of_zero_falls_back_to_the_default(self):
        """**1 is the floor on the floor.** Zero would generate every
        combination, which is the single thing this gate exists to prevent."""

        async def body(db):
            await db.platform_settings.update_one(
                {"_id": server._LANDING_SETTINGS_ID},
                {"$set": {"city_minimum": 0, "sector_minimum": 0}},
                upsert=True,
            )
            return await server.landing_page_settings()

        assert run(body) == {
            "city_minimum": server.CITY_PAGE_MIN_CREATORS_DEFAULT,
            "sector_minimum": server.SECTOR_PAGE_MIN_CREATORS_DEFAULT,
        }

    def test_the_route_404s_where_the_supply_does_not_justify_a_page(self):
        """**The 404 is the feature**, not a gap. A slug that parses perfectly
        is still not served when the supply behind it is too thin."""

        async def body(db):
            await _supply(db, PLAN)
            out = {}
            for slug in ("india", "bengaluru", "food-drink-bengaluru",
                         "pune", "food-drink-kochi", "wellness-bengaluru"):
                try:
                    res = await server.public_landing_page(slug, Req())
                    out[slug] = res.status_code
                except HTTPException as err:
                    out[slug] = err.status_code
            return out

        assert run(body) == {
            "india": 200,
            "bengaluru": 200,
            "food-drink-bengaluru": 200,
            "pune": 404,
            "food-drink-kochi": 404,
            "wellness-bengaluru": 404,
        }

    def test_a_malformed_slug_is_a_404_not_a_500(self):
        async def body(db):
            await _supply(db, PLAN)
            try:
                await server.public_landing_page("../../etc/passwd", Req())
            except HTTPException as err:
                return err.status_code
            return None

        assert run(body) == 404

    def test_a_page_leaves_the_sitemap_when_its_supply_drops(self):
        """**The property the whole per-request count exists for.** Nothing
        has to remember to remove it."""

        async def body(db):
            await _supply(db, PLAN)
            before = _slugs(
                server._landing_pages_from(
                    await server._landing_supply(), await server.landing_page_settings()
                )
            )
            # Unverify enough of Mumbai to drop it under the city floor.
            ids = [
                d["_id"]
                for d in await db.creator_profiles.find({"city": "Mumbai"}).to_list(
                    length=None
                )
            ][:10]
            for oid in ids:
                await db.creator_profiles.update_one(
                    {"_id": oid}, {"$set": {"verification_status": "rejected"}}
                )
            after = _slugs(
                server._landing_pages_from(
                    await server._landing_supply(), await server.landing_page_settings()
                )
            )
            return before, after

        before, after = run(body)
        assert "mumbai" in before and "fashion-mumbai" in before
        assert "mumbai" not in after and "fashion-mumbai" not in after


# --- 4. The sitemap ---------------------------------------------------------


class TestTheSitemap:
    def _sitemap(self, plan=None):
        async def body(db):
            await _supply(db, plan or PLAN)
            res = await server.public_sitemap()
            return res.body.decode()

        return run(body)

    def test_every_generated_page_is_listed(self):
        xml = self._sitemap()
        pages = run(_pages)
        for p in pages:
            assert server._landing_url(p["sector"], p["city"]) in xml

    def test_nothing_listed_would_404(self):
        """**The one invariant that matters here**: the sitemap and the route
        share `_landing_pages_from`, so a URL cannot be advertised to a
        crawler and then refused when it follows it."""
        xml = self._sitemap()
        listed = set(re.findall(r"<loc>([^<]*influencer-marketing[^<]*)</loc>", xml))
        assert listed

        async def body(db):
            await _supply(db, PLAN)
            bad = []
            for loc in listed:
                slug = loc.rsplit("/", 1)[1]
                try:
                    await server.public_landing_page(slug, Req())
                except HTTPException:
                    bad.append(slug)
            return bad

        assert run(body) == []

    def test_a_page_under_the_floor_is_not_listed(self):
        xml = self._sitemap()
        assert "/influencer-marketing/pune" not in xml
        assert "/influencer-marketing/kochi" not in xml
        assert "/influencer-marketing/wellness-bengaluru" not in xml

    def test_it_is_well_formed_xml(self):
        """It is served as `application/xml`, so a crawler parses it — an
        unescaped ampersand in a city or sector name would make the whole
        document unreadable rather than one entry wrong."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(self._sitemap())
        assert root.tag.endswith("urlset")
        locs = [e.text for e in root.iter() if e.tag.endswith("loc")]
        assert len(locs) == len(set(locs)), "a duplicate <loc> in the sitemap"

    def test_the_marketing_pages_and_case_studies_are_still_there(self):
        """The matrix is added to the sitemap, not substituted for it."""
        xml = self._sitemap()
        for path in server.MARKETING_PATHS:
            if path == "/":
                continue
            assert path in xml, path


# --- 5. Schema validity -----------------------------------------------------


def _ld(html):
    """Every JSON-LD block on the page, parsed."""
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    )
    return [json.loads(b.replace("\\u003c", "<")) for b in blocks]


class TestTheStructuredData:
    def _html(self, slug="food-drink-bengaluru", plan=None):
        async def body(db):
            await _supply(db, plan or PLAN)
            res = await server.public_landing_page(slug, Req())
            return res.body.decode()

        return run(body)

    def test_there_is_exactly_one_json_ld_block_and_it_parses(self):
        """Two blocks is two answers to the same question. One `@graph`."""
        blocks = _ld(self._html())
        assert len(blocks) == 1
        assert blocks[0]["@context"] == "https://schema.org"

    @pytest.mark.parametrize(
        "slug,kind,place",
        [
            ("india", "Country", "India"),
            ("bengaluru", "City", "Bengaluru"),
            ("food-drink-india", "Country", "India"),
            ("food-drink-bengaluru", "City", "Bengaluru"),
        ],
    )
    def test_area_served_comes_from_the_real_city(self, slug, kind, place):
        """**From the cut, never a constant.** `areaServed` naming a city the
        page is not about is structured data that contradicts the page."""
        graph = _ld(self._html(slug))[0]["@graph"]
        service = next(n for n in graph if n["@type"] == "Service")
        assert service["areaServed"] == {"@type": kind, "name": place}
        assert service["serviceType"] == "Influencer marketing"
        assert service["provider"]["@type"] == "Organization"

    def test_the_service_url_is_the_pages_own_canonical(self):
        html = self._html("food-drink-bengaluru")
        graph = _ld(html)[0]["@graph"]
        service = next(n for n in graph if n["@type"] == "Service")
        url = server._landing_url("fnb", "Bengaluru")
        assert service["url"] == url
        assert f'<link rel="canonical" href="{url}">' in html

    def test_the_faq_page_is_shaped_the_way_schema_org_requires(self):
        graph = _ld(self._html())[0]["@graph"]
        faq = next(n for n in graph if n["@type"] == "FAQPage")
        assert faq["mainEntity"]
        for q in faq["mainEntity"]:
            assert q["@type"] == "Question"
            assert q["name"].strip()
            assert q["acceptedAnswer"]["@type"] == "Answer"
            assert q["acceptedAnswer"]["text"].strip()

    def test_every_faq_answer_is_actually_on_the_page(self):
        """**A FAQPage whose questions are not on the page is markup making a
        claim the page does not.** Google treats that as a violation and a
        reader treats it as a bait."""
        html = self._html()
        faq = next(n for n in _ld(html)[0]["@graph"] if n["@type"] == "FAQPage")
        for q in faq["mainEntity"]:
            assert server.html_escape(q["name"]) in html, q["name"]
            assert server.html_escape(q["acceptedAnswer"]["text"]) in html

    def test_the_sector_rule_rides_into_the_faq_only_where_there_is_one(self):
        with_rule = _ld(self._html("food-drink-bengaluru"))[0]["@graph"]
        plain = _ld(self._html("bengaluru"))[0]["@graph"]
        n_with = len(next(n for n in with_rule if n["@type"] == "FAQPage")["mainEntity"])
        n_plain = len(next(n for n in plain if n["@type"] == "FAQPage")["mainEntity"])
        assert n_with == n_plain + 1

    def test_the_json_ld_cannot_break_out_of_its_script_tag(self):
        """`<` is escaped to `\\u003c`, so a `</script>` in any value — a
        business name, a city — cannot end the block early."""
        html = self._html()
        block = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        ).group(1)
        assert "<" not in block


# --- 6. What is on the page -------------------------------------------------


class TestThePageSaysSomethingCheckable:
    def _html(self, slug="food-drink-bengaluru"):
        async def body(db):
            await _supply(db, PLAN)
            res = await server.public_landing_page(slug, Req())
            return res.body.decode()

        return run(body)

    def test_one_h1_naming_the_service_the_sector_and_the_place(self):
        html = self._html()
        h1 = re.findall(r"<h1>(.*?)</h1>", html, re.S)
        assert len(h1) == 1
        assert "influencer marketing" in h1[0].lower()
        assert "Food &amp; drink" in h1[0] or "Food & drink" in h1[0]
        assert "Bengaluru" in h1[0]

    def test_the_counted_supply_is_the_real_count(self):
        """Counted for *that cut*, not the platform total. Bengaluru's food
        niche is twelve in the fixture."""
        html = self._html("food-drink-bengaluru")
        assert "<b>12</b>" in html

    def test_a_city_page_counts_the_whole_city(self):
        """Bengaluru is 12 food + 8 fashion + 6 fitness in the fixture, and a
        city page counts the city rather than any one sector of it."""
        assert "<b>26</b>" in self._html("bengaluru")

    def test_both_commercial_terms_are_on_every_page(self):
        for slug in ("india", "bengaluru", "food-drink-bengaluru"):
            html = self._html(slug).lower()
            assert "on top" in html
            assert "comes back" in html

    def test_the_sector_rules_render_where_they_exist(self):
        assert "FSSAI" in self._html("food-drink-bengaluru")
        # A plain city page has no sector, so no rules section.
        assert "What the rules say" not in self._html("bengaluru")

    def test_it_links_to_the_hub_and_to_for_brands(self):
        html = self._html("food-drink-bengaluru")
        assert server._landing_url(None, None) in html
        assert "/for-brands" in html

    def test_it_links_to_the_city_hub_and_to_sibling_sectors(self):
        """**Search value compounds through the cross-links**, which is the
        only reason these are worth having as a set."""
        html = self._html("food-drink-bengaluru")
        assert server._landing_url(None, "Bengaluru") in html
        assert server._landing_url("fashion", "Bengaluru") in html

    def test_it_never_links_to_a_page_the_supply_does_not_justify(self):
        """A cross-link to a 404 is worse than no cross-link."""
        html = self._html("food-drink-bengaluru")
        for dead in ("/influencer-marketing/pune", "/influencer-marketing/kochi",
                     "/influencer-marketing/wellness-bengaluru"):
            assert dead not in html, dead

    def test_case_studies_come_through_the_public_projection(self):
        """**Never a second projection** — that is what keeps money and a
        creator's consent off a public page by construction."""
        src = __import__("inspect").getsource(server.public_landing_page)
        assert "_public_case_study" in src
        assert "_published_case_study_query" in src

    def test_a_planted_case_study_value_does_not_leak(self):
        async def body(db):
            await _supply(db, PLAN)
            await db.case_studies.insert_one(
                {
                    "slug": "a-launch",
                    "status": "published",
                    "title": "A launch",
                    "category": "fnb",
                    "city": "Bengaluru",
                    "brand_name": "A Brand",
                    "campaign_fee": 48500,
                    "creator_payout": 22000,
                    "commission_percent": 17.5,
                }
            )
            res = await server.public_landing_page("food-drink-bengaluru", Req())
            return res.body.decode()

        html = run(body)
        assert "a-launch" in html          # it is on the page...
        for leaked in ("48500", "22000", "17.5"):
            assert leaked not in html, leaked   # ...and the money is not

    def test_everything_typed_is_escaped(self):
        """A sector label and a city come from our own enums, but a case
        study's title is typed by an admin and lands on a public page."""

        async def body(db):
            await _supply(db, PLAN)
            await db.case_studies.insert_one(
                {
                    "slug": "xss",
                    "status": "published",
                    "title": '<script>alert(1)</script>',
                    "category": "fnb",
                    "city": "Bengaluru",
                    "brand_name": '"><img onerror=x>',
                }
            )
            res = await server.public_landing_page("food-drink-bengaluru", Req())
            return res.body.decode()

        html = run(body)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html
        assert "<img onerror=x>" not in html

    def test_it_is_served_as_html_and_cacheable(self):
        async def body(db):
            await _supply(db, PLAN)
            return await server.public_landing_page("india", Req())

        res = run(body)
        assert res.media_type.startswith("text/html")
        assert "max-age" in res.headers["Cache-Control"]

    def test_images_sit_in_a_ratio_container_and_load_lazily(self):
        async def body(db):
            await _supply(db, PLAN)
            await db.case_studies.insert_one(
                {"slug": "s", "status": "published", "title": "A campaign",
                 "category": "fnb", "city": "Bengaluru", "brand_name": "B",
                 "hero_image_url": "/uploads/hero.png"}
            )
            res = await server.public_landing_page("food-drink-bengaluru", Req())
            return res.body.decode()

        html = run(body)
        assert 'loading="lazy"' in html
        assert 'class="cover"' in html


# --- 7. No two pages share a title or a description -------------------------


class TestEveryPageIsItsOwnSearchResult:
    def _every_possible_page(self):
        """The whole space the vocabularies could ever generate, not just what
        the current supply does — uniqueness has to hold for any supply."""
        pages = [{"sector": None, "city": None}]
        pages += [{"sector": None, "city": c} for c in server.INDIAN_CITIES]
        pages += [{"sector": k, "city": None} for k in server.CATEGORY_LABELS]
        pages += [
            {"sector": k, "city": c}
            for k in server.CATEGORY_LABELS
            for c in server.INDIAN_CITIES
        ]
        return pages

    def test_no_two_titles_are_the_same(self):
        """One title for two pages makes two search results identical, which
        is the whole reason they are separate pages."""
        titles = [server._landing_titles(p)[0] for p in self._every_possible_page()]
        assert len(titles) == len(set(titles))

    def test_no_two_descriptions_are_the_same(self):
        descs = [server._landing_titles(p)[1] for p in self._every_possible_page()]
        assert len(descs) == len(set(descs))

    def test_every_title_names_both_the_sector_and_the_place(self):
        """What makes uniqueness structural rather than lucky: the (sector,
        place) pair is exactly what the URL is."""
        for p in self._every_possible_page():
            title, summary = server._landing_titles(p)
            place = p["city"] or "India"
            assert place in title, title
            assert place in summary, summary
            if p["sector"]:
                label = server.CATEGORY_LABELS[p["sector"]]
                assert label in title, title
                assert label.lower() in summary.lower(), summary

    def test_no_title_or_description_collides_with_a_marketing_page(self):
        """The five marketing pages each have their own title too — a matrix
        page duplicating one would make them compete."""
        marketing = (FRONTEND / "src" / "pages").glob("*.jsx")
        taken = set()
        for f in marketing:
            taken.update(re.findall(r'title="([^"]+)"', f.read_text()))
        for p in self._every_possible_page():
            assert server._landing_titles(p)[0] not in taken

    def test_a_description_is_long_enough_to_be_used_and_short_enough_to_show(
        self,
    ):
        """Google truncates around 160 characters, and a 40-character
        description gets replaced by whatever it finds on the page."""
        for p in self._every_possible_page():
            summary = server._landing_titles(p)[1]
            assert 70 <= len(summary) <= 320, (len(summary), summary)


# --- 8. The route is reachable ----------------------------------------------


class TestItIsActuallyServed:
    def test_the_route_is_registered_outside_the_api_prefix(self):
        paths = [getattr(r, "path", "") for r in server.app.routes]
        assert f"{server.LANDING_PATH}/{{slug}}" in paths

    def test_the_dev_proxy_and_the_deploy_config_both_know_about_it(self):
        """`setupProxy.js` is the dev half; without it the dev server answers
        with `index.html` and the SPA takes over."""
        proxy = (FRONTEND / "src" / "setupProxy.js").read_text()
        assert "influencer-marketing" in proxy
        vercel = json.loads((FRONTEND / "vercel.json").read_text())
        sources = [r["source"] for r in vercel["rewrites"]]
        assert f"{server.LANDING_PATH}/:slug" in sources
        # Above the catch-all, or it is dead config that looks live.
        assert sources.index(f"{server.LANDING_PATH}/:slug") < sources.index(
            "/((?!api/).*)"
        )

    def test_the_module_docstring_says_why_we_do_not_generate_all_of_them(self):
        """So nobody later "fixes" the gate by emitting the whole matrix. The
        reasoning is the product promise, not an SEO preference."""
        src = Path(server.__file__).read_text()
        start = src.index("# The landing page matrix")
        block = src[start : start + 3000]
        assert "refund" in block.lower()
        assert "LIVE SUPPLY" in block
        assert "product promise" in block
