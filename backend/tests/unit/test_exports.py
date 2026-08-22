"""Where creator contact details are allowed, and where they never are.

The rule has two halves and they pull in opposite directions:

  - an **admin** export is an internal document. A payout row without a phone
    number to chase is useless to whoever is reconciling a bank statement, so
    contact details belong there.
  - anything **brand-facing** must not carry them at any state, in any payload,
    in any export — including the campaign report, which is the artefact most
    likely to be forwarded on to somebody we have never met.

The interesting tests here walk the **real output** of the brand-facing
builders, with deliberately recognisable contact values planted in the input.
Reading the source for a forbidden key name only catches the mistake somebody
makes on purpose; running the builder catches the one where a field arrives via
a `**spread` from a document nobody remembered had a phone number on it.
"""
import asyncio
import inspect
import json

import pytest

import server


# Planted values, chosen to be unmistakable in a haystack of real-looking data.
PHONE = "+919876500001"
EMAIL = "creator.private@example.com"
ADDRESS = "42 Private Lane, Indiranagar"
UPI = "creator@upi"
PAN = "ABCDE1234F"

SECRETS = (PHONE, EMAIL, ADDRESS, UPI, PAN)


def _profile(**over):
    return {
        "_id": "p1",
        "user_id": "u1",
        "name": "Ana K",
        "instagram_handle": "anak",
        "follower_count": 42000,
        "city": "Bengaluru",
        "niches": ["fnb"],
        "genres": [],
        "platforms": ["instagram"],
        "base_rate": 8000,
        "verification_status": "verified",
        # Every one of these must stay out of a brand response.
        "phone": PHONE,
        "email": EMAIL,
        "full_address": ADDRESS,
        "address": ADDRESS,
        "payout_upi": UPI,
        "pan": PAN,
        "gstin": "29ABCDE1234F1Z5",
        **over,
    }


def _leaks(blob) -> list:
    """Any planted secret appearing anywhere in a structure, at any depth."""
    text = json.dumps(blob, default=str)
    return [s for s in SECRETS if s in text]


class TestTheBrandFacingLine:
    def test_the_creator_projection_emits_no_contact_details(self):
        out = server._brand_visible_creator(
            _profile(), {"_id": "u1", "phone": PHONE, "email": EMAIL}
        )
        assert _leaks(out) == [], f"brand-visible creator leaked {_leaks(out)}"

    def test_it_omits_the_keys_rather_than_nulling_them(self):
        # A `"phone": null` in a response tells a reader the field exists and
        # invites somebody to start populating it.
        out = server._brand_visible_creator(_profile(), {"_id": "u1", "phone": PHONE})
        for field in server.BRAND_FORBIDDEN_CREATOR_FIELDS:
            assert field not in out, f"{field} is present (as {out.get(field)!r})"

    def test_the_forbidden_list_covers_everything_we_plant(self):
        # If somebody adds a new contact field to profiles, this is the test
        # that should be updated alongside it — so it is written to fail loudly
        # rather than to quietly cover less than it claims.
        assert set(server.BRAND_FORBIDDEN_CREATOR_FIELDS) >= {
            "phone", "email", "full_address", "address", "payout_upi", "pan", "gstin",
        }

    def test_the_campaign_report_builder_names_no_contact_field(self):
        src = inspect.getsource(server._build_campaign_report)
        for forbidden in server.BRAND_FORBIDDEN_CREATOR_FIELDS:
            assert f'"{forbidden}"' not in src, f"the report reads {forbidden}"

    def test_the_report_renderers_cannot_print_what_they_are_not_given(self):
        """Belt and braces on the two renderers.

        The builder is the gate, but the renderers are what a person reads. If
        one of them ever reached back into a profile for "just the phone
        number", this is what would catch it.
        """
        for fn in (server._report_csv, server._report_html):
            src = inspect.getsource(fn)
            for forbidden in ("phone", "payout_upi", "pan", "gstin", "full_address"):
                # The quoted key, not the bare word: "pan" is a substring of
                # "span", and a checker that cannot tell those apart fails on
                # correct code and teaches people to weaken it.
                for form in (f"'{forbidden}'", f'"{forbidden}"'):
                    assert form not in src, f"{fn.__name__} reads {form}"

    def test_a_rendered_report_carries_no_planted_secret(self):
        """The end-to-end version: build a report row by hand carrying every
        secret, render both formats, and search the bytes."""
        report = {
            "campaign": {
                "id": "1", "title": "Brunch", "brand_name": "Blue Tokai",
                "category": "fnb", "area": "Indiranagar", "status": "completed",
                "compensation_type": "fixed", "campaign_type": "personal_table",
                "event_date": None, "start_date": None, "end_date": None,
                "deliverables": "1 reel", "showcase": False,
            },
            # A row shaped as the builder emits it. If the builder ever starts
            # including contact keys, they would land here and show up below.
            "creators": [
                {
                    "creator_name": "Ana K", "instagram_handle": "anak",
                    "follower_count": 42000, "content_urls": [],
                    "reach": 100, "impressions": None, "views": None,
                    "likes": 1, "comments": None, "saves": None,
                    "engagements": 1, "engagement_rate": 1.0,
                    "measured": True, "measurement_source": "manual",
                }
            ],
            "totals": server._rollup_performance([], set(), 0.0),
            "generated_at": "2026-08-16T00:00:00+00:00",
        }
        csv_out = server._report_csv(report)
        html_out = server._report_html(report)
        for blob, name in ((csv_out, "csv"), (html_out, "html")):
            found = [s for s in SECRETS if s in blob]
            assert not found, f"the {name} report leaked {found}"


