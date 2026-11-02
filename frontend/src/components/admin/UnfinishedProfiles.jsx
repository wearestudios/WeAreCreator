// Creators who signed up and never finished their profile.
//
// `GET /admin/creators/incomplete` existed with no screen, and so did the door
// to run the onboarding nudge by hand. Not a review queue — nothing here is
// waiting on us — but a nudge list: who stalled, when they joined, whether the
// one WhatsApp reminder has gone, and a way to send the round now rather than
// waiting for the timer.
//
// **The nudge goes once per creator, ever.** The button runs the same function
// the timer calls, under the same claim, so pressing it twice cannot message
// anybody twice. That is what makes it safe to have here at all.
//
// Admin-only: the list is drawn from the global roster, and a creator who has
// not finished a profile has applied to nothing — there is no brand for a
// scoped console to be scoped to.
import React, { useCallback, useEffect, useState } from "react";
import { Loader2, Send, UserRoundPen } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { ListEmptyState } from "@/components/data/DenseView";
import { ADMIN_UNFINISHED as IDS } from "@/constants/testIds";
import DataTable from "./console/DataTable";
import { TimeAgo } from "./console/format";
import { TEXT } from "./console/tokens";
import { CreatorLink } from "./links";

export default function UnfinishedProfiles() {
    const [rows, setRows] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/admin/creators/incomplete");
            setRows(Array.isArray(data) ? data : []);
        } catch (err) {
            notifyError(err, { fallback: "That list couldn't load." });
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const nudge = async () => {
        setBusy(true);
        try {
            const { data } = await api.post("/admin/jobs/creator-nudges");
            const sent = data?.sent ?? 0;
            notifySuccess(
                sent === 1 ? "One reminder sent." : `${sent} reminders sent.`,
            );
            await load();
        } catch (err) {
            notifyError(err, { fallback: "The reminders didn't go." });
        } finally {
            setBusy(false);
        }
    };

    const columns = [
        {
            key: "name",
            mobile: "primary",
            header: "Name",
            sortable: true,
            value: (r) => r.name,
            cell: (r) => <CreatorLink id={r.user_id} name={r.name} className="truncate" />,
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
            key: "phone",
            mobile: "meta",
            header: "WhatsApp",
            width: "w-40",
            cell: (r) => <span className="tabular-nums">{r.phone || "—"}</span>,
        },
        {
            key: "joined",
            mobile: "trailing",
            header: "Joined",
            sortable: true,
            width: "w-32",
            value: (r) => r.created_at || "",
            cell: (r) => (r.created_at ? <TimeAgo iso={r.created_at} /> : <span>—</span>),
        },
    ];

    return (
        <div data-testid={IDS.page} className="space-y-section">
            <div className="flex flex-wrap items-center gap-3">
                <UserRoundPen className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>Unfinished profiles</h1>
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    Signed up and never finished. Each is reminded on WhatsApp once, ever.
                </p>
                <Button
                    size="sm"
                    variant="outline"
                    onClick={nudge}
                    disabled={busy}
                    data-testid={IDS.nudge}
                    className="ml-auto"
                >
                    {busy ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                        <Send className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    Send due reminders now
                </Button>
            </div>

            {rows && rows.length === 0 ? (
                <ListEmptyState
                    Icon={UserRoundPen}
                    testid={IDS.empty}
                    emptyTitle="Nobody is stuck"
                    emptyBody="Every creator who signed up has finished their profile."
                />
            ) : (
                <DataTable
                    rows={(rows || []).map((r) => ({ ...r, id: r.user_id }))}
                    columns={columns}
                    loading={!rows}
                    rowTestId={(r) => IDS.row(r.id)}
                />
            )}
        </div>
    );
}
