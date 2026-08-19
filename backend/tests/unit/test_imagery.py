"""Pictures on briefs, and a mark on brands.

Every listing looked identical because nothing in it was a picture. Two fields
fix that — `cover_image_url` on a campaign and `logo_url` on a brand profile —
and the whole of the work is in the three rules around them:

**The value is a path we issued.** Both are set by uploading a file, never by
accepting a URL on an edit payload. `_store_upload` decides the type from the
leading bytes and names the file itself, which is the same function the
creator's profile photo goes through — a cover is a stranger-visible image on
our domain, so "it says it's a JPEG" is not a check.

**The box is reserved before the picture arrives.** Every surface draws the
cover in an aspect-ratio container and every skeleton that stands in for one
reserves the same box. A picture that lands and pushes the page down is the
failure mode this feature would otherwise introduce everywhere at once.

**No picture is a state, not a hole.** The fallback is generated from the
campaign's id, so a brief with no cover still looks like itself rather than
like every other coverless brief. `_cover_hue` and `coverHue` in
`frontend/src/lib/cover.js` compute the same number, so the card in the app and
the server-rendered share page of the same brief are the same colour.
"""
import inspect
import re
from pathlib import Path

import pytest

import server

BACKEND = Path(server.__file__).resolve()
FRONTEND = BACKEND.parents[1] / "frontend" / "src"


def source(fn):
    return inspect.getsource(fn)


# --- The upload routes ------------------------------------------------------


@pytest.mark.parametrize(
    "fn",
    [
        "upload_campaign_cover",
        "delete_campaign_cover",
        "upload_brand_logo",
        "delete_brand_logo",
    ],
)
def test_the_four_routes_exist(fn):
    assert callable(getattr(server, fn))


@pytest.mark.parametrize(
    "fn", ["upload_campaign_cover", "delete_campaign_cover"]
)
def test_a_cover_is_the_brand_s_or_an_admin_s(fn):
    """The brand posts the brief; an admin fixing one should not need a
    different door to do it through."""
    src = source(getattr(server, fn))

    assert "require_roles(*BRAND_ROLES" in src
    assert '"admin"' in src


@pytest.mark.parametrize("fn", ["upload_brand_logo", "delete_brand_logo"])
def test_a_logo_is_the_brand_s_own(fn):
    src = source(getattr(server, fn))

    assert "require_roles(*BRAND_ROLES)" in src


@pytest.mark.parametrize(
    "fn", ["upload_campaign_cover", "delete_campaign_cover"]
)
def test_another_brand_s_campaign_is_a_404(fn):
    """Same ownership helper as every other campaign write, which answers 404
    rather than 403 so the ids that exist stay unknowable."""
    assert "_own_campaign_or_404" in source(getattr(server, fn))


@pytest.mark.parametrize("fn", ["upload_brand_logo", "delete_brand_logo"])
def test_a_logo_is_scoped_by_the_brand_not_the_login(fn):
    """`user["_id"]` is the person; `_brand_scope` is the business."""
    src = source(getattr(server, fn))

    assert "_brand_scope(user)" in src
    assert 'user["_id"]' not in src


def test_neither_upload_is_behind_verification():
    """An unverified brand may draft. A cover on a draft reaches nobody — the
    gate belongs on publish, which has it, and putting a second one here would
    mean a brand could not prepare a brief while we read its paperwork."""
    for fn in ("upload_campaign_cover", "upload_brand_logo"):
        assert "_verified_brand_or_403" not in source(getattr(server, fn))


def test_a_cover_change_is_audited():
    """Who put that picture on the brief is a question with an answer."""
    for fn, action in (
        (server.upload_campaign_cover, "campaign.cover_upload"),
        (server.delete_campaign_cover, "campaign.cover_removed"),
    ):
        src = source(fn)
        assert action in src
        assert "_campaign_audit_context(campaign)" in src, (
            "the line has to carry the brand and the campaign, like every other"
        )


# --- What actually gets stored ----------------------------------------------


def test_both_go_through_the_same_sniffing_upload():
    """`_store_upload` reads the leading bytes, names the file itself and
    enforces the ceiling while streaming. A second implementation here is a
    second place to forget one of the three."""
    assert "_store_upload(file, prefix=prefix)" in source(server._replace_image)


