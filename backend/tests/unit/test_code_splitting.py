"""One bundle, five audiences, and the four of them nobody was reading.

The frontend shipped as a single file. Every creator on mobile data downloaded
the admin console, the brand console and the manager screens before their own
dashboard could paint — three surfaces they will never open, on a mid-range
Android phone, which is the audience this product is actually for.

These tests hold the split in place. **The failure they exist for is a route
added the old way**: a static `import` in `App.js` is invisible in review and
silently pulls a whole surface back into the shell, and nobody notices until
somebody measures the bundle again six months later.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"


def read(*parts):
    return (FRONTEND.joinpath(*parts)).read_text()


APP = read("App.js")
# `/dashboard` dispatches to two audiences, so two of the lazy imports live
# there rather than in App.js — the routing table is both files.
ROUTING = APP + read("pages", "Dashboard.jsx")

# The pages that may still be imported eagerly, and why each one earns it.
#
# `Landing`, `Login`, `Signup` and `AdminLogin` are **not** here — measured,
# splitting the auth screens alone took 35KB off the shell every signed-in user
# pays, which was more than the guess that kept them eager.
_EAGER_ALLOWED = set()

# Every audience, and the chunk its code belongs in.
_SURFACES = {
    "marketing": ("ForBrands", "ForCreators", "HowItWorks", "WhyWeAre", "NotFound", "Legal"),
    "auth": ("Login", "Signup", "AdminLogin"),
    "creator": ("CreatorHome", "CreatorOnboarding", "CreatorProfile", "SelfCheckIn",
                "InstagramCallback"),
    "brand": ("BrandOnboarding", "PostCampaign",
              "BrandCampaignApplicants", "BrandDashboardView"),
    "manager": ("ManagerHome", "ManagerCampaign"),
    "admin": ("AdminConsole", "admin/routes", "admin/CampaignDetailPage",
              "admin/CreatorDetailPage", "admin/BrandDetailPage",
              "admin/CollaborationDetailPage"),
}


class TestEverySurfaceIsItsOwnChunk:
    def test_no_page_is_imported_eagerly(self):
        """**The regression this whole file exists for.** One static import is
        a whole surface back in the shell, and it reads like every other line
        in the file."""
        eager = set(re.findall(r'^import\s+\w+\s+from\s+"@/pages/(\w+)"', APP, re.M))
        assert eager <= _EAGER_ALLOWED, f"eagerly imported pages: {sorted(eager - _EAGER_ALLOWED)}"

    def test_no_admin_component_is_imported_eagerly(self):
        """The console is the largest of the five and the one the fewest people
        open. A static import of any of its pieces drags the rest with it."""
        eager = re.findall(r'^import\s+.*from\s+"@/components/admin/', APP, re.M)
        assert eager == [], eager

    @pytest.mark.parametrize("chunk,modules", sorted(_SURFACES.items()))
    def test_each_surface_is_named_into_one_chunk(self, chunk, modules):
        """Named rather than left to webpack. Without the name every page is
        its own file, which trades a bundle nobody needs for a waterfall
        everybody feels — and inside the console, a fallback under the sidebar
        forty times an afternoon."""
        for module in modules:
            pattern = (
                r'webpackChunkName:\s*"' + chunk + r'"\s*\*/\s*"@/(?:pages|components)/'
                + re.escape(module) + r'"'
            )
            assert re.search(pattern, ROUTING), (chunk, module)

    def test_the_shared_screens_are_named_apart(self):
        """`ApplicationDetail` is read by three consoles and the campaign pages
        by all of them. Naming them into any one surface's chunk would make the
        other two download that surface to reach a shared screen."""
        for chunk, module in (
            ("application", "components/application/ApplicationDetail"),
            ("campaigns", "pages/Campaigns"),
            ("campaigns", "pages/CampaignDetail"),
            ("calendar", "pages/ShootCalendar"),
        ):
            assert f'webpackChunkName: "{chunk}" */ "@/{module}"' in APP, module

    def test_every_lazy_import_goes_through_the_retry(self):
        """A bare `lazy(() => import(...))` is one that gives up on the first
        dropped packet — see `retryImport`."""
        bare = re.findall(r"lazy\(\(\)\s*=>\s*import\(", APP)
        assert bare == [], "lazy import without retryImport"
        assert "const load = (importer) => lazy(() => retryImport(importer));" in APP


class TestDashboardIsTwoSurfacesBehindOnePath:
    def test_the_dispatcher_holds_no_page_of_its_own(self):
        """`/dashboard` is the creator's home for one role and the brand
        console for another. While both lived in this file, each audience
        downloaded the other's product to reach their own."""
        src = read("pages", "Dashboard.jsx")
        assert "CreatorHome" in src and "BrandDashboardView" in src
        for smell in (
            'import CreatorHome from',
            'import BrandDashboardView from',
        ):
            assert smell not in src, smell

    def test_both_branches_are_lazy_and_in_their_own_audience_chunk(self):
        src = read("pages", "Dashboard.jsx")
        assert 'webpackChunkName: "creator" */ "@/pages/CreatorHome"' in src
        assert 'webpackChunkName: "brand" */ "@/pages/BrandDashboardView"' in src

    def test_the_dispatcher_is_not_named_into_either_chunk(self):
        """It was `creator` first, which made a brand manager download the
        creator app to reach the file that decides they are not one."""
        assert 'webpackChunkName: "dashboard" */ "@/pages/Dashboard"' in APP

    def test_it_brings_its_own_suspense(self):
        """The router's boundary sits above `Routes` and has already resolved
        by the time this branch renders."""
        src = read("pages", "Dashboard.jsx")
        assert "<Suspense fallback={<RouteFallback />}>" in src

    def test_the_creator_home_still_exists_whole(self):
        """Extracted, not rewritten: the same component, in a file of its own.
        Every piece the dashboard is documented as putting above the fold is
        still mounted by it."""
        src = read("pages", "CreatorHome.jsx")
        assert "export default function CreatorHome" in src
        for piece in ("<Hero", "<ActiveCampaigns", "<Completeness", "<Suggested",
                      "<Applications", "<Earnings", "<HeldApplications",
                      "<VerificationExpiry", "StatusBanners"):
            assert piece in src, piece


