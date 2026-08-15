// Who did what, when, and — for anything destructive — why. The reason column
// is the point: every reject, cancel, revert and refund records one, and this
// is where it surfaces.
import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ScrollText, X } from "lucide-react";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { ADMIN_AUDIT as IDS } from "@/constants/testIds";
import {
    DateFilter,
    EmptyState,
    FilterSelect,
    SectionHeader,
    TableSkeleton,
    endOfDay,
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

    return (
        <section data-testid={IDS.section}>
            <SectionHeader
                kicker="Audit"
                title="Who did what"
                blurb="Every decision that moved a creator, a campaign or money — with the person who made it and the reason they gave."
                onRefresh={load}
                refreshTestId={IDS.refresh}
            />

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
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
                        onClick={() => {
                            setFamily("");
                            setActor("");
                            setActorQuery("");
                            setFrom(null);
                            setTo(null);
                        }}
                        data-testid={IDS.filterClear}
                        className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                    >
                        <X className="h-3.5 w-3.5" />
                        Clear
                    </button>
                )}
            </div>

            <div className="mt-6 rounded-md border border-white/10 bg-card">
                {!rows ? (
                    <TableSkeleton rows={10} cols={4} testid={IDS.skeleton} />
                ) : visible.length === 0 ? (
                    <EmptyState testid={IDS.empty} Icon={ScrollText}>
                        {rows.length === 0
                            ? "Nothing recorded for those filters."
                            : "No entry matches that admin."}
                    </EmptyState>
                ) : (
                    // The table scrolls inside its own container on small
                    // screens rather than forcing the page wide.
                    <div className="overflow-x-auto">
                        <table data-testid={IDS.table} className="w-full min-w-[40rem] text-sm">
                            <thead>
                                <tr className="border-b border-white/10 text-left">
                                    {["When", "Who", "Did what", "Change", "Reason"].map((h) => (
                                        <th
                                            key={h}
                                            className="px-5 py-3 text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground"
                                        >
                                            {h}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/10">
                                {visible.map((r) => (
                                    <tr key={r.id} data-testid={IDS.row(r.id)}>
                                        <td className="whitespace-nowrap px-5 py-3 text-xs text-muted-foreground">
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
                                            className="max-w-[18rem] px-5 py-3 text-xs leading-relaxed text-muted-foreground"
                                        >
                                            {r.note || "—"}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {rows && (
                <p
                    data-testid={IDS.count}
                    className="mt-4 text-xs uppercase tracking-[0.18em] text-muted-foreground"
                >
                    {visible.length} entr{visible.length === 1 ? "y" : "ies"} · newest first ·
                    capped at 200
                </p>
            )}
        </section>
    );
}