def test_the_client_never_supplies_the_url():
    """The field is written from what we stored, never from the payload — so
    there is no way to point a campaign at somebody else's server."""
    for payload in (server.PostCampaignPayload, server.UpdateCampaignPayload):
        assert "cover_image_url" not in payload.model_fields
    assert "logo_url" not in server.BrandProfileUpdate.model_fields


def test_the_new_file_is_written_before_the_old_one_is_deleted():
    """The other order leaves a record pointing at nothing when the write
    fails, and a broken image is worse than an out-of-date one."""
    src = source(server._replace_image)

    assert src.index("_store_upload") < src.index("_delete_upload")
    assert src.index("update_one") < src.index("_delete_upload")


def test_replacing_with_the_same_path_does_not_delete_it():
    assert 'previous != public_url' in source(server._replace_image)


def test_a_missing_record_says_which_one():
    """`_replace_image` serves two collections, so the message has to come from
    the caller — "Not found" on a logo upload reads as a broken route."""
    assert "missing: str" in source(server._replace_image)
    assert 'missing="Campaign not found"' in source(server.upload_campaign_cover)
    assert 'missing="Brand profile not found"' in source(server.upload_brand_logo)


def test_covers_land_in_the_public_directory_not_the_private_one():
    """The opposite of a verification document: a cover is meant to be seen by
    strangers, which is the whole point of it."""
    src = source(server._store_upload)

    assert "UPLOAD_DIR" in src
    assert "PRIVATE_UPLOAD_DIR" not in src


# --- The formats we offer ---------------------------------------------------


def test_the_accepted_formats_come_from_the_signature_table():
    """An `accept=` attribute promising a format the sniffer rejects invites
    the file and then refuses it — a minute of upload wasted on mobile data.
    Same reasoning as ACCEPTED_DOCUMENT_MIMES."""
    from_signatures = {mime for _, mime, _ in server._IMAGE_SIGNATURES}

    assert from_signatures <= server.ACCEPTED_IMAGE_MIMES
    assert "image/webp" in server.ACCEPTED_IMAGE_MIMES, (
        "two-part magic, so it isn't in the table and has to be added by hand"
    )


def test_pdf_is_not_an_image():
    """It is accepted as a *document* — a licence usually is one — and must not
    leak into the picture uploads from sharing a constant."""
    assert "application/pdf" not in server.ACCEPTED_IMAGE_MIMES
    assert "application/pdf" in server.ACCEPTED_DOCUMENT_MIMES


def test_the_browser_is_told_the_limits_rather_than_copying_them():
    """A copy of MAX_UPLOAD_MB in JavaScript is a copy that drifts the day
    somebody raises it here."""
    src = source(server._brand_profile_response)

    assert '"max_image_bytes": max_upload_bytes()' in src
    assert "ACCEPTED_IMAGE_MIMES" in src


# --- The generated fallback -------------------------------------------------


def test_the_hue_is_stable_for_an_id():
    assert server._cover_hue("abc") == server._cover_hue("abc")


def test_ids_that_differ_by_one_byte_are_far_apart():
    """Consecutive ObjectIds differ only in the counter's last byte, and that is
    exactly what a list of briefs posted the same afternoon looks like. The
    first version summed character codes and put them two degrees apart — a row
    of the same rectangle, which is what this feature exists to avoid."""
    ids = [f"65a1b2c3d4e5f60718293a{n:02x}" for n in range(12)]
    hues = [server._cover_hue(i) for i in ids]
    gaps = [
        min(abs(a - b), 360 - abs(a - b))
        for a, b in zip(hues, hues[1:])
    ]

    assert len(set(hues)) >= 10, "too many collisions across neighbouring ids"
    assert sum(gaps) / len(gaps) > 60, f"neighbouring hues are crowded: {hues}"


def test_it_copes_with_no_seed_at_all():
    assert 0 <= server._cover_hue("") < 360
    assert 0 <= server._cover_hue(None) < 360


