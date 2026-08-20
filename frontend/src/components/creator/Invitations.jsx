// Briefs a brand asked you to take.
//
// **An invitation used to exist only as a WhatsApp message.** It was written
// to the database and sent to a phone, and then had nowhere to live in the
// product: the applications view reads collaborations, and an invitation is
// not one until the creator pitches. So somebody who missed the message, or
// read it on a bus and meant to come back, had no way to find out they had
// been asked at all.
//
// It sits above the pitches now, in the same view, because being asked and
// asking are the same conversation from opposite ends — and it carries the
// two answers rather than a link to somewhere the answer might be.
//
// Accepting is applying: the server routes it through the same handler, so a
// rate and a line about why are what it needs. That is why Accept opens the
// same short form the campaign page does rather than committing silently —
// an application with no rate on it is one the brand cannot act on.
import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, MailOpen } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { formatCompensation } from "@/lib/compensation";
import { CREATOR_APPLICATIONS as IDS } from "@/constants/testIds";

import { formatDate } from "./shared";

export default function Invitations({ invitations, onChanged }) {
    const rows = (invitations || []).filter((i) => i.open);
    const [accepting, setAccepting] = useState(null);
    const [busyId, setBusyId] = useState(null);
    const [rate, setRate] = useState("");
    const [pitch, setPitch] = useState("");
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);

    if (rows.length === 0) return null;

    const openAccept = (invite) => {
        setError("");
        // Their fee is the obvious opening number, and the brief's is the
        // best guess we have at what this one pays.
        setRate(invite.budget_per_creator ? String(invite.budget_per_creator) : "");
        setPitch("");
        setAccepting(invite);
    };

    const accept = async () => {
        if (!accepting) return;
        const value = Number(rate);
        if (!pitch.trim()) return setError("Say a line about why you're right for it.");
        if (!Number.isFinite(value) || value < 0) return setError("Give the rate you want.");
        setSubmitting(true);
        setError("");
        try {
            await api.post(`/creator/invitations/${accepting.id}/accept`, {
                pitch: pitch.trim(),
                quoted_rate: value,
            });
            notifySuccess("Accepted — the brand has your pitch");
            setAccepting(null);
            await onChanged?.();
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setSubmitting(false);
        }
    };

    const decline = async (invite) => {
        setBusyId(invite.id);
        try {
            await api.post(`/creator/invitations/${invite.id}/decline`);
            notifySuccess("Declined");
            await onChanged?.();
        } catch (err) {
            notifyError(err);
        } finally {
            setBusyId(null);
        }
    };

    return (
        <>
            <div className="overflow-hidden rounded-md border border-ember-500/30 bg-ember-500/[0.06]">
                <p className="flex items-center gap-2 border-b border-ember-500/20 px-5 py-4 text-xs uppercase tracking-[0.2em] text-ember-500 sm:px-6">
                    <MailOpen className="h-3.5 w-3.5" />
                    {rows.length === 1 ? "You've been invited" : `${rows.length} invitations`}
                </p>
                <ul data-testid={IDS.invitationList} className="divide-y divide-white/10">
                    {rows.map((invite) => (
                        <li
                            key={invite.id}
                            data-testid={IDS.invitation(invite.id)}
                            className="flex flex-col gap-4 px-5 py-5 sm:px-6 md:flex-row md:items-center md:gap-6"
                        >
                            <Link
                                to={`/campaigns/${invite.campaign_id}`}
                                className="group min-w-0 flex-1"
                            >
                                <span className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                    <BrandAvatar brand={invite} size="h-5 w-5" />
                                    <span className="truncate">
                                        {invite.brand_name || "A brand"}
                                        {invite.area ? ` · ${invite.area}` : ""}
                                    </span>
                                </span>
                                <span className="mt-1 block truncate font-serif text-lg leading-tight transition-colors duration-200 group-hover:text-ember-500">
                                    {invite.campaign_title || "Untitled campaign"}
                                </span>
                                <span className="mt-2 block text-xs text-muted-foreground">
                                    {/* `.text`, not the object — the formatter
                                        returns the parts so a caller can lay
                                        out the figure and its qualifier
                                        separately, and this row wants the
                                        sentence. */}
                                    {formatCompensation(invite).text} · invited{" "}
                                    {formatDate(invite.invited_at)}
                                </span>
                                {/* What they said when they asked. It is the
                                    reason this is not a mailshot, so it is on
                                    the row rather than a click away. */}
                                {invite.note && (
                                    <span
                                        data-testid={IDS.invitationNote(invite.id)}
                                        className="mt-2 block text-sm leading-relaxed text-muted-foreground"
                                    >
                                        “{invite.note}”
                                    </span>
                                )}
                            </Link>

                            <div className="flex flex-none items-center gap-2">
                                <Button
                                    type="button"
                                    variant="outline"
                                    disabled={busyId === invite.id}
                                    onClick={() => decline(invite)}
                                    data-testid={IDS.invitationDecline(invite.id)}
                                    className="h-11 rounded-full border-white/15 bg-transparent px-4 text-sm hover:bg-white/5"
                                >
                                    {busyId === invite.id ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        "Not this one"
                                    )}
                                </Button>
                                <Button
                                    type="button"
                                    onClick={() => openAccept(invite)}
                                    data-testid={IDS.invitationAccept(invite.id)}
                                    className="h-11 rounded-full bg-ember-500 px-5 text-sm text-black hover:bg-ember-400"
                                >
                                    Accept
                                </Button>
                            </div>
                        </li>
                    ))}
                </ul>
            </div>

            <Dialog open={Boolean(accepting)} onOpenChange={(v) => !v && setAccepting(null)}>
                <DialogContent
                    data-testid={IDS.invitationDialog}
                    className="max-w-md rounded-md border border-white/10 bg-card"
                >
                    <DialogHeader className="text-left">
                        <DialogTitle className="font-serif text-2xl leading-tight">
                            Accept “{accepting?.campaign_title}”
                        </DialogTitle>
                        <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
                            Accepting sends the brand a pitch like any other — your
                            rate, and a line about why you're right for it.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4">
                        <div>
                            <Label htmlFor="invite-rate" className="text-sm">
                                Your rate for this
                            </Label>
                            <Input
                                id="invite-rate"
                                inputMode="numeric"
                                value={rate}
                                onChange={(e) => setRate(e.target.value)}
                                data-testid={IDS.invitationRate}
                                className="mt-2 h-11 border-white/10 bg-background/60"
                            />
                        </div>
                        <div>
                            <Label htmlFor="invite-pitch" className="text-sm">
                                Why you
                            </Label>
                            <Textarea
                                id="invite-pitch"
                                rows={4}
                                value={pitch}
                                onChange={(e) => setPitch(e.target.value)}
                                placeholder="A line or two — what you'd shoot, and why it suits them."
                                data-testid={IDS.invitationPitch}
                                className="mt-2 border-white/10 bg-background/60"
                            />
                        </div>
                        {error && <p className="text-sm text-red-300">{error}</p>}
                    </div>

                    <DialogFooter className="flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setAccepting(null)}
                            className="h-12 rounded-full border-white/15 bg-transparent px-5 sm:h-11"
                        >
                            Back
                        </Button>
                        <Button
                            type="button"
                            onClick={accept}
                            disabled={submitting}
                            data-testid={IDS.invitationSubmit}
                            className="h-12 rounded-full bg-ember-500 px-6 text-black hover:bg-ember-400 sm:h-11"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Sending…
                                </>
                            ) : (
                                "Send my pitch"
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
