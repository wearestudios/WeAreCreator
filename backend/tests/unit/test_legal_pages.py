"""/terms and /privacy, and the footer that is the only way to reach them.

Signup writes `terms_accepted_at` and `terms_version` against the account, so
these two pages are the thing a consent record points at. That makes them the
one place in the product where being *out of date* is worse than being absent:
a placeholder is obviously a placeholder, while a paragraph describing a data
flow we removed six months ago is read and believed.

That is not hypothetical. This page said, months after it stopped being true,
that a brand received a creator's contact details once it accepted them —
which is the single strongest privacy promise the product now makes, described
backwards. So the tests below are mostly of one shape: **for each class of
data the product really handles, does the privacy page say so.** They read the
backend for what is collected and the page for whether it is named, rather
than checking the copy against a list somebody typed here, which would drift in
exactly the same way.

They deliberately do **not** check the copy for legal adequacy. Nobody here can
do that, and pretending otherwise by asserting the presence of legal-sounding
phrases would be the failure mode the file header calls out. What needs a
lawyer is listed in a comment block in the page itself, and one test below
checks that block still exists — because deleting it is how "we know this needs
review" quietly becomes "this looks finished".
"""
import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


LEGAL = read("src", "pages", "Legal.jsx")


def _body(name):
    """The copy of one page, without the shared shell or the comments.

    Split on the two exported components, and strip `//` comment lines: a test
    that fails because an explanatory comment happens to contain the word it
    bans is a test that teaches people to stop writing comments.
    """
    start = LEGAL.index(f"export function {name}(")
    rest = LEGAL[start:]
    end = rest.find("\nexport function ", 1)
    chunk = rest if end < 0 else rest[:end]
    return "\n".join(
        line for line in chunk.splitlines() if not line.lstrip().startswith("//")
    )


TERMS = _body("Terms")
PRIVACY = _body("Privacy")


def says(text, *phrases):
    """True when the copy mentions all of these, ignoring case and JSX breaks.

    The pages are JSX, so a sentence is routinely broken across lines by the
    formatter and a phrase spanning that break is not findable as written.
    Whitespace is collapsed before matching, and `{" "}` — prettier's way of
    keeping a space next to a tag — collapses with it.
    """
    flat = re.sub(r"\s+", " ", text.replace('{" "}', " "))
    return all(p.lower() in flat.lower() for p in phrases)


# --- What we actually collect -------------------------------------------------
#
# The instruction was to confirm the pages describe what we really collect:
# phone numbers, addresses with map coordinates, identity and business
# documents, Instagram data from connected accounts, and payment records.


def test_the_privacy_page_names_the_phone_number():
    """It is the login, so every account has one whether or not it filled in
    anything else — which makes it the one field that cannot be described as
    optional detail."""
    assert says(PRIVACY, "WhatsApp number")


def test_the_privacy_page_names_the_address_and_the_pin_separately():
    """`full_address` and `location_lat`/`location_lng` are two different
    things — a label to post to, and a coordinate on a front door. Describing
    only "your address" would understate the second, which is the one precise
    enough to identify a home."""
    assert says(PRIVACY, "delivery address")
    assert says(PRIVACY, "map coordinates")


def test_the_privacy_page_names_the_business_documents_and_what_is_in_them():
    """These are the highest-sensitivity files the product holds: they carry
    directors' names and registered addresses, which is why they live outside
    the statically-served upload directory."""
    assert says(PRIVACY, "GST certificate")
    assert says(PRIVACY, "FSSAI")
    assert says(PRIVACY, "never served publicly")


def test_the_privacy_page_describes_instagram_as_read_only_and_official():
    """Two claims worth pinning, because both are architectural promises the
    codebase enforces elsewhere: the scopes are read-only, and the token is
    encrypted at rest in a collection of its own."""
    assert says(PRIVACY, "Instagram", "official API")
    assert says(PRIVACY, "encrypted")
    assert says(PRIVACY, "never post or change anything")


def test_the_privacy_page_names_the_payout_fields_it_really_asks_for():
    """`payout_ready` is UPI plus PAN, and PAN is there because tax is
    deducted at source. Saying "payment details" would leave somebody
    surprised at the point a PAN is demanded."""
    assert says(PRIVACY, "UPI")
    assert says(PRIVACY, "PAN")


