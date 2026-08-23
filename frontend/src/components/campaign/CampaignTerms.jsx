// The two things a creator has to know before applying, and the one they
// have to accept after.
//
// **Both were nowhere.** A creator applied not knowing whether a reel would be
// reposted once or run as a paid ad for a year — very different pieces of work
// at very different prices, and the single most common thing to argue about
// after delivery. And nothing on the brief said the post had to carry a
// disclosure at all, on a platform where ASCI liability sits with the
// advertiser rather than only with the creator.
//
// Every value here is decided server-side (`_usage_block`,
// `_required_disclosure`) — the components render what they are given and work
// nothing out, so the brief, the application page and the frozen terms cannot
// phrase the same grant three ways.
import React, { useEffect, useState } from "react";
import { Check, FileText, Loader2, Megaphone, ShieldCheck } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { TERMS as IDS } from "@/constants/testIds";
import { formatDate } from "@/lib/time";

/**
 * What the post must say and what the brand may do with it, on the brief.
 *
 * Renders on every campaign — there is no brief here without a material
 * connection, so there is none without a disclosure.
 */
export function BriefTerms({ disclosure, usage }) {
    if (!disclosure && !usage) return null;
    return (
        <div
            data-testid={IDS.brief}
            className="grid gap-3 sm:grid-cols-2"
        >
            {disclosure && (
                <div className="rounded-md border border-white/10 bg-card/60 p-4">
                    <p className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        <Megaphone aria-hidden="true" className="h-3.5 w-3.5" />
                        Must carry
                    </p>
                    <p
                        data-testid={IDS.disclosure}
                        className="mt-2 text-sm leading-relaxed text-foreground"
                    >
                        {disclosure.label}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        Up front in the post itself, not in the comments.
                    </p>
                </div>
            )}
            {usage && (
                <div className="rounded-md border border-white/10 bg-card/60 p-4">
                    <p className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        <ShieldCheck aria-hidden="true" className="h-3.5 w-3.5" />
                        Usage rights
                    </p>
                    <p
                        data-testid={IDS.usage}
                        className="mt-2 text-sm leading-relaxed text-foreground"
                    >
                        {usage.text}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        {usage.kind === "organic_only"
                            ? "They can repost it. Running it as an ad needs a separate agreement."
                            : usage.kind === "full_buyout"
                            ? "They own the content outright once it's approved."
                            : "Paid promotion is included for the period above, then it lapses."}
                    </p>
                </div>
            )}
        </div>
    );
}

/** One labelled line inside the terms card. */
function Line({ label, children, testId }) {
    if (!children) return null;
    return (
        <div className="border-t border-white/10 pt-3 first:border-0 first:pt-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {label}
            </p>
            <p data-testid={testId} className="mt-1 text-sm leading-relaxed">
                {children}
            </p>
        </div>
    );
}

/**
 * The frozen terms, and the creator's one tap.
 *
 * **The same card for all three parties**, for the same reason the dispute
 * panel is: a mediation where each side is reading its own version of the
 * terms is the argument rather than the resolution. Only the creator gets the
 * button, and only while it is unaccepted — `canAccept` is passed in rather
 * than worked out here, so this never asks what role is looking.
 */
