"""Who runs a campaign, and where its applications go.

Before this, every new application went to the brand's manager — whether or
not the brand had asked us to run the campaign. There was no field saying who
executed one, so there was nothing to route on: a brand that handed a campaign
over still got paged for every applicant, and no WeAre manager was told at all.

`execution_owner` is that field. The rules it has to keep:

  * It never disagrees with `manager_id`. A WeAre manager on a campaign means
    we run it; a campaign we run does not carry the brand's person as its
    manager. Two fields that can contradict each other will.
  * A campaign we have taken on but not yet staffed still reaches somebody —
    otherwise handing execution to us is the one arrangement where an
    application lands nowhere.
  * Reading it never returns None. Every surface has to say one of two words.
"""
import inspect
import re
from pathlib import Path

import pytest
from fastapi import HTTPException

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def campaign(**kw):
    base = {"status": "draft", "brand_id": "b", "_id": "c"}
    base.update(kw)
    return base


# --- Reading it -------------------------------------------------------------


@pytest.mark.parametrize("owner", server.EXECUTION_OWNERS)
def test_it_reads_back_what_was_stored(owner):
    assert server._execution_owner(campaign(execution_owner=owner)) == owner


def test_a_campaign_written_before_the_field_is_brand_run():
    """Campaigns predate this. They were brand briefs unless an admin had put
    one of our managers on them, which the startup backfill looks for."""
    assert server._execution_owner(campaign()) == "brand"
    assert server._execution_owner({}) == "brand"
    assert server._execution_owner(None) == "brand"


def test_an_unrecognised_value_reads_as_brand_rather_than_travelling_as_is():
    """A badge has to print one of two words. Passing junk through would put it
    on screen."""
    assert server._execution_owner(campaign(execution_owner="partner")) == "brand"


def test_weare_runs_is_the_same_answer():
    assert server._weare_runs(campaign(execution_owner="weare")) is True
    assert server._weare_runs(campaign(execution_owner="brand")) is False


# --- Filtering --------------------------------------------------------------


def test_filtering_for_brand_matches_documents_with_no_field():
    """`{"execution_owner": "brand"}` would miss every pre-field campaign. The
    backfill fills them in, but a filter that only works after a migration has
    run is one that silently returns nothing on a box that has not restarted."""
    query = server._execution_owner_query("brand")

    assert query == {"execution_owner": {"$ne": "weare"}}


def test_filtering_for_weare_is_an_equality_test():
    assert server._execution_owner_query("weare") == {"execution_owner": "weare"}


@pytest.mark.parametrize("fn", [server.list_all_campaigns, server.list_brand_campaigns])
def test_both_campaign_lists_take_the_filter(fn):
    assert "execution_owner" in inspect.signature(fn).parameters


@pytest.mark.parametrize("fn", [server.list_all_campaigns, server.list_brand_campaigns])
def test_both_lists_refuse_a_value_that_is_not_an_owner(fn):
    source = inspect.getsource(fn)

    assert "EXECUTION_OWNERS" in source
    assert "422" in source


# --- Routing ----------------------------------------------------------------


def test_a_brand_run_campaign_notifies_the_brand_manager():
    source = inspect.getsource(server._create_application)
    branch = source[source.index("if _weare_runs(campaign):") :]
    _, brand_branch = branch.split("else:", 1)

    assert "notify_brand_manager" in brand_branch


def test_a_weare_run_campaign_notifies_the_weare_team():
    source = inspect.getsource(server._create_application)
    weare_branch = source[source.index("if _weare_runs(campaign):") : source.index("    else:")]

    assert "notify_weare_team" in weare_branch
    assert "notify_brand_manager(" not in weare_branch, "the brand is not the one actioning it"


def test_the_brand_is_not_told_about_a_raw_application_on_our_campaign():
    """**This reverses an earlier rule**, on purpose.

    The brand used to be copied in on every application to a campaign it had
    handed us — "not the one actioning it is different from not being told".
    That was wrong about what handing a campaign over means: the brand watched
    thirty unchecked pitches arrive and was paged about each. Shortlisting is
    the job they asked us to do, and a notification about a raw application is
    that job leaking back to them in a different envelope.
    """
    source = inspect.getsource(server._create_application)
    weare_branch = source[source.index("if _weare_runs(campaign):") : source.index("    else:")]

    assert "_tell_brand_manager_unless_managed" not in weare_branch
    assert "notify_brand_manager" not in weare_branch


