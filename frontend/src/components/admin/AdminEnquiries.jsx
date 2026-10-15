// Enquiries from the public contact form.
//
// **Admin-only, not `CONSOLE_ROLES`.** An enquiry is attached to no brand and
// no campaign, so there is nothing for a scoped console to be scoped *to* —
// narrowing it would return an empty list rather than a smaller one. The same
// line `ADMIN_ONLY_EXPORTS` draws, and the reason the survey and the global
// creator directory are admin-only too.
//
// **The message body goes in a peek, not a detail page.** Working this is
// "read, act, next", and a full-page round trip per row loses the sort, the
// scroll and the place in the list. There is no detail page to open, so the
// peek deliberately offers no "Open full page" link — one that went nowhere
// would be worse than none.
import React, { useCallback, useEffect, useState } from "react";
import { Mail, MessageCircle } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { useOptimisticRows } from "@/lib/useOptimistic";
import { ENQUIRIES as IDS } from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";
import { Button } from "@/components/ui/button";
import DataTable from "./console/DataTable";
import { PeekPanel } from "./console/PeekPanel";
import { ConfirmDialog } from "./dialogs";
import { TimeAgo } from "./console/format";
import { StatusTag } from "./console/StatusTag";
import { TEXT } from "./console/tokens";

const ROLE_LABEL = { brand: "Brand", creator: "Creator", other: "Other" };

