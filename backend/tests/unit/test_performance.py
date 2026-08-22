"""Performance reporting, and the arithmetic a brand will check.

These numbers go in front of a client at renewal. The two ways they can be
wrong quietly are barter — which has audience but no cost — and unknown
metrics, which are not zeroes. Both are pinned here.
"""
import pytest

import server


def _rec(collab_id, **kw):
    return {"collaboration_id": collab_id, **kw}


class TestEngagementRate:
    def test_it_is_engagements_over_reach(self):
        # 150 of 10,000 people who saw it did something: 1.5%.
        assert server._engagement_rate_from(
            {"reach": 10000, "likes": 100, "comments": 30, "saves": 20}
        ) == 1.5

    def test_it_sums_only_the_metrics_present(self):
        # A reading off a phone screen often has likes and comments and no
        # saves. Refusing that would mean recording nothing at all.
        assert server._engagements({"likes": 10, "comments": 5}) == 15
        assert server._engagements({"likes": 10, "comments": 5, "saves": None}) == 15

    def test_unknown_is_not_zero(self):
        """The distinction the whole module rests on.

        A post with no saves and a post whose saves we could not read are
        different things. Treating the second as a zero drags every average
        down and makes a campaign look worse than it was.
        """
        assert server._engagements({}) is None
        assert server._engagements({"likes": None}) is None
        # No reach means no denominator, so no rate — not a rate of zero.
        assert server._engagement_rate_from({"likes": 100}) is None
        assert server._engagement_rate_from({"reach": 0, "likes": 100}) is None
        assert server._engagement_rate_from({"reach": 1000}) is None

    def test_a_genuine_zero_is_kept(self):
        # Nobody engaged, and we know that. 0.0, not None.
        assert server._engagement_rate_from({"reach": 500, "likes": 0}) == 0.0

    def test_the_rate_is_derived_not_stored(self):
        """It is recomputed on read, so a record written under an older formula
        still reports the current one — and cannot contradict its own inputs."""
        import inspect

        assert "engagement_rate" not in server.PerformancePayload.model_fields
        assert "_engagement_rate_from(doc)" in inspect.getsource(
            server._serialize_performance
        )

    def test_the_denominator_is_reach_not_followers(self):
        # Against followers, a post that reached nobody looks fine and one that
        # travelled beyond its audience looks bad. The choice is documented in
        # one place so it cannot drift between surfaces.
        import inspect

        src = inspect.getsource(server._engagement_rate_from)
        assert "follower" not in src.split('"""')[2]  # not in the code body
        assert 'doc.get("reach")' in src


