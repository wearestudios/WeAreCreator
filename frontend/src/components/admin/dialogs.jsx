// Every admin action that undoes, stops or claws something back goes through
// one of these. The server requires a reason on all of them; so does this, and
// for the same reason — the audit log is read a week later by somebody who
// wasn't there.
import React, { useEffect, useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { ADMIN_ADVANCE, ADMIN_CAMPAIGN_EDIT, ADMIN_CONFIRM } from "@/constants/testIds";
import { formatRupees } from "./shared";

// The server's ReasonPayload floor. Enforced here too so a three-character
// "no" is refused before it becomes a round trip.
const MIN_REASON = 3;

/**
 * Confirm an action, collecting the reason it required.
 *
 * `extra` renders an additional field above the reason (the payment reference
 * on a payout, for example) and its value is merged into what `onSubmit`
 * receives.
 */
export function ConfirmDialog({
    open,
    onOpenChange,
    kicker,
    title,
    description,
    reasonLabel = "Reason",
    placeholder,
    confirmLabel = "Confirm",
    destructive = false,
    submitting = false,
    extra = null,
    onSubmit,
}) {
    const [reason, setReason] = useState("");
    const [extraValue, setExtraValue] = useState("");
    const [err, setErr] = useState("");

    useEffect(() => {
        if (open) {
            setReason("");
            setExtraValue("");
            setErr("");
        }
    }, [open]);

    const submit = (e) => {
        e.preventDefault();
        if (reason.trim().length < MIN_REASON) {
            setErr("Give a reason — it's shown in the audit log and to the person affected.");
            return;
        }
        if (extra?.required && !extraValue.trim()) {
            setErr(`${extra.label} is required.`);
            return;
        }
        setErr("");
        onSubmit({
            reason: reason.trim(),
            ...(extra ? { [extra.name]: extraValue.trim() || null } : {}),
        });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={ADMIN_CONFIRM.dialog}
                className="max-w-md rounded-md border border-white/10 bg-card grain-surface"
            >
                <DialogHeader className="text-left">
                    {kicker && (
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            {kicker}
                        </p>
                    )}
                    <DialogTitle
                        data-testid={ADMIN_CONFIRM.title}
                        className="mt-3 font-serif text-2xl leading-tight"
                    >
                        {title}
                    </DialogTitle>
                    {description && (
                        <DialogDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                            {description}
                        </DialogDescription>
                    )}
                </DialogHeader>

                <form onSubmit={submit} noValidate className="mt-4 space-y-5">
                    {extra && (
                        <div>
                            <Label
                                htmlFor="admin-confirm-extra"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                {extra.label}
                            </Label>
                            <Input
                                id="admin-confirm-extra"
                                data-testid={ADMIN_CONFIRM.extra}
                                value={extraValue}
                                onChange={(e) => setExtraValue(e.target.value)}
                                maxLength={140}
                                placeholder={extra.placeholder}
                                className="mt-2 h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            />
                        </div>
                    )}

                    <div>
                        <Label
                            htmlFor="admin-confirm-reason"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            {reasonLabel}
                        </Label>
                        <Textarea
                            id="admin-confirm-reason"
                            data-testid={ADMIN_CONFIRM.reason}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            maxLength={500}
                            rows={3}
                            placeholder={placeholder}
                            className="mt-2 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                        />
                    </div>

                    {err && (
                        <p data-testid={ADMIN_CONFIRM.error} className="text-sm text-destructive">
                            {err}
                        </p>
                    )}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                data-testid={ADMIN_CONFIRM.cancel}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Back
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            disabled={submitting}
                            data-testid={ADMIN_CONFIRM.submit}
                            className={
                                destructive
                                    ? "rounded-full border border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10"
                                    : "rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            }
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving…
                                </>
                            ) : (
                                confirmLabel
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

// A local datetime for <input type="datetime-local">, defaulted a week out.
const defaultSlotValue = () => {
    const d = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
    d.setMinutes(0, 0, 0);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
        d.getHours(),
    )}:${pad(d.getMinutes())}`;
};

/**
 * The three forward steps that need a number or a date before they can happen.
 * Every other step advances on a click, so it never opens this.
 */
export function AdvanceDialog({
    open,
    onOpenChange,
    mode,
    collab,
    onSubmit,
    submitting,
    feePercent,
}) {
    const [amount, setAmount] = useState("");
    const [fee, setFee] = useState("");
    const [overrideFee, setOverrideFee] = useState(false);
    const [slot, setSlot] = useState("");
    const [location, setLocation] = useState("");
    const [err, setErr] = useState("");

    useEffect(() => {
        if (!open) return;
        setErr("");
        if (mode === "commercial_agreed") {
            setAmount(
                collab?.quoted_rate != null
                    ? String(collab.quoted_rate)
                    : collab?.campaign?.budget_per_creator != null
                    ? String(collab.campaign.budget_per_creator)
                    : "",
            );
        } else if (mode === "in_payment") {
            // The fee comes from central config — this is a preview unless
            // somebody deliberately overrides it.
            const agreed = collab?.agreed_amount ?? 0;
            const pct = feePercent ?? 15;
            setFee(agreed > 0 ? String(Math.round((agreed * pct) / 100)) : "");
            setOverrideFee(false);
        } else if (mode === "slot_booked") {
            setSlot(defaultSlotValue());
            setLocation("");
        }
    }, [open, mode, collab, feePercent]);

    const submit = (e) => {
        e.preventDefault();
        setErr("");
        if (mode === "commercial_agreed") {
            const n = Number(amount);
            if (!Number.isFinite(n) || n < 0) {
                setErr("Enter a valid agreed amount.");
                return;
            }
            onSubmit({ agreed_amount: n });
        } else if (mode === "in_payment") {
            if (!overrideFee) {
                onSubmit({});
                return;
            }
            const n = Number(fee);
            if (!Number.isFinite(n) || n < 0) {
                setErr("Enter a valid platform fee.");
                return;
            }
            onSubmit({ platform_fee: n });
        } else if (mode === "slot_booked") {
            if (!slot) {
                setErr("Pick the date and time of the shoot.");
                return;
            }
            const when = new Date(slot);
            if (Number.isNaN(when.getTime())) {
                setErr("That date doesn't look right.");
                return;
            }
            onSubmit({
                scheduled_at: when.toISOString(),
                location_note: location.trim() || null,
            });
        } else {
            onSubmit({});
        }
    };

    const title =
        mode === "commercial_agreed"
            ? "Agree the commercials"
            : mode === "in_payment"
            ? "Move to payment"
            : mode === "slot_booked"
            ? "Book the slot"
            : "";

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={ADMIN_ADVANCE.dialog}
                className="max-w-md rounded-md border border-white/10 bg-card grain-surface"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Collaboration transition
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {title}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm text-muted-foreground">
                        {collab?.campaign?.title} · {collab?.creator?.name || "Creator"}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} noValidate className="mt-4 space-y-5">
                    {mode === "commercial_agreed" && (
                        <div>
                            <Label
                                htmlFor="ad-amt"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                Final agreed amount
                            </Label>
                            <Input
                                id="ad-amt"
                                data-testid={ADMIN_ADVANCE.amount}
                                type="number"
                                min="0"
                                step="500"
                                value={amount}
                                onChange={(e) => setAmount(e.target.value)}
                                className="mt-2 h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                                placeholder="e.g. 8000"
                            />
                            <p className="mt-2 text-xs text-muted-foreground">
                                Creator quoted ₹{formatRupees(collab?.quoted_rate)} · brand budget ₹
                                {formatRupees(collab?.campaign?.budget_per_creator)}
                            </p>
                        </div>
                    )}

                    {mode === "slot_booked" && (
                        <>
                            <div>
                                <Label
                                    htmlFor="ad-slot"
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    Date and time of the shoot
                                </Label>
                                <Input
                                    id="ad-slot"
                                    data-testid={ADMIN_ADVANCE.slot}
                                    type="datetime-local"
                                    value={slot}
                                    onChange={(e) => setSlot(e.target.value)}
                                    className="mt-2 h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                                />
                            </div>
                            <div>
                                <Label
                                    htmlFor="ad-loc"
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    Where (optional)
                                </Label>
                                <Input
                                    id="ad-loc"
                                    data-testid={ADMIN_ADVANCE.location}
                                    value={location}
                                    onChange={(e) => setLocation(e.target.value)}
                                    maxLength={200}
                                    placeholder="e.g. Ask for Priya at the counter"
                                    className="mt-2 h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                                />
                            </div>
                        </>
                    )}

                    {mode === "in_payment" && (
                        <div className="space-y-3">
                            <p className="text-sm text-muted-foreground">
                                Creator is paid ₹{formatRupees(collab?.agreed_amount)} in full. Our
                                margin of {feePercent ?? 15}% is added on top of the brand's invoice.
                            </p>
                            <label className="flex items-center gap-2 text-xs text-muted-foreground">
                                <input
                                    type="checkbox"
                                    data-testid={ADMIN_ADVANCE.feeOverride}
                                    checked={overrideFee}
                                    onChange={(e) => setOverrideFee(e.target.checked)}
                                    className="h-3.5 w-3.5 accent-ember-500"
                                />
                                Override the fee for this one
                            </label>
                            {overrideFee && (
                                <Input
                                    data-testid={ADMIN_ADVANCE.fee}
                                    type="number"
                                    min="0"
                                    step="100"
                                    value={fee}
                                    onChange={(e) => setFee(e.target.value)}
                                    className="h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                                />
                            )}
                        </div>
                    )}

                    {err && (
                        <p data-testid={ADMIN_ADVANCE.error} className="text-sm text-destructive">
                            {err}
                        </p>
                    )}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                data-testid={ADMIN_ADVANCE.cancel}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            disabled={submitting}
                            data-testid={ADMIN_ADVANCE.submit}
                            className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving…
                                </>
                            ) : (
                                <>
                                    Confirm
                                    <ArrowRight className="ml-2 h-4 w-4" />
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

/**
 * Correcting a live campaign. Only the fields support actually gets asked to
 * change — the whole brief is the brand's to rewrite, not ours.
 */
export function CampaignEditDialog({ campaign, open, onOpenChange, onSubmit, submitting }) {
    const [title, setTitle] = useState("");
    const [budget, setBudget] = useState("");
    const [needed, setNeeded] = useState("");
    const [deliverables, setDeliverables] = useState("");
    const [err, setErr] = useState("");

    useEffect(() => {
        if (!open || !campaign) return;
        setTitle(campaign.title || "");
        setBudget(campaign.budget_per_creator != null ? String(campaign.budget_per_creator) : "");
        setNeeded(campaign.creators_needed != null ? String(campaign.creators_needed) : "");
        setDeliverables(campaign.deliverables || "");
        setErr("");
    }, [open, campaign]);

    const submit = (e) => {
        e.preventDefault();
        const changes = {};
        if (title.trim() && title.trim() !== campaign.title) changes.title = title.trim();
        if (deliverables.trim() && deliverables.trim() !== campaign.deliverables) {
            changes.deliverables = deliverables.trim();
        }
        const b = Number(budget);
        if (budget !== "" && b !== campaign.budget_per_creator) {
            if (!Number.isFinite(b) || b < 0) {
                setErr("Enter a valid budget.");
                return;
            }
            changes.budget_per_creator = b;
        }
        const n = Number(needed);
        if (needed !== "" && n !== campaign.creators_needed) {
            if (!Number.isInteger(n) || n < 1) {
                setErr("Creators needed has to be at least 1.");
                return;
            }
            changes.creators_needed = n;
        }
        if (Object.keys(changes).length === 0) {
            setErr("Nothing has changed.");
            return;
        }
        setErr("");
        onSubmit(changes);
    };

    const filled = campaign?.filled_slots ?? 0;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={ADMIN_CAMPAIGN_EDIT.dialog}
                className="max-w-md rounded-md border border-white/10 bg-card grain-surface"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Edit campaign
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {campaign?.title}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm text-muted-foreground">
                        {campaign?.brand_name || "Unknown brand"} · changes show on the creator
                        feed straight away.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} noValidate className="mt-4 space-y-5">
                    <div>
                        <Label htmlFor="ce-title" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            Title
                        </Label>
                        <Input
                            id="ce-title"
                            data-testid={ADMIN_CAMPAIGN_EDIT.title}
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            maxLength={140}
                            className="mt-2 h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                        />
                    </div>
                    <div>
                        <Label htmlFor="ce-deliv" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            Deliverables
                        </Label>
                        <Textarea
                            id="ce-deliv"
                            data-testid={ADMIN_CAMPAIGN_EDIT.deliverables}
                            value={deliverables}
                            onChange={(e) => setDeliverables(e.target.value)}
                            maxLength={1000}
                            rows={2}
                            className="mt-2 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                        />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                            <Label htmlFor="ce-budget" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Budget per creator
                            </Label>
                            <Input
                                id="ce-budget"
                                data-testid={ADMIN_CAMPAIGN_EDIT.budget}
                                type="number"
                                min="0"
                                step="500"
                                value={budget}
                                onChange={(e) => setBudget(e.target.value)}
                                className="mt-2 h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            />
                        </div>
                        <div>
                            <Label htmlFor="ce-needed" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Creators needed
                            </Label>
                            <Input
                                id="ce-needed"
                                data-testid={ADMIN_CAMPAIGN_EDIT.creatorsNeeded}
                                type="number"
                                min="1"
                                value={needed}
                                onChange={(e) => setNeeded(e.target.value)}
                                className="mt-2 h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            />
                            {filled > 0 && (
                                <p className="mt-2 text-xs text-muted-foreground">
                                    {filled} already confirmed — it can't go below that.
                                </p>
                            )}
                        </div>
                    </div>

                    {err && (
                        <p data-testid={ADMIN_CAMPAIGN_EDIT.error} className="text-sm text-destructive">
                            {err}
                        </p>
                    )}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                data-testid={ADMIN_CAMPAIGN_EDIT.cancel}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            disabled={submitting}
                            data-testid={ADMIN_CAMPAIGN_EDIT.submit}
                            className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving…
                                </>
                            ) : (
                                "Save changes"
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