export default function AdminEnquiries({ onChanged }) {
    const [data, setData] = useState(null);
    const [peek, setPeek] = useState(null);
    const [confirming, setConfirming] = useState(null);
    // **`useOptimisticRows`, not `useOptimisticAction`.** A row in a list is
    // what the first one is for: it keys the patch, the pending flag and the
    // failed flash by row id, drops a patch when a refetch covers it, and
    // clears the flash after `ROLLBACK_FLASH_MS`. The single-control version
    // has one flag for the whole table, so a failure could not flash the row
    // it belonged to — hand-rolling that on top of it was a worse copy of
    // this, and a browser check caught the flash never firing.
    const { rows, pending, failed, apply } = useOptimisticRows(data?.enquiries || []);

    const load = useCallback(async () => {
        try {
            const { data: d } = await api.get("/admin/contact-enquiries", {
                params: { limit: 100 },
            });
            setData(d);
        } catch (err) {
            notifyError(err);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    async function markHandled(row, note) {
        // The row shows the new value before the server confirms, because the
        // overwhelming majority succeed and optimising for the failure makes
        // every success feel slow. A failure rolls the patch back **and**
        // flashes the row — somebody who watched it change and looked away
        // believes it changed.
        const ok = await apply(
            row.id,
            { handled_at: new Date().toISOString() },
            () =>
                api.post(`/admin/contact-enquiries/${row.id}/handled`, {
                    note: note || null,
                }),
            { onError: notifyError },
        );
        if (ok) {
            onChanged?.();
            load();
        }
    }

    const columns = [
        {
            key: "name",
            mobile: "primary",
            header: "From",
            sortable: true,
            value: (r) => r.name || "",
            cell: (r) => (
                <button
                    type="button"
                    data-testid={IDS.row(r.id)}
                    onClick={() => setPeek(r)}
                    className="truncate text-left hover:text-primary-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                    {r.name || "Unnamed"}
                </button>
            ),
        },
        {
            key: "role",
            mobile: "meta",
            header: "Who",
            width: "w-28",
            value: (r) => ROLE_LABEL[r.role] || "Other",
            cell: (r) => <span>{ROLE_LABEL[r.role] || "Other"}</span>,
        },
        {
            key: "whatsapp",
            mobile: "meta",
            header: "WhatsApp",
            width: "w-40",
            value: (r) => r.whatsapp || "",
            cell: (r) => (
                <a
                    href={`https://wa.me/${(r.whatsapp || "").replace(/\D/g, "")}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 truncate hover:text-primary-ink"
                >
                    <MessageCircle className="h-3.5 w-3.5" />
                    {r.whatsapp}
                </a>
            ),
        },
        {
            key: "message",
            header: "Message",
            width: "w-80",
            value: (r) => r.message || "",
            cell: (r) => (
                <span className="truncate text-muted-foreground">{r.message}</span>
            ),
        },
        {
            key: "created",
            mobile: "meta",
            header: "When",
            width: "w-28",
            sortable: true,
            value: (r) => r.created_at || "",
            cell: (r) => <TimeAgo iso={r.created_at} />,
        },
        {
            key: "state",
            mobile: "trailing",
            header: "State",
            width: "w-28",
            value: (r) => (r.handled_at ? 1 : 0),
            cell: (r) =>
                r.handled_at ? (
                    <StatusTag state="closed" label="Handled" />
                ) : (
                    <StatusTag state="pending_review" label="Waiting" />
                ),
        },
        {
            key: "act",
            mobile: "action",
            header: "",
            width: "w-32",
            cell: (r) =>
                r.handled_at ? null : (
                    <Button
                        size="sm"
                        variant="outline"
                        data-testid={IDS.handle(r.id)}
                        disabled={Boolean(pending[r.id])}
                        onClick={() => setConfirming(r)}
                    >
                        Mark handled
                    </Button>
                ),
        },
    ];

    return (
        <section data-testid={IDS.section}>
            <div className="mb-4">
                <p className={`${TEXT.eyebrow} uppercase tracking-[0.2em] text-muted-foreground`}>
                    Enquiries
                </p>
                <h2 className="mt-1 font-serif text-fluid-2xl leading-tight">
                    From the contact form
                </h2>
            </div>

            {data && !rows.length ? (
                <ListEmptyState
                    title="Nothing yet"
                    line="Messages sent through the contact page land here."
                />
            ) : (
                <DataTable
                    rows={rows}
                    columns={columns}
                    loading={!data}
                    rowTestId={(r) => IDS.rowRoot(r.id)}
                    // Destructive, never ember: ember is the primary action in
                    // this console and a row wearing it reads as something to
                    // press rather than something that just failed.
                    rowClass={(r) => (failed[r.id] ? "bg-destructive/10" : "")}
                />
            )}

            <PeekPanel
                open={Boolean(peek)}
                onOpenChange={(v) => !v && setPeek(null)}
                title={peek?.name || ""}
                subtitle={peek ? `${ROLE_LABEL[peek.role] || "Other"} · ${peek.whatsapp}` : ""}
                testid={IDS.peek}
            >
                {peek ? (
                    <div className="space-y-4">
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                            {peek.message}
                        </p>
                        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
                            <a
                                href={`https://wa.me/${(peek.whatsapp || "").replace(/\D/g, "")}`}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-sm hover:border-primary/60"
                            >
                                <MessageCircle className="h-4 w-4" />
                                Reply on WhatsApp
                            </a>
                            {peek.email ? (
                                <a
                                    href={`mailto:${peek.email}`}
                                    className="inline-flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-sm hover:border-primary/60"
                                >
                                    <Mail className="h-4 w-4" />
                                    {peek.email}
                                </a>
                            ) : null}
                        </div>
                        {peek.handled_note ? (
                            <p className="text-sm text-muted-foreground">
                                Note: {peek.handled_note}
                            </p>
                        ) : null}
                    </div>
                ) : null}
            </PeekPanel>

            {/* `onSubmit`, not `onConfirm`, and the dialog takes no testid —
                its own root carries one. Caught in a browser: with the wrong
                prop name the dialog rendered, the button pressed and nothing
                happened at all. */}
            <ConfirmDialog
                open={Boolean(confirming)}
                onOpenChange={(v) => !v && setConfirming(null)}
                title="Mark this enquiry handled?"
                description="Optionally note what was done about it."
                reasonLabel="Note"
                confirmLabel="Mark handled"
                requireReason={false}
                submitting={Boolean(pending[confirming?.id])}
                onSubmit={async ({ reason } = {}) => {
                    const row = confirming;
                    setConfirming(null);
                    if (row) await markHandled(row, reason);
                }}
            />
        </section>
    );
}
