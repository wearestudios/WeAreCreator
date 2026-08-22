// What a brand owes us, and the one way past the block it causes.
//
// **Money owed stops new work, not work under way.** A brand with three unpaid
// invoices posting a fourth brief is the arrangement that ends with creators
// unpaid for work somebody was never billed for. Campaigns already running are
// untouched: the creators on them did nothing wrong, and punishing them for
// the brand's accounts payable would be the one outcome worse than the debt.
//
// **The override exists because the block has a false positive.** An invoice
// is overdue because a brand is not paying, or because our own accounts sent
// it to the wrong address — and blocking a good client over the second is
// worse than the problem the block solves. So it is admin-only, it demands a
// reason, and the reason is shown back with who granted it and when: an
// override nobody can revisit is one that quietly becomes permanent.
import React, { useState } from "react";
import { Loader2, ShieldOff } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { INVOICE as IDS } from "@/constants/testIds";
import { formatDateTime } from "@/lib/time";
import { TEXT } from "./console/tokens";

export default function BrandInvoices({ userId, owing, override, onChanged }) {
    const [asking, setAsking] = useState(false);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);

    const active = Boolean(override?.active);

    const set = async (on) => {
        setBusy(true);
        try {
            await api.post(`/admin/brands/${userId}/invoice-override`, {
                active: on,
                // The clear still carries a reason because the route requires
                // one — and "why we put the block back" is as worth recording
                // as why we lifted it.
                reason: on ? reason.trim() : "Override cleared",
            });
            notifySuccess(on ? "They can post again" : "Override cleared");
            setAsking(false);
            setReason("");
            onChanged?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be saved." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="space-y-4">
            {owing ? (
                <p
                    data-testid={IDS.overdue}
                    className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm"
                >
                    {owing.count} invoice{owing.count === 1 ? "" : "s"} past due — ₹
                    {Number(owing.total || 0).toLocaleString("en-IN")}, the oldest{" "}
                    {owing.worst_days} day{owing.worst_days === 1 ? "" : "s"} over.
                    {active
                        ? " They can still post: an override is on."
                        : " They cannot publish new campaigns until this is settled."}
                </p>
            ) : (
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    Nothing overdue. Invoices are marked issued and paid on each
                    collaboration's own page.
                </p>
            )}

            {active && (
                <div className="rounded-md border border-white/10 bg-card p-4">
                    <p className="flex items-center gap-2 text-sm">
                        <ShieldOff aria-hidden="true" className="h-3.5 w-3.5 text-amber-300" />
                        Override on
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
                        {override.reason}
                    </p>
                    <p className={`mt-1 ${TEXT.meta} text-muted-foreground`}>
                        {override.by_name || "Somebody"}
                        {override.at ? ` · ${formatDateTime(override.at)}` : ""}
                    </p>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => set(false)}
                        disabled={busy}
                        data-testid={IDS.overrideClear}
                        className="mt-3 min-h-[2.75rem] border-white/20 bg-transparent sm:min-h-0"
                    >
                        {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                        Put the block back
                    </Button>
                </div>
            )}

            {/* Absent rather than disabled where there is nothing to override:
                a greyed button on a brand that owes nothing is a question
                nobody can answer. */}
            {!active && owing && !asking && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setAsking(true)}
                    data-testid={IDS.override}
                    className="min-h-[2.75rem] border-white/20 bg-transparent sm:min-h-0"
                >
                    Let them post anyway
                </Button>
            )}

            {asking && (
                <div className="space-y-2">
                    <Textarea
                        rows={2}
                        maxLength={500}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Why. e.g. Invoice went to the wrong address, resent today."
                        data-testid={IDS.overrideReason}
                        className="rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                    />
                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            onClick={() => set(true)}
                            disabled={busy || !reason.trim()}
                            data-testid={IDS.overrideSubmit}
                            className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                        >
                            {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            Lift the block
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setAsking(false)}>
                            Cancel
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
