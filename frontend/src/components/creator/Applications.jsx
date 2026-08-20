// Applications: waiting, and not this time.
//
// Two lists rather than one, because they are read in completely different
// moods. The declined list is deliberately quiet — a brand picking somebody
// else is not a verdict on the creator, and a red row implying otherwise is
// the fastest way to lose one. It ends with somewhere to go next.
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Hourglass, X } from "lucide-react";
import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import BrandAvatar from "@/components/BrandAvatar";
import AgeBadge from "@/components/AgeBadge";
import Shortfall from "@/components/Shortfall";
import { SHORTFALL } from "@/constants/testIds";
import Invitations from "./Invitations";
import { CREATOR_APPLICATIONS as IDS } from "@/constants/testIds";
import {
    CAT_LABEL,
    EmptyState,
    Money,
    SectionHead,
    StatePill,
    formatDate,
    formatRupees,
} from "./shared";

// Up to acceptance, which is the same line the server draws. After that a
// change of mind is a cancellation — there is a venue booked and a commitment
// on both sides — and the button is absent rather than present and refused.
const WITHDRAWABLE = new Set(["applied", "verified"]);

const Row = ({ row, testid, muted, onWithdraw }) => (
    <li
        data-testid={testid}
        className="flex flex-col gap-3 px-5 py-5 sm:flex-row sm:items-center sm:gap-6 sm:px-6"
    >
        <Link
            to={`/campaigns/${row.campaign_id}`}
            className="group min-w-0 flex-1"
        >
            <span className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                <BrandAvatar brand={row} size="h-5 w-5" />
                <span className="truncate">
                    {row.brand_name || "Brand"}
                    {row.area ? ` · ${row.area}` : ""}
                    {row.category ? ` · ${CAT_LABEL[row.category] || row.category}` : ""}
                </span>
            </span>
            <span
                className={
                    "mt-1 block truncate font-serif text-lg leading-tight transition-colors duration-200 group-hover:text-ember-500 " +
                    (muted ? "text-muted-foreground" : "")
                }
            >
                {row.campaign_title || "Untitled campaign"}
            </span>
            <span className="mt-2 block text-xs text-muted-foreground">
                Applied {formatDate(row.created_at)}
            </span>
            {row.exit_reason && (
                <span
                    data-testid={IDS.note(row.id)}
                    className="mt-2 block text-xs leading-relaxed text-muted-foreground"
                >
                    {row.exit_reason}
                </span>
            )}
        </Link>

        <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end">
            <Money symbolClass="h-3.5 w-3.5" className="font-serif text-xl leading-none">
                {formatRupees(row.agreed_amount ?? row.quoted_rate)}
            </Money>
            <StatePill state={row.state} testid={IDS.state(row.id)} />
            {/* **The age, and no verdict.** The server sends this row no SLA
                target on purpose: an SLA is the standard WeAre holds itself
                to internally, not a promise made to the creator, and telling
                them "the brand is 4 days over" would turn one into the other.
                How long they have been waiting is simply a fact, and a useful
                one. */}
            <AgeBadge ageing={row.ageing} testid={IDS.ageing(row.id)} />
            {/* **Said to them, and not only to the brand.** A shortfall is a
                judgement about the creator, and finding out from a smaller
                payment than expected is the version of this that costs
                somebody. */}
            <Shortfall shortfall={row.shortfall} testid={SHORTFALL.block(row.id)} />
            {onWithdraw && WITHDRAWABLE.has(row.state) && (
                <button
                    type="button"
                    onClick={() => onWithdraw(row)}
                    data-testid={IDS.withdraw(row.id)}
                    className="inline-flex min-h-[2.75rem] items-center gap-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-foreground sm:min-h-0"
                >
                    <X className="h-3.5 w-3.5" />
                    Withdraw
                </button>
            )}
        </div>
    </li>
);

/**
 * Taking an application back.
 *
 * **The exit the creator did not have.** Every other way out was somebody
 * else's move, so a creator who had changed their mind could only go quiet —
 * and a brand then shortlisted somebody who was never going to turn up.
 *
 * The reason is required because it is the half that makes this actionable for
 * whoever runs the campaign: "one of your three applicants is gone" is not
 * something anybody can do anything with on its own.
 */
