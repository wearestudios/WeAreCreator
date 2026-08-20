// Who did what, when, and — for anything destructive — why. The reason column
// is the point: every reject, cancel, revert and refund records one, and this
// is where it surfaces.
//
// This screen was already a table; what it gains from the console's shared one
// is a sticky header that works, sortable columns, and the same row height and
// focus treatment as every other list. The reason stays clamped to one line
// with the full text on hover and in the peek panel — a long reason took a row
// from 64px to 201px, which turns a log you scan into one you scroll.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { ScrollText } from "lucide-react";

import { notifyError } from "@/lib/feedback";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { ADMIN_AUDIT as IDS, ADMIN_TABLE as TABLE_IDS } from "@/constants/testIds";
import { FilterChips, ListEmptyState } from "@/components/data/DenseView";

import DataTable, { sortRows } from "./console/DataTable";
import PeekPanel, { PeekField } from "./console/PeekPanel";
import SaveFilter from "./console/SaveFilter";
import { TimeAgo, absolute } from "./console/format";
import { DENSITY, PANEL, TEXT } from "./console/tokens";
import useListState from "./console/useListState";
import useTableKeys from "./console/useTableKeys";
import { DateFilter, FilterSelect, endOfDay, formatDate } from "./shared";

const ACTION_LABEL = {
    "creator.verified": "approved creator",
    "creator.rejected": "rejected creator",
    "brand.verify": "verified brand",
    "brand.reject": "rejected brand",
    "brand.unverify": "un-verified brand",
    "campaign.create": "created campaign",
    "campaign.update": "edited campaign",
    "campaign.submit_for_review": "submitted for review",
    "campaign.approve": "approved campaign",
    "campaign.reject": "sent campaign back",
    "campaign.pause": "paused campaign",
    "campaign.resume": "resumed campaign",
    "campaign.publish": "published campaign",
    "campaign.close": "closed campaign",
    "campaign.delete": "deleted draft",
    "campaign.invite": "invited creators",
    "collaboration.accept": "accepted creator",
    "collaboration.decline": "declined applicant",
    "collaboration.advance": "advanced collaboration",
    "collaboration.revert": "reverted collaboration",
    "collaboration.cancel": "cancelled collaboration",
    "collaboration.approve_content": "approved content",
    "collaboration.request_changes": "requested changes",
    "collaboration.submit_content": "submitted content",
    "payment.mark_paid": "recorded payout",
    "payment.refund": "refunded payout",
    "payment.invoice_state": "updated invoice",
};

// Filter on the family — "everything that happened to money" is the question
// people actually arrive with. The server treats a bare word as a prefix.
const FAMILY_OPTIONS = [
    { value: "payment", label: "Payments" },
    { value: "collaboration", label: "Collaborations" },
    { value: "campaign", label: "Campaigns" },
    { value: "brand", label: "Brands" },
    { value: "creator", label: "Creators" },
];

const summarizeChange = (entry) => {
    const b = entry.before?.state ?? entry.before?.status ?? entry.before?.verification_status;
    const a = entry.after?.state ?? entry.after?.status ?? entry.after?.verification_status;
    if (b != null && a != null && b !== a) return `${b} → ${a}`;
    if (a != null && b == null) return String(a);
    return null;
};

const DEFAULTS = {
    family: "",
    actor: "",
    from: null,
    to: null,
    // Newest first is what a log is for. The column is sortable, but nobody
    // arrives at an audit trail wanting the oldest entry.
    sort: { key: "created_at", dir: "desc" },
};

/** The stored dates are ISO strings; the pickers want Date objects. */
const asDate = (v) => (v ? new Date(v) : null);

