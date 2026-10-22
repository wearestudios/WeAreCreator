"""How a deal got to its number: one writer, an append-only history.

Two layers, for the two different failures.

**Structural**, because the promise is about *every* write: no collaboration
write anywhere in the backend may set `agreed_amount` except
`_set_agreed_amount`, and nothing may rewrite or remove a history entry. A
list of call sites somebody maintains is a list somebody forgets to add the
next route to, so these walk the AST of every backend module instead.

**Driven**, because a helper being called is not the helper working: each
path is run against mongomock and the stored row read back — exactly one new
entry, the right kind, source and author, and no amount on barter.
"""

from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

BACKEND = Path(server.__file__).parent
LOOP = None

_WRITES = {"update_one", "update_many", "find_one_and_update", "replace_one",
           "find_one_and_replace", "insert_one", "insert_many"}


def run(body):
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["negotiation"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


# ---------------------------------------------------------------------------
# Structural: one writer, and nothing rewrites history
# ---------------------------------------------------------------------------


def _modules():
    """Every backend module that could write to the database, tests aside."""
    for path in sorted(BACKEND.glob("*.py")):
        yield path, ast.parse(path.read_text())


def _enclosing_functions(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def owner(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return None

    return owner


def _collab_writes(tree):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _WRITES
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "collaborations"
        ):
            yield node


def _keys(node):
    for n in ast.walk(node):
        if isinstance(n, ast.Dict):
            for k in n.keys:
                if isinstance(k, ast.Constant):
                    yield k.value


def test_nothing_writes_agreed_amount_except_the_helper():
    offenders = []
    for path, tree in _modules():
        owner = _enclosing_functions(tree)
        for call in _collab_writes(tree):
            fn = owner(call)
            if fn == "_set_agreed_amount":
                continue
            # The update document (or, for an insert, the document itself).
            # A filter matching on the fee is a read, not a write.
            docs = call.args if call.func.attr.startswith("insert") else call.args[1:]
            docs = list(docs) + [k.value for k in call.keywords]
            if any("agreed_amount" in _keys(d) for d in docs):
                offenders.append(f"{path.name}:{call.lineno} ({fn})")
        # And the indirect shape: `update["agreed_amount"] = …` handed to a
        # `$set` later, which is how advance_collaboration used to do it.
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if (isinstance(t, ast.Subscript)
                            and isinstance(t.slice, ast.Constant)
                            and t.slice.value == "agreed_amount"
                            and owner(node) != "_set_agreed_amount"):
                        offenders.append(f"{path.name}:{node.lineno} ({owner(node)})")
    assert not offenders, f"writes agreed_amount outside _set_agreed_amount: {offenders}"


def test_the_converted_call_sites():
    """Named, so the count in the change description is checkable and a new
    caller is a deliberate addition to this list."""
    callers = set()
    for path, tree in _modules():
        owner = _enclosing_functions(tree)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and ((isinstance(node.func, ast.Name) and node.func.id == "_set_agreed_amount")
                         or (isinstance(node.func, ast.Attribute) and node.func.attr == "_set_agreed_amount"))):
                callers.add(f"{path.name}:{owner(node)}")
    assert callers == {
        "server.py:brand_accept_applicant",
        "server.py:accept_partial_delivery",
        "server.py:brand_record_agreed_amount",
        "server.py:advance_collaboration",
        "server.py:resolve_dispute",
        "seed_demo.py:_collab",
    }


def test_history_is_only_ever_appended_to():
    """`$push` and nothing else: no `$set`, `$unset`, `$pull` or `$pop` on the
    field, anywhere. A correction is a new entry."""
    offenders = []
    for path, tree in _modules():
        owner = _enclosing_functions(tree)
        for call in _collab_writes(tree):
            if call.func.attr.startswith("insert"):
                continue  # an insert opening the history is not a rewrite of one
            for doc in call.args[1:]:
                for n in ast.walk(doc):
                    if not isinstance(n, ast.Dict):
                        continue
                    for k, v in zip(n.keys, n.values):
                        if (isinstance(k, ast.Constant) and k.value in
                                ("$set", "$unset", "$pull", "$pop", "$pullAll", "$rename")
                                and "negotiation_history" in _keys(v)):
                            offenders.append(f"{path.name}:{call.lineno} ({owner(call)})")
    assert not offenders, offenders


def test_no_route_takes_a_history_entry_as_input():
    """No payload model carries the field, so no endpoint can be handed an
    entry to write or an index to change."""
    for name in dir(server):
        model = getattr(server, name)
        fields = getattr(model, "model_fields", None)
        if isinstance(fields, dict):
            assert "negotiation_history" not in fields, name


# ---------------------------------------------------------------------------
# Driven: each path appends exactly one entry
# ---------------------------------------------------------------------------


async def _scene(db, *, state="verified", compensation="fixed", budget=12000,
                 execution_owner="brand", **collab_extra):
    brand_oid, creator_oid, campaign_oid, collab_oid = (ObjectId() for _ in range(4))
    await db.users.insert_many([
        {"_id": brand_oid, "role": "brand_manager", "name": "Toit", "brand_id": brand_oid},
        {"_id": creator_oid, "role": "creator", "name": "Asha"},
    ])
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": True,
         "verification_state": "verified", "verified_at": _now()}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified",
         "phone": "+919876543210", "email": "asha@example.com"}
    )
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Tasting",
         "status": "in_progress", "campaign_type": "personal_table",
         "execution_owner": execution_owner, "compensation_type": compensation,
         "budget_per_creator": budget, "creators_needed": 5,
         "barter_description": "Dinner for two and a signature cocktail",
         "deliverable_items": [{"type": "story", "quantity": 2}]}
    )
    await db.collaborations.insert_one(
        {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
         "state": state, "state_since": _now(), "quoted_rate": 15000.0, "active": True,
         **collab_extra}
    )
    return {
        "collab_id": str(collab_oid), "collab_oid": collab_oid, "campaign_oid": campaign_oid,
        "brand": {"_id": str(brand_oid), "role": "brand_manager", "name": "Toit",
                  "brand_id": brand_oid},
        "creator": {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
        "brand_oid": brand_oid,
    }


async def _row(db, s):
    return await db.collaborations.find_one({"_id": s["collab_oid"]})


def _history(row):
    return row.get("negotiation_history") or []


class TestEachPathAppendsOne:
    def test_accepting_at_the_quote_is_an_accept(self):
        async def body(db):
            s = await _scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"])
            return s, await _row(db, s)

        s, row = run(body)
        [e] = _history(row)
        assert row["agreed_amount"] == 15000.0
        assert e["kind"] == "accept" and e["amount"] == 15000.0 and e["currency"] == "INR"
        assert e["by_role"] == "brand" and e["source"] == "in_app"
        assert e["by_user_id"] == s["brand_oid"]

    def test_accepting_at_another_figure_is_a_counter(self):
        async def body(db):
            s = await _scene(db)
            await server.brand_accept_applicant(
                s["collab_id"],
                server.BrandAcceptPayload(agreed_amount=12000, note="Our ceiling"),
                s["brand"])
            return await _row(db, s)

        row = run(body)
        [e] = _history(row)
        assert e["kind"] == "counter" and e["amount"] == 12000 and e["note"] == "Our ceiling"
        assert row["agreed_amount"] == 12000

    def test_recording_the_offline_agreement(self):
        async def body(db):
            s = await _scene(db, state="accepted", compensation="negotiated")
            await server.brand_record_agreed_amount(
                s["collab_id"],
                server.AgreedAmountPayload(agreed_amount=13500, note="Agreed on the call"),
                s["brand"])
            return await _row(db, s)

        row = run(body)
        [e] = _history(row)
        assert e["kind"] == "accept" and e["source"] == "recorded_offline"
        assert row["agreed_amount"] == 13500 and row["state"] == "commercial_agreed"

    def test_a_staff_correction_is_an_adjustment_and_needs_a_note(self):
        async def body(db):
            s = await _scene(db, state="commercial_agreed", compensation="negotiated",
                             agreed_amount=13500.0, agreed_at=_now())
            with pytest.raises(HTTPException) as err:
                await server.brand_record_agreed_amount(
                    s["collab_id"], server.AgreedAmountPayload(agreed_amount=12500), ADMIN)
            refused = await _row(db, s)
            await server.brand_record_agreed_amount(
                s["collab_id"],
                server.AgreedAmountPayload(agreed_amount=12500, note="Typo on the first entry"),
                ADMIN)
            return err.value, refused, await _row(db, s)

        exc, refused, row = run(body)
        assert exc.status_code == 422
        # Refused before anything moved.
        assert refused["agreed_amount"] == 13500.0 and not _history(refused)
        [e] = _history(row)
        assert e["kind"] == "adjust" and e["source"] == "admin_adjustment"
        assert e["by_role"] == "admin" and str(e["by_user_id"]) == ADMIN["_id"]
        assert row["agreed_amount"] == 12500

    def test_the_console_fee_step(self):
        async def body(db):
            s = await _scene(db, state="accepted", compensation="negotiated",
                             execution_owner="weare")
            await server.advance_collaboration(
                s["collab_id"],
                server.AdvanceCollabPayload(from_state="accepted", agreed_amount=14000,
                                            note="Settled on WhatsApp"),
                ADMIN)
            return await _row(db, s), await db.audit_log.find_one({"action": "collaboration.advance"})

        row, line = run(body)
        [e] = _history(row)
        assert e["kind"] == "accept" and e["source"] == "recorded_offline"
        assert e["note"] == "Settled on WhatsApp" and row["agreed_amount"] == 14000
        assert line["after"]["agreed_amount"] == 14000

    def test_settling_for_part_of_a_delivery(self):
        async def body(db):
            s = await _scene(db, state="content_submitted", compensation="negotiated",
                             agreed_amount=12000.0, agreed_at=_now(),
                             content_urls=["https://instagram.com/p/x"])
            await server.accept_partial_delivery(
                s["collab_id"],
                server.PartialDeliveryPayload(delivered={"story": 1}, agreed_amount=6000,
                                              note="One of two stories went up"),
                s["brand"])
            return await _row(db, s)

        row = run(body)
        [e] = _history(row)
        assert e["kind"] == "adjust" and e["source"] == "in_app" and e["amount"] == 6000
        assert row["agreed_amount"] == 6000 and row["state"] == "content_approved"

    def test_a_mediated_partial_release(self):
        async def body(db):
            s = await _scene(db, state="content_approved", compensation="negotiated",
                             agreed_amount=12000.0, agreed_at=_now(),
                             dispute={"state": "open", "raised_by_role": "creator"})
            await db.payments.insert_one(
                {"collaboration_id": s["collab_oid"], "state": "pending",
                 "agreed_amount": 12000.0, "creator_payout": 12000.0, "fee_percent": 10.0})
            await server.resolve_dispute(
                s["collab_id"],
                server.DisputeResolutionPayload(resolution="partial_release", amount=8000,
                                                note="Half the stories were late"),
                ADMIN)
            return await _row(db, s)

        row = run(body)
        [e] = _history(row)
        assert e["kind"] == "adjust" and e["source"] == "admin_adjustment"
        assert e["note"] == "Half the stories were late" and row["agreed_amount"] == 8000

    def test_a_lost_race_leaves_neither_the_figure_nor_an_entry(self):
        async def body(db):
            s = await _scene(db)
            campaign = await db.campaigns.find_one({"_id": s["campaign_oid"]})
            result = await server._set_agreed_amount(
                s["collab_oid"], 9000, campaign=campaign, kind="accept", by_role="brand",
                by_user_id=None, note=None, source="in_app",
                precondition={"state": "accepted"},  # it is `verified`
            )
            return result, await _row(db, s)

        result, row = run(body)
        assert result is None and "agreed_amount" not in row and not _history(row)

    def test_declining_records_the_end_without_a_figure(self):
        async def body(db):
            s = await _scene(db)
            await server.brand_decline_applicant(
                s["collab_id"], server.DecisionPayload(reason="Not this time"), s["brand"])
            return await _row(db, s)

        [e] = _history(run(body))
        assert e["kind"] == "decline" and e["amount"] is None and e["note"] == "Not this time"


class TestBarter:
    def test_accepting_a_barter_applicant_writes_no_amount(self):
        async def body(db):
            s = await _scene(db, compensation="barter")
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(agreed_amount=5000), s["brand"])
            return await _row(db, s)

        row = run(body)
        assert row.get("agreed_amount") is None
        [e] = _history(row)
        assert e["amount"] is None and e["kind"] == "accept"

    def test_recording_a_barter_agreement_writes_no_amount(self):
        async def body(db):
            s = await _scene(db, state="accepted", compensation="barter")
            await server.brand_record_agreed_amount(
                s["collab_id"], server.AgreedAmountPayload(), s["brand"])
            return await _row(db, s)

        row = run(body)
        assert row.get("agreed_amount") is None
        assert [e["amount"] for e in _history(row)] == [None]

    def test_the_history_shows_the_terms_instead_of_a_number(self):
        campaign = {"compensation_type": "barter",
                    "barter_description": "Dinner for two"}
        collab = {"negotiation_history": [
            {"at": _now(), "kind": "accept", "amount": 4000, "by_role": "brand",
             "source": "in_app"}]}
        block = server._serialize_negotiation(collab, campaign, full=False)
        assert block["barter_terms"] == "Dinner for two"
        assert block["entries"][0]["amount"] is None

    def test_an_application_opens_with_the_quote_except_on_barter(self):
        async def body(db):
            out = []
            for comp in ("fixed", "barter"):
                s = await _scene(db, compensation=comp)
                await db.collaborations.delete_one({"_id": s["collab_oid"]})
                campaign = await db.campaigns.find_one({"_id": s["campaign_oid"]})
                campaign["status"] = "open"
                await db.campaigns.update_one({"_id": campaign["_id"]}, {"$set": {"status": "open"}})
                await server._create_application(campaign, s["creator"], pitch="Keen", quoted_rate=7000)
                out.append(await db.collaborations.find_one({"campaign_id": s["campaign_oid"]}))
            return out

        paid, barter = run(body)
        assert "agreed_amount" not in paid
        [e] = _history(paid)
        assert e["kind"] == "offer" and e["by_role"] == "creator" and e["amount"] == 7000
        assert _history(barter)[0]["amount"] is None


