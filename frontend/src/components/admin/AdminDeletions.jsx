// The erasure queue.
//
// Somebody has asked to be forgotten and a person has to decide. **Admin-only,
// and not scoped work**: this is a right being exercised against the whole
// company, not a task belonging to whichever brands somebody runs.
//
// **Irreversible, so the screen is arranged around checking rather than
// clearing.** Every other queue in this console is built for speed — approve,
// next, approve — and that is exactly wrong here. There is no bulk action, the
// erase button opens a confirmation naming the person, and the blocking list
// is re-read on the server at the moment of erasure rather than trusted from
// when the request was made.
import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Trash2, UserX } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { ADMIN_DELETIONS as IDS } from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";
import { ConfirmDialog } from "@/components/admin/dialogs";

import { TimeAgo } from "./console/format";
import { CALM, PANEL, TEXT } from "./console/tokens";

const STATES = [
    { value: "requested", label: "Waiting" },
    { value: "erased", label: "Erased" },
    { value: "declined", label: "Declined" },
    { value: "withdrawn", label: "Taken back" },
];

export default function AdminDeletions() {
    const [state, setState] = useState("requested");
    const [rows, setRows] = useState(null);
    const [dialog, setDialog] = useState({ kind: null });
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get("/admin/deletion-requests", {
                params: { state },
            });
            setRows(data);
        } catch (err) {
            notifyError(err, { fallback: "The erasure queue couldn't load." });
            setRows([]);
        }
    }, [state]);

    useEffect(() => {
        load();
    }, [load]);

    const act = async (row, kind, note) => {
        setBusy(true);
        try {
            await api.post(`/admin/deletion-requests/${row.id}/${kind}`, { note });
            notifySuccess(kind === "erase" ? "Erased" : "Declined — they've been told");
            setDialog({ kind: null });
            await load();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be recorded." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.page} className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
                <UserX className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>Deletion requests</h1>
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    {/* The consequential sentence, on the screen rather than in
                        a doc: what "erased" means here is not "everything
                        vanishes". */}
                    Erasing removes the person and keeps the arithmetic — names,
                    numbers, addresses and payout details go; collaborations, amounts
                    and audit lines stay without them.
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

            {rows && rows.length === 0 ? (
                <ListEmptyState
                    Icon={UserX}
                    testid={IDS.empty}
                    emptyTitle="Nobody is waiting"
                    emptyBody="Requests appear here the moment somebody asks to be deleted."
                />
            ) : (
                <ul className="space-y-3">
                    {(rows || []).map((row) => (
                        <li
                            key={row.id}
                            data-testid={IDS.row(row.id)}
                            className={`${PANEL} p-4`}
                        >
                            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                                <span className="text-sm">{row.name || "Unnamed"}</span>
                                <span className={`${TEXT.meta} text-muted-foreground`}>
                                    {row.role} · asked <TimeAgo value={row.requested_at} />
                                </span>
                            </div>
                            {row.reason && (
                                <p className="mt-2 text-sm text-muted-foreground">
                                    “{row.reason}”
                                </p>
                            )}

                            {/* **Re-read now, not from when they asked.** Work
                                can start in between, and erasing then would
                                leave a brand with a booking against nobody. */}
                            {row.blocking?.length > 0 && (
                                <div
                                    data-testid={IDS.blocked(row.id)}
                                    className="mt-3 rounded border border-amber-500/30 bg-amber-500/10 p-3"
                                >
                                    <p className="flex items-center gap-2 text-sm text-amber-200">
                                        <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />
                                        {row.blocking.length} collaboration
                                        {row.blocking.length === 1 ? "" : "s"} still under way
                                    </p>
                                    <ul className={`mt-2 space-y-1 ${TEXT.meta} text-amber-100/90`}>
                                        {row.blocking.map((b) => (
                                            <li key={b.collaboration_id}>
                                                {b.campaign_title} — {b.state?.replace(/_/g, " ")}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {state === "requested" && (
                                <div className="mt-4 flex flex-wrap gap-2">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        disabled={row.blocking?.length > 0}
                                        onClick={() => setDialog({ kind: "erase", row })}
                                        data-testid={IDS.erase(row.id)}
                                        className="border-destructive/40 bg-transparent text-destructive hover:bg-destructive/10"
                                    >
                                        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                                        Erase
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => setDialog({ kind: "decline", row })}
                                        data-testid={IDS.decline(row.id)}
                                    >
                                        Decline
                                    </Button>
                                </div>
                            )}

                            {row.decision_note && (
                                <p className={`mt-3 ${TEXT.meta} text-muted-foreground`}>
                                    {row.decided_by_name}: {row.decision_note}
                                </p>
                            )}
                        </li>
                    ))}
                </ul>
            )}

            {/* **Irreversible, so it is confirmed by name and demands a
                note.** Every other queue in this console is built for speed;
                this one is deliberately not. The shared dialog always requires
                a reason, which is the right shape here — the server takes it
                as optional on an erasure and required on a decline, and an
                admin who has to type why they are satisfied has looked. */}
            <ConfirmDialog
                open={dialog.kind !== null}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker={dialog.kind === "erase" ? "Erase" : "Decline"}
                title={
                    dialog.kind === "erase"
                        ? `Erase ${dialog.row?.name || "this account"}?`
                        : `Decline ${dialog.row?.name || "this request"}?`
                }
                description={
                    dialog.kind === "erase"
                        ? "Their personal details go for good. The collaborations, amounts and audit lines stay, without them in them. This cannot be undone."
                        : "They're told what you write here. Being refused with no reason is worse than being refused."
                }
                reasonLabel={dialog.kind === "erase" ? "Note" : "Why not"}
                confirmLabel={
                    dialog.kind === "erase" ? "Erase permanently" : "Decline the request"
                }
                destructive={dialog.kind === "erase"}
                submitting={busy}
                onSubmit={({ reason }) => act(dialog.row, dialog.kind, reason)}
            />
        </div>
    );
}
