// Every brand, with the two numbers that matter (what they've run, what
// they've actually paid) and the verification decision inline. Rejection
// demands a reason — the brand is told, and the audit log keeps it.
//
// A table now, like every other list in the console. The row carries the
// decision because verifying is a one-glance judgement most of the time; the
// peek panel carries it too, with the rejection reason and the counts, for the
// times it isn't. Both go through the same handlers, so the keyboard's A and R
// cannot mean anything different from the buttons.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { BadgeCheck, Building2, Search, XCircle } from "lucide-react";

import { notifyError, notifySuccess } from "@/lib/feedback";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { ADMIN_BRANDS as IDS, ADMIN_PEEK, ADMIN_TABLE as TABLE_IDS } from "@/constants/testIds";
import { FilterChips, ListEmptyState } from "@/components/data/DenseView";
import BrandAvatar from "@/components/BrandAvatar";

import { ConfirmDialog } from "./dialogs";
import DataTable, { sortRows } from "./console/DataTable";
import PeekPanel, { PeekField } from "./console/PeekPanel";
import SaveFilter from "./console/SaveFilter";
import { PeekButton, RowButton } from "./console/RowActions";
import StatusTag from "./console/StatusTag";
import { TimeAgo, count as fmtCount, rupees } from "./console/format";
import { CALM, DENSITY, FOCUS, PANEL, TEXT } from "./console/tokens";
import useListState from "./console/useListState";
import useTableKeys from "./console/useTableKeys";
import { FilterSelect } from "./shared";

const STATUS_OPTIONS = [
    { value: "verified", label: "Verified" },
    { value: "pending", label: "Pending" },
    { value: "rejected", label: "Rejected" },
];

const brandStatus = (b) =>
    b.verified ? "verified" : b.verification_reason ? "rejected" : "pending";

const DEFAULTS = { q: "", status: "", sort: { key: "business_name", dir: "asc" } };

