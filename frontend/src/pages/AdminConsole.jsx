import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
    ArrowRight,
    BadgeCheck,
    BadgeX,
    Check,
    Clock,
    ExternalLink,
    IndianRupee,
    Instagram,
    Loader2,
    RotateCw,
    Sparkles,
    TrendingUp,
    Users,
    Wallet,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

const STATE_ORDER = [
    "applied",
    "vetted",
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "content_submitted",
    "content_approved",
    "in_payment",
    "closed",
    "declined",
    "cancelled",
];

const STATE_META = {
    applied: { label: "Applied", tone: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
    vetted: { label: "Vetted", tone: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
    accepted: { label: "Accepted", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    commercial_agreed: { label: "Commercial agreed", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    slot_booked: { label: "Slot booked", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    attended: { label: "Attended", tone: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
    content_submitted: { label: "Content submitted", tone: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
    content_approved: { label: "Content approved", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    in_payment: { label: "In payment", tone: "bg-ember-500/15 text-ember-500 border-ember-500/30" },
    closed: { label: "Closed", tone: "bg-white/5 text-muted-foreground border-white/15" },
    declined: { label: "Declined", tone: "bg-white/5 text-muted-foreground border-white/15" },
    cancelled: { label: "Cancelled", tone: "bg-red-500/10 text-red-300/80 border-red-500/25" },
};

// Steps the brand takes. The console shows these as waiting on them rather than
// offering an Advance button the API will refuse.
const BRAND_OWNED = {
    accepted: "Waiting on the brand to accept",
    content_approved: "Waiting on the brand to approve content",
};

const formatDateTime = (iso) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleString("en-IN", {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return iso;
    }
};

// A local datetime for <input type="datetime-local">, defaulted a week out.
const defaultSlotValue = () => {
    const d = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
    d.setMinutes(0, 0, 0);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
        d.getHours(),
    )}:${pad(d.getMinutes())}`;
};

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN") : "—";

const StatePill = ({ state }) => {
    const m = STATE_META[state] || {
        label: state,
        tone: "bg-white/5 text-muted-foreground border-white/15",
    };
    return (
        <span
            data-testid={`admin-state-pill-${state}`}
            className={
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                m.tone
            }
        >
            {m.label}
        </span>
    );
};

const MetricTile = ({ label, value, prefix, Icon, testid }) => (
    <div
        data-testid={testid}
        className="rounded-md border border-white/10 bg-card p-6"
    >
        <div className="flex items-center justify-between">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {label}
            </p>
            {Icon && <Icon className="h-4 w-4 text-ember-500" />}
        </div>
        <div className="mt-5 flex items-baseline font-serif text-4xl md:text-5xl">
            {prefix && (
                <IndianRupee className="h-6 w-6 text-ember-500 md:h-7 md:w-7" />
            )}
            {value}
        </div>
    </div>
);

// ---------------------------------------------------------------------------
// Section 1: Creator vetting queue
// ---------------------------------------------------------------------------

// Three separate lists, because "waiting on us", "edited since approval" and
// "never finished signing up" are three different jobs.
const VETTING_TABS = [
    {
        key: "pending",
        label: "New",
        endpoint: "/admin/creators/pending",
        empty: "No creators pending review — inbox zero.",
    },
    {
        key: "changed",
        label: "Edited since approval",
        endpoint: "/admin/creators/changed",
        empty: "No vetted creator has changed anything material.",
    },
    {
        key: "incomplete",
        label: "Never finished",
        endpoint: "/admin/creators/incomplete",
        empty: "Everyone who signed up has completed their profile.",
    },
];

function VettingQueue({ onChange }) {
    const [rows, setRows] = useState(null);
    const [busy, setBusy] = useState({});
    const [tab, setTab] = useState("pending");

    const active = VETTING_TABS.find((t) => t.key === tab) || VETTING_TABS[0];

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get(active.endpoint);
            setRows(data);
        } catch (e) {
            toast.error(formatApiError(e));
            setRows([]);
        }
    }, [active.endpoint]);

    useEffect(() => {
        load();
    }, [load]);

    const decide = async (uid, verb) => {
        setBusy((b) => ({ ...b, [uid]: true }));
        try {
            await api.post(`/admin/creators/${uid}/${verb}`);
            toast.success(verb === "approve" ? "Creator vetted" : "Creator rejected");
            setRows((r) => (r ? r.filter((row) => row.user_id !== uid) : r));
            onChange?.();
        } catch (e) {
            toast.error(formatApiError(e));
        } finally {
            setBusy((b) => ({ ...b, [uid]: false }));
        }
    };

    return (
        <section data-testid="admin-vetting-section" className="mt-14">
            <div className="flex items-baseline justify-between">
                <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Section 1
                    </p>
                    <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                        Creator vetting queue
                    </h2>
                </div>
                <button
                    type="button"
                    onClick={load}
                    data-testid="admin-vetting-refresh"
                    className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    <RotateCw className="h-3.5 w-3.5" />
                    Refresh
                </button>
            </div>

            <div
                data-testid="admin-vetting-tabs"
                className="mt-6 flex flex-wrap gap-2"
            >
                {VETTING_TABS.map((t) => {
                    const isActive = tab === t.key;
                    return (
                        <button
                            key={t.key}
                            type="button"
                            aria-pressed={isActive}
                            data-testid={`admin-vetting-tab-${t.key}`}
                            onClick={() => setTab(t.key)}
                            className={
                                "rounded-full border px-4 py-1.5 text-xs uppercase tracking-[0.15em] transition-colors duration-200 " +
                                (isActive
                                    ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                    : "border-white/10 bg-transparent text-muted-foreground hover:border-white/25 hover:text-foreground")
                            }
                        >
                            {t.label}
                        </button>
                    );
                })}
            </div>

            {tab === "incomplete" && (
                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                    These accounts signed up but never submitted a profile. Nothing to
                    approve — they need a nudge, not a decision.
                </p>
            )}
            {tab === "changed" && (
                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                    Already vetted and still live to brands. Approving clears the flag;
                    rejecting takes them out of the directory.
                </p>
            )}

            <div className="mt-8 rounded-md border border-white/10 bg-card">
                {rows === null && (
                    <div className="grid place-items-center py-16 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin" />
                    </div>
                )}
                {Array.isArray(rows) && rows.length === 0 && (
                    <div
                        data-testid="admin-vetting-empty"
                        className="flex items-center gap-4 px-6 py-10 text-sm text-muted-foreground"
                    >
                        <Sparkles className="h-5 w-5 flex-none text-ember-500" />
                        <p>{active.empty}</p>
                    </div>
                )}
                {Array.isArray(rows) && rows.length > 0 && (
                    <ul className="divide-y divide-white/10">
                        {rows.map((c) => (
                            <li
                                key={c.user_id}
                                data-testid={`admin-vetting-row-${c.user_id}`}
                                className="flex flex-col gap-4 px-6 py-6 md:flex-row md:items-start md:gap-8"
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        {c.city || "India"} · applied {new Date(c.created_at).toLocaleDateString("en-IN")}
                                    </div>
                                    <div className="mt-1.5 font-serif text-2xl leading-tight">
                                        {c.name}
                                    </div>
                                    <div className="mt-1 text-sm text-muted-foreground">
                                        {c.email}
                                        {c.phone ? ` · ${c.phone}` : ""}
                                    </div>
                                    <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
                                        {c.instagram_handle && (
                                            <a
                                                href={c.instagram_profile_url ||
                                                    `https://instagram.com/${c.instagram_handle}`}
                                                target="_blank"
                                                rel="noreferrer"
                                                data-testid={`admin-vetting-ig-${c.user_id}`}
                                                className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-background/60 px-3 py-1 text-xs text-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                                            >
                                                <Instagram className="h-3.5 w-3.5" />
                                                @{c.instagram_handle}
                                                <ExternalLink className="h-3 w-3" />
                                            </a>
                                        )}
                                        {typeof c.follower_count === "number" && (
                                            <span className="text-xs text-muted-foreground">
                                                {c.follower_count.toLocaleString("en-IN")} followers
                                            </span>
                                        )}
                                        {c.base_rate != null && (
                                            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                                                <IndianRupee className="h-3 w-3" />
                                                {formatRupees(c.base_rate)} base
                                            </span>
                                        )}
                                    </div>
                                    {(c.niches?.length > 0 || c.address) && (
                                        <div className="mt-4 flex flex-wrap items-center gap-2">
                                            {c.niches?.map((n) => (
                                                <span
                                                    key={n}
                                                    className="rounded-full bg-ember-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-ember-500"
                                                >
                                                    {n}
                                                </span>
                                            ))}
                                            {c.address && (
                                                <span className="text-xs text-muted-foreground">
                                                    {c.address}
                                                </span>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {/* Nothing to decide on a profile that was never submitted. */}
                                {tab === "incomplete" ? (
                                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground md:min-w-[140px] md:text-right">
                                        Onboarding unfinished
                                    </div>
                                ) : (
                                    <div className="flex flex-row gap-2 md:flex-col md:min-w-[140px]">
                                        <Button
                                            data-testid={`admin-vetting-approve-${c.user_id}`}
                                            disabled={busy[c.user_id]}
                                            onClick={() => decide(c.user_id, "approve")}
                                            className="flex-1 rounded-full bg-emerald-500/90 text-black hover:bg-emerald-400"
                                        >
                                            <BadgeCheck className="mr-1.5 h-4 w-4" />
                                            Approve
                                        </Button>
                                        <Button
                                            data-testid={`admin-vetting-reject-${c.user_id}`}
                                            disabled={busy[c.user_id]}
                                            variant="outline"
                                            onClick={() => decide(c.user_id, "reject")}
                                            className="flex-1 rounded-full border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10 hover:text-red-200"
                                        >
                                            <BadgeX className="mr-1.5 h-4 w-4" />
                                            Reject
                                        </Button>
                                    </div>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </section>
    );
}

// ---------------------------------------------------------------------------
// Advance / Mark-paid dialogs
// ---------------------------------------------------------------------------

function AdvanceDialog({ open, onOpenChange, mode, collab, onSubmit, submitting, feePercent }) {
    const [amount, setAmount] = useState("");
    const [fee, setFee] = useState("");
    const [overrideFee, setOverrideFee] = useState(false);
    const [slot, setSlot] = useState("");
    const [location, setLocation] = useState("");
    const [err, setErr] = useState("");

    useEffect(() => {
        if (open) {
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
                // The fee comes from central config now — this is only a preview
                // unless somebody deliberately overrides it.
                const agreed = collab?.agreed_amount ?? 0;
                const pct = feePercent ?? 15;
                setFee(agreed > 0 ? String(Math.round((agreed * pct) / 100)) : "");
                setOverrideFee(false);
            } else if (mode === "slot_booked") {
                setSlot(defaultSlotValue());
                setLocation("");
            }
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
                data-testid="admin-advance-dialog"
                className="max-w-md rounded-md border border-white/10 bg-card"
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
                            <div className="relative mt-2">
                                <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    id="ad-amt"
                                    data-testid="admin-advance-amount-input"
                                    type="number"
                                    min="0"
                                    step="500"
                                    value={amount}
                                    onChange={(e) => setAmount(e.target.value)}
                                    className="h-11 border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                                    placeholder="e.g. 8000"
                                />
                            </div>
                            <p className="mt-2 text-xs text-muted-foreground">
                                Creator quoted: ₹{formatRupees(collab?.quoted_rate)} · Brand budget: ₹
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
                                    data-testid="admin-advance-slot-input"
                                    type="datetime-local"
                                    value={slot}
                                    onChange={(e) => setSlot(e.target.value)}
                                    className="mt-2 h-11 border-white/10 bg-background/60 focus-visible:ring-ember-500"
                                />
                                <p className="mt-2 text-xs text-muted-foreground">
                                    The creator is messaged with this, and it appears on
                                    their dashboard and the brand's applicant board.
                                </p>
                            </div>
                            <div>
                                <Label
                                    htmlFor="ad-location"
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    Where (optional)
                                </Label>
                                <Input
                                    id="ad-location"
                                    data-testid="admin-advance-location-input"
                                    value={location}
                                    onChange={(e) => setLocation(e.target.value)}
                                    maxLength={300}
                                    className="mt-2 h-11 border-white/10 bg-background/60 focus-visible:ring-ember-500"
                                    placeholder="e.g. Koramangala outlet, ask for Anita"
                                />
                            </div>
                        </>
                    )}

                    {mode === "in_payment" && (
                        <div>
                            <div className="rounded-md border border-white/10 bg-background/60 p-4 text-sm">
                                <div className="flex items-center justify-between">
                                    <span className="text-muted-foreground">
                                        Creator receives
                                    </span>
                                    <span className="font-serif text-lg">
                                        ₹{formatRupees(collab?.agreed_amount)}
                                    </span>
                                </div>
                                <div className="mt-2 flex items-center justify-between">
                                    <span className="text-muted-foreground">
                                        Platform fee ({feePercent ?? 15}%)
                                    </span>
                                    <span className="font-serif text-lg text-ember-500">
                                        ₹{formatRupees(Number(fee) || 0)}
                                    </span>
                                </div>
                                <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3">
                                    <span className="text-muted-foreground">
                                        Brand is invoiced
                                    </span>
                                    <span className="font-serif text-lg">
                                        ₹
                                        {formatRupees(
                                            (collab?.agreed_amount ?? 0) + (Number(fee) || 0),
                                        )}
                                    </span>
                                </div>
                            </div>

                            {!collab?.creator?.payout_ready && (
                                <p
                                    data-testid="admin-advance-payout-warning"
                                    className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-200"
                                >
                                    This creator hasn't added a UPI ID and PAN yet, so this
                                    will be refused. Ask them to finish their profile first.
                                </p>
                            )}

                            <button
                                type="button"
                                data-testid="admin-advance-fee-override-toggle"
                                onClick={() => setOverrideFee((v) => !v)}
                                className="mt-3 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                            >
                                {overrideFee ? "Use the standard fee" : "Override the fee"}
                            </button>

                            {overrideFee && (
                                <div className="mt-3">
                                    <Label
                                        htmlFor="ad-fee"
                                        className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                    >
                                        One-off platform fee
                                    </Label>
                                    <div className="relative mt-2">
                                        <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            id="ad-fee"
                                            data-testid="admin-advance-fee-input"
                                            type="number"
                                            min="0"
                                            step="100"
                                            value={fee}
                                            onChange={(e) => setFee(e.target.value)}
                                            className="h-11 border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {err && (
                        <p
                            data-testid="admin-advance-error"
                            className="text-sm text-destructive"
                        >
                            {err}
                        </p>
                    )}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                data-testid="admin-advance-cancel"
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            data-testid="admin-advance-submit"
                            disabled={submitting}
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
 * A confirm dialog that collects one piece of text. Used for the two actions
 * that must never be a bare click: cancelling a collaboration, and asserting
 * that money left the bank.
 */
function TextConfirmDialog({
    open,
    onOpenChange,
    kicker,
    title,
    description,
    label,
    placeholder,
    confirmLabel,
    required,
    destructive,
    submitting,
    onSubmit,
}) {
    const [value, setValue] = useState("");
    const [err, setErr] = useState("");

    useEffect(() => {
        if (open) {
            setValue("");
            setErr("");
        }
    }, [open]);

    const submit = (e) => {
        e.preventDefault();
        if (required && !value.trim()) {
            setErr(`${label} is required.`);
            return;
        }
        setErr("");
        onSubmit(value.trim() || null);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid="admin-text-confirm-dialog"
                className="max-w-md rounded-md border border-white/10 bg-card"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        {kicker}
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {title}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm text-muted-foreground">
                        {description}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} noValidate className="mt-4 space-y-5">
                    <div>
                        <Label
                            htmlFor="admin-confirm-input"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            {label}
                        </Label>
                        <Input
                            id="admin-confirm-input"
                            data-testid="admin-text-confirm-input"
                            value={value}
                            onChange={(e) => setValue(e.target.value)}
                            maxLength={500}
                            className="mt-2 h-11 border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            placeholder={placeholder}
                        />
                    </div>

                    {err && (
                        <p
                            data-testid="admin-text-confirm-error"
                            className="text-sm text-destructive"
                        >
                            {err}
                        </p>
                    )}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Back
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            data-testid="admin-text-confirm-submit"
                            disabled={submitting}
                            className={
                                destructive
                                    ? "rounded-full border border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10"
                                    : "rounded-full bg-emerald-500/90 text-black hover:bg-emerald-400"
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

// ---------------------------------------------------------------------------
// Brand verification — the landing page promises both sides are reviewed
// ---------------------------------------------------------------------------

function BrandQueue({ onChange }) {
    const [rows, setRows] = useState(null);
    const [busy, setBusy] = useState({});

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get("/admin/brands", {
                params: { unverified_only: true },
            });
            setRows(data);
        } catch (e) {
            toast.error(formatApiError(e));
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const verify = async (uid) => {
        setBusy((b) => ({ ...b, [uid]: true }));
        try {
            await api.post(`/admin/brands/${uid}/verify`);
            toast.success("Brand verified");
            setRows((r) => (r ? r.filter((row) => row.user_id !== uid) : r));
            onChange?.();
        } catch (e) {
            toast.error(formatApiError(e));
        } finally {
            setBusy((b) => ({ ...b, [uid]: false }));
        }
    };

    return (
        <section data-testid="admin-brands-section" className="mt-16">
            <div className="flex items-baseline justify-between">
                <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Section 2
                    </p>
                    <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                        Brands to verify
                    </h2>
                </div>
                <button
                    type="button"
                    onClick={load}
                    data-testid="admin-brands-refresh"
                    className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    <RotateCw className="h-3.5 w-3.5" />
                    Refresh
                </button>
            </div>

            <div className="mt-8 rounded-md border border-white/10 bg-card">
                {rows === null && (
                    <div className="grid place-items-center py-16 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin" />
                    </div>
                )}
                {Array.isArray(rows) && rows.length === 0 && (
                    <div
                        data-testid="admin-brands-empty"
                        className="flex items-center gap-4 px-6 py-10 text-sm text-muted-foreground"
                    >
                        <BadgeCheck className="h-5 w-5 flex-none text-ember-500" />
                        <p>Every brand is verified.</p>
                    </div>
                )}
                {Array.isArray(rows) && rows.length > 0 && (
                    <ul className="divide-y divide-white/10">
                        {rows.map((b) => (
                            <li
                                key={b.user_id}
                                data-testid={`admin-brand-row-${b.user_id}`}
                                className="flex flex-col gap-4 px-6 py-5 md:flex-row md:items-center md:gap-6"
                            >
                                <div className="min-w-0 flex-1">
                                    <div className="font-serif text-xl leading-tight">
                                        {b.business_name}
                                    </div>
                                    <div className="mt-1 text-sm text-muted-foreground">
                                        {b.email || b.phone || "No contact on file"}
                                        {b.areas?.length ? ` · ${b.areas.join(", ")}` : ""}
                                    </div>
                                    <div className="mt-2 text-xs text-muted-foreground">
                                        {b.campaign_count}{" "}
                                        {b.campaign_count === 1 ? "campaign" : "campaigns"} posted
                                    </div>
                                </div>
                                <Button
                                    data-testid={`admin-brand-verify-${b.user_id}`}
                                    disabled={busy[b.user_id]}
                                    onClick={() => verify(b.user_id)}
                                    className="rounded-full bg-emerald-500/90 text-black hover:bg-emerald-400"
                                >
                                    <BadgeCheck className="mr-1.5 h-4 w-4" />
                                    Verify
                                </Button>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </section>
    );
}

// ---------------------------------------------------------------------------
// Section 3: Collaborations board
// ---------------------------------------------------------------------------

function CollaborationsBoard({ onChange, feePercent }) {
    const [board, setBoard] = useState(null);
    const [dialog, setDialog] = useState({ open: false, mode: null, collab: null });
    const [cancelFor, setCancelFor] = useState(null);
    const [paidFor, setPaidFor] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [busyId, setBusyId] = useState(null);

    const load = useCallback(async () => {
        setBoard(null);
        try {
            const { data } = await api.get("/admin/collaborations");
            setBoard(data);
        } catch (e) {
            toast.error(formatApiError(e));
            setBoard({ by_state: {}, total: 0 });
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const advance = async (collab, body = {}) => {
        setBusyId(collab.id);
        setSubmitting(true);
        try {
            // from_state is the write precondition — if somebody else moved this
            // row while the dialog was open, the server refuses rather than
            // skipping a stage.
            await api.post(`/admin/collaborations/${collab.id}/advance`, {
                ...body,
                from_state: collab.state,
            });
            toast.success("Moved forward");
            setDialog({ open: false, mode: null, collab: null });
            await load();
            onChange?.();
        } catch (e) {
            toast.error(formatApiError(e));
            if (e?.response?.status === 409) await load();
        } finally {
            setBusyId(null);
            setSubmitting(false);
        }
    };

    const onAdvanceClick = (collab) => {
        const next = collab.next_state;
        if (!next) return;
        if (["commercial_agreed", "in_payment", "slot_booked"].includes(next)) {
            setDialog({ open: true, mode: next, collab });
            return;
        }
        advance(collab);
    };

    const cancel = async (collab, reason) => {
        setBusyId(collab.id);
        setSubmitting(true);
        try {
            await api.post(`/admin/collaborations/${collab.id}/cancel`, { reason });
            toast.success("Collaboration cancelled");
            setCancelFor(null);
            await load();
            onChange?.();
        } catch (e) {
            toast.error(formatApiError(e));
        } finally {
            setBusyId(null);
            setSubmitting(false);
        }
    };

    const markPaid = async (collab, reference) => {
        if (!collab.payment?.id) return;
        setBusyId(collab.id);
        setSubmitting(true);
        try {
            await api.post(`/admin/payments/${collab.payment.id}/mark_paid`, {
                payment_reference: reference,
            });
            toast.success("Payout recorded — collaboration closed");
            setPaidFor(null);
            await load();
            onChange?.();
        } catch (e) {
            toast.error(formatApiError(e));
        } finally {
            setBusyId(null);
            setSubmitting(false);
        }
    };

    const orderedStates = STATE_ORDER.filter(
        (s) => (board?.by_state?.[s] || []).length > 0,
    );

    return (
        <section data-testid="admin-collabs-section" className="mt-16">
            <div className="flex items-baseline justify-between">
                <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Section 3
                    </p>
                    <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                        Collaborations board
                    </h2>
                </div>
                <button
                    type="button"
                    onClick={load}
                    data-testid="admin-collabs-refresh"
                    className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    <RotateCw className="h-3.5 w-3.5" />
                    Refresh
                </button>
            </div>

            <div className="mt-8 space-y-8">
                {board === null && (
                    <div className="grid place-items-center py-16 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin" />
                    </div>
                )}

                {board && orderedStates.length === 0 && (
                    <div
                        data-testid="admin-collabs-empty"
                        className="rounded-md border border-white/10 bg-card px-6 py-10 text-sm text-muted-foreground"
                    >
                        No collaborations yet.
                    </div>
                )}

                {board &&
                    orderedStates.map((state) => {
                        const rows = board.by_state[state] || [];
                        return (
                            <div
                                key={state}
                                data-testid={`admin-collabs-group-${state}`}
                                className="rounded-md border border-white/10 bg-card"
                            >
                                <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
                                    <div className="flex items-center gap-3">
                                        <StatePill state={state} />
                                        <span className="text-xs text-muted-foreground">
                                            {rows.length} {rows.length === 1 ? "collab" : "collabs"}
                                        </span>
                                    </div>
                                </div>
                                <ul className="divide-y divide-white/10">
                                    {rows.map((c) => (
                                        <li
                                            key={c.id}
                                            data-testid={`admin-collab-row-${c.id}`}
                                            className="flex flex-col gap-4 px-5 py-5 md:flex-row md:items-center md:gap-6"
                                        >
                                            <div className="flex-1 min-w-0">
                                                <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                                    {c.brand_name || "Brand"}
                                                    {c.campaign?.area ? ` · ${c.campaign.area}` : ""}
                                                </div>
                                                <div className="mt-1 truncate font-serif text-lg leading-tight">
                                                    {c.campaign?.title || "Untitled campaign"}
                                                </div>
                                                <div className="mt-1 text-sm text-muted-foreground">
                                                    Creator:{" "}
                                                    <span className="text-foreground">
                                                        {c.creator?.name || "—"}
                                                    </span>
                                                    {c.creator?.instagram_handle
                                                        ? ` · @${c.creator.instagram_handle}`
                                                        : ""}
                                                </div>
                                                <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                                    <span className="inline-flex items-center gap-1">
                                                        <IndianRupee className="h-3 w-3" />
                                                        Quoted {formatRupees(c.quoted_rate)}
                                                    </span>
                                                    {c.agreed_amount != null && (
                                                        <>
                                                            <span>·</span>
                                                            <span className="inline-flex items-center gap-1 text-emerald-300">
                                                                <IndianRupee className="h-3 w-3" />
                                                                Agreed {formatRupees(c.agreed_amount)}
                                                            </span>
                                                        </>
                                                    )}
                                                    {c.payment && (
                                                        <>
                                                            <span>·</span>
                                                            <span className="inline-flex items-center gap-1 text-ember-500">
                                                                Payout ₹{formatRupees(c.payment.creator_payout)} · fee ₹
                                                                {formatRupees(c.payment.platform_fee)}
                                                            </span>
                                                        </>
                                                    )}
                                                    {c.payment?.payment_reference && (
                                                        <>
                                                            <span>·</span>
                                                            <span className="text-emerald-300">
                                                                Ref {c.payment.payment_reference}
                                                            </span>
                                                        </>
                                                    )}
                                                    {c.scheduled_at && (
                                                        <>
                                                            <span>·</span>
                                                            <span className="inline-flex items-center gap-1 text-sky-300">
                                                                <Clock className="h-3 w-3" />
                                                                {formatDateTime(c.scheduled_at)}
                                                            </span>
                                                        </>
                                                    )}
                                                    {c.creator?.payout_ready === false && (
                                                        <>
                                                            <span>·</span>
                                                            <span
                                                                data-testid={`admin-collab-no-payout-${c.id}`}
                                                                className="text-amber-300"
                                                            >
                                                                No payout details
                                                            </span>
                                                        </>
                                                    )}
                                                </div>
                                                {c.exit_reason && (
                                                    <p className="mt-2 text-xs text-muted-foreground">
                                                        {c.exit_reason}
                                                    </p>
                                                )}
                                            </div>

                                            <div className="flex flex-col items-stretch gap-2 md:items-end">
                                                {c.state === "in_payment" && c.payment?.state === "pending" ? (
                                                    <Button
                                                        data-testid={`admin-collab-mark-paid-${c.id}`}
                                                        disabled={busyId === c.id}
                                                        onClick={() => setPaidFor(c)}
                                                        className="rounded-full bg-emerald-500/90 text-black hover:bg-emerald-400"
                                                    >
                                                        <Check className="mr-1.5 h-4 w-4" />
                                                        Mark as paid
                                                    </Button>
                                                ) : BRAND_OWNED[c.next_state] ? (
                                                    <span
                                                        data-testid={`admin-collab-waiting-brand-${c.id}`}
                                                        className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.15em] text-sky-300"
                                                    >
                                                        <Clock className="h-3 w-3" />
                                                        {BRAND_OWNED[c.next_state]}
                                                    </span>
                                                ) : c.can_advance ? (
                                                    <Button
                                                        data-testid={`admin-collab-advance-${c.id}`}
                                                        disabled={busyId === c.id}
                                                        onClick={() => onAdvanceClick(c)}
                                                        className="group rounded-full bg-ember-500 text-black hover:bg-ember-400"
                                                    >
                                                        Advance to {STATE_META[c.next_state]?.label || c.next_state}
                                                        <ArrowRight className="ml-1.5 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                                    </Button>
                                                ) : (
                                                    <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                                                        {["declined", "cancelled"].includes(c.state)
                                                            ? "Ended"
                                                            : "Final state"}
                                                    </span>
                                                )}

                                                {c.can_cancel && (
                                                    <button
                                                        type="button"
                                                        data-testid={`admin-collab-cancel-${c.id}`}
                                                        disabled={busyId === c.id}
                                                        onClick={() => setCancelFor(c)}
                                                        className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-red-300 disabled:opacity-40"
                                                    >
                                                        Cancel collaboration
                                                    </button>
                                                )}
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        );
                    })}
            </div>

            <AdvanceDialog
                open={dialog.open}
                onOpenChange={(v) => setDialog((d) => ({ ...d, open: v }))}
                mode={dialog.mode}
                collab={dialog.collab}
                submitting={submitting}
                feePercent={feePercent}
                onSubmit={(body) => advance(dialog.collab, body)}
            />

            <TextConfirmDialog
                open={cancelFor !== null}
                onOpenChange={(v) => !v && setCancelFor(null)}
                kicker="End collaboration"
                title="Cancel this collaboration?"
                description={`${cancelFor?.creator?.name || "The creator"} is told, and any pending payment row is voided. This can't be undone.`}
                label="Reason"
                placeholder="e.g. Creator couldn't make the rescheduled slot."
                confirmLabel="Cancel collaboration"
                destructive
                submitting={submitting}
                onSubmit={(reason) => cancel(cancelFor, reason)}
            />

            <TextConfirmDialog
                open={paidFor !== null}
                onOpenChange={(v) => !v && setPaidFor(null)}
                kicker="Record payout"
                title={`Pay ₹${formatRupees(paidFor?.payment?.creator_payout)}`}
                description={
                    paidFor?.payment
                        ? "This records a transfer you've already made — it doesn't move money. Paste the bank or UPI reference so it can be reconciled later."
                        : ""
                }
                label="Payment reference"
                placeholder="e.g. UTR 402512345678"
                confirmLabel="Record payout"
                required
                submitting={submitting}
                onSubmit={(ref) => markPaid(paidFor, ref)}
            />
        </section>
    );
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export default function AdminConsole() {
    const [metrics, setMetrics] = useState(null);
    const [refreshKey, setRefreshKey] = useState(0);

    const loadMetrics = useCallback(async () => {
        try {
            const { data } = await api.get("/admin/metrics");
            setMetrics(data);
        } catch (e) {
            /* silent */
        }
    }, []);

    useEffect(() => {
        loadMetrics();
    }, [loadMetrics, refreshKey]);

    const bump = () => setRefreshKey((k) => k + 1);

    return (
        <div data-testid="admin-console-page" className="min-h-screen bg-background">
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-12 md:py-16">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    WeAre · Admin console
                </p>
                <h1
                    data-testid="admin-heading"
                    className="mt-3 font-serif text-4xl leading-none tracking-tight md:text-5xl"
                >
                    The marketplace, from the inside.
                </h1>
                <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground">
                    Approve creators, move collaborations forward, close out payments.
                    Only you (the WeAre team) see this page.
                </p>

                {/* Metrics */}
                <section
                    data-testid="admin-metrics-strip"
                    className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                >
                    <MetricTile
                        testid="admin-metric-open-campaigns"
                        label="Open campaigns"
                        Icon={Sparkles}
                        value={metrics ? metrics.open_campaigns : "—"}
                    />
                    <MetricTile
                        testid="admin-metric-vetted-creators"
                        label="Vetted creators"
                        Icon={Users}
                        value={metrics ? metrics.vetted_creators : "—"}
                    />
                    <MetricTile
                        testid="admin-metric-paid-out"
                        label="Paid to creators"
                        prefix
                        Icon={Wallet}
                        value={metrics ? formatRupees(metrics.total_paid_out) : "—"}
                    />
                    {/* What the business earned — previously invisible here. */}
                    <MetricTile
                        testid="admin-metric-revenue"
                        label={`Platform revenue${
                            metrics ? ` · ${metrics.platform_fee_percent}%` : ""
                        }`}
                        prefix
                        Icon={TrendingUp}
                        value={metrics ? formatRupees(metrics.platform_revenue) : "—"}
                    />
                    <MetricTile
                        testid="admin-metric-payouts-pending"
                        label={`Payouts owed${
                            metrics ? ` · ${metrics.payouts_pending_count}` : ""
                        }`}
                        prefix
                        Icon={Wallet}
                        value={metrics ? formatRupees(metrics.payouts_pending) : "—"}
                    />
                    <MetricTile
                        testid="admin-metric-receivable"
                        label="Owed by brands"
                        prefix
                        Icon={IndianRupee}
                        value={metrics ? formatRupees(metrics.brand_receivable) : "—"}
                    />
                </section>

                {/* Queues that should be at zero. */}
                {metrics && (
                    <div
                        data-testid="admin-queue-strip"
                        className="mt-4 flex flex-wrap gap-3 text-xs"
                    >
                        {[
                            {
                                label: "creators awaiting review",
                                value: metrics.creators_pending_review,
                            },
                            {
                                label: "applicants awaiting vetting",
                                value: metrics.applicants_awaiting_vetting,
                            },
                            { label: "brands unverified", value: metrics.brands_unverified },
                        ].map(({ label, value }) => (
                            <span
                                key={label}
                                className={
                                    "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 uppercase tracking-[0.15em] " +
                                    (value > 0
                                        ? "border-ember-500/40 bg-ember-500/10 text-ember-500"
                                        : "border-white/10 bg-transparent text-muted-foreground")
                                }
                            >
                                <span className="font-serif text-sm">{value}</span>
                                {label}
                            </span>
                        ))}
                    </div>
                )}

                <VettingQueue onChange={bump} />
                <BrandQueue onChange={bump} />
                <CollaborationsBoard
                    onChange={bump}
                    feePercent={metrics?.platform_fee_percent}
                />
            </main>
        </div>
    );
}
