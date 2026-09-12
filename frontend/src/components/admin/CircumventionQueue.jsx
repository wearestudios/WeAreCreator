// Work that went off-platform, flagged and waiting on somebody here.
//
// **The decision is made on this screen and not on the collaboration's page**,
// which is the opposite of the dispute queue beside it — and deliberately. A
// dispute is decided from the pitch, the notes, the delivery and the amount,
// none of which a row carries. This is decided from what was reported and by
// whom, both of which are on the row; opening the collaboration adds nothing,
// and the link is there for the times it does.
//
// Confirming suspends the creator, so it is confirmed and it costs a note.
// Dismissing costs one too: "we looked and it was nothing" is a finding, and
// it is the one most likely to be asked about later, because nothing visible
// happens as a result of it.
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { CIRCUMVENTION as IDS } from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";
import { Button } from "@/components/ui/button";
import DataTable from "./console/DataTable";
import { ConfirmDialog } from "./dialogs";
import { TimeAgo } from "./console/format";
import { CALM, TEXT } from "./console/tokens";

const STATES = [
    { value: "open", label: "Open" },
    { value: "confirmed", label: "Confirmed" },
    { value: "dismissed", label: "Dismissed" },
];

// **Both routes spelled out rather than interpolated.** A path built as
// `/${action}` is a path no grep can find, and this repository's tests look
// for exactly that — a route with no caller is how the manager router grew
// five endpoints nothing could reach.
const DECIDE = {
    confirm: (id) => `/admin/circumvention-reports/${id}/confirm`,
    dismiss: (id) => `/admin/circumvention-reports/${id}/dismiss`,
};

export default function CircumventionQueue() {
    const [state, setState] = useState("open");
    const [data, setData] = useState(null);
    // { id, action } — the row being decided, and which way.
    const [deciding, setDeciding] = useState(null);

    const load = useCallback(async () => {
        setData(null);
        try {
            const { data: payload } = await api.get("/admin/circumvention-reports", {
                params: { state },
            });
            setData(payload);
        } catch (err) {
            notifyError(err, { fallback: "The reports couldn't load." });
            setData({ reports: [] });
        }
    }, [state]);

    useEffect(() => {
        load();
    }, [load]);

    const rows = data?.reports || [];

    const decide = async (note) => {
        const { id, action } = deciding;
        try {
            await api.post(DECIDE[action](id), { note });
            notifySuccess(
                action === "confirm"
                    ? "Upheld. The creator's account is on hold."
                    : "Dismissed. Nothing happens to the creator.",
            );
            setDeciding(null);
            load();
        } catch (err) {
            notifyError(err, { fallback: "That didn't go through." });
        }
    };

    const columns = [
        {
            key: "creator",
            mobile: "primary",
            header: "Creator",
            sortable: true,
            value: (r) => r.creator_name || "",
            cell: (r) => (
                <Link
                    to={`/admin/creators/${r.creator_id}`}
                    data-testid={IDS.row(r.id)}
                    className="truncate hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                >
                    {r.creator_name || "Unnamed"}
                </Link>
            ),
        },
        {
            key: "campaign",
            mobile: "meta",
            header: "Campaign",
            width: "w-48",
            value: (r) => r.campaign_title || "",
            cell: (r) => (
                <Link
                    to={`/admin/applications/${r.collaboration_id}`}
                    className="truncate text-muted-foreground hover:text-ember-500"
                >
                    {r.campaign_title || "Untitled"}
                </Link>
            ),
        },
        {
            key: "reason",
            mobile: "meta",
            header: "What happened",
            width: "w-56",
            value: (r) => r.reason_label || "",
            cell: (r) => <span className="truncate">{r.reason_label || "—"}</span>,
        },
        {
            key: "evidence",
            header: "Reported",
            hideBelow: true,
            cell: (r) => (
                <span className={`block truncate ${TEXT.meta} text-muted-foreground`}>
                    {r.evidence}
                </span>
            ),
        },
        {
            key: "by",
            header: "By",
            width: "w-32",
            hideBelow: true,
            cell: (r) => (
                <span className={`${TEXT.meta} text-muted-foreground`}>
                    {r.reported_by_name || "—"}
                </span>
            ),
        },
        {
            key: "created_at",
            mobile: "meta",
            header: "Flagged",
            width: "w-24",
            sortable: true,
            value: (r) => r.created_at || null,
            cell: (r) => (r.created_at ? <TimeAgo iso={r.created_at} /> : <span>—</span>),
        },
        // The decision, and only where there is one to make. A confirmed or
        // dismissed row is a record, not a queue item.
        ...(state === "open"
            ? [
                  {
                      key: "decide",
                      mobile: "action",
                      header: "",
                      width: "w-48",
                      cell: (r) => (
                          <div className="flex gap-2">
                              <Button
                                  size="sm"
                                  variant="outline"
                                  data-testid={IDS.confirm(r.id)}
                                  onClick={() => setDeciding({ id: r.id, action: "confirm" })}
                              >
                                  Uphold
                              </Button>
                              <Button
                                  size="sm"
                                  variant="ghost"
                                  data-testid={IDS.dismiss(r.id)}
                                  onClick={() => setDeciding({ id: r.id, action: "dismiss" })}
                              >
                                  Dismiss
                              </Button>
                          </div>
                      ),
                  },
              ]
            : [
                  {
                      key: "decision",
                      mobile: "meta",
                      header: "Decision",
                      width: "w-56",
                      cell: (r) => (
                          <span className={`block truncate ${TEXT.meta} text-muted-foreground`}>
                              {r.decided_by_name ? `${r.decided_by_name}: ` : ""}
                              {r.decision_note || "—"}
                          </span>
                      ),
                  },
              ]),
    ];

    return (
        <div data-testid={IDS.queue} className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
                <ShieldAlert className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>Off-platform</h1>
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    Collaborations somebody has flagged as having been taken off the
                    platform. Nothing has happened to any of these creators yet —
                    upholding one suspends their account.
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
                    Icon={ShieldAlert}
                    testid={IDS.empty}
                    emptyTitle={
                        state === "open" ? "Nothing is flagged" : "Nothing here"
                    }
                    emptyBody={
                        state === "open"
                            ? "Nobody has reported a collaboration as off-platform. A brand, a campaign manager or an admin can flag one from the application page."
                            : `No ${state} reports.`
                    }
                />
            ) : (
                <DataTable rows={rows} columns={columns} loading={!data} />
            )}

            <ConfirmDialog
                open={Boolean(deciding)}
                onOpenChange={(v) => !v && setDeciding(null)}
                title={
                    deciding?.action === "confirm"
                        ? "Uphold this report?"
                        : "Dismiss this report?"
                }
                description={
                    deciding?.action === "confirm"
                        ? "This suspends the creator's account and records the reason against it. Their collaborations, ratings and payments are all kept — nothing is deleted. They can be reinstated afterwards, but the confirmation stays on their record and keeps them off the homepage permanently."
                        : "The report is closed and nothing happens to the creator. Say what you found — a dismissal nobody can read is one somebody will raise again next week."
                }
                confirmLabel={deciding?.action === "confirm" ? "Uphold and suspend" : "Dismiss"}
                destructive={deciding?.action === "confirm"}
                // Required on both, which is the dialog's default. A
                // confirmation ends an account; a dismissal clears somebody of
                // something. Neither is a decision anybody should be able to
                // make without saying why.
                reasonLabel={
                    deciding?.action === "confirm"
                        ? "What you decided, and on what"
                        : "What you found"
                }
                onSubmit={({ reason }) => decide(reason)}
            />
        </div>
    );
}