def test_the_privacy_page_covers_the_records_a_collaboration_leaves():
    """The collaboration is where most of the data actually accrues — and the
    draft is the newest and least obvious of it, because it is content that is
    not public yet."""
    for phrase in ("application", "agreed fee", "checked in", "draft", "payment record"):
        assert says(PRIVACY, phrase), phrase


@pytest.mark.parametrize(
    "field",
    ["profile photo", "city", "niches", "GSTIN"],
)
def test_the_privacy_page_names_the_rest_of_the_creator_profile(field):
    assert says(PRIVACY, field)


# --- The promise the product actually makes -----------------------------------


def test_the_privacy_page_states_the_brand_contact_rule():
    """`_brand_visible_creator` is an allow-list and every one of these is off
    it. This is the strongest privacy promise the product makes, and it is the
    one this page previously described backwards."""
    assert says(
        PRIVACY,
        "A brand never receives your phone number, WhatsApp number, email or full address",
    )


def test_the_privacy_page_says_the_rule_changed():
    """Somebody who read this page a year ago acted on the old answer. Silently
    correcting it leaves them believing a brand has their number."""
    assert says(PRIVACY, "used to be different")


def test_the_privacy_page_keeps_the_map_pin_off_the_brand_surface():
    """`location_lat`/`location_lng` are named in BRAND_FORBIDDEN_CREATOR_FIELDS
    for the reason this sentence gives."""
    assert says(PRIVACY, "map pin", "never shown to a brand")


def test_the_privacy_page_explains_why_staff_do_see_the_number():
    """The manager's roster and daysheet carry phone numbers by design. Claiming
    nobody sees them would be the mirror-image inaccuracy of the one we just
    fixed."""
    assert says(PRIVACY, "WeAre team running a shoot does see your number")


def test_document_access_is_described_as_logged():
    """`GET /admin/brands/{id}/documents/{id}` audits every read. A brand
    handing over its registration papers is owed that fact."""
    assert says(PRIVACY, "every time one is opened it is logged")


# --- Terms: the flow as it is now ---------------------------------------------


def test_the_terms_describe_the_draft_gate():
    """The draft stage changed *when content becomes public*, which is most of
    what a creator is agreeing to. Terms written before it describe a product
    where the brand's first sight of the work is after the followers'."""
    assert says(TERMS, "draft")
    assert says(TERMS, "before publishing")
    assert says(TERMS, "asks for changes")


def test_the_terms_say_a_draft_is_held_privately():
    """It is the one thing here that must not be one guessed URL away from the
    internet, and the only page that tells the creator so."""
    assert says(TERMS, "held privately")


def test_the_terms_put_the_fee_before_the_shoot():
    """The positioning across the whole site is "the rate is agreed in writing
    before anyone shoots". If the terms did not say it, the marketing pages
    would be the only place it appeared."""
    assert says(TERMS, "agreed in writing before anyone shoots")


def test_the_terms_say_the_creator_keeps_the_whole_fee():
    """The fee sits on the brand. Every audience page says so, and this is the
    document that makes it a term rather than a claim."""
    assert says(TERMS, "100% of the fee")
    assert says(TERMS, "charged to the brand on top")


def test_the_terms_do_not_imply_a_cut_of_the_creators_rate():
    for phrase in ("commission", "deducted from your", "we take", "our cut"):
        assert phrase not in TERMS.lower(), phrase


def test_the_terms_say_joining_is_free():
    assert says(TERMS, "free")


def test_the_terms_name_barter_rather_than_promising_money_always():
    """A barter brief pays nothing and says so on its face. Terms that
    described every collaboration as paid would be contradicted by the first
    barter brief somebody opened."""
    assert says(TERMS, "barter")


def test_the_terms_describe_who_runs_a_campaign():
    """`execution_owner` decides who answers a creator's questions and who
    reviews their draft. From the creator's side that is not an implementation
    detail — it is who they are dealing with."""
    assert says(TERMS, "run by the brand", "WeAre Studios")


def test_the_terms_mention_invite_only_briefs():
    assert says(TERMS, "invite-only")


def test_the_terms_state_the_slot_cancellation_window():
    """24 hours is enforced in `release_slot`; a creator finding that out from
    a 409 is a term they were never told."""
    assert says(TERMS, "24 hours")