class TestBarterIsExcludedFromCost:
    """A barter campaign has reach and engagement and no spend."""

    RECORDS = [
        _rec("paid1", reach=10000, likes=200, comments=50, saves=50),
        _rec("paid2", reach=30000, likes=600, comments=100, saves=100),
        _rec("barter1", reach=60000, likes=900, comments=100, saves=0),
    ]
    PAID = {"paid1", "paid2"}
    BARTER = {"barter1"}
    SPEND = 20000.0

    def test_audience_totals_include_barter(self):
        # Barter reach is real reach. It belongs in what the campaign achieved.
        r = server._rollup_performance(self.RECORDS, self.PAID, self.SPEND, self.BARTER)
        assert r["total_reach"] == 100000
        assert r["total_engagements"] == 2100
        assert r["creators_delivered"] == 3

    def test_cost_per_thousand_uses_paid_reach_on_both_sides(self):
        """The trap this feature is most likely to fall into.

        Barter spend is already zero, so "exclude barter from cost" cannot mean
        excluding its spend — there is none. The damage is on the *other* side
        of the division: counting its 60,000 reach against the paid ₹20,000
        would report ₹200 per thousand, when the paid work actually cost ₹500.
        """
        r = server._rollup_performance(self.RECORDS, self.PAID, self.SPEND, self.BARTER)
        assert r["paid_reach"] == 40000
        assert r["cost_per_thousand_reach"] == 500.0
        # The number a naive implementation would print:
        naive = round(self.SPEND / r["total_reach"] * 1000, 2)
        assert naive == 200.0
        assert r["cost_per_thousand_reach"] != naive

    def test_the_split_is_reported_so_the_figure_can_be_checked(self):
        r = server._rollup_performance(self.RECORDS, self.PAID, self.SPEND, self.BARTER)
        assert r["barter_reach"] == 60000
        assert r["barter_deliveries"] == 1
        assert r["awaiting_payment_deliveries"] == 0
        # Here paid and barter do account for everything, because every
        # delivery is one or the other. That is a property of this fixture,
        # not of the model — see the test below.
        assert r["paid_reach"] + r["barter_reach"] == r["total_reach"]

    def test_unpaid_is_not_the_same_as_barter(self):
        """The bug this separation exists to prevent.

        A delivery on a paid campaign whose payment has not gone out yet is
        neither paid nor barter. Deriving barter as "everything not paid" would
        put a line in a client report claiming we got work for free that we
        have simply not settled.
        """
        records = [
            _rec("paid", reach=10000, likes=100),
            _rec("owed", reach=20000, likes=200),   # paid campaign, unsettled
            _rec("barter", reach=5000, likes=50),
        ]
        r = server._rollup_performance(records, {"paid"}, 5000.0, {"barter"})
        assert r["barter_deliveries"] == 1
        assert r["barter_reach"] == 5000
        assert r["awaiting_payment_deliveries"] == 1
        # The unsettled 20,000 is in neither cost bucket, so it cannot flatter
        # the CPM and cannot be described as free.
        assert r["paid_reach"] == 10000
        assert r["cost_per_thousand_reach"] == 500.0
        assert r["paid_reach"] + r["barter_reach"] < r["total_reach"]

    def test_barter_is_read_from_the_campaign_not_from_a_missing_payment(self):
        import inspect

        src = inspect.getsource(server._barter_collab_ids)
        assert "_compensation_type(c)" in src
        assert "payments" not in src

    def test_an_all_barter_campaign_reports_no_cost_rather_than_dividing_by_zero(self):
        r = server._rollup_performance(
            [_rec("b1", reach=5000, likes=100)], set(), 0.0, {"b1"}
        )
        assert r["cost_per_thousand_reach"] is None
        assert r["total_reach"] == 5000
        assert r["total_spend"] == 0.0

    def test_no_readings_at_all_is_not_a_crash(self):
        r = server._rollup_performance([], set(), 0.0)
        assert r["total_reach"] == 0
        assert r["engagement_rate"] is None
        assert r["cost_per_thousand_reach"] is None
        assert r["creators_delivered"] == 0

    def test_spend_with_no_measured_reach_yields_no_cpm(self):
        # Money went out and nobody has recorded reach yet. The honest answer
        # is "not known", not a division by zero and not ₹0.
        r = server._rollup_performance([_rec("paid1", likes=10)], {"paid1"}, 5000.0)
        assert r["cost_per_thousand_reach"] is None
        assert r["total_spend"] == 5000.0


class TestTheAggregateRate:
    def test_it_is_total_over_total_not_a_mean_of_rates(self):
        """One tiny post with a freak rate must not move the headline.

        A 100-reach post at 20% and a 100,000-reach post at 1% average to 10.5%
        as a mean of rates, which describes nothing that happened.
        """
        records = [
            _rec("a", reach=100, likes=20),
            _rec("b", reach=100000, likes=1000),
        ]
        r = server._rollup_performance(records, set(), 0.0)
        assert r["engagement_rate"] == round(1020 / 100100 * 100, 2)
        assert r["engagement_rate"] < 1.1
        mean_of_rates = (20.0 + 1.0) / 2
        assert r["engagement_rate"] != mean_of_rates

    def test_partial_measurement_is_counted_and_named(self):
        # Three delivered, one measured. A report has to be able to say so
        # rather than implying the total covers everybody.
        records = [_rec("a", reach=1000, likes=10), _rec("b"), _rec("c")]
        r = server._rollup_performance(records, set(), 0.0)
        assert r["creators_delivered"] == 3
        assert r["with_reach"] == 1


class TestManualEntryAlwaysWorks:
    def test_a_reading_needs_at_least_one_number(self):
        with pytest.raises(Exception):
            server.PerformancePayload()

    @pytest.mark.parametrize("metric", server.PERFORMANCE_METRICS)
    def test_any_single_metric_is_enough(self, metric):
        # Whatever the person can see on the screen in front of them.
        assert server.PerformancePayload(**{metric: 1})

    def test_negative_numbers_are_refused(self):
        with pytest.raises(Exception):
            server.PerformancePayload(reach=-1)

    def test_the_instagram_fetch_never_raises(self):
        """Manual entry must always be available, so the automatic path is
        best-effort by construction: it returns a reason, it does not throw."""
        import inspect

        # The body, not the docstring — which says "never raises" and would
        # otherwise satisfy a substring check about the word "raise".
        src = inspect.getsource(server._fetch_instagram_performance)
        body = src.split('"""')[2]
        assert "raise " not in body
        # Every early exit hands back a sentence, not a bare None.
        assert src.count("return None, ") >= 6

    def test_the_fetch_endpoint_answers_200_when_it_cannot_fetch(self):
        # A creator who has not connected Instagram is the ordinary case, not
        # a fault. A 4xx would make the UI treat it as one.
        import inspect

        src = inspect.getsource(server.fetch_collaboration_performance)
        assert '"fetched": False' in src
        assert "raise HTTPException" not in src

    def test_the_fetch_only_reads_the_creators_own_media(self):
        """It matches the permalink against the creator's own media list rather
        than fetching insights for a link we were handed."""
        import inspect

        src = inspect.getsource(server._fetch_instagram_performance)
        assert '"/me/media"' in src
        assert 'db.instagram_connections.find_one({"user_id": collab["creator_id"]})' in src

    @pytest.mark.parametrize(
        "url,key",
        [
            ("https://www.instagram.com/reel/ABC123_x/", "ABC123_x"),
            ("https://instagram.com/p/ABC123_x", "ABC123_x"),
            ("https://www.instagram.com/reel/ABC123_x/?igsh=tracking", "ABC123_x"),
            ("https://www.instagram.com/tv/ABC123_x/", "ABC123_x"),
            ("https://youtube.com/watch?v=x", None),
            (None, None),
        ],
    )
    def test_permalinks_match_however_they_were_pasted(self, url, key):
        # Creators paste links with tracking noise, with and without the
        # trailing slash, with and without www. The shortcode is the invariant.
        assert server._permalink_key(url) == key