def test_the_frontend_computes_the_same_number():
    """The two have to agree or one brief is two colours: the card in the app
    and the server-rendered share page of the same brief.

    Checked two ways, because neither is enough on its own. The pinned table is
    what the JS actually produced when run side by side with this — change the
    Python and it fails. The source check is for the other direction: nothing
    here executes the JS, so a change to *it* would otherwise go unnoticed.
    """
    js = (FRONTEND / "lib" / "cover.js").read_text()
    body = js[js.index("export function coverHue"):js.index("export function coverGradient")]

    for token in ("2166136261", "16777619", "Math.imul", ">>> 0", "% 360"):
        assert token in body, f"coverHue is no longer FNV-1a — {token} is gone"

    for seed, hue in [
        ("k1", 249), ("k2", 72), ("", 358), ("Kaapi", 75),
        ("65a1b2c3d4e5f60718293a01", 44), ("65a1b2c3d4e5f60718293a02", 221),
    ]:
        assert server._cover_hue(seed) == hue, f"{seed!r} no longer hashes to {hue}"


# --- The shareable page -----------------------------------------------------


def test_the_preview_image_is_the_brief_s_own_cover():
    """A shared brief that previews as the site card previews the same as every
    other shared brief."""
    src = source(server._share_page_html)

    assert "cover = _absolute_media_url(" in src
    assert 'og_image = e(cover or f"{app_base}/og-image.png")' in src


def test_the_preview_image_is_absolute():
    """A crawler is handed the tag and no page to resolve it against."""
    assert server._absolute_media_url("/uploads/a.jpg", "https://api.example/") == (
        "https://api.example/uploads/a.jpg"
    )


def test_an_already_absolute_url_is_left_alone():
    """Storage could move to a CDN without this becoming a double prefix."""
    url = "https://cdn.example/a.jpg"

    assert server._absolute_media_url(url, "https://api.example") == url


def test_no_cover_means_no_url_rather_than_a_bare_origin():
    assert server._absolute_media_url(None, "https://api.example") == ""


def test_the_base_is_the_host_that_serves_the_file():
    """_share_base() is the frontend, where only /c/* is proxied — using it
    would produce a URL for a file that host does not have."""
    src = source(server.public_campaign_page)

    assert "media_base=str(request.base_url)" in src
    assert "media_base=_share_base()" not in src


def test_the_declared_dimensions_only_describe_the_card_we_made():
    """A brand's cover is whatever they uploaded. A wrong og:image:width is
    worse than none — some crawlers lay the card out from it."""
    src = source(server._share_page_html)

    assert 'og_image_size = (\n        ""\n        if cover' in src


def test_the_page_reserves_the_box():
    src = source(server._share_page_html)

    assert "aspect-ratio:16/9" in src


def test_the_page_draws_a_generated_cover_when_there_is_none():
    src = source(server._share_page_html)

    assert "cover fallback" in src
    assert "_cover_hue(cid)" in src


def test_the_initial_is_escaped_like_everything_else():
    """It comes off a brand-supplied business name."""
    src = source(server._share_page_html)

    assert "initial = e(" in src


# --- Every surface that draws a campaign gets the field ---------------------


CAMPAIGN_RESPONSES = [
    "_serialize_campaign",
    "_serialize_brand_campaign",
    "_serialize_collab_row",
    "list_all_campaigns",
    "list_campaigns_for_review",
    "public_campaign_preview",
]


@pytest.mark.parametrize("fn", CAMPAIGN_RESPONSES)
def test_a_campaign_payload_carries_its_cover(fn):
    assert "cover_image_url" in source(getattr(server, fn))


BRAND_NAMED_RESPONSES = [
    "_serialize_campaign",
    "_serialize_brand_profile",
    "_admin_brand_fields",
    "_load_brand_map",
    "list_campaigns_for_review",
    "public_campaign_preview",
    "get_application",
]


@pytest.mark.parametrize("fn", BRAND_NAMED_RESPONSES)
def test_a_brand_named_in_a_payload_carries_its_logo(fn):
    assert "logo_url" in source(getattr(server, fn))


def test_no_response_dict_repeats_a_key():
    """A duplicated dict key is legal Python and silently keeps the last one,
    so a patch that lands twice never announces itself. Caught for real: three
    responses carried `brand_logo_url` twice, at two indentation levels."""
    import ast

    tree = ast.parse(BACKEND.read_text())
    repeats = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        names = [
            k.value for k in node.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        ]
        for name in set(names):
            if names.count(name) > 1:
                repeats.append(f"{name!r} at line {node.lineno}")

    assert not repeats, "duplicated dict keys: " + ", ".join(sorted(repeats))


