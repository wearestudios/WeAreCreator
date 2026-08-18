"""Three small things a brand says about itself.

**The contact role.** `manager_designation` was free text, so the same job
arrived as "mktg", "Mktg." and "marketing head". `CONTACT_ROLE_SUGGESTIONS` is
a **suggestion list, not an enum** — the field stays free text, so every brand
that signed up before this keeps a value that reads as a sentence in the
console and in an export, and "Other" opens a box rather than storing the word
"Other", which tells a reviewer nothing.

**The tagline.** One line, shown on every campaign card the brand posts.
Separate from `about` and short on purpose: a card has room for a clause, and
slicing the first sentence off a paragraph gives you half of one.

**What happens next.** A brand that has just filled in a form and landed on an
empty dashboard has no idea whether anything is happening. The honest answer is
"not until you post a brief, and then not instantly" — much better said than
discovered over three silent days.
"""
import inspect
from pathlib import Path

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


# --- The contact role ---------------------------------------------------------


def test_the_roles_are_the_six_asked_for():
    assert server.CONTACT_ROLE_SUGGESTIONS == (
        "Owner",
        "Marketing Manager",
        "PR",
        "General Manager",
        "Operations",
        "Other",
    )


def test_the_field_is_still_free_text():
    """A list, not an enum. Narrowing it to six would invalidate every value
    typed before today — and there is always a seventh job title."""
    field = server.BrandContactSignup.model_fields["manager_designation"]
    assert field.annotation is not None
    assert "Literal" not in str(field.annotation)

    profile_field = server.BrandProfileUpdate.model_fields["contact_person_designation"]
    assert "Literal" not in str(profile_field.annotation)


def test_the_frontend_list_matches():
    src = read("lib", "contactRoles.js")
    for role in server.CONTACT_ROLE_SUGGESTIONS:
        assert f'"{role}"' in src


def test_other_opens_a_box_rather_than_ending_the_question():
    """Storing the word "Other" tells a reviewer nothing about who is asking
    on the business's behalf, which is the whole point of the field."""
    src = read("pages", "Signup.jsx")
    assert "roleOption === OTHER_ROLE" in src
    assert "signup-manager-role-other" in src


def test_an_unrecognised_stored_value_lands_on_other_with_its_text():
    """Every designation typed before this list existed. Resetting it to blank
    would silently lose it."""
    src = read("lib", "contactRoles.js")
    assert "roleSelectionFor" in src
    assert "option: OTHER_ROLE, custom: text" in src


# --- The tagline --------------------------------------------------------------


def test_the_tagline_is_short_enough_for_a_card():
    """90 characters. `about` is 1500 — that is a paragraph, and a card has
    room for a clause."""
    field = server.BrandProfileUpdate.model_fields["tagline"]
    limits = [m for m in field.metadata if getattr(m, "max_length", None)]
    assert limits and limits[0].max_length == 90


def test_it_rides_on_every_campaign_card():
    src = inspect.getsource(server._serialize_campaign)
    assert '"brand_tagline"' in src


def test_the_card_omits_it_rather_than_drawing_a_blank_line():
    src = read("pages", "Campaigns.jsx")
    assert "c.brand_tagline &&" in src


def test_it_is_public_because_it_was_written_to_be_read():
    assert "tagline" in server._PUBLIC_BRAND_FIELDS
    assert "tagline" not in server.PUBLIC_BRAND_FORBIDDEN_FIELDS


def test_the_share_preview_prefers_it_over_slicing_a_paragraph():
    """It was written to be one line, which is exactly what a meta description
    and a WhatsApp preview are."""
    src = inspect.getsource(server._brand_summary)
    assert src.index('brand.get("tagline")') < src.index('brand.get("about")')


def test_the_public_page_escapes_it_like_everything_else():
    """Brand-supplied text on a public page."""
    src = inspect.getsource(server._brand_page_html)
    assert 'e(brand.get("tagline"))' in src


def test_the_form_counts_the_characters():
    """A 90-character limit that silently truncates is a limit somebody finds
    out about by reading their own card."""
    src = read("pages", "BrandOnboarding.jsx")
    assert "maxLength={90}" in src
    assert "{tagline.length}/90" in src


def test_the_form_re_seeds_it():
    src = read("pages", "BrandOnboarding.jsx")
    assert 'setTagline(data.tagline || "")' in src


# --- What happens next --------------------------------------------------------


def test_the_expectation_copy_is_shown_once_on_the_way_in():
    """Keyed on the navigation state onboarding sets, not on a stored flag —
    so it appears when a brand arrives from the form and never again, and
    there is nothing to reset."""
    dash = read("pages", "Dashboard.jsx")
    view = read("pages", "BrandDashboardView.jsx")

    assert "justOnboarded={justOnboarded}" in dash
    assert "brand-what-happens-next" in view
    assert "justOnboarded &&" in view


def test_it_says_when_to_expect_the_first_applications():
    """The question a brand actually has. "Soon" is not an answer."""
    view = read("pages", "BrandDashboardView.jsx")
    block = view[view.index("brand-what-happens-next") : view.index("profileMissing &&")]

    assert "first applications" in block
    assert "day or two" in block and "first week" in block


def test_it_does_not_promise_what_the_operation_cannot_do():
    """No numbers we cannot stand behind, and nothing that reads as a
    guarantee — this is a two-sided marketplace in one city."""
    view = read("pages", "BrandDashboardView.jsx")
    block = view[view.index("brand-what-happens-next") : view.index("profileMissing &&")]

    for overclaim in ("guarantee", "guaranteed", "instantly", "every city", "thousands"):
        assert overclaim not in block.lower()