class TestAdminExportsMayCarryContact:
    """The other half of the rule. Admin exports are internal documents."""

    def test_the_payments_export_has_what_accounting_needs(self):
        # If somebody has to come back and ask "which campaign was this?", the
        # export has failed at the one job it has.
        src = inspect.getsource(server._export_payments)
        for column in (
            "Campaign", "Brand", "Creator", "Agreed amount", "Platform fee",
            "Creator payout", "Brand invoice amount", "Invoice state",
            "Raised", "Paid",
        ):
            assert f'"{column}"' in src, f"payments export is missing {column}"

    def test_the_payments_export_can_reach_the_creator(self):
        src = inspect.getsource(server._export_payments)
        assert '"Phone"' in src and '"UPI"' in src

    def test_the_exports_that_carry_contact_are_named(self):
        # So "which files have phone numbers in them" is answerable without
        # reading six builders — and so the audit line can say.
        assert set(server.EXPORTS_WITH_CONTACT) <= set(server.EXPORT_KINDS)
        assert "campaigns" not in server.EXPORTS_WITH_CONTACT
        assert "audit" not in server.EXPORTS_WITH_CONTACT

    @pytest.mark.parametrize("kind", server.EXPORT_KINDS)
    def test_every_declared_export_has_a_builder(self, kind):
        assert hasattr(server, f"_export_{kind}")

    def test_every_export_is_audited(self):
        """A file of creators' phone numbers leaving the system is exactly the
        event the audit log exists to record."""
        src = inspect.getsource(server.admin_export)
        assert "await audit(" in src
        assert 'f"export.{kind}"' in src
        assert '"includes_contact_details"' in src

    def test_exports_are_console_only_and_scoped(self):
        """WeAre's own staff export their brands' work; the narrowing is passed
        into the builder rather than applied to the rows afterwards."""
        src = inspect.getsource(server.admin_export)
        assert "require_roles(*CONSOLE_ROLES)" in src
        assert "brand_scope=_console_brand_ids(user)" in src

    def test_the_platform_wide_exports_stay_with_admin(self):
        """**Two of the six cannot be narrowed without becoming a different
        document.** The creator roster is the global directory in CSV form and
        the audit log is the whole platform's history — neither is a brand's
        work, so neither is a scoped role's to download."""
        assert set(server.ADMIN_ONLY_EXPORTS) == {"creators", "audit"}
        src = inspect.getsource(server.admin_export)
        assert "kind in ADMIN_ONLY_EXPORTS and not is_all_access(user)" in src

    def test_exports_are_not_cached(self):
        # They carry phone numbers and payout figures.
        assert '"Cache-Control": "no-store"' in inspect.getsource(server._csv_response)

    def test_an_unknown_export_is_refused_rather_than_resolved(self):
        """`kind` selects a function by name. Without the allow-list, a crafted
        value would reach `globals()` and call something that is not an
        export."""
        src = inspect.getsource(server.admin_export)
        assert "if kind not in EXPORT_KINDS" in src
        # And the refusal comes before the lookup, not after.
        assert src.index("EXPORT_KINDS") < src.index("globals()")

    def test_csv_goes_through_the_csv_module(self):
        # A business name with a comma would otherwise shift every column.
        assert "csv.writer" in inspect.getsource(server._csv_response)


