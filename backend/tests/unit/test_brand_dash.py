"""The brand dashboard — board 24, "Option B · Warm".

The page is `BrandDashboardView` with `components/brand/BrandOverview.jsx`
on top: the live campaign's navy panel, then Needs you, Creators, and a
stack of the AI summary, the budget and the brand's other briefs. The
rendered behaviour (what is absent, the one red card, the AI gate, the leak
check) is `BrandOverview.test.jsx`. What is held here is the shape around
it:

* every number comes from an endpoint the page already calls — nothing is
  added up in the browser, and the budget has no "paid" segment because the
  budget block does not serve one;
* a creator is read for a name and a photo and nothing else;
* the page arrives in one commit, so the overview's three reads are made
  before anything is drawn;
* the class-merging helper knows the type scale, which is what made a navy
  button's label disappear.
"""
from __future__ import annotations

import re

from app_surface import SRC, code_of

FRONTEND = SRC.parent
OVERVIEW = code_of((SRC / "components" / "brand" / "BrandOverview.jsx").read_text())
PAGE = code_of((SRC / "pages" / "BrandDashboardView.jsx").read_text())


def test_the_overview_reads_only_the_endpoints_the_page_owns():
    urls = re.findall(r"api\.get\(`([^`]+)`", OVERVIEW)
    assert urls == [
        "/brand/campaigns/${live.id}/analytics",
        "/brand/campaigns/${live.id}/applicants",
        "/brand/campaigns/${live.id}/summary",
    ], urls
    assert 'aiLive("campaignSummary") ? ask(api.get(`/brand/campaigns/${live.id}/summary`))' in OVERVIEW


def test_a_creator_is_read_for_a_name_and_a_photo_and_nothing_else():
    """`_brand_visible_creator` is the projection; this is the second line —
    a field the projection sent by mistake still never reaches the screen."""
    read = set(re.findall(r"creator\?\.(\w+)", OVERVIEW))
    assert read <= {"name", "profile_image_url"}, read
    for forbidden in ("phone", "whatsapp", "email", "full_address", "location_lat", "upi", "pan"):
        assert not re.search(rf"\.{forbidden}\b", OVERVIEW), forbidden


def test_nothing_is_added_up_in_the_browser():
    """The DATA RULES: every number is one an endpoint served. A `reduce`, a
    running `+=` or a `paid` figure here would be a second definition of a
    number the server owns."""
    assert ".reduce(" not in OVERVIEW and "+=" not in OVERVIEW
    budget = OVERVIEW[OVERVIEW.index("export function BudgetCard"):OVERVIEW.index("const STATUS_PILL")]
    assert "Paid" not in budget and "payment" not in budget
    for key in ("b.remaining", "b.committed", "b.total", "b.ratio"):
        assert key in budget, key


def test_the_page_draws_once():
    """The three reads finish before the page is drawn, so nothing arrives
    above something already on screen and pushes it."""
    load = PAGE[PAGE.index("const load = useCallback"):PAGE.index("useEffect(() => {\n        load();")]
    assert load.index("loadBrandOverview") < load.index("setData(data)")
    # "Your results" too: it used to fetch for itself and land a beat later,
    # pushing the campaign list down (0.03 CLS at 1280 with the API delayed).
    assert load.index('api.get("/brand/analytics")') < load.index("setData(data)")
    assert "<BrandAnalyticsSummary initial={results} />" in PAGE
    assert 'data-testid="brand-dashboard-skeleton"' in PAGE


def test_the_title_moved_into_the_panel():
    assert "app-title" not in PAGE, "the page's one Fraunces is the live campaign's title now"
    assert OVERVIEW.count('className="app-title') == 2


def test_the_greeting_is_bengaluru_s_hour():
    assert "istHour()" in PAGE
    time = (SRC / "lib" / "time.js").read_text()
    assert "export function istHour" in time and "timeZone: IST" in time.split("export function istHour")[1]


def test_the_sidebar_count_is_the_dashboard_s_own():
    assert "useShellBadges({" in PAGE
    badge = PAGE[PAGE.index("useShellBadges({"):PAGE.index("});", PAGE.index("useShellBadges({"))]
    assert "awaiting_decision" in badge and "content_to_review" in badge


def test_the_class_merger_knows_every_type_size():
    """`tailwind-merge` read `text-meta` as a colour, so a small `Button`
    dropped its variant's `text-primary-foreground` and drew a navy label on
    a navy button. Every size in the Tailwind config is named to it."""
    utils = (SRC / "lib" / "utils.js").read_text()
    named = set(re.findall(r'"([a-z0-9-]+)"', utils.split("const SIZE_TOKENS = [")[1].split("];")[0]))
    tw = (FRONTEND / "tailwind.config.js").read_text()
    block = tw[tw.index("fontSize: {"):]
    block = block[:block.index("\n            },")]
    sizes = set(re.findall(r'^\s{16}"?([a-z0-9-]+)"?: \[', block, flags=re.M))
    assert sizes and named == sizes, (sizes ^ named)
    assert 'extendTailwindMerge' in utils and '"font-size": [{ text: SIZE_TOKENS }]' in utils