def test_the_terms_describe_re_review_after_a_material_edit():
    """`MATERIAL_PROFILE_FIELDS` puts a verified creator back in a queue for
    changing their handle or payout details, which is surprising unless
    somebody said so first — and the surprise lands at the moment they try to
    apply."""
    assert says(TERMS, "material change")
    assert says(TERMS, "Work already accepted carries on")


def test_the_terms_say_the_creator_keeps_ownership_despite_the_draft_step():
    """Sending an unpublished file to a reviewer is exactly the moment somebody
    wonders whether they just handed over the rights to it."""
    assert says(TERMS, "keep ownership")
    assert says(TERMS, "Sending a draft for review does not change that")


def test_the_terms_disclose_that_performance_is_measured_and_reported():
    """`content_performance` reads the reach and engagement of a published post
    and the campaign report hands it to the brand. It is collected data, and it
    was described nowhere."""
    assert says(TERMS, "how published content performed")


# --- Words this codebase does not use -----------------------------------------


@pytest.mark.parametrize("word", ["vets", "vetted", "vetting", "approved creator"])
def test_neither_page_reintroduces_the_old_vocabulary(word):
    """"Vetted" and "approved" are the two words this concept was called before
    it settled on `verification_status`. The mismatch once hid every approved
    creator from every brand, which is why the rule is never to write them
    again — including in copy, where a future rename is likeliest to start."""
    combined = f"{TERMS}\n{PRIVACY}".lower()
    assert word not in combined


# --- What we are not pretending to have done ----------------------------------


def test_the_page_still_says_it_is_not_the_legal_document():
    """The copy is a plain-English description of what the product does. It
    reads confidently because it is accurate, and confidence is exactly what
    would let somebody mistake it for reviewed legal text."""
    # Flattened, because the sentence lives in a block comment and the
    # formatter breaks it across lines behind a ` * ` gutter.
    flat = re.sub(r"\s+\*?\s*", " ", LEGAL)
    assert "has not been reviewed by a lawyer" in flat
    assert 'data-testid="legal-draft-notice"' in LEGAL


def test_the_open_legal_questions_are_still_written_down():
    """These were flagged rather than answered, on instruction. The failure
    this guards is not a wrong answer — it is the block being tidied away, at
    which point a page that needs review looks finished."""
    assert "NEEDS A LAWYER" in LEGAL
    for topic in ("DPDP", "Retention", "Location coordinates", "licensing", "Meta"):
        assert topic in LEGAL, topic


def test_the_terms_version_is_something_to_bump():
    """Consent is recorded against `terms_version`, so the pages and the stamp
    have to be able to move together."""
    assert "TERMS_VERSION" in LEGAL
    assert server.TERMS_VERSION


# --- Reaching them ------------------------------------------------------------


def test_the_footer_links_to_both_pages():
    """Before the footer, the only route to either was to know the URL — and a
    consent checkbox pointing at pages nothing links to is a consent record
    that is hard to defend."""
    nav = read("src", "lib", "siteNav.js")
    assert '"/terms"' in nav
    assert '"/privacy"' in nav


# Landing moved to `MarketingFooter` — the marketing variant — when the
# marketing site got its own chrome. It still carries a footer; it is not this
# one. `test_marketing_pages.py` covers it there.
@pytest.mark.parametrize(
    "page",
    ["Legal.jsx", "Campaigns.jsx", "CampaignDetail.jsx"],
)
def test_the_public_pages_carry_the_footer(page):
    """Every page a signed-out person can land on. Deliberately not the admin
    console, the manager screens or the dashboards: those are dense working
    surfaces under a sticky header, and a marketing footer beneath a data table
    is noise rather than navigation. The OTP screens are the other exception —
    they are one focused task, and `Signup` already links both documents
    inline, at the moment consent is actually recorded."""
    src = read("src", "pages", page)
    assert "components/Footer" in src
    assert "<Footer />" in src


def test_the_marketing_pages_carry_the_marketing_footer():
    """Same links, same terms and privacy — a different renderer, so the
    shared one could stay untouched for the authenticated surfaces."""
    src = read("src", "pages", "Landing.jsx")
    assert "MarketingFooter" in src
    nav = read("src", "lib", "siteNav.js")
    assert '"/terms"' in nav and '"/privacy"' in nav


def test_signup_still_links_the_documents_where_consent_is_taken():
    src = read("src", "pages", "Signup.jsx")
    assert 'to="/terms"' in src
    assert 'to="/privacy"' in src