export default function AdminBrands({ onChanged, onViewCampaigns }) {
    const [data, setData] = useState(null);
    const [busyId, setBusyId] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [confirm, setConfirm] = useState(null);
    const [focused, setFocused] = useState(-1);
    const [peek, setPeek] = useState(null);
    const { state, patch, reset, scrollRef, saved, save, apply } = useListState(
        "brands",
        DEFAULTS,
    );
    const { q, status, sort } = state;
    const [typed, setTyped] = useState(q);
    const location = useLocation();

    useEffect(() => {
        if (location.state?.savedFilter) apply(location.state.savedFilter);
    }, [location.state, apply]);

    useEffect(() => {
        const t = setTimeout(() => {
            if (typed.trim() !== q) patch({ q: typed.trim() });
        }, 250);
        return () => clearTimeout(t);
    }, [typed, q, patch]);

    const load = useCallback(async () => {
        setData(null);
        try {
            // /admin/brands carries the counts and spend; /admin/brands/pending
            // carries the rejection reasons. One merged list, one mental model.
            const [all, pending] = await Promise.all([
                api.get("/admin/brands"),
                api.get("/admin/brands/pending"),
            ]);
            const reasonById = Object.fromEntries(
                pending.data.map((p) => [p.user_id, p]),
            );
            setData(
                all.data.map((b) => ({
                    ...b,
                    verification_reason: reasonById[b.user_id]?.verification_reason,
                })),
            );
        } catch (e) {
            notifyError(e);
            setData([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const run = useCallback(
        async (id, fn, msg) => {
            setBusyId(id);
            setSubmitting(true);
            try {
                await fn();
                notifySuccess(msg);
                setConfirm(null);
                setPeek(null);
                await load();
                onChanged?.();
            } catch (e) {
                notifyError(e);
            } finally {
                setBusyId(null);
                setSubmitting(false);
            }
        },
        [load, onChanged],
    );

    const verify = useCallback(
        (b) =>
            run(b.user_id, () => api.post(`/admin/brands/${b.user_id}/verify`), "Brand verified"),
        [run],
    );

    const reject = useCallback(
        (b) =>
            setConfirm({
                title: `Reject ${b.business_name || "this brand"}?`,
                onSubmit: (body) =>
                    run(
                        b.user_id,
                        () => api.post(`/admin/brands/${b.user_id}/reject`, body),
                        "Brand rejected",
                    ),
            }),
        [run],
    );

    const unverify = useCallback(
        (b) =>
            setConfirm({
                unverify: true,
                title: `Take ${b.business_name || "this brand"} back to unverified?`,
                onSubmit: (body) =>
                    run(
                        b.user_id,
                        () => api.post(`/admin/brands/${b.user_id}/unverify`, body),
                        "Brand un-verified",
                    ),
            }),
        [run],
    );

    const columns = useMemo(
        () => [
            {
                key: "business_name",
                header: "Brand",
                sortable: true,
                value: (b) => b.business_name || "",
                cell: (b) => (
                    <span className="flex min-w-0 items-center gap-2">
                        <BrandAvatar brand={b} size="h-6 w-6" />
                        <Link
                            to={`/admin/brands/${b.user_id}`}
                            onClick={(e) => e.stopPropagation()}
                            data-testid={IDS.open(b.user_id)}
                            className={`truncate ${CALM} hover:text-ember-500 ${FOCUS}`}
                        >
                            {b.business_name || "Unnamed brand"}
                        </Link>
                    </span>
                ),
            },
            {
                key: "verification",
                header: "Status",
                sortable: true,
                width: "w-32",
                value: (b) => brandStatus(b),
                cell: (b) => (
                    <StatusTag state={brandStatus(b)} testid={IDS.rowStatus(b.user_id)} />
                ),
            },
            {
                key: "category",
                header: "Category",
                sortable: true,
                hideBelow: true,
                cell: (b) => b.category || <span className="text-muted-foreground">—</span>,
            },
            {
                key: "campaign_count",
                header: "Campaigns",
                sortable: true,
                numeric: true,
                width: "w-28",
                value: (b) => b.campaign_count ?? null,
                cell: (b) => (
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            onViewCampaigns?.(b.user_id);
                        }}
                        data-testid={IDS.viewCampaigns(b.user_id)}
                        className={`${CALM} hover:text-ember-500 ${FOCUS}`}
                        title={
                            b.active_campaign_count > 0
                                ? `${b.active_campaign_count} live`
                                : "None live"
                        }
                    >
                        {fmtCount(b.campaign_count)}
                    </button>
                ),
            },
            {
                key: "total_spend",
                header: "Spend",
                sortable: true,
                numeric: true,
                width: "w-32",
                value: (b) => b.total_spend ?? null,
                cell: (b) => (
                    <span data-testid={IDS.rowSpend(b.user_id)}>{rupees(b.total_spend)}</span>
                ),
            },
            {
                key: "created_at",
                header: "Joined",
                sortable: true,
                numeric: true,
                width: "w-28",
                hideBelow: true,
                value: (b) => (b.created_at ? new Date(b.created_at).getTime() : null),
                cell: (b) => <TimeAgo iso={b.created_at} />,
            },
            {
                key: "decision",
                header: "",
                width: "w-40",
                cell: (b) => (
                    <span
                        className="flex justify-end gap-1"
                        // The row itself opens the peek panel; a click on a
                        // decision is a decision, not a request to look.
                        onClick={(e) => e.stopPropagation()}
                    >
                        {brandStatus(b) === "verified" ? (
                            <RowButton
                                onClick={() => unverify(b)}
                                disabled={busyId === b.user_id}
                                testid={IDS.unverify(b.user_id)}
                            >
                                Un-verify
                            </RowButton>
                        ) : (
                            <>
                                <RowButton
                                    onClick={() => reject(b)}
                                    disabled={busyId === b.user_id}
                                    testid={IDS.reject(b.user_id)}
                                    tone="bad"
                                >
                                    Reject
                                </RowButton>
                                <RowButton
                                    onClick={() => verify(b)}
                                    disabled={busyId === b.user_id}
                                    testid={IDS.verify(b.user_id)}
                                    tone="primary"
                                >
                                    Verify
                                </RowButton>
                            </>
                        )}
                    </span>
                ),
            },
        ],
        [busyId, onViewCampaigns, reject, unverify, verify],
    );

    const filtered = Boolean(q || status);

    const matched = useMemo(() => {
        const term = q.trim().toLowerCase();
        return (data || []).filter((b) => {
            if (status && brandStatus(b) !== status) return false;
            if (!term) return true;
            return [b.business_name, b.email, b.phone]
                .filter(Boolean)
                .some((v) => String(v).toLowerCase().includes(term));
        });
    }, [data, q, status]);

    const rows = useMemo(() => sortRows(matched, columns, sort), [matched, columns, sort]);

    const openPeek = useCallback(
        (i) => {
            setFocused(i);
            setPeek(rows[i] || null);
        },
        [rows],
    );

    // A and R reach the same two handlers the buttons do — including the
    // rejection dialog, which is the whole point: a keystroke is a faster way
    // to the reason box, never a way past it.
    useTableKeys({
        count: rows.length,
        focused,
        setFocused,
        onOpen: openPeek,
        onApprove: (i) => {
            const b = rows[i];
            if (b && brandStatus(b) !== "verified") verify(b);
        },
        onReject: (i) => {
            const b = rows[i];
            if (b && brandStatus(b) !== "verified") reject(b);
        },
        onEscape: () => (peek ? setPeek(null) : setFocused(-1)),
        enabled: !confirm,
    });

    const clearFilters = () => {
        setTyped("");
        reset();
    };

    const chips = [
        { key: "search", label: "Search", value: q, onRemove: () => { setTyped(""); patch({ q: "" }); } },
        {
            key: "status",
            label: "Status",
            value: status
                ? (STATUS_OPTIONS.find((o) => o.value === status) || {}).label || status
                : "",
            onRemove: () => patch({ status: "" }),
        },
    ];

    return (
        <section data-testid={IDS.section}>
            <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className={TEXT.heading}>Brands</h1>
                    <p data-testid={IDS.count} className={`${TEXT.meta} text-muted-foreground`}>
                        {data
                            ? `${rows.length} of ${data.length} · spend counts money that left the bank`
                            : "Loading…"}
                    </p>
                </div>
                <SaveFilter onSave={save} disabled={!filtered} savedNames={saved.map((s) => s.name)} />
            </header>

            <div
                data-testid={TABLE_IDS.toolbar}
                className={`mb-3 flex flex-wrap items-center gap-2 ${PANEL} ${DENSITY.row}`}
            >
                <div className="relative min-w-[9rem] flex-1">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={typed}
                        onChange={(e) => setTyped(e.target.value)}
                        data-testid={IDS.search}
                        placeholder="Business name, email or phone"
                        aria-label="Search brands"
                        className={`h-8 border-white/10 bg-transparent pl-8 ${TEXT.body}`}
                    />
                </div>
                <FilterSelect
                    dense
                    label="Status"
                    value={status}
                    onChange={(v) => patch({ status: v })}
                    options={STATUS_OPTIONS}
                    testid={IDS.filterStatus}
                />
            </div>

            {filtered && (
                <div className="mb-3">
                    <FilterChips chips={chips} onClearAll={clearFilters} />
                </div>
            )}

            <DataTable
                columns={columns}
                rows={rows}
                rowKey={(b) => b.user_id}
                rowTestId={(b) => IDS.row(b.user_id)}
                sort={sort}
                onSortChange={(s) => patch({ sort: s })}
                focused={focused}
                onFocus={setFocused}
                onOpen={openPeek}
                loading={!data}
                scrollRef={scrollRef}
                testid={IDS.list}
                empty={
                    <ListEmptyState
                        Icon={Building2}
                        testid={IDS.empty}
                        filtered={filtered}
                        onClearFilters={clearFilters}
                        emptyTitle="No brands yet."
                        emptyBody="Every business that signs up appears here with its verification state and what it has actually paid out."
                        filteredTitle="No brand matches that."
                        filteredBody="Clear the search, or widen the status filter."
                    />
                }
            />

            <PeekPanel
                open={Boolean(peek)}
                onOpenChange={(o) => !o && setPeek(null)}
                title={peek?.business_name || "Brand"}
                subtitle={peek?.category}
                href={peek ? `/admin/brands/${peek.user_id}` : undefined}
                actions={
                    peek ? (
                        brandStatus(peek) === "verified" ? (
                            <PeekButton
                                onClick={() => unverify(peek)}
                                testid={ADMIN_PEEK.action("unverify")}
                            >
                                Un-verify
                            </PeekButton>
                        ) : (
                            <>
                                <PeekButton
                                    tone="bad"
                                    onClick={() => reject(peek)}
                                    testid={ADMIN_PEEK.action("reject")}
                                >
                                    <XCircle className="h-3.5 w-3.5" />
                                    Reject
                                </PeekButton>
                                <PeekButton
                                    tone="primary"
                                    onClick={() => verify(peek)}
                                    testid={ADMIN_PEEK.action("verify")}
                                >
                                    <BadgeCheck className="h-3.5 w-3.5" />
                                    Verify
                                </PeekButton>
                            </>
                        )
                    ) : null
                }
            >
                {peek && (
                    <div>
                        <PeekField label="Status">
                            <StatusTag state={brandStatus(peek)} chip />
                        </PeekField>
                        <PeekField label="Campaigns">
                            {fmtCount(peek.campaign_count)}
                            {peek.active_campaign_count > 0
                                ? ` · ${peek.active_campaign_count} live`
                                : ""}
                        </PeekField>
                        <PeekField label="Spend">{rupees(peek.total_spend)}</PeekField>
                        <PeekField label="Joined">
                            <TimeAgo iso={peek.created_at} />
                        </PeekField>
                        {brandStatus(peek) === "rejected" && peek.verification_reason && (
                            <p
                                data-testid={IDS.rowReason(peek.user_id)}
                                className={`mt-3 rounded border border-rose-500/25 bg-rose-500/5 p-3 ${TEXT.body} text-rose-300`}
                            >
                                Rejected: {peek.verification_reason}
                            </p>
                        )}
                    </div>
                )}
            </PeekPanel>

            <ConfirmDialog
                open={Boolean(confirm)}
                onOpenChange={(v) => !v && setConfirm(null)}
                submitting={submitting}
                kicker={confirm?.unverify ? "Un-verify brand" : "Reject brand"}
                title={confirm?.title || ""}
                description={
                    confirm?.unverify
                        ? "They can keep drafting but can't submit campaigns until re-verified. Live campaigns are untouched."
                        : "They're told why, any briefs of theirs waiting for review go back to draft, and they can't submit until we verify them."
                }
                placeholder="What should they fix?"
                confirmLabel={confirm?.unverify ? "Un-verify" : "Reject brand"}
                destructive
                onSubmit={(body) => confirm?.onSubmit(body)}
            />
        </section>
    );
}
