import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
    ArrowLeft,
    Check,
    CheckCircle2,
    Clock,
    ExternalLink,
    IndianRupee,
    Instagram,
    Link as LinkIcon,
    Loader2,
    MapPin,
    MessageSquare,
    Phone,
    Send,
    ShieldCheck,
    Users,
    X,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api, formatApiError, mediaUrl } from "@/lib/api";
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

const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    real_estate: "Real Estate",
    fashion: "Fashion",
    travel: "Travel",
    wellness: "Wellness",
    lifestyle: "Lifestyle",
};

const STATE_META = {
    applied: {
        label: "With WeAre",
        tone: "bg-white/5 text-muted-foreground border-white/15",
        note: "Our team is verifying this applicant. You'll see them once they're through.",
    },
    verified: {
        label: "Waiting on you",
        tone: "bg-ember-500/15 text-ember-500 border-ember-500/40",
        note: "Verified by our team. Your call.",
    },
    accepted: {
        label: "Accepted",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
        note: "Confirmed. We'll agree the fee and book the slot.",
    },
    commercial_agreed: {
        label: "Fee agreed",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    slot_booked: {
        label: "Slot booked",
        tone: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    },
    attended: {
        label: "Shoot done",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
        note: "Waiting on the creator to publish and submit links.",
    },
    content_submitted: {
        label: "Review content",
        tone: "bg-ember-500/15 text-ember-500 border-ember-500/40",
        note: "Content is in. Approve it or ask for a change.",
    },
    content_approved: {
        label: "Approved",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
        note: "Approved — payment is being processed.",
    },
    in_payment: {
        label: "In payment",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    closed: {
        label: "Complete",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    },
    declined: {
        label: "Declined",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    },
    cancelled: {
        label: "Cancelled",
        tone: "bg-red-500/10 text-red-300/80 border-red-500/25",
    },
};

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN") : "—";

const formatCompact = (n) => {
    if (typeof n !== "number") return "—";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
    return String(n);
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

const formatDate = (iso) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
        });
    } catch {
        return iso;
    }
};

const StatePill = ({ state }) => {
    const meta = STATE_META[state] || {
        label: state,
        tone: "bg-white/5 text-muted-foreground border-white/15",
    };
    return (
        <span
            data-testid={`applicant-state-${state}`}
            className={
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                meta.tone
            }
        >
            {meta.label}
        </span>
    );
};

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