def test_a_picture_is_not_contact_detail():
    """It must not have been quietly added to the forbidden list, which would
    strip it out of every brand-facing response."""
    forbidden = set(server.BRAND_FORBIDDEN_CREATOR_FIELDS)

    assert "cover_image_url" not in forbidden
    assert "logo_url" not in forbidden


# --- The frontend -----------------------------------------------------------


def component(*parts):
    return (FRONTEND.joinpath(*parts)).read_text()


def test_there_is_one_cover_component():
    """The card, the detail page and the dashboards draw the same picture,
    including the same generated one — a brief that is green in the list and
    blue on its own page reads as two briefs."""
    assert (FRONTEND / "components" / "CampaignCover.jsx").is_file()


def test_the_cover_reserves_its_box():
    src = component("components", "CampaignCover.jsx")

    assert 'ratio = "aspect-[16/9]"' in src
    assert "media-frame" in src


def test_the_ratio_is_on_the_container_not_the_image():
    """An image that never arrives still has to occupy the space it claimed."""
    src = component("components", "CampaignCover.jsx")
    img = src[src.index("<img"):src.index("/>", src.index("<img"))]

    assert "aspect-" not in img
    assert "absolute inset-0" in img


def test_a_broken_image_falls_back_rather_than_leaving_a_hole():
    src = component("components", "CampaignCover.jsx")

    assert "onError={() => setBroken(true)}" in src


def test_the_fallback_is_generated_from_the_id():
    src = component("components", "CampaignCover.jsx")

    assert "coverGradient(id)" in src
    assert "initialOf(" in src


def test_the_generated_cover_is_never_grained():
    """`.media-frame` and the gradient both set `background-image`, and one
    silently wins — the same rule the design foundations state for `.grain-*`.
    So the grain goes on the branch that reserves a box for a photograph, and
    not on the branch that is already a gradient."""
    src = component("components", "CampaignCover.jsx")
    # Comments stripped: both branches *talk* about the rule, and the check is
    # about which one applies the class.
    code = "\n".join(
        line for line in src.splitlines() if not line.strip().startswith("//")
    )
    split = code.index("coverGradient(id)")

    assert "media-frame" not in code[split - 200:]
    assert "media-frame" in code[:split]


@pytest.mark.parametrize("name", ["CampaignCover", "BrandAvatar", "ImageUploadField"])
def test_every_file_that_uses_a_component_imports_it(name):
    """A bare undefined identifier is legal JavaScript, so this compiles
    cleanly and throws at runtime — Landing.jsx really did ship a whole page
    behind an error boundary this way, and the build said nothing."""
    missing = []
    for path in sorted(FRONTEND.rglob("*.jsx")):
        if path.name == f"{name}.jsx":
            continue
        text = path.read_text()
        if f"<{name}" not in text:
            continue
        # Imports wrap: `import X, {\n  Y,\n} from "..."` is one statement over
        # four lines, so this reads the bindings of every import in the file
        # rather than one line at a time.
        bound = any(
            re.search(rf"\b{name}\b", m.group(1))
            for m in re.finditer(r"^import\s+([\s\S]*?)\s+from\s", text, re.M)
        )
        if not bound:
            missing.append(str(path.relative_to(FRONTEND)))

    assert not missing, f"{name} used without importing it in: {missing}"


def test_the_brand_avatar_mirrors_the_creator_one():
    """They appear on the same screens; two fallback treatments would read as
    two kinds of account."""
    brand = component("components", "BrandAvatar.jsx")
    creator = component("components", "admin", "shared.jsx")

    for shared in ("rounded-md border border-white/10", "bg-ember-500/10", "font-serif"):
        assert shared in brand, f"BrandAvatar has dropped {shared}"
        assert shared in creator


def test_a_logo_is_contained_and_a_photo_is_covered():
    """A logo is usually not square and usually has whitespace around it;
    cropping one to fill a square cuts the mark in half."""
    assert "object-contain" in component("components", "BrandAvatar.jsx")


# --- Uploading, in the browser ----------------------------------------------


def test_the_size_is_checked_before_a_byte_moves():
    """A 6MB scan on mobile data should fail instantly, not after a minute."""
    src = component("components", "ImageUploadField.jsx")

    assert "file.size > maxBytes" in src
    assert src.index("file.size > maxBytes") < src.index("api.post(endpoint")