# ---------------------------------------------------------------------------
# Who reads what
# ---------------------------------------------------------------------------


def _entries():
    base = _now()
    return [
        {"at": base - timedelta(days=3), "kind": "offer", "amount": 15000, "currency": "INR",
         "by_role": "creator", "by_user_id": ObjectId(), "note": None, "source": "in_app"},
        {"at": base - timedelta(days=2), "kind": "accept", "amount": 12000, "currency": "INR",
         "by_role": "admin", "by_user_id": ObjectId(),
         "note": "Call her on +91 98765 43210 or asha@example.com", "source": "recorded_offline"},
        {"at": base - timedelta(days=1), "kind": "accept", "amount": 12000, "currency": "INR",
         "by_role": "system", "by_user_id": None, "note": None, "source": "backfill"},
    ]


def test_newest_first():
    block = server._serialize_negotiation({"negotiation_history": _entries()},
                                          {"compensation_type": "fixed"}, full=False)
    assert [e["kind"] for e in block["entries"]] == ["accept", "accept", "offer"]


def test_a_brand_or_creator_reads_which_side_and_never_who_or_how_they_reach_them():
    block = server._serialize_negotiation({"negotiation_history": _entries()},
                                          {"compensation_type": "fixed"}, full=False)
    text = repr(block)
    for e in block["entries"]:
        assert "by_user_id" not in e and "source" not in e
    assert "98765" not in text and "asha@example.com" not in text
    assert "[contact removed]" in text
    # Every forbidden creator key stays off the shape too.
    for key in server.BRAND_FORBIDDEN_CREATOR_FIELDS:
        assert f"'{key}'" not in text


