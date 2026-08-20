// The mediation queue.
//
// A dispute freezes a collaboration and any payment on it, which means every
// row here is somebody waiting and money not moving — the one queue in this
// console where the cost of not looking is measured in days of somebody's
// income. So it is a section of its own rather than a filter on the
// collaborations list, and open is what it opens on.
//
// **Resolving happens on the collaboration's own page, not here.** A decision
// that releases or refunds money is one somebody should make with the pitch,
// the notes, the delivery and the amount in front of them, and a queue row
// carries none of that. The row's job is to get you there.
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Scale, Snowflake } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { DISPUTE as IDS } from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";
import DataTable from "./console/DataTable";
import { TimeAgo } from "./console/format";
import { CALM, TEXT } from "./console/tokens";

const STATES = [
    { value: "open", label: "Open" },
    { value: "resolved", label: "Resolved" },
    { value: "withdrawn", label: "Withdrawn" },
];

const RAISED_BY = { creator: "Creator", runner: "Runner" };

export default function DisputeQueue() {
    const [state, setState] = useState("open");
    const [data, setData] = useState(null);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: payload } = await api.get("/admin/disputes", {
                params: { state },
            });
            setData(payload);
        } catch (err) {
            notifyError(err, { fallback: "The disputes couldn't load." });
            setData({ disputes: [] });
        }
    }, [state]);

    useEffect(() => {
        load();
    }, [load]);

    const rows = data?.disputes || [];

    const columns = [
        {
            key: "campaign",
            mobile: "primary",
            header: "Campaign",
            sortable: true,
            value: (r) => r.campaign_title || "",
            cell: (r) => (
                <Link
                    to={r.href}
                    data-testid={IDS.row(r.id)}
                    className="truncate hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                >
                    {r.campaign_title || "Untitled"}
                </Link>
            ),
        },
        {
            key: "creator",
            mobile: "meta",
            header: "Creator",
            width: "w-40",
            value: (r) => r.creator?.name || "",
            cell: (r) => (
                <span className="truncate">{r.creator?.name || "—"}</span>
            ),
        },
        {
            key: "raised_by",
            header: "Raised by",
            width: "w-28",
            hideBelow: true,
            cell: (r) => (
                <span className={`${TEXT.meta} text-muted-foreground`}>
                    {RAISED_BY[r.dispute?.raised_by_role] || "—"}
                </span>
            ),
        },
        {
            key: "amount",
            mobile: "trailing",
            header: "Held",
            numeric: true,
            width: "w-28",
            sortable: true,
            value: (r) => r.agreed_amount ?? null,
            cell: (r) => (
                <span className="inline-flex items-center gap-1 tabular-nums">
                    {/* **The freeze, said on the row.** A queue of disputes
                        where you cannot see which ones are holding money is a
                        queue you work in the order it arrived rather than the
                        order it matters. */}
                    {r.payment_frozen && (
                        <Snowflake
                            aria-label="Payment held"
                            className="h-3 w-3 text-sky-300"
                        />
                    )}
                    {typeof r.agreed_amount === "number"
                        ? `₹${r.agreed_amount.toLocaleString("en-IN")}`
                        : "—"}
                </span>
            ),
        },
        {
            key: "raised_at",
            mobile: "meta",
            header: "Raised",
            width: "w-28",
            sortable: true,
            value: (r) => r.dispute?.raised_at || null,
            cell: (r) =>
                r.dispute?.raised_at ? (
                    <TimeAgo iso={r.dispute.raised_at} />
                ) : (
                    <span>—</span>
                ),
        },
        {
            key: "reason",
            header: "Why",
            hideBelow: true,
            cell: (r) => (
                <span className={`block truncate ${TEXT.meta} text-muted-foreground`}>
                    {r.dispute?.reason || "—"}
                </span>
            ),
        },
    ];

    return (
        <div data-testid={IDS.queue} className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
                <Scale className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>Disputes</h1>
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    Every open one is a collaboration frozen and, usually, a payment
                    not going out. Open the row to see what it is about and decide it.
                </p>
            </div>

            <div className="flex flex-wrap gap-2">
                {STATES.map((s) => (
                    <button
                        key={s.value}
                        type="button"
                        aria-pressed={state === s.value}
                        onClick={() => setState(s.value)}
                        className={
                            `rounded border px-3 py-1.5 ${TEXT.meta} uppercase tracking-[0.14em] ${CALM} ` +
                            (state === s.value
                                ? "border-ember-500/40 bg-ember-500/10 text-ember-500"
                                : "border-white/10 text-muted-foreground hover:text-foreground")
                        }
                    >
                        {s.label}
                    </button>
                ))}
            </div>

            {data && rows.length === 0 ? (
                <ListEmptyState
                    Icon={Scale}
                    testid={IDS.empty}
                    emptyTitle={
                        state === "open" ? "Nothing is disputed" : "Nothing here"
                    }
                    emptyBody={
                        state === "open"
                            ? "No collaboration is frozen. Either side can raise one from the application page."
                            : `No ${state} disputes.`
                    }
                />
            ) : (
                <DataTable rows={rows} columns={columns} loading={!data} />
            )}
        </div>
    );
}