def test_the_brand_hears_when_there_is_a_shortlisted_creator_and_a_number():
    """And that is the moment it hears — both fee routes reach it, so which of
    the two settled the number cannot change whether the brand finds out."""
    helper = inspect.getsource(server._tell_brand_about_shortlist)
    assert "_weare_runs" in helper, "it must stay silent on a brand-run brief"
    assert "notify_brand_manager" in helper

    for fn in (server.brand_record_agreed_amount, server.advance_collaboration):
        assert "_tell_brand_about_shortlist" in inspect.getsource(fn), (
            f"{fn.__name__} agrees a fee without telling the brand"
        )


def test_an_unstaffed_weare_campaign_still_reaches_an_admin():
    """`notify_campaign_manager` is silent with nobody assigned, so on its own
    it would drop the application entirely."""
    source = inspect.getsource(server.notify_weare_team)

    assert 'distinct("_id", {"role": "admin"})' in source
    assert "notify_campaign_manager" in source


# --- The two fields cannot contradict ---------------------------------------


def test_assigning_a_weare_manager_makes_the_campaign_ours():
    """There is no such thing as one of our managers running a campaign the
    console still calls brand-run."""
    source = inspect.getsource(server.assign_campaign_manager)

    assert '"execution_owner": "weare"' in source


def test_a_weare_campaign_is_created_with_no_brand_manager_on_it():
    """Stamping the brand's person would route applications straight back to
    the brand that asked us to take it on."""
    source = inspect.getsource(server.create_brand_campaign)

    assert "_NO_CAMPAIGN_MANAGER" in source
    assert 'resolved_execution_owner == "weare"' in source


def test_the_blank_manager_covers_every_field_the_real_one_writes():
    """A half-blanked manager leaves a stale name beside a null id."""
    import asyncio

    real = asyncio.run(_manager_contact_keys())

    assert set(server._NO_CAMPAIGN_MANAGER) == real
    assert set(server._NO_CAMPAIGN_MANAGER.values()) == {None}


async def _manager_contact_keys():
    return set(
        re.findall(r'^\s+"(\w+)":', inspect.getsource(server._brand_manager_contact), re.M)
    )


def test_changing_the_owner_moves_the_manager_with_it():
    import asyncio

    blanked = asyncio.run(server._execution_manager_fields(campaign(), "weare"))

    assert blanked == server._NO_CAMPAIGN_MANAGER


# --- A brand may not change it at all ----------------------------------------
#
# This used to be a *window*: a brand could hand a campaign over, or take one
# back, while the brief was still a draft or in review, and
# `_refuse_late_execution_handover` closed the window once it went live. Every
# brand-posted brief is WeAre-run now, so there is no choice to make at any
# status, and that guard is gone rather than left in front of inputs that can
# no longer reach it.


@pytest.mark.parametrize("status", ["draft", server.CAMPAIGN_REVIEW_STATUS, "open", "paused"])
def test_a_brand_may_not_change_who_runs_it_at_any_status(status):
    """Including a draft, which is where the old rule allowed it."""
    with pytest.raises(HTTPException) as err:
        server._refuse_brand_execution_choice(
            campaign(status=status, execution_owner="weare"),
            {"execution_owner": "brand"},
        )

    assert err.value.status_code == 409
    assert err.value.detail["code"] == "managed_by_weare"
    # The refusal is the offer, not a rule quoted back: a brand reading this
    # should hear what it is getting rather than what it may not do.
    assert "runs every campaign" in err.value.detail["message"]


def test_resending_the_same_owner_is_not_a_change():
    """A form that round-trips every field must not trip the guard."""
    server._refuse_brand_execution_choice(
        campaign(status="open", execution_owner="weare"),
        {"execution_owner": "weare"},
    )  # does not raise


def test_an_edit_that_never_mentions_it_is_not_a_change():
    server._refuse_brand_execution_choice(
        campaign(status="open", execution_owner="weare"), {"title": "New title"}
    )  # does not raise


def test_the_guard_is_wired_into_the_brand_edit():
    """The update loop copies the payload generically, so an unguarded
    execution_owner would ride along with everything else — the same shape of
    hole `compensation_type` had."""
    source = inspect.getsource(server.update_brand_campaign)

    assert "_refuse_brand_execution_choice" in source
    assert "_execution_manager_fields" in source


def test_the_admin_route_is_not_subject_to_the_guard():
    """An admin moving a campaign is a conversation that has happened, and is
    the only way a campaign becomes brand-executed at all."""
    source = inspect.getsource(server.admin_update_campaign)

    assert "_refuse_brand_execution_choice" not in source


def test_the_dead_guard_is_actually_gone():
    """Not merely unused — removed. A guard nothing can reach is the shape
    this codebase keeps finding bugs in, so leaving it beside a live one to
    'document the old rule' is the thing not to do."""
    assert not hasattr(server, "_refuse_late_execution_handover")


# --- Every view is told ------------------------------------------------------


