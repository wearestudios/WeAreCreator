// Who did what, when, and — for anything destructive — why. The reason column
// is the point: every reject, cancel, revert and refund records one, and this
// is where it surfaces.
import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ScrollText, X } from "lucide-react";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { ADMIN_AUDIT as IDS, STICKY_BAR } from "@/constants/testIds";
import {
    FilterChips,
    ListEmptyState,
    ResultCount,
    ScrollTable,
    StickyBar,
    pinnedCellClass,
    pinnedHeadClass,
    tableHeadClass,
} from "@/components/data/DenseView";
import {
    DateFilter,
    FilterSelect,
    SectionHeader,
    TableSkeleton,
    endOfDay,
    formatDate,
    formatDateTime,
} from "./shared";

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

export default function AdminAudit() {
    const [rows, setRows] = useState(null);
    const [family, setFamily] = useState("");
    const [actor, setActor] = useState("");
    const [actorQuery, setActorQuery] = useState("");
    const [from, setFrom] = useState(null);
    const [to, setTo] = useState(null);

    useEffect(() => {
        const t = setTimeout(() => setActorQuery(actor.trim()), 300);
        return () => clearTimeout(t);
    }, [actor]);

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get("/admin/audit", {
                params: {
                    limit: 200,
                    ...(family ? { action: family } : {}),
                    ...(from ? { date_from: from.toISOString() } : {}),
                    ...(to ? { date_to: endOfDay(to).toISOString() } : {}),
                },
            });
            setRows(data);
        } catch (e) {
            toast.error(formatApiError(e));
            setRows([]);
        }
    }, [family, from, to]);

    useEffect(() => {
        load();
    }, [load]);

    // Actor filtering is by name, client-side: admins know each other by name,
    // not by ObjectId, and the list is already capped at 200 rows.
    const visible = (rows || []).filter(
        (r) =>
            !actorQuery ||
            (r.actor_name || "").toLowerCase().includes(actorQuery.toLowerCase()),
    );

    const filtered = Boolean(family || actorQuery || from || to);

    // One implementation behind the Clear button, the chips and the empty
    // state's own clear, so all three undo exactly the same thing.
    const clearAll = () => {
        setFamily("");
        setActor("");
        setActorQuery("");
        setFrom(null);
        setTo(null);
    };

    const chips = [
        {
            key: "action",
            label: "Action",
            value: family
                ? (FAMILY_OPTIONS.find((o) => o.value === family) || {}).label || family
                : "",
            onRemove: () => setFamily(""),
        },
        {
            key: "actor",
            label: "Admin",
            value: actorQuery,
            onRemove: () => {
                setActor("");
                setActorQuery("");
            },
        },
        {
            key: "from",
            label: "From",
            value: from ? formatDate(from.toISOString()) : "",
            onRemove: () => setFrom(null),
        },
        {
            key: "to",
            label: "To",
            value: to ? formatDate(to.toISOString()) : "",
            onRemove: () => setTo(null),
        },
    ];

    return (
        <section data-testid={IDS.section}>
            <SectionHeader
                kicker="Audit"
                title="Who did what"
                blurb="Every decision that moved a creator, a campaign or money — with the person who made it and the reason they gave."
                onRefresh={load}
                refreshTestId={IDS.refresh}
            />

            <StickyBar level="headerFromMd" testid={STICKY_BAR.audit} className="mt-8">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                <FilterSelect
                    label="Everything"
                    value={family}
                    onChange={setFamily}
                    options={FAMILY_OPTIONS}
                    testid={IDS.filterAction}
                />
                <Input
                    value={actor}
                    onChange={(e) => setActor(e.target.value)}
                    data-testid={IDS.filterActor}
                    placeholder="Filter by admin name"
                    aria-label="Filter by admin"
                    className="h-10 w-full rounded-md border-white/10 bg-background/60 text-sm focus-visible:ring-ember-500 sm:w-48"
                />
                <DateFilter label="From" value={from} onChange={setFrom} testid={IDS.filterDateFrom} />
                <DateFilter label="To" value={to} onChange={setTo} testid={IDS.filterDateTo} />
                {filtered && (
                    <button
                        type="button"
                        onClick={clearAll}
                        data-testid={IDS.filterClear}
                        className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                    >
                        <X className="h-3.5 w-3.5" />
                        Clear
                    </button>
                )}
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <FilterChips chips={chips} onClearAll={clearAll} />
                {rows && (
                    <ResultCount
                        shown={visible.length}
                        total={rows.length}
                        noun="entry"
                        nounPlural="entries"
                        testid={IDS.count}
                        className="ml-auto"
                    />
                )}
            </div>
            </StickyBar>

            <div className="mt-6">
                {!rows ? (
                    <div className="rounded-lg border border-white/10 bg-card grain-surface">
                        <TableSkeleton rows={10} cols={4} testid={IDS.skeleton} />
                    </div>
                ) : visible.length === 0 ? (
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
                ) : (
                    // Scrolls sideways rather than forcing the page wide, with
                    // the timestamp pinned: five columns of values with no idea
                    // which entry they belong to is not a readable log. The
                    // header sticks to this container — `overflow-x` makes it
                    // the scroller, so it has to own the height too.
                    <ScrollTable testid={IDS.scroll}>
                        <table data-testid={IDS.table} className="w-full min-w-[46rem] text-sm">
                            <thead>
                                <tr className="border-b border-white/10 text-left">
                                    {["When", "Who", "Did what", "Change", "Reason"].map((h, i) => (
                                        <th
                                            key={h}
                                            className={i === 0 ? pinnedHeadClass : tableHeadClass}
                                        >
                                            {h}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/10">
                                {visible.map((r) => (
                                    <tr key={r.id} data-testid={IDS.row(r.id)}>
                                        <td
                                            className={
                                                pinnedCellClass +
                                                " whitespace-nowrap px-5 py-3 text-xs text-muted-foreground"
                                            }
                                        >
                                            {formatDateTime(r.created_at)}
                                        </td>
                                        <td
                                            data-testid={IDS.rowActor(r.id)}
                                            className="whitespace-nowrap px-5 py-3"
                                        >
                                            {r.actor_name || "—"}
                                            <span className="ml-2 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                                                {r.actor_role}
                                            </span>
                                        </td>
                                        <td
                                            data-testid={IDS.rowAction(r.id)}
                                            className="whitespace-nowrap px-5 py-3"
                                        >
                                            {ACTION_LABEL[r.action] || r.action}
                                        </td>
                                        <td
                                            data-testid={IDS.rowChange(r.id)}
                                            className="whitespace-nowrap px-5 py-3 text-xs text-muted-foreground"
                                        >
                                            {summarizeChange(r) || "—"}
                                        </td>
                                        <td
                                            data-testid={IDS.rowReason(r.id)}
                                            // Clamped rather than wrapped. A long
                                            // reason took a row from 64px to 201px
                                            // on a phone, which turns a log you
                                            // scan into one you scroll. The full
                                            // text is on the title attribute.
                                            title={r.note || undefined}
                                            className="w-[18rem] max-w-[18rem] px-5 py-3 text-xs leading-relaxed text-muted-foreground"
                                        >
                                            <span className="line-clamp-2">{r.note || "—"}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </ScrollTable>
                )}
            </div>

            {rows && (
                <p className="mt-4 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    Newest first · capped at 200
                </p>
            )}
        </section>
    );
}