def test_the_admin_reads_source_and_author():
    block = server._serialize_negotiation({"negotiation_history": _entries()},
                                          {"compensation_type": "fixed"}, full=True)
    assert all("source" in e and "by_user_id" in e for e in block["entries"])
    assert "asha@example.com" in repr(block)


def test_a_backfilled_entry_is_labelled_as_one():
    block = server._serialize_negotiation({"negotiation_history": _entries()},
                                          {"compensation_type": "fixed"}, full=False)
    flags = [e["recorded_before_tracking"] for e in block["entries"]]
    assert flags == [True, False, False]


def test_the_application_screen_serves_each_role_its_view():
    async def body(db):
        s = await _scene(db, state="accepted", compensation="negotiated", agreed_at=_now())
        await server.brand_record_agreed_amount(
            s["collab_id"], server.AgreedAmountPayload(agreed_amount=13500), s["brand"])
        return (await server.get_application(s["collab_id"], ADMIN),
                await server.get_application(s["collab_id"], s["brand"]))

    admin_view, brand_view = run(body)
    assert "source" in admin_view["negotiation"]["entries"][0]
    assert "source" not in brand_view["negotiation"]["entries"][0]
    assert brand_view["negotiation"]["entries"][0]["amount"] == 13500


# ---------------------------------------------------------------------------
# The backfill
# ---------------------------------------------------------------------------