@pytest.mark.parametrize(
    "fn", [server._serialize_brand_campaign, server._serialize_campaign]
)
def test_the_campaign_serializers_carry_it(fn):
    assert "_execution_owner" in inspect.getsource(fn)


def test_the_creator_serializer_carries_it_without_any_contact_detail():
    """A creator is told which of us runs it, not how to ring them."""
    source = inspect.getsource(server._serialize_campaign)

    assert '"execution_owner": _execution_owner(doc)' in source
    assert "manager_phone" not in source


def test_it_is_read_through_the_reader_everywhere_it_is_emitted():
    """A bare `.get("execution_owner")` would emit None for a pre-field
    campaign, which is the one value no surface can render.

    Query operators are skipped — `{"$exists": False}` in the backfill and
    `{"$ne": "weare"}` in the filter are asking about the field, not sending
    it. Same exclusion the compensation-type invariant makes.
    """
    source = Path(server.__file__).read_text()
    allowed = {
        "_execution_owner(doc)",
        "_execution_owner(d)",
        "_execution_owner(c)",
        "_execution_owner(campaign)",
        "payload.execution_owner",
        # The brand's create path, where a launch or a brief above the
        # threshold is forced to `weare` before anything is written. Named
        # rather than allowing a bare `execution_owner`, so the allow-list
        # still says *which* expression may be stored — see
        # `_weare_run_reason`.
        "resolved_execution_owner",
        '"weare"',
        # The backfill's `$set`, which writes the literal default rather than
        # reading it — that is what a backfill is for.
        "DEFAULT_EXECUTION_OWNER",
        "None",
    }
    for value in re.findall(r'"execution_owner":\s*(.+)', source):
        # A single-line query dict closes on the same line, so strip the brace
        # before comparing — `{"execution_owner": "weare"}` is a filter.
        value = value.strip().rstrip(",").rstrip("}")
        if value.startswith("{"):
            continue  # a query, not a response
        assert value in allowed, f"emitted through {value!r} rather than the reader"


# --- The frontend agrees ------------------------------------------------------


def test_the_frontend_knows_the_same_two_owners():
    source = (FRONTEND / "lib" / "execution.js").read_text()
    owners = set(re.findall(r'"(brand|weare)"', source))

    assert owners == set(server.EXECUTION_OWNERS)


def test_the_frontend_defaults_the_same_way():
    source = (FRONTEND / "lib" / "execution.js").read_text()

    assert f'DEFAULT_EXECUTION_OWNER = "{server.DEFAULT_EXECUTION_OWNER}"' in source


def test_the_post_form_offers_no_choice_and_sends_no_value():
    """**There is nothing left to pick.**

    This test used to assert the opposite: that the form showed the two
    options and posted what was chosen. Every brand-posted brief is WeAre-run
    now, so a picker would be a choice the server is about to override — and
    posting the field would be noise on create and a 409 on edit.

    What survives is the shape: the form shows the *reason* where there is a
    specific one (a launch, a large brief) and the general offer otherwise."""
    source = (FRONTEND / "pages" / "PostCampaign.jsx").read_text()

    assert "EXECUTION_OPTIONS" not in source
    assert "execution_owner:" not in source
    assert "weareRun ? weareRun.line" in source


def test_the_creator_is_shown_who_runs_it():
    """Requirement in its own right: a creator should know before applying
    whether they will be dealing with us or the brand."""
    for page in ("Campaigns.jsx", "CampaignDetail.jsx"):
        source = (FRONTEND / "pages" / page).read_text()
        assert "ExecutionBadge" in source, f"{page} does not show it"
        assert 'audience="creator"' in source, f"{page} uses the wrong wording"


def test_both_lists_can_filter_on_it():
    admin = (FRONTEND / "components" / "admin" / "AdminCampaigns.jsx").read_text()
    brand = (FRONTEND / "pages" / "BrandDashboardView.jsx").read_text()

    assert "execution_owner: execution" in admin, "admin list does not send the filter"
    assert "EXECUTION_FILTERS" in brand, "brand list has no filter"


def test_the_admin_filter_refetches_when_it_changes():
    """A filter left out of the dependency array is a filter that does
    nothing — caught by the linter once, worth keeping caught."""
    source = (FRONTEND / "components" / "admin" / "AdminCampaigns.jsx").read_text()
    # The list's fetch, whatever the surrounding state is called this month —
    # naming the whole array pinned the console's variable names rather than
    # the rule, and broke on a rename that changed nothing about the rule.
    load = source[source.index("const load = useCallback("):]
    deps = re.search(r"\}, \[([^\]]*)\]\);", load)

    assert deps, "AdminCampaigns has no load callback with a dependency array"
    assert "execution" in deps.group(1), deps.group(1)