export default function AdminAudit() {
    const [data, setData] = useState(null);
    const [focused, setFocused] = useState(-1);
    const [peek, setPeek] = useState(null);
    const { state, patch, reset, scrollRef, saved, save, apply } = useListState(
        "audit",
        DEFAULTS,
    );
    const { family, actor, from, to, sort } = state;
    const [typedActor, setTypedActor] = useState(actor);
    const location = useLocation();

    useEffect(() => {
        if (location.state?.savedFilter) apply(location.state.savedFilter);
    }, [location.state, apply]);

    useEffect(() => {
        const t = setTimeout(() => {
            if (typedActor.trim() !== actor) patch({ actor: typedActor.trim() });
        }, 300);
        return () => clearTimeout(t);
    }, [typedActor, actor, patch]);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: d } = await api.get("/admin/audit", {
                params: {
                    limit: 200,
                    ...(family ? { action: family } : {}),
                    ...(from ? { date_from: new Date(from).toISOString() } : {}),
                    ...(to ? { date_to: endOfDay(new Date(to)).toISOString() } : {}),
                },
            });
            setData(d);
        } catch (e) {
            notifyError(e);
            setData([]);
        }
    }, [family, from, to]);

    useEffect(() => {
        load();
    }, [load]);

    const columns = useMemo(
        () => [
            {
                key: "created_at",
                mobile: "trailing",
                header: "When",
                sortable: true,
                width: "w-32",
                value: (r) => (r.created_at ? new Date(r.created_at).getTime() : null),
                cell: (r) => <TimeAgo iso={r.created_at} />,
            },
            {
                key: "actor_name",
                mobile: "meta",
                header: "Who",
                sortable: true,
                width: "w-44",
                value: (r) => r.actor_name || "",
                cell: (r) => (
                    <span data-testid={IDS.rowActor(r.id)} className="truncate">
                        {r.actor_name || "—"}
                        <span className={`ml-2 ${TEXT.meta} text-muted-foreground`}>
                            {r.actor_role}
                        </span>
                    </span>
                ),
            },
            {
                key: "action",
                mobile: "primary",
                header: "Did what",
                sortable: true,
                value: (r) => ACTION_LABEL[r.action] || r.action || "",
                cell: (r) => (
                    <span data-testid={IDS.rowAction(r.id)} className="whitespace-nowrap">
                        {ACTION_LABEL[r.action] || r.action}
                    </span>
                ),
            },
            {
                key: "change",
                mobile: "meta",
                header: "Change",
                hideBelow: true,
                width: "w-44",
                cell: (r) => (
                    <span
                        data-testid={IDS.rowChange(r.id)}
                        className="whitespace-nowrap text-muted-foreground"
                    >
                        {summarizeChange(r) || "—"}
                    </span>
                ),
            },
            {
                key: "note",
                header: "Reason",
                width: "w-[20rem]",
                cell: (r) => (
                    <span
                        data-testid={IDS.rowReason(r.id)}
                        // Clamped rather than wrapped, so the row height holds.
                        // The whole reason is on the title, and in the panel.
                        title={r.note || undefined}
                        className="line-clamp-1 text-muted-foreground"
                    >
                        {r.note || "—"}
                    </span>
                ),
            },
        ],
        [],
    );

    // Actor filtering is by name, client-side: admins know each other by name,
    // not by ObjectId, and the list is already capped at 200 rows.
    const matched = useMemo(
        () =>
            (data || []).filter(
                (r) =>
                    !actor ||
                    (r.actor_name || "").toLowerCase().includes(actor.toLowerCase()),
            ),
        [data, actor],
    );

    const rows = useMemo(() => sortRows(matched, columns, sort), [matched, columns, sort]);

    const openPeek = useCallback(
        (i) => {
            setFocused(i);
            setPeek(rows[i] || null);
        },
        [rows],
    );

    useTableKeys({
        count: rows.length,
        focused,
        setFocused,
        onOpen: openPeek,
        onEscape: () => (peek ? setPeek(null) : setFocused(-1)),
    });

    const filtered = Boolean(family || actor || from || to);

    // One implementation behind the chips, the empty state's clear and the
    // saved-set reset, so all three undo exactly the same thing.
    const clearAll = () => {
        setTypedActor("");
        reset();
    };

    const chips = [
        {
            key: "action",
            label: "Action",
            value: family
                ? (FAMILY_OPTIONS.find((o) => o.value === family) || {}).label || family
                : "",
            onRemove: () => patch({ family: "" }),
        },
        {
            key: "actor",
            label: "Admin",
            value: actor,
            onRemove: () => {
                setTypedActor("");
                patch({ actor: "" });
            },
        },
        {
            key: "from",
            label: "From",
            value: from ? formatDate(from) : "",
            onRemove: () => patch({ from: null }),
        },
        {
            key: "to",
            label: "To",
            value: to ? formatDate(to) : "",
            onRemove: () => patch({ to: null }),
        },
    ];

    return (
        <section data-testid={IDS.section}>
            <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className={TEXT.heading}>Audit</h1>
                    <p data-testid={IDS.count} className={`${TEXT.meta} text-muted-foreground`}>
                        {data
                            ? `${rows.length} of ${data.length} · newest first, capped at 200`
                            : "Loading…"}
                    </p>
                </div>
                <SaveFilter onSave={save} disabled={!filtered} savedNames={saved.map((s) => s.name)} />
            </header>

            <div
                data-testid={TABLE_IDS.toolbar}
                className={`mb-3 flex flex-wrap items-center gap-2 ${PANEL} ${DENSITY.row}`}
            >
                <FilterSelect
                    dense
                    label="Everything"
                    value={family}
                    onChange={(v) => patch({ family: v })}
                    options={FAMILY_OPTIONS}
                    testid={IDS.filterAction}
                />
                <Input
                    value={typedActor}
                    onChange={(e) => setTypedActor(e.target.value)}
                    data-testid={IDS.filterActor}
                    placeholder="Filter by admin name"
                    aria-label="Filter by admin"
                    className={`h-8 w-48 border-white/10 bg-transparent ${TEXT.body}`}
                />
                <DateFilter
                    dense
                    label="From"
                    value={asDate(from)}
                    onChange={(d) => patch({ from: d ? d.toISOString() : null })}
                    testid={IDS.filterDateFrom}
                />
                <DateFilter
                    dense
                    label="To"
                    value={asDate(to)}
                    onChange={(d) => patch({ to: d ? d.toISOString() : null })}
                    testid={IDS.filterDateTo}
                />
            </div>

            {filtered && (
                <div className="mb-3">
                    <FilterChips chips={chips} onClearAll={clearAll} />
                </div>
            )}

            <DataTable
                columns={columns}
                rows={rows}
                rowKey={(r) => r.id}
                rowTestId={(r) => IDS.row(r.id)}
                sort={sort}
                onSortChange={(s) => patch({ sort: s })}
                focused={focused}
                onFocus={setFocused}
                onOpen={openPeek}
                loading={!data}
                scrollRef={scrollRef}
                testid={IDS.table}
                empty={
                    <ListEmptyState
                        Icon={ScrollText}
                        testid={IDS.empty}
                        filtered={filtered}
                        onClearFilters={clearAll}
                        emptyTitle="Nothing recorded yet."
                        emptyBody="Every decision that moves a creator, a campaign or money lands here the moment it is made — with who made it and the reason they gave."
                        filteredTitle="No entries match those filters."
                        filteredBody="Widen the date range, or clear the action and admin filters."
                    />
                }
            />

            {/* The panel is where a long reason is actually readable, and where
                the exact instant lives — a log is read for both. */}
            <PeekPanel
                open={Boolean(peek)}
                onOpenChange={(o) => !o && setPeek(null)}
                title={peek ? ACTION_LABEL[peek.action] || peek.action : "Entry"}
                subtitle={peek?.actor_name}
            >
                {peek && (
                    <div>
                        <PeekField label="When">{absolute(peek.created_at)}</PeekField>
                        <PeekField label="Who">
                            {peek.actor_name} · {peek.actor_role}
                        </PeekField>
                        <PeekField label="Action">{peek.action}</PeekField>
                        <PeekField label="Change">{summarizeChange(peek)}</PeekField>
                        {peek.note ? (
                            <p className={`mt-3 whitespace-pre-wrap rounded border border-white/10 p-3 ${TEXT.body} text-muted-foreground`}>
                                {peek.note}
                            </p>
                        ) : null}
                    </div>
                )}
            </PeekPanel>
        </section>
    );
}
