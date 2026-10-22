"""The admin-only density switch, and where it is allowed to be.

Two densities, one component set. Comfortable is the default for everybody and
the only option a creator or a brand ever gets; compact is for an admin
working a long queue. The brief asked for the scope to be **enforced, not
documented**: a future contributor wrapping the whole app in compact should
fail CI rather than ship. That is most of this file.

Three layers:

- **The server** refuses to store a density for any role but admin, and only
  an admin's `/auth/me` carries one. Driven against mongomock and read back.
- **The mechanism** is one attribute redefining custom properties: the compact
  block may touch sizes and spacing and nothing else, and one component writes
  the attribute.
- **The scope** is a named list of console sections. The overview is not on
  it, no creator, brand or manager file can reach the module, and the row
  height the windowing multiplies by is the stylesheet's.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient
from pydantic import ValidationError

import server

SRC = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
CSS = (SRC / "index.css").read_text()
DENSITY_JS = (SRC / "components" / "admin" / "console" / "density.jsx").read_text()
ROUTES = (SRC / "components" / "admin" / "routes.jsx").read_text()

LOOP = None


def _run(coro):
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP.run_until_complete(coro)


def _code(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))


def _app_files():
    for p in sorted(SRC.rglob("*")):
        if p.suffix in (".js", ".jsx") and "constants/testIds" not in str(p):
            yield p


# ---------------------------------------------------------------------------
# The server: an admin's field, and nobody else's
# ---------------------------------------------------------------------------


def _guard(fn):
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and getattr(dep.dependency, "__name__", "") == "_guard":
            return dep.dependency
    raise AssertionError(f"{fn.__name__} declares no require_roles guard")


@pytest.mark.parametrize("role,allowed", [
    ("admin", True),
    ("weare_team", False),
    ("campaign_manager", False),
    ("brand_manager", False),
    ("brand", False),
    ("creator", False),
])
def test_only_an_admin_may_set_a_density(role, allowed):
    """Run the real dependency rather than reading its arguments: a guard
    listing the wrong roles fails here, where a string match would pass."""
    guard = _guard(server.set_admin_density)

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    assert _run(go()) is allowed


def test_the_two_values_and_nothing_else():
    assert server.AdminDensityPayload(density="compact").density == "compact"
    for bad in ("dense", "Compact", "", None):
        with pytest.raises(ValidationError):
            server.AdminDensityPayload(density=bad)


def test_setting_it_writes_the_admins_record_and_me_reads_it_back():
    async def go():
        db = AsyncMongoMockClient()["density"]
        original = server.db
        server.db = db
        try:
            admin_oid, creator_oid = ObjectId(), ObjectId()
            await db.users.insert_many([
                {"_id": admin_oid, "role": "admin", "email": "a@x.in", "name": "A"},
                {"_id": creator_oid, "role": "creator", "email": "c@x.in", "name": "C"},
            ])
            admin = {"_id": str(admin_oid), "role": "admin", "email": "a@x.in", "name": "A"}
            await server.set_admin_density(server.AdminDensityPayload(density="compact"), admin)
            stored = await db.users.find_one({"_id": admin_oid})
            me_admin = await server.me({**admin, "admin_density": stored.get("admin_density")})
            me_creator = await server.me({"_id": str(creator_oid), "role": "creator",
                                          "email": "c@x.in", "name": "C"})
            untouched = await db.users.find_one({"_id": creator_oid})
            return stored, me_admin, me_creator, untouched
        finally:
            server.db = original

    stored, me_admin, me_creator, untouched = _run(go())
    assert stored["admin_density"] == "compact"
    assert me_admin["admin_density"] == "compact"
    # **No field for anybody else** — not a null, not a default: absent.
    assert "admin_density" not in me_creator
    assert "admin_density" not in untouched


def test_the_reader_never_hands_a_density_to_another_role():
    assert server._admin_density({"role": "creator", "admin_density": "compact"}) is None
    assert server._admin_density({"role": "weare_team", "admin_density": "compact"}) is None
    assert server._admin_density({"role": "admin"}) == "comfortable"
    assert server._admin_density({"role": "admin", "admin_density": "sepia"}) == "comfortable"


# ---------------------------------------------------------------------------
# The mechanism: one attribute, sizes only
# ---------------------------------------------------------------------------


def _compact_block():
    i = CSS.index('[data-density="compact"] {')
    return CSS[i:CSS.index("}", i)]


def test_compact_redefines_sizes_and_spacing_and_nothing_else():
    """**Colours, radii and focus styles do not change between densities** —
    held by what the block is allowed to contain, so adding a colour to it
    fails here rather than in somebody's review."""
    names = set(re.findall(r"--([\w-]+):", _compact_block()))
    assert names == {"space-row-y", "row-h", "text-body", "text-meta", "space-section"}, names


def test_the_compact_deltas_are_the_briefs():
    block = _compact_block()
    for name, value in (("space-row-y", "9px"), ("text-body", "14px"),
                        ("text-meta", "13px"), ("space-section", "16px")):
        assert re.search(rf"--{name}:\s*{value};", block), name
    for name, value in (("space-row-y", "22px"), ("text-body", "16px"),
                        ("text-meta", "14px"), ("space-section", "26px")):
        assert re.search(rf"--{name}:\s*{value};", CSS), name
    assert '[data-density="compact"] .density-avatar' in CSS