function AcceptDialog({ open, onOpenChange, applicant, budget, onConfirm, busy }) {
    const [amount, setAmount] = useState("");
    const [note, setNote] = useState("");
    const [err, setErr] = useState("");

    useEffect(() => {
        if (open) {
            setAmount(
                applicant?.quoted_rate != null
                    ? String(applicant.quoted_rate)
                    : budget != null
                    ? String(budget)
                    : "",
            );
            setNote("");
            setErr("");
        }
    }, [open, applicant, budget]);

    const submit = (e) => {
        e.preventDefault();
        const n = Number(amount);
        if (!Number.isFinite(n) || n < 0) {
            setErr("Enter the fee you're accepting at.");
            return;
        }
        setErr("");
        onConfirm({ agreed_amount: n, note: note.trim() || null });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid="accept-applicant-dialog"
                className="max-w-md rounded-md border border-white/10 bg-card"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Accept creator
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {applicant?.creator?.name}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm text-muted-foreground">
                        They'll be told straight away, and we'll take it from there —
                        fee confirmation, slot booking, then content.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} noValidate className="mt-4 space-y-5">
                    <div>
                        <Label
                            htmlFor="accept-amount"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            Fee you're accepting at
                        </Label>
                        <div className="relative mt-2">
                            <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                id="accept-amount"
                                data-testid="accept-amount-input"
                                type="number"
                                min="0"
                                step="500"
                                value={amount}
                                onChange={(e) => setAmount(e.target.value)}
                                className="h-11 border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                            />
                        </div>
                        <p className="mt-2 text-xs text-muted-foreground">
                            They quoted ₹{formatRupees(applicant?.quoted_rate)} · your
                            budget is ₹{formatRupees(budget)} per creator.
                        </p>
                    </div>

                    <div>
                        <Label
                            htmlFor="accept-note"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            Note for our team (optional)
                        </Label>
                        <Textarea
                            id="accept-note"
                            data-testid="accept-note-input"
                            rows={2}
                            maxLength={500}
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            className="mt-2 border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            placeholder="Anything we should know when we book the slot?"
                        />
                    </div>

                    {err && (
                        <p data-testid="accept-error" className="text-sm text-destructive">
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
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            data-testid="accept-confirm-btn"
                            disabled={busy}
                            className="rounded-full bg-emerald-500/90 text-black hover:bg-emerald-400"
                        >
                            {busy ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Accepting…
                                </>
                            ) : (
                                <>
                                    <Check className="mr-2 h-4 w-4" />
                                    Accept creator
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

function ReasonDialog({
    open,
    onOpenChange,
    title,
    kicker,
    description,
    label,
    placeholder,
    confirmLabel,
    required,
    destructive,
    onConfirm,
    busy,
}) {
    const [reason, setReason] = useState("");
    const [err, setErr] = useState("");

    useEffect(() => {
        if (open) {
            setReason("");
            setErr("");
        }
    }, [open]);

    const submit = (e) => {
        e.preventDefault();
        if (required && !reason.trim()) {
            setErr("Please say what needs to change — the creator sees this.");
            return;
        }
        setErr("");
        onConfirm(reason.trim() || null);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid="reason-dialog"
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
                            htmlFor="reason-input"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            {label}
                        </Label>
                        <Textarea
                            id="reason-input"
                            data-testid="reason-input"
                            rows={3}
                            maxLength={500}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            className="mt-2 border-white/10 bg-background/60 focus-visible:ring-ember-500"
                            placeholder={placeholder}
                        />
                    </div>

                    {err && (
                        <p data-testid="reason-error" className="text-sm text-destructive">
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
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            data-testid="reason-confirm-btn"
                            disabled={busy}
                            className={
                                destructive
                                    ? "rounded-full border border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10"
                                    : "rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            }
                        >
                            {busy ? (
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
// Applicant row
// ---------------------------------------------------------------------------

const ApplicantCard = ({ applicant: a, budget, busy, onAccept, onDecline, onApprove, onRequestChanges }) => {
    const meta = STATE_META[a.state] || {};
    const c = a.creator || {};
    const overBudget =
        typeof budget === "number" &&
        typeof a.quoted_rate === "number" &&
        a.quoted_rate > budget;

    return (
        <li
            data-testid={`applicant-row-${a.id}`}
            className="flex flex-col gap-5 px-5 py-6 md:px-6"
        >
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:gap-6">
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-3">
                        {c.profile_image_url && (
                            <img
                                src={mediaUrl(c.profile_image_url)}
                                alt=""
                                data-testid={`applicant-photo-${a.id}`}
                                className="h-10 w-10 flex-none rounded-full border border-white/10 object-cover"
                            />
                        )}
                        <span className="font-serif text-2xl leading-tight">
                            {c.name || "Creator"}
                        </span>
                        <StatePill state={a.state} />
                    </div>

                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                        {c.instagram_handle && (
                            <a
                                href={
                                    c.instagram_profile_url ||
                                    `https://instagram.com/${c.instagram_handle}`
                                }
                                target="_blank"
                                rel="noreferrer"
                                data-testid={`applicant-ig-${a.id}`}
                                className="inline-flex items-center gap-1.5 transition-colors duration-200 hover:text-ember-500"
                            >
                                <Instagram className="h-3.5 w-3.5" />@{c.instagram_handle}
                                <ExternalLink className="h-3 w-3" />
                            </a>
                        )}
                        {typeof c.follower_count === "number" && (
                            <span className="inline-flex items-center gap-1.5">
                                <Users className="h-3.5 w-3.5" />
                                {formatCompact(c.follower_count)} followers
                            </span>
                        )}
                        {c.city && (
                            <span className="inline-flex items-center gap-1.5">
                                <MapPin className="h-3.5 w-3.5" />
                                {c.city}
                            </span>
                        )}
                        <span className="text-muted-foreground/70">
                            Applied {formatDate(a.applied_at)}
                        </span>
                    </div>

                    {c.niches?.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                            {c.niches.map((n) => (
                                <span
                                    key={n}
                                    className="rounded-full bg-ember-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-ember-500"
                                >
                                    {n}
                                </span>
                            ))}
                        </div>
                    )}
                </div>

                <div className="flex flex-row items-end gap-6 md:flex-col md:items-end md:gap-2">
                    <div className="md:text-right">
                        <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            {a.agreed_amount != null ? "Agreed" : "They quoted"}
                        </div>
                        <div className="mt-1 flex items-baseline font-serif text-3xl">
                            <IndianRupee className="h-5 w-5 text-ember-500" />
                            {formatRupees(a.agreed_amount ?? a.quoted_rate)}
                        </div>
                        {overBudget && a.agreed_amount == null && (
                            <div
                                data-testid={`applicant-over-budget-${a.id}`}
                                className="mt-1 text-[11px] text-amber-300"
                            >
                                ₹{formatRupees(a.quoted_rate - budget)} over budget
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {a.pitch && (
                <blockquote
                    data-testid={`applicant-pitch-${a.id}`}
                    className="border-l-2 border-ember-500/40 pl-4 text-sm leading-relaxed text-foreground/85"
                >
                    {a.pitch}
                </blockquote>
            )}

            {/* Contact details, once you're working together */}
            {(c.email || c.phone) && (
                <div className="flex flex-wrap items-center gap-4 rounded-md border border-white/10 bg-background/40 px-4 py-3 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5 text-ember-500">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Contact unlocked
                    </span>
                    {c.phone && (
                        <span className="inline-flex items-center gap-1.5">
                            <Phone className="h-3.5 w-3.5" />
                            {c.phone}
                        </span>
                    )}
                    {c.email && <span>{c.email}</span>}
                </div>
            )}

            {a.scheduled_at && (
                <div
                    data-testid={`applicant-slot-${a.id}`}
                    className="flex flex-wrap items-center gap-2 text-sm text-sky-300"
                >
                    <Clock className="h-4 w-4" />
                    {formatDateTime(a.scheduled_at)}
                    {a.location_note && (
                        <span className="text-muted-foreground">· {a.location_note}</span>
                    )}
                </div>
            )}

            {a.content_urls?.length > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Submitted
                    </span>
                    {a.content_urls.map((u, i) => (
                        <a
                            key={u + i}
                            href={u}
                            target="_blank"
                            rel="noreferrer"
                            data-testid={`applicant-content-${a.id}-${i}`}
                            className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-background/60 px-2.5 py-1 text-[10px] uppercase tracking-[0.15em] text-ember-500 transition-colors duration-200 hover:border-ember-500/40"
                        >
                            <LinkIcon className="h-3 w-3" />
                            Post {i + 1}
                            <ExternalLink className="h-3 w-3" />
                        </a>
                    ))}
                </div>
            )}

            {a.revision_note && (
                <p
                    data-testid={`applicant-revision-${a.id}`}
                    className="rounded-md border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
                >
                    <span className="uppercase tracking-[0.15em] text-[10px]">
                        You asked for
                    </span>
                    <br />
                    {a.revision_note}
                </p>
            )}

            {a.exit_reason && (
                <p className="text-sm text-muted-foreground">
                    Reason given: {a.exit_reason}
                </p>
            )}

            {meta.note && !a.can_accept && !a.can_review_content && (
                <p className="text-xs text-muted-foreground">{meta.note}</p>
            )}

            {/* Actions */}
            {(a.can_accept || a.can_decline || a.can_review_content) && (
                <div className="flex flex-wrap items-center gap-2 border-t border-white/10 pt-4">
                    {a.can_accept && (
                        <Button
                            data-testid={`applicant-accept-btn-${a.id}`}
                            disabled={busy}
                            onClick={() => onAccept(a)}
                            className="rounded-full bg-emerald-500/90 text-black hover:bg-emerald-400"
                        >
                            <Check className="mr-1.5 h-4 w-4" />
                            Accept
                        </Button>
                    )}
                    {a.can_review_content && (
                        <>
                            <Button
                                data-testid={`applicant-approve-btn-${a.id}`}
                                disabled={busy}
                                onClick={() => onApprove(a)}
                                className="rounded-full bg-emerald-500/90 text-black hover:bg-emerald-400"
                            >
                                <CheckCircle2 className="mr-1.5 h-4 w-4" />
                                Approve content
                            </Button>
                            <Button
                                data-testid={`applicant-changes-btn-${a.id}`}
                                disabled={busy}
                                variant="outline"
                                onClick={() => onRequestChanges(a)}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                <MessageSquare className="mr-1.5 h-4 w-4" />
                                Ask for a change
                            </Button>
                        </>
                    )}
                    {a.can_decline && (
                        <Button
                            data-testid={`applicant-decline-btn-${a.id}`}
                            disabled={busy}
                            variant="outline"
                            onClick={() => onDecline(a)}
                            className="rounded-full border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10 hover:text-red-200"
                        >
                            <X className="mr-1.5 h-4 w-4" />
                            Decline
                        </Button>
                    )}
                </div>
            )}
        </li>
    );
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const FILTERS = [
    { key: "awaiting_you", label: "Waiting on you", states: ["verified"] },
    { key: "content", label: "Content to review", states: ["content_submitted"] },
    {
        key: "in_progress",
        label: "In progress",
        states: ["accepted", "commercial_agreed", "slot_booked", "attended", "content_approved", "in_payment"],
    },
    { key: "with_weare", label: "With WeAre", states: ["applied"] },
    { key: "closed", label: "Closed", states: ["closed", "declined", "cancelled"] },
    { key: "all", label: "Everyone", states: null },
];

export default function BrandCampaignApplicants() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const [busyId, setBusyId] = useState(null);
    const [filter, setFilter] = useState("awaiting_you");
    const [dialog, setDialog] = useState({ kind: null, applicant: null });

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/brand/campaigns/${id}/applicants`);
            setData(data);
            setError("");
        } catch (err) {
            setError(formatApiError(err));
        }
    }, [id]);

    useEffect(() => {
        load();
    }, [load]);

    // Land people on the tab that actually has work in it.
    useEffect(() => {
        if (!data) return;
        const t = data.totals || {};
        if (t.awaiting_you > 0) setFilter("awaiting_you");
        else if (t.needs_content_review > 0) setFilter("content");
        else if (t.in_progress > 0) setFilter("in_progress");
        else setFilter("all");
    }, [data?.campaign?.id]); // eslint-disable-line react-hooks/exhaustive-deps

    const closeDialog = () => setDialog({ kind: null, applicant: null });

    const act = async (applicant, path, body, successMessage) => {
        setBusyId(applicant.id);
        try {
            await api.post(`/brand/collaborations/${applicant.id}/${path}`, body || {});
            toast.success(successMessage);
            closeDialog();
            await load();
        } catch (err) {
            toast.error(formatApiError(err));
            // A 409 means somebody else moved it — refresh so the buttons match.
            if (err?.response?.status === 409) await load();
        } finally {
            setBusyId(null);
        }
    };

    // Memoised so the filter counts below don't recompute on every render.
    const applicants = useMemo(() => data?.applicants || [], [data]);
    const counts = useMemo(() => {
        const out = {};
        for (const f of FILTERS) {
            out[f.key] = f.states
                ? applicants.filter((a) => f.states.includes(a.state)).length
                : applicants.length;
        }
        return out;
    }, [applicants]);

    const visible = useMemo(() => {
        const f = FILTERS.find((x) => x.key === filter);
        if (!f || !f.states) return applicants;
        return applicants.filter((a) => f.states.includes(a.state));
    }, [applicants, filter]);

    if (!data && !error) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <div className="grid place-items-center py-32 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                </div>
            </div>
        );
    }

    if (error && !data) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <div className="mx-auto max-w-2xl px-6 py-24 text-center">
                    <p className="font-serif text-3xl">Campaign not found</p>
                    <p className="mt-4 text-sm text-muted-foreground">{error}</p>
                    <Button
                        onClick={() => navigate("/dashboard")}
                        className="mt-8 rounded-full bg-ember-500 text-black hover:bg-ember-400"
                    >
                        Back to dashboard
                    </Button>
                </div>
            </div>
        );
    }

    const campaign = data.campaign;
    const totals = data.totals || {};

    return (
        <div
            data-testid="brand-applicants-page"
            className="min-h-screen bg-background text-foreground"
        >
            <Navbar />
            <main className="mx-auto max-w-5xl px-6 py-12 md:py-16">
                <Link
                    to="/dashboard"
                    data-testid="applicants-back-link"
                    className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.2em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Your campaigns
                </Link>

                <p className="mt-6 text-xs uppercase tracking-[0.2em] text-ember-500">
                    Applicants
                </p>
                <h1
                    data-testid="applicants-campaign-title"
                    className="mt-3 max-w-3xl font-serif text-4xl leading-none tracking-tight md:text-5xl"
                >
                    {campaign.title}
                </h1>
                <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                        <IndianRupee className="h-3.5 w-3.5" />
                        {formatRupees(campaign.budget_per_creator)} per creator
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                        <Users className="h-3.5 w-3.5" />
                        {campaign.filled_slots} of {campaign.creators_needed} confirmed
                    </span>
                    {campaign.area && <span>{campaign.area}</span>}
                    {campaign.category && (
                        <span>{CAT_LABEL[campaign.category] || campaign.category}</span>
                    )}
                </div>

                {totals.awaiting_you > 0 && (
                    <div
                        data-testid="applicants-action-banner"
                        className="mt-8 flex items-start gap-3 rounded-md border border-ember-500/30 bg-ember-500/10 p-4 text-sm text-ember-500/90"
                    >
                        <Send className="mt-0.5 h-4 w-4 flex-none" />
                        <p>
                            {totals.awaiting_you}{" "}
                            {totals.awaiting_you === 1 ? "creator is" : "creators are"} verified
                            and waiting on your decision.
                            {campaign.spots_left > 0
                                ? ` You have ${campaign.spots_left} ${
                                      campaign.spots_left === 1 ? "spot" : "spots"
                                  } left.`
                                : " Your slots are full — declining someone frees one up."}
                        </p>
                    </div>
                )}

                {/* Filters */}
                <div
                    data-testid="applicants-filters"
                    className="mt-10 flex flex-wrap gap-2 border-b border-white/10 pb-5"
                >
                    {FILTERS.map((f) => {
                        const active = filter === f.key;
                        const n = counts[f.key] || 0;
                        return (
                            <button
                                key={f.key}
                                type="button"
                                aria-pressed={active}
                                data-testid={`applicants-filter-${f.key}`}
                                onClick={() => setFilter(f.key)}
                                className={
                                    "rounded-full border px-4 py-1.5 text-xs uppercase tracking-[0.15em] transition-colors duration-200 " +
                                    (active
                                        ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                        : "border-white/10 bg-transparent text-muted-foreground hover:border-white/25 hover:text-foreground")
                                }
                            >
                                {f.label}
                                <span className="ml-2 text-[10px] opacity-70">{n}</span>
                            </button>
                        );
                    })}
                </div>

                <div className="mt-8 overflow-hidden rounded-md border border-white/10 bg-card">
                    {visible.length === 0 ? (
                        <div
                            data-testid="applicants-empty"
                            className="flex flex-col items-center gap-3 px-6 py-16 text-center"
                        >
                            <Users className="h-6 w-6 text-ember-500" />
                            <p className="font-serif text-2xl">
                                {applicants.length === 0
                                    ? "No applications yet."
                                    : "Nothing in this list."}
                            </p>
                            <p className="max-w-md text-sm text-muted-foreground">
                                {applicants.length === 0
                                    ? "Verified creators see this brief on their feed. Applications usually start within a day of publishing."
                                    : "Try another tab — there's work in one of them."}
                            </p>
                        </div>
                    ) : (
                        <ul className="divide-y divide-white/10">
                            {visible.map((a) => (
                                <ApplicantCard
                                    key={a.id}
                                    applicant={a}
                                    budget={campaign.budget_per_creator}
                                    busy={busyId === a.id}
                                    onAccept={(x) => setDialog({ kind: "accept", applicant: x })}
                                    onDecline={(x) => setDialog({ kind: "decline", applicant: x })}
                                    onApprove={(x) =>
                                        act(x, "approve_content", null, "Content approved")
                                    }
                                    onRequestChanges={(x) =>
                                        setDialog({ kind: "changes", applicant: x })
                                    }
                                />
                            ))}
                        </ul>
                    )}
                </div>
            </main>

            <AcceptDialog
                open={dialog.kind === "accept"}
                onOpenChange={(v) => !v && closeDialog()}
                applicant={dialog.applicant}
                budget={campaign.budget_per_creator}
                busy={busyId === dialog.applicant?.id}
                onConfirm={(body) =>
                    act(dialog.applicant, "accept", body, "Creator accepted")
                }
            />

            <ReasonDialog
                open={dialog.kind === "decline"}
                onOpenChange={(v) => !v && closeDialog()}
                kicker="Decline applicant"
                title={dialog.applicant?.creator?.name || "Decline"}
                description="They'll be told, so they're not left waiting. A short reason helps them pitch better next time."
                label="Reason (optional)"
                placeholder="e.g. Looking for a more food-focused audience this time."
                confirmLabel="Decline applicant"
                destructive
                busy={busyId === dialog.applicant?.id}
                onConfirm={(reason) =>
                    act(dialog.applicant, "decline", { reason }, "Applicant declined")
                }
            />

            <ReasonDialog
                open={dialog.kind === "changes"}
                onOpenChange={(v) => !v && closeDialog()}
                kicker="Request a change"
                title="What needs to change?"
                description="The creator gets this note and can resubmit without starting over."
                label="What to change"
                placeholder="e.g. Could you add the venue tag to the reel caption?"
                confirmLabel="Send request"
                required
                busy={busyId === dialog.applicant?.id}
                onConfirm={(reason) =>
                    act(
                        dialog.applicant,
                        "request_changes",
                        { reason },
                        "Change request sent",
                    )
                }
            />
        </div>
    );
}