function WithdrawDialog({ row, onClose, onDone }) {
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (row) {
            setReason("");
            setError("");
        }
    }, [row]);

    const submit = async () => {
        if (reason.trim().length < 3) {
            setError("A line is enough — it goes to whoever is running the campaign.");
            return;
        }
        setBusy(true);
        try {
            await api.post(`/creator/collaborations/${row.id}/withdraw`, {
                reason: reason.trim(),
            });
            notifySuccess("Withdrawn — they've been told");
            onClose();
            await onDone?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be withdrawn." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open={Boolean(row)} onOpenChange={(v) => !v && onClose()}>
            <DialogContent data-testid={IDS.withdrawDialog} className="sm:max-w-md">
                <DialogHeader className="text-left">
                    <DialogTitle>Withdraw from {row?.campaign_title}?</DialogTitle>
                    <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
                        {/* Said plainly, because a creator worrying that pulling
                            out counts against them is a creator who goes quiet
                            instead — which is the behaviour this replaces. */}
                        This takes your pitch off their board. It doesn't count
                        against you, and you can apply to anything else.
                    </DialogDescription>
                </DialogHeader>
                <Textarea
                    rows={3}
                    maxLength={500}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    data-testid={IDS.withdrawReason}
                    placeholder="e.g. I've got a clashing shoot that week"
                    className="rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                />
                {error && (
                    <p data-testid={IDS.withdrawError} className="text-sm text-destructive">
                        {error}
                    </p>
                )}
                <DialogFooter className="gap-2">
                    <Button variant="ghost" onClick={onClose} data-testid={IDS.withdrawCancel}>
                        Keep it
                    </Button>
                    <Button onClick={submit} disabled={busy} data-testid={IDS.withdrawSubmit}>
                        {busy ? "Withdrawing…" : "Withdraw"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

export default function Applications({ applied, declined, invitations, onChanged }) {
    const [withdrawing, setWithdrawing] = useState(null);
    const waiting = applied || [];
    const notThisTime = declined || [];
    // An open invitation is something to answer, so it counts as work in this
    // view even though no application exists yet.
    const open = (invitations || []).filter((i) => i.open);
    const total = waiting.length + notThisTime.length;

    return (
        <>
            {/* Above the section heading, not under it: an invitation is not a
                pitch, and "Pitched — waiting to hear back" printed over a row
                the creator has not answered describes the wrong party as the
                one being waited on. It renders nothing when there are none. */}
            <Invitations invitations={invitations} onChanged={onChanged} />

            <WithdrawDialog
                row={withdrawing}
                onClose={() => setWithdrawing(null)}
                onDone={onChanged}
            />

            <SectionHead
                className={open.length > 0 ? "mt-10" : ""}
                kicker="Pitched"
                title="Waiting to hear back."
                aside={
                    total > 0 && (
                        <span data-testid={IDS.count} className="text-xs text-muted-foreground">
                            {total} {total === 1 ? "application" : "applications"}
                        </span>
                    )
                }
            />

            <div className="mt-8 space-y-4">
                {/* Shown whenever there are no pitches, invitation or not: the
                    heading above says "Pitched", and a heading with nothing
                    under it is a section that looks broken. It is also still
                    true — being asked is not the same as having pitched. */}
                {total === 0 ? (
                    <EmptyState
                        testid={IDS.empty}
                        Icon={Hourglass}
                        title="You haven't pitched on anything yet."
                        action={
                            <Link to="/campaigns" data-testid={IDS.browse} className="mt-2">
                                <Button className="h-12 rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                    Browse campaigns
                                </Button>
                            </Link>
                        }
                    >
                        Pick a brief that fits your work, tell the brand why in a line
                        or two, and name your rate.
                    </EmptyState>
                ) : (
                    <>
                        {waiting.length > 0 && (
                            <ul
                                data-testid={IDS.list}
                                className="divide-y divide-white/10 overflow-hidden rounded-md border border-white/10 bg-card grain-surface"
                            >
                                {waiting.map((row) => (
                                    <Row
                                        key={row.id}
                                        row={row}
                                        testid={IDS.row(row.id)}
                                        onWithdraw={setWithdrawing}
                                    />
                                ))}
                            </ul>
                        )}

                        {notThisTime.length > 0 && (
                            <div className="overflow-hidden rounded-md border border-white/10 bg-card/50">
                                <p className="border-b border-white/10 px-5 py-4 text-xs uppercase tracking-[0.2em] text-muted-foreground sm:px-6">
                                    Went another way
                                </p>
                                <ul data-testid={IDS.declinedList} className="divide-y divide-white/10">
                                    {notThisTime.map((row) => (
                                        <Row
                                            key={row.id}
                                            row={row}
                                            testid={IDS.declinedRow(row.id)}
                                            muted
                                        />
                                    ))}
                                </ul>
                                <div className="border-t border-white/10 px-5 py-5 sm:px-6">
                                    <p className="text-sm leading-relaxed text-muted-foreground">
                                        Briefs get filled for all sorts of reasons —
                                        dates, budget, how many creators they needed.
                                        None of it changes what you make.
                                    </p>
                                    <Link
                                        to="/campaigns"
                                        data-testid={IDS.declinedBrowse}
                                        className="group mt-4 inline-flex items-center gap-2 text-sm text-ember-500 transition-colors duration-200 hover:text-ember-400"
                                    >
                                        See what else is open
                                        <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                    </Link>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </>
    );
}