class TestTheReport:
    def test_it_describes_only_deliveries(self):
        # A report listing everyone who applied would describe a campaign that
        # did not happen.
        assert "applied" not in server.DELIVERED_COLLAB_STATES
        assert "accepted" not in server.DELIVERED_COLLAB_STATES
        # `attended` is out too: somebody turned up, but there is no link yet
        # and so nothing to measure.
        assert "attended" not in server.DELIVERED_COLLAB_STATES
        assert set(server.DELIVERED_COLLAB_STATES) == {
            "content_submitted",
            "content_approved",
            "in_payment",
            "closed",
        }

    def test_it_carries_no_creator_contact_details(self):
        """It goes to the brand, so it obeys the brand-visible line.

        This is the artefact most likely to be forwarded onwards, which makes
        it the worst place to leak a phone number.
        """
        import inspect

        src = inspect.getsource(server._build_campaign_report)
        for forbidden in ("phone", "email", "full_address", "payout_upi", "pan"):
            assert f'"{forbidden}"' not in src, f"the report exposes {forbidden}"

    def test_the_three_formats_share_one_builder(self):
        # Or the spreadsheet and the printable page come to different totals.
        import inspect

        src = inspect.getsource(server.campaign_report)
        assert src.count("_build_campaign_report(") == 1
        assert "_report_csv(report)" in src
        assert "_report_html(report)" in src

    def test_the_csv_is_written_by_the_csv_module(self):
        # A campaign title with a comma in it would otherwise shift every
        # column to its right, silently.
        import inspect

        src = inspect.getsource(server._report_csv)
        assert "csv.writer" in src

    def test_the_html_escapes_what_people_typed(self):
        import inspect

        src = inspect.getsource(server._report_html)
        assert "html_escape" in src
        # Campaign title, creator name and the URLs all go through it.
        assert "esc(c['title']" in src
        assert "esc(r['creator_name']" in src

    def test_the_exports_are_not_cached(self):
        import inspect

        src = inspect.getsource(server.campaign_report)
        assert src.count('"Cache-Control": "no-store"') == 2

    def test_a_barter_campaign_says_so_in_the_file_itself(self):
        # A spreadsheet gets forwarded without whatever was on screen beside it.
        import inspect

        assert "barter" in inspect.getsource(server._report_csv).lower()
        assert "barter" in inspect.getsource(server._report_html).lower()


class TestShowcase:
    def test_it_is_not_on_the_shared_edit_payload(self):
        """Which of our campaigns we put in front of a prospect is not a
        brand's decision, and UpdateCampaignPayload is their edit route too."""
        assert "showcase" not in server.UpdateCampaignPayload.model_fields
        assert "showcase" not in server.PostCampaignPayload.model_fields

    def test_it_is_console_only_and_scoped(self):
        """Which campaigns we put in front of a prospect is still not the
        brand's to decide — and a `weare_team` member decides it only for the
        brands they run."""
        import inspect

        src = inspect.getsource(server.set_campaign_showcase)
        assert "require_roles(*CONSOLE_ROLES)" in src
        assert "_admin_campaign_or_404(campaign_id, user)" in src

    def test_it_is_audited(self):
        import inspect

        assert "await audit(" in inspect.getsource(server.set_campaign_showcase)

    def test_filtering_to_not_showcased_includes_campaigns_predating_the_field(self):
        # `showcase: False` would match nothing, because the field is absent on
        # every campaign written before this existed.
        import inspect

        src = inspect.getsource(server.list_all_campaigns)
        assert '{"$ne": True}' in src