def test_the_backfill_is_idempotent_labelled_and_skips_barter():
    import backfill_negotiation_history as bf

    async def body(db):
        fixed = await _scene(db, state="closed", compensation="fixed",
                             agreed_amount=9000.0, agreed_at=_now() - timedelta(days=90))
        barter = await _scene(db, state="closed", compensation="barter", agreed_amount=0.0)
        tracked = await _scene(db, state="closed", agreed_amount=7000.0)
        await db.collaborations.update_one(
            {"_id": tracked["collab_oid"]},
            {"$push": {"negotiation_history": {"kind": "accept", "amount": 7000}}})
        dry = await bf.backfill(apply=False)
        first = await bf.backfill(apply=True)
        second = await bf.backfill(apply=True)
        return (dry, first, second, await _row(db, fixed), await _row(db, barter),
                await _row(db, tracked))

    dry, first, second, fixed, barter, tracked = run(body)
    assert dry["written"] == 0 and dry["candidates"] == 2
    assert first["written"] == 1 and first["skipped_barter"] == 1
    assert second["written"] == 0
    [e] = _history(fixed)
    assert e["source"] == "backfill" and e["kind"] == "accept" and e["by_role"] == "system"
    assert e["amount"] == 9000.0
    assert e["at"].replace(tzinfo=timezone.utc) < _now() - timedelta(days=89)
    assert not _history(barter)
    assert len(_history(tracked)) == 1