class TestTheFallbackIsPartOfTheDesign:
    def test_it_is_shapes_rather_than_a_spinner(self):
        """The rule the whole product already holds: loading is a skeleton
        shaped like the content, never a spinner."""
        src = read("components", "RouteFallback.jsx")
        assert "<Skeleton" in src
        assert "animate-spin" not in src

    def test_it_stands_on_the_same_ground_every_page_does(self):
        """So the swap is a fill rather than a flash, and the page that lands is
        at least a screen tall in every case."""
        src = read("components", "RouteFallback.jsx")
        assert "min-h-screen bg-background" in src
        assert "grain-page" in src

    def test_it_does_not_guess_at_the_chrome(self):
        """Marketing pages carry `MarketingNavbar`, the app carries `Navbar`,
        the console has a sidebar. Drawing one would draw the wrong one about
        half the time, and a header that appears and is then replaced by a
        different header is worse than one that arrives once."""
        src = read("components", "RouteFallback.jsx")
        # The rendered half only — the header comment names both navbars while
        # explaining why neither is drawn.
        body = src[src.index("export default function RouteFallback") :]
        assert "MarketingNavbar" not in body
        assert "<Navbar" not in body
        assert "@/components/Navbar" not in src

    def test_a_screen_reader_hears_loading_rather_than_empty_boxes(self):
        src = read("components", "RouteFallback.jsx")
        assert "<LoadingAnnouncement" in src
        assert 'aria-hidden="true"' in src


class TestAChunkThatNeverArrives:
    def test_the_retry_happens_inside_the_importer(self):
        """**`React.lazy` does not retry.** It memoises the promise including
        its rejection, so remounting the boundary re-throws the same error and
        never re-requests the file — which makes an ordinary "Try again" button
        a lie. The second attempt has to be a fresh call to the importer."""
        src = read("lib", "lazyRoute.js")
        body = src[src.index("export function retryImport") :]
        # Two calls: the first attempt, and a real second one after the pause.
        assert body.count("importer()") == 2
        assert "setTimeout" in body

    def test_a_second_failure_is_tagged_rather_than_left_generic(self):
        src = read("lib", "lazyRoute.js")
        assert "asChunkError(error)" in src
        assert "wrapped.isChunkError = true" in src

    def test_the_reader_does_not_depend_on_a_browser_s_wording(self):
        """Webpack's own `ChunkLoadError` is recognised too, because a prefetch
        can raise one this module never wrapped — but the tag is what decides,
        so a copy edit to an error string cannot change which fallback somebody
        sees."""
        src = read("lib", "lazyRoute.js")
        body = src[src.index("export function isChunkError") :]
        assert "error.isChunkError === true" in body
        assert 'error.name === "ChunkLoadError"' in body

    def test_the_boundary_answers_a_chunk_failure_differently(self):
        """"Something on our side broke" is wrong about a dropped connection,
        and a soft Try again cannot fix it. The two are different failures and
        say different things."""
        src = read("components", "ErrorBoundary.jsx")
        assert "isChunkError(error)" in src
        block = src[src.index("if (isChunkError(error))") :]
        block = block[: block.index('if (variant === "page")')]
        assert "window.location.reload()" in block
        assert "didn't finish downloading" in block

    def test_it_is_decided_by_the_error_and_not_by_the_variant(self):
        """A chunk can fail under the route boundary or a section one, and the
        honest answer is the same in both places — so the branch comes before
        the variant check rather than inside one."""
        src = read("components", "ErrorBoundary.jsx")
        assert src.index("if (isChunkError(error))") < src.index('if (variant === "page")')


class TestWhereSuspenseSits:
    def test_it_is_inside_the_route_boundary(self):
        """A chunk that never arrives rejects through Suspense, and the
        boundary above is what turns that into a page with a reload on it.
        Outside, the rejection reaches the root boundary and takes the
        impersonation banner down with it — and an admin must never be left
        acting as somebody else with nothing on screen saying so."""
        assert APP.index("<RouteBoundary>") < APP.index("<Suspense fallback={<RouteFallback />}>")
        assert APP.index("<Suspense fallback={<RouteFallback />}>") < APP.index("<Routes>")

    def test_the_banner_is_still_above_all_of_it(self):
        assert APP.index("<ImpersonationBanner />") < APP.index("<RouteBoundary>")

    def test_one_suspense_rather_than_one_per_route(self):
        """The fallback replaces the whole page either way, and a boundary per
        route is a boundary somebody forgets on the route they add next."""
        assert APP.count("<Suspense") == 1