export function TermsCard({ terms, collabId, canAccept = false, onAccepted }) {
    const [busy, setBusy] = useState(false);
    if (!terms) return null;

    const accept = async () => {
        setBusy(true);
        try {
            await api.post(`/creator/collaborations/${collabId}/accept-terms`);
            notifySuccess("Terms accepted");
            onAccepted?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be recorded." });
        } finally {
            setBusy(false);
        }
    };

    const dates = [terms.event_date, terms.start_date, terms.end_date]
        .filter(Boolean)
        .map(formatDate);

    return (
        <section
            data-testid={IDS.card}
            className="rounded-md border border-white/10 bg-card p-5 grain-surface sm:p-6"
        >
            <p className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-ember-500">
                <FileText aria-hidden="true" className="h-4 w-4" />
                What was agreed
            </p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                Frozen when this was accepted on {formatDate(terms.issued_at)}. The
                campaign can be edited afterwards; this cannot.
            </p>

            <div className="mt-4 space-y-3">
                <Line label="Deliverables" testId={IDS.deliverables}>
                    {terms.deliverables}
                </Line>
                <Line label="Dates" testId={IDS.dates}>
                    {terms.scheduled_at
                        ? formatDate(terms.scheduled_at)
                        : dates.join(" – ") || null}
                </Line>
                {/* An amount or a barter description — never a zero, which on
                    a barter row reads as "agreed, nothing". */}
                <Line label="Fee" testId={IDS.money}>
                    {terms.money?.description}
                </Line>
                <Line label="Usage rights" testId={IDS.termsUsage}>
                    {terms.usage?.text}
                </Line>
                <Line label="Disclosure" testId={IDS.termsDisclosure}>
                    {terms.disclosure?.label}
                </Line>
                <Line label="If it's called off" testId={IDS.cancellation}>
                    {terms.cancellation_terms}
                </Line>
            </div>

            {terms.accepted ? (
                <p
                    data-testid={IDS.accepted}
                    className="mt-5 flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200"
                >
                    <Check aria-hidden="true" className="h-4 w-4 flex-none" />
                    Accepted by the creator on {formatDate(terms.accepted_at)}.
                </p>
            ) : canAccept ? (
                <div className="mt-5">
                    <Button
                        onClick={accept}
                        disabled={busy}
                        data-testid={IDS.acceptBtn}
                        className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600"
                    >
                        {busy && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                        I agree to these terms
                    </Button>
                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                        One tap, timestamped. It records that you read this — anything
                        you want changed is a message to whoever runs the campaign.
                    </p>
                </div>
            ) : (
                <p
                    data-testid={IDS.awaiting}
                    className="mt-5 text-xs uppercase tracking-[0.15em] text-muted-foreground"
                >
                    Waiting for the creator to accept
                </p>
            )}
        </section>
    );
}

/**
 * Who confirmed the disclosure was actually on the post, at each review point.
 *
 * `null` at a stage means it has not been reviewed yet, which is why nothing
 * renders for it — a red cross on every draft nobody has looked at yet is a
 * warning people learn to ignore.
 */
export function DisclosureChecks({ disclosure }) {
    const rows = [
        ["At draft review", disclosure?.draft_check],
        ["At the live post", disclosure?.content_check],
    ].filter(([, row]) => row);
    if (!rows.length) return null;
    return (
        <div data-testid={IDS.checks} className="space-y-1.5">
            {rows.map(([label, row]) => (
                <p
                    key={label}
                    className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground"
                >
                    <Check aria-hidden="true" className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="uppercase tracking-[0.15em]">{label}</span>
                    <span className="text-foreground/80">
                        {row.label} confirmed by {row.confirmed_by_name || "a reviewer"}
                        {row.confirmed_at ? ` on ${formatDate(row.confirmed_at)}` : ""}
                    </span>
                </p>
            ))}
        </div>
    );
}

/**
 * The second disclosure checkpoint: the live post, before it is signed off.
 *
 * **It lives here rather than on the brand's applicant board**, which is
 * where it was written. `_refuse_unconfirmed_disclosure` is on
 * `brand_approve_content`, so every console that can approve content has to
 * ask this — and the shared application screen, which the admin and the
 * manager open, would otherwise have had a second copy of the question or,
 * worse, an Approve button the route refuses.
 *
 * The box arrives unticked and the confirm is disabled until it is not. A box
 * that arrives ticked is a box nobody read, which is the one thing this
 * checkpoint is for.
 */
export function DisclosureConfirmDialog({ open, onOpenChange, label, busy, onConfirm }) {
    const [ok, setOk] = useState(false);
    useEffect(() => {
        if (open) setOk(false);
    }, [open]);
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid="approve-content-dialog"
                className="max-w-md rounded-md border border-white/10 bg-card"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Approve the content
                    </p>
                    <DialogTitle className="mt-2 font-serif text-fluid-2xl leading-tight">
                        One check before you sign this off
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm text-muted-foreground">
                        Approving releases payment, and nobody looks at the post
                        again afterwards.
                    </DialogDescription>
                </DialogHeader>
                <label
                    data-testid="approve-content-disclosure-check"
                    className="flex cursor-pointer items-start gap-3 rounded-md border border-white/10 bg-background/60 p-4 text-sm leading-relaxed"
                >
                    <input
                        type="checkbox"
                        checked={ok}
                        onChange={(e) => setOk(e.target.checked)}
                        className="mt-0.5 h-4 w-4 flex-none accent-[color:var(--ember-500,#F05D14)]"
                    />
                    <span>
                        I've checked the live post carries{" "}
                        <span className="text-foreground">
                            {label || "the required disclosure"}
                        </span>
                        , up front rather than in the comments.
                    </span>
                </label>
                <DialogFooter className="flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                    <Button variant="ghost" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={onConfirm}
                        disabled={!ok || busy}
                        data-testid="approve-content-confirm"
                        className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                    >
                        {busy && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                        Approve
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}


export default TermsCard;