def test_the_format_is_checked_against_the_server_s_list():
    src = component("components", "ImageUploadField.jsx")

    assert "acceptedMimes.includes(file.type)" in src


def test_the_browser_sets_the_multipart_boundary():
    """The client's JSON default would make the body unparseable."""
    src = component("components", "ImageUploadField.jsx")

    assert '"Content-Type": undefined' in src


def test_the_same_file_can_be_picked_again_after_a_refusal():
    """Which is exactly what somebody does after resizing it."""
    src = component("components", "ImageUploadField.jsx")

    assert "e.target.value" in src


def test_a_deferred_preview_is_revoked():
    """A blob left dangling is a copy of the file held for the rest of the
    session."""
    src = component("components", "ImageUploadField.jsx")

    assert "URL.revokeObjectURL" in src
    assert "useEffect(() => releasePreview, [releasePreview])" in src


def test_a_new_campaign_holds_its_cover_until_it_has_an_id():
    """There is no /campaigns/undefined/cover — the file waits and goes up the
    moment the brief exists."""
    src = component("pages", "PostCampaign.jsx")

    assert "onFile={setPendingCover}" in src
    assert "if (pendingCover)" in src
    assert "`/brand/campaigns/${data.id}/cover`" in src


def test_a_failed_cover_does_not_lose_the_brief():
    """The brief is the thing that mattered, and it already exists — throwing
    it away over a picture would make somebody retype the whole form."""
    src = component("pages", "PostCampaign.jsx")
    block = src[src.index("if (pendingCover)"):][:900]

    assert "catch" in block
    assert "Add it from Edit" in block


def test_editing_a_campaign_uploads_straight_away():
    src = component("pages", "PostCampaign.jsx")

    assert "isEditing\n                                        ? `/brand/campaigns/${editingId}/cover`" in src


def test_the_admin_uses_the_same_control_against_the_same_route():
    src = component("components", "admin", "CampaignDetailPage.jsx")

    assert "ImageUploadField" in src
    assert "`/brand/campaigns/${id}/cover`" in src


def test_a_logo_stays_editable_after_verification():
    """It is how a brand is recognised, not evidence of who it is — a rebrand
    must not need a support ticket."""
    src = component("pages", "BrandOnboarding.jsx")
    block = src[src.index("<ImageUploadField"):src.index("<ImageUploadField") + 1200]

    assert "fieldsLocked" not in block


def test_the_upload_limits_are_read_from_the_profile():
    src = component("pages", "BrandOnboarding.jsx")

    assert "uploads?.max_image_bytes" in src
    assert "uploads?.accepted_image_mime_types" in src


# --- Nothing shifts ---------------------------------------------------------


def test_the_campaign_card_skeleton_reserves_a_cover():
    """The cover is most of the card's height, so a skeleton without one shifts
    the whole grid when the briefs land."""
    dense = component("components", "data", "DenseView.jsx")

    assert 'aspect-[16/9] w-full rounded-none' in dense
    assert "cover" in component("pages", "Campaigns.jsx")


def test_the_detail_skeleton_reserves_a_cover():
    page = component("components", "data", "PageSkeleton.jsx")

    assert 'aspect-[16/9] w-full max-w-3xl' in page
    assert 'cover />' in component("pages", "CampaignDetail.jsx")


def test_home_reserves_the_space_its_images_will_fill():
    """Home used to carry a grid of live brief cards, measured to 0.0048 CLS,
    and this test checked that grid's skeleton reserved a 16:9 cover. The feed
    moved to /campaigns when home became a router, so what is left to reserve
    is the marketing site's image slots — which do it in the one component
    rather than at each call site.

    `PlaceholderImage` is the reservation: a ratio on the container, never on
    the <img>, so dropping real photography in moves nothing."""
    src = component("pages", "Landing.jsx")
    assert "PlaceholderImage" in src
    assert "CampaignCover" not in src

    slot = component("components", "marketing", "PlaceholderImage.jsx")
    assert "aspect-[16/9]" in slot
    # The ratio is on the container. An <img> that carried it would collapse
    # the box for as long as the file took to arrive.
    assert 'className={`relative overflow-hidden ${' in slot