def test_a_row_is_tall_enough_for_its_own_padding_and_a_line():
    """`--row-h` is a fixed height the windowing multiplies by; a row whose
    content outgrew it would drift a fraction of a pixel per row until the
    scroll position pointed at the wrong record. Line height 1.55 is
    `text-body`'s in tailwind.config.js."""
    def px(name, text):
        return float(re.search(rf"--{name}:\s*([\d.]+)px", text).group(1))

    comfortable_h, compact = px("row-h", CSS), _compact_block()
    assert comfortable_h >= 2 * px("space-row-y", CSS) + 1.55 * px("text-body", CSS)
    assert px("row-h", compact) >= 2 * px("space-row-y", compact) + 1.55 * px("text-body", compact)


def test_one_writer_of_the_attribute():
    writers = [
        str(p.relative_to(SRC)) for p in _app_files()
        if "data-density=" in _code(p.read_text())
    ]
    assert writers == ["components/admin/console/density.jsx"], writers


def test_no_conditional_class_tree_reads_the_density():
    """The density is consumed through custom properties. A component that
    branches on it to choose a class is the second stylesheet the brief
    forbids. `DataTable` reads the density only to know when to re-measure."""
    offenders = []
    for p in _app_files():
        code = _code(p.read_text())
        if re.search(r"density\s*===?\s*[\"']compact[\"']", code) and p.name != "density.jsx":
            offenders.append(str(p.relative_to(SRC)))
    assert not offenders, offenders


# ---------------------------------------------------------------------------
# The scope: named, enforced, and never the whole app
# ---------------------------------------------------------------------------


def _surfaces():
    body = DENSITY_JS.split("export const DENSITY_SURFACES = [")[1].split("]")[0]
    return re.findall(r'"([a-z-]+)"', body)


def test_the_surfaces_are_console_sections_and_the_overview_is_not_one():
    sidebar = (SRC / "components" / "admin" / "console" / "Sidebar.jsx").read_text()
    sections = set(re.findall(r'key: "([a-z-]+)"', sidebar))
    surfaces = _surfaces()
    assert surfaces and set(surfaces) <= sections, set(surfaces) - sections
    for never in ("overview", "", "health", "analytics", "performance", "settings"):
        assert never not in surfaces, never
    # The three the brief names are all present.
    for must in ("queue", "audit", "creators", "campaigns", "brands"):
        assert must in surfaces, must


def test_every_scope_names_an_allowed_surface_and_lives_in_the_route_table():
    """`DensityScope` appears in one file, wrapping one section each, and the
    overview's route is not among them."""
    users = [
        str(p.relative_to(SRC)) for p in _app_files()
        if "<DensityScope" in _code(p.read_text())
    ]
    assert users == ["components/admin/routes.jsx"], users
    named = re.findall(r'<DensityScope surface="([a-z-]+)"', ROUTES)
    assert named and set(named) <= set(_surfaces()), set(named) - set(_surfaces())
    overview = ROUTES.split("export const OverviewRoute")[1].split("\nexport ")[0]
    assert "DensityScope" not in overview


def test_nothing_outside_the_console_can_reach_it():
    """A creator, brand or manager screen importing the module is the first
    step of wrapping it in compact; refuse the import, not just the use."""
    offenders = []
    for p in _app_files():
        rel = str(p.relative_to(SRC))
        if rel.startswith("components/admin/") or rel == "pages/AdminConsole.jsx":
            continue
        if "console/density" in p.read_text():
            offenders.append(rel)
    assert not offenders, offenders
    app = (SRC / "App.js").read_text()
    assert "DensityScope" not in app and "data-density" not in app


def test_a_mistake_is_loud_in_development():
    """The guard has to be able to fail in front of whoever made the mistake:
    off-list surface or off-route render throws outside production."""
    scope = DENSITY_JS.split("export function DensityScope")[1].split("\nexport ")[0]
    assert "densityAllowed(surface, pathname)" in scope
    assert "if (ON_DEV) throw new Error" in scope
    assert 'process.env.NODE_ENV !== "production"' in DENSITY_JS
    # And the check is the exact list route, not a prefix: a record's detail
    # page under /admin/campaigns is not a table.
    allowed = DENSITY_JS.split("export function densityAllowed")[1].split("\n}")[0]
    assert "return path === `/admin/${surface}`;" in allowed
    assert "startsWith" not in allowed


def test_the_windowing_reads_the_row_height_from_the_stylesheet():
    table = _code((SRC / "components" / "admin" / "console" / "DataTable.jsx").read_text())
    assert 'getPropertyValue("--row-h")' in table
    assert "useDensity()" in table


# ---------------------------------------------------------------------------
# The control
# ---------------------------------------------------------------------------


def test_the_control_is_two_real_buttons_in_the_console_header():
    toggle = DENSITY_JS.split("export function DensityToggle")[1]
    assert "<button" in toggle and "aria-pressed={on}" in toggle
    assert '"Comfortable"' in toggle and '"Compact"' in toggle
    assert 'role="group"' in toggle
    # Only an admin, only where it does something.
    assert "!adjustable" in toggle
    console = (SRC / "pages" / "AdminConsole.jsx").read_text()
    assert "<DensityToggle />" in console and "<DensityProvider user={user}>" in console


def test_the_choice_is_cached_for_first_paint_and_the_account_wins():
    assert 'DENSITY_STORAGE_KEY = "weare:admin-density"' in DENSITY_JS
    assert 'api.put("/auth/me/density"' in DENSITY_JS
    provider = DENSITY_JS.split("export function DensityProvider")[1].split("\nexport ")[0]
    # Account, then cache, then the default — and a non-admin is comfortable.
    assert "fromAccount || cached() || DEFAULT_DENSITY" in provider
    assert "isAdmin ?" in provider