class TestTheCsvFramingIsSafe:
    def test_commas_quotes_and_newlines_survive(self):
        resp = server._csv_response(
            [['Weekend "brunch", reel', "line one\nline two", 42]],
            ["Title", "Note", "N"],
            "t.csv",
        )
        body = resp.body.decode()
        import csv as _csv
        import io as _io

        rows = list(_csv.reader(_io.StringIO(body)))
        assert rows[0] == ["Title", "Note", "N"]
        # Three cells, not five — which is what naive comma-joining would give.
        assert len(rows[1]) == 3
        assert rows[1][0] == 'Weekend "brunch", reel'
        assert rows[1][1] == "line one\nline two"



def _health_with_one_of_everything():
    """Run the real health endpoint against a database holding one of each
    problem it looks for, and return what it produced.

    Seeded rather than mocked, because the rule being tested is about the rows
    the handler actually builds — and the previous source-reading version of
    this test passed while a row went out with no link, which is the failure it
    existed to catch.
    """
    from datetime import datetime, timedelta, timezone

    from bson import ObjectId
    from mongomock_motor import AsyncMongoMockClient

    now = datetime.now(timezone.utc)
    long_ago = now - timedelta(days=45)

    async def go():
        db = AsyncMongoMockClient()["health"]
        original = server.db
        server.db = db
        try:
            brand_id, creator_id = ObjectId(), ObjectId()
            soon = now + timedelta(days=2)
            campaign_id = (
                await db.campaigns.insert_one(
                    {
                        "brand_id": brand_id,
                        "title": "Toit tasting",
                        "status": "open",
                        # Deliberately far more than the four collaborations
                        # below, or the campaign is fully booked and the
                        # underfilling check produces no rows to check.
                        "creators_needed": 12,
                        "event_date": soon,
                        "state_since": long_ago,
                    }
                )
            ).inserted_id
            await db.campaigns.insert_one(
                {
                    "brand_id": brand_id,
                    "title": "Waiting on us",
                    "status": server.CAMPAIGN_REVIEW_STATUS,
                    "submitted_for_review_at": long_ago,
                }
            )
            await db.campaigns.insert_one(
                {
                    "brand_id": brand_id,
                    "title": "Forgotten draft",
                    "status": "draft",
                    "updated_at": long_ago,
                }
            )
            await db.brand_profiles.insert_one(
                {
                    "user_id": brand_id,
                    "business_name": "Toit",
                    "verified": False,
                    "verification_state": "pending_verification",
                    "submitted_for_verification_at": long_ago,
                }
            )
            await db.creator_profiles.insert_one(
                {
                    "user_id": creator_id,
                    "name": "Aditi Rao",
                    "verification_status": "pending",
                    "submitted_for_review_at": long_ago,
                    "updated_at": long_ago,
                    "created_at": long_ago,
                }
            )
            for state in ("applied", "accepted", "attended", "draft_submitted", "content_approved"):
                await db.collaborations.insert_one(
                    {
                        "campaign_id": campaign_id,
                        "creator_id": creator_id,
                        "state": state,
                        "state_since": long_ago,
                        "updated_at": long_ago,
                        "created_at": long_ago,
                        "content_overdue": state == "attended",
                        "content_overdue_at": long_ago,
                    }
                )
            await db.payments.insert_one(
                {"collaboration_id": ObjectId(), "state": "pending", "created_at": long_ago}
            )
            return await server.admin_health(user={"_id": str(ObjectId()), "role": "admin"})
        finally:
            server.db = original

    return asyncio.run(go())


