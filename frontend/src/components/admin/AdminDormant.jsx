// Who has gone quiet.
//
// The intelligence panel already counted these and named nobody, which is the
// difference between knowing there is a problem and being able to do something
// about it: "48 dormant creators" is a fact you cannot act on, and a list with
// a last-active date beside each name is a morning's work.
//
// **Two lists rather than one**, because the message is different. A brand
// that has not briefed in two months is a sales conversation; a creator who
// has not worked in two months is a supply one, and mixing them gives whoever
// is working the list two jobs on one screen.
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MoonStar } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { ADMIN_DORMANT as IDS } from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";
import DataTable from "./console/DataTable";
import { TimeAgo } from "./console/format";
import { CALM, TEXT } from "./console/tokens";
import { formatCompact } from "./shared";

const KINDS = [
    { value: "brands", label: "Brands" },
    { value: "creators", label: "Creators" },
];

export default function AdminDormant() {
    const [kind, setKind] = useState("brands");
    const [data, setData] = useState(null);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: payload } = await api.get("/admin/dormant", { params: { kind } });
            setData(payload);
        } catch (err) {
            notifyError(err, { fallback: "That list couldn't load." });
            setData({});
        }
    }, [kind]);

    useEffect(() => {
        load();
    }, [load]);

    const rows = (data?.[kind] || []).map((r) => ({ ...r, id: r.id }));

    const columns = [
        {
            key: "name",
            mobile: "primary",
            header: "Name",
            sortable: true,
            value: (r) => r.name,
            cell: (r) => (
                <Link
                    to={r.href}
                    data-testid={IDS.row(r.id)}
                    className="truncate hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                >
                    {r.name}
                </Link>
            ),
        },
        {
            key: "reference",
            header: "Ref",
            width: "w-24",
            hideBelow: true,
            cell: (r) => (
                <span className={`${TEXT.meta} text-muted-foreground`}>{r.reference || "—"}</span>
            ),
        },
        {
            key: "detail",
            mobile: "meta",
            header: kind === "brands" ? "Category" : "Reach",
            width: "w-32",
            cell: (r) =>
                kind === "brands"
                    ? r.category || "—"
                    : r.follower_count != null
                    ? formatCompact(r.follower_count)
                    : "—",
        },
        {
            key: "quiet",
            mobile: "trailing",
            header: "Quiet for",
            sortable: true,
            numeric: true,
            width: "w-32",
            // **Never active sorts first, not last.** A brand we verified and
            // never heard from again got stuck somewhere and nobody found out,
            // which is the strongest signal on this list rather than the
            // weakest — the opposite of how an unknown sorts in a data column.
            value: (r) => (r.never_active ? Number.MAX_SAFE_INTEGER : r.days_quiet ?? 0),
            cell: (r) =>
                r.never_active ? (
                    <span className="text-amber-300">Never</span>
                ) : (
                    <span className="tabular-nums">{r.days_quiet}d</span>
                ),
        },
        {
            key: "last",
            header: "Last active",
            width: "w-32",
            hideBelow: true,
            cell: (r) =>
                r.last_active_at ? <TimeAgo iso={r.last_active_at} /> : <span>—</span>,
        },
    ];

    return (
        <div data-testid={IDS.page} className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
                <MoonStar className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>Gone quiet</h1>
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    Nothing in {data?.window_days ?? 60} days. Longest first, and anybody who
                    never started at the top — that is somebody who got stuck.
                </p>
            </div>

            <div className="flex flex-wrap gap-2">
                {KINDS.map((k) => (
                    <button
                        key={k.value}
                        type="button"
                        aria-pressed={kind === k.value}
                        onClick={() => setKind(k.value)}
                        data-testid={IDS.tab(k.value)}
                        className={
                            `rounded border px-3 py-1.5 ${TEXT.meta} uppercase tracking-[0.14em] ${CALM} ` +
                            (kind === k.value
                                ? "border-ember-500/40 bg-ember-500/10 text-ember-500"
                                : "border-white/10 text-muted-foreground hover:text-foreground")
                        }
                    >
                        {k.label}
                        {data?.[`${k.value}_total`] != null && kind === k.value ? (
                            <span data-testid={IDS.count(k.value)} className="ml-2">
                                {data[`${k.value}_total`]}
                            </span>
                        ) : null}
                    </button>
                ))}
            </div>

            {data && rows.length === 0 ? (
                <ListEmptyState
                    Icon={MoonStar}
                    testid={IDS.empty}
                    emptyTitle="Everybody is active"
                    emptyBody={`No ${kind} have been quiet for ${data.window_days} days.`}
                />
            ) : (
                <DataTable
                    rows={rows}
                    columns={columns}
                    loading={!data}
                    rowTestId={(r) => IDS.row(r.id)}
                />
            )}
        </div>
    );
}