class TestHealthThresholds:
    def test_every_threshold_is_named(self):
        # Each of these is a judgement about how much slack the operation has,
        # and will be argued about. Arguing about a constant is easier than
        # arguing about a number buried in a query.
        for name in (
            "FILL_WARNING_DAYS", "FILL_WARNING_RATIO", "SLOT_WARNING_DAYS",
            "CONTENT_OVERDUE_DAYS", "PAYMENT_OVERDUE_DAYS",
            "VERIFICATION_OVERDUE_DAYS", "PROFILE_STALE_DAYS",
        ):
            assert isinstance(getattr(server, name), (int, float))

    def test_the_thresholds_travel_with_the_response(self):
        # So the panel can say "under 70% with 7 days to go" from the server's
        # numbers rather than a copy that drifts.
        src = inspect.getsource(server.admin_health)
        assert '"thresholds"' in src
        assert "fill_warning_ratio" in src

    def test_every_health_row_links_to_the_thing_it_is_about(self):
        """A count tells you there is a problem and then makes you go and find
        it. Every row carries an href.

        **Checked per block rather than by counting.** This used to assert
        `src.count('"href":') == src.count('checks.append(')`, which was a
        proxy that stopped working the moment a row carried more than one link
        — the underfill rows now carry three actions beside their own href, and
        the counting version failed on a change that made the panel strictly
        more useful. Splitting on the append and requiring an href inside each
        block tests the rule itself.
        """
        report = _health_with_one_of_everything()
        assert len(report["checks"]) >= 8, "the health panel lost a check"
        seen = 0
        for check in report["checks"]:
            for item in check["items"]:
                seen += 1
                assert item.get("href"), (
                    f"a {check['key']} row names a problem with nowhere to go"
                )
        assert seen, "the fixture stopped producing rows, so this proves nothing"

    def test_the_overdue_check_links_too(self):
        """It is built in its own helper, so the rule above cannot see inside
        it — and it is the check most likely to be the only place a stalled
        record appears."""
        src = inspect.getsource(server._overdue_check)
        assert '"href": href' in src
        assert src.count("href=f\"/admin/") >= 4, "not every kind of record links"

    def test_health_is_admin_only(self):
        assert 'require_roles("admin")' in inspect.getsource(server.admin_health)

    def test_unpaid_money_is_treated_as_the_urgent_one(self):
        # Creators chase us for this, and it is the fastest way to lose one.
        src = inspect.getsource(server.admin_health)
        # The check's own block, from its key to the end of its rows — not a
        # byte window, which silently slides off the block when a neighbour
        # grows.
        start = src.index('"key": "payments_pending"')
        block = src[start : src.index("checks.append(", start)]
        assert '"severity": "critical"' in block


class TestIntelligenceIsHonest:
    def test_empty_weeks_are_still_points(self):
        """A chart that silently skips weeks with nothing in them draws a lie —
        the line keeps going and the gap disappears."""
        src = inspect.getsource(server.admin_intelligence)
        assert "while cursor <= now" in src
        assert "[0] * len(weeks)" in src

    def test_fill_rate_is_none_rather_than_zero_when_nothing_was_due(self):
        # Same rule as the performance module: a week with no campaigns has an
        # unknown fill rate, not a rate of zero.
        src = inspect.getsource(server.admin_intelligence)
        assert "if fill_den[i] else None" in src

    def test_dormant_is_measured_against_a_named_window(self):
        assert server.DORMANT_AFTER_DAYS == 60
        src = inspect.getsource(server.admin_intelligence)
        assert '"window_days": DORMANT_AFTER_DAYS' in src
