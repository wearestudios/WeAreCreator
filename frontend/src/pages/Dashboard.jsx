import React, { useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import {
    ArrowRight,
    CheckCircle2,
    Clock,
    Compass,
    ExternalLink,
    Instagram,
    Link as LinkIcon,
    Loader2,
    Plus as PlusIcon,
    Send,
    Sparkles,
    Users,
    Wallet,
    IndianRupee,
    X as XIcon,
    XCircle,
    CalendarClock,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { useAuth, homePathFor } from "@/context/AuthContext";
import { api, formatApiError, mediaUrl } from "@/lib/api";
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
import BrandDashboardView from "@/pages/BrandDashboardView";

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    lifestyle: "Lifestyle",
};

const STATE_META = {
    applied: {
        label: "Applied",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    },
    verified: {
        label: "With the brand",
        tone: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    },
    accepted: {
        label: "Accepted",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    commercial_agreed: {
        label: "Commercial agreed",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    slot_booked: {
        label: "Slot booked",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    attended: {
        label: "Attended",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    },
    content_submitted: {
        label: "In review",
        tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    },
    content_approved: {
        label: "Approved",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    },
    in_payment: {
        label: "In payment",
        tone: "bg-ember-500/15 text-ember-500 border-ember-500/30",
    },
    closed: {
        label: "Paid",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    },
    declined: {
        label: "Not taken forward",
        tone: "bg-white/5 text-muted-foreground border-white/15",
    },
    cancelled: {
        label: "Cancelled",
        tone: "bg-red-500/10 text-red-300/80 border-red-500/25",
    },
};

const StatePill = ({ state }) => {
    const meta = STATE_META[state] || {
        label: state,
        tone: "bg-white/5 text-muted-foreground border-white/15",
    };
    return (
        <span
            data-testid={`state-pill-${state}`}
            className={
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                meta.tone
            }
        >
            {meta.label}
        </span>
    );
};

const formatRupees = (n) =>
    typeof n === "number" ? n.toLocaleString("en-IN") : "—";

const formatCompact = (n) => {
    if (typeof n !== "number") return "—";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
    return n.toString();
};

const formatDate = (iso) => {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric",
        });
    } catch {
        return iso;
    }
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

// ---------------------------------------------------------------------------
// Creator dashboard
// ---------------------------------------------------------------------------

const VERIFICATION_META = {
    pending: {
        Icon: Clock,
        label: "Under review",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    },
    verified: {
        Icon: CheckCircle2,
        label: "Verified",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
    },
    rejected: {
        Icon: XCircle,
        label: "Needs changes",
        tone: "bg-red-500/15 text-red-300 border-red-500/40",
    },
};

const CreatorHeader = ({ user, profile }) => {
    const meta = VERIFICATION_META[profile?.verification_status] || VERIFICATION_META.pending;
    const handle = profile?.instagram_handle;
    return (
        <header data-testid="creator-header" className="grid gap-6 md:grid-cols-12 md:items-end">
            <div className="md:col-span-8">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Creator · India
                </p>
                {profile?.profile_image_url && (
                    <img
                        src={mediaUrl(profile.profile_image_url)}
                        alt=""
                        data-testid="creator-profile-image"
                        className="mt-4 h-16 w-16 rounded-md border border-white/10 object-cover"
                    />
                )}
                <h1
                    data-testid="creator-name-heading"
                    className="mt-3 font-serif text-4xl leading-none tracking-tight md:text-5xl"
                >
                    {profile?.name || user.name}
                </h1>
                <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                    {handle ? (
                        <a
                            href={
                                profile?.instagram_profile_url ||
                                `https://instagram.com/${handle}`
                            }
                            target="_blank"
                            rel="noreferrer"
                            data-testid="creator-ig-handle"
                            className="inline-flex items-center gap-1.5 transition-colors duration-200 hover:text-ember-500"
                        >
                            <Instagram className="h-4 w-4" />@{handle}
                        </a>
                    ) : (
                        <span
                            data-testid="creator-ig-handle-empty"
                            className="text-muted-foreground"
                        >
                            No Instagram handle yet
                        </span>
                    )}
                    <span className="text-muted-foreground/60">·</span>
                    <span
                        data-testid={`verification-badge-${profile?.verification_status || "pending"}`}
                        className={
                            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] " +
                            meta.tone
                        }
                    >
                        <meta.Icon className="h-3.5 w-3.5" />
                        {meta.label}
                    </span>
                </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 md:col-span-4 md:justify-end">
                <Link to="/onboarding/creator" data-testid="header-edit-profile">
                    <Button
                        variant="outline"
                        className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                    >
                        Edit profile
                    </Button>
                </Link>
                <Link to="/campaigns" data-testid="header-browse-campaigns">
                    <Button className="group rounded-full bg-ember-500 text-black hover:bg-ember-400">
                        Browse campaigns
                        <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                    </Button>
                </Link>
            </div>
        </header>
    );
};

const StatsPanel = ({ profile }) => {
    const niches = profile?.niches || [];
    const followers = profile?.follower_count;

    return (
        <section
            data-testid="stats-panel"
            className="mt-10 grid gap-4 md:grid-cols-12"
        >
            <div className="rounded-md border border-white/10 bg-card p-7 md:col-span-4">
                <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Followers
                    </p>
                    <Users className="h-4 w-4 text-ember-500" />
                </div>
                <div
                    data-testid="stat-followers"
                    className="mt-6 font-serif text-4xl md:text-5xl"
                >
                    {formatCompact(followers)}
                </div>
                {/* Said plainly. The figure is the creator's own until we have a
                    source we're allowed to measure it with. */}
                <div className="mt-3 space-y-2 text-xs text-muted-foreground">
                    <p data-testid="stat-source-note">Self-reported</p>
                    <p
                        data-testid="stat-verified-coming"
                        className="leading-relaxed"
                    >
                        Verified audience stats are coming. Until then brands see
                        this as your own figure — keep it accurate.
                    </p>
                    <Link
                        to="/onboarding/creator"
                        data-testid="stat-edit-followers"
                        className="inline-block underline underline-offset-2 transition-colors duration-200 hover:text-ember-500"
                    >
                        Update your count
                    </Link>
                </div>
            </div>

            <div className="rounded-md border border-white/10 bg-card p-7 md:col-span-5">
                <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Your niches
                    </p>
                    <Sparkles className="h-4 w-4 text-ember-500" />
                </div>
                <div data-testid="stat-niches" className="mt-5 flex flex-wrap gap-2">
                    {niches.length === 0 && (
                        <p className="text-sm text-muted-foreground">
                            No niches yet — add some on your profile.
                        </p>
                    )}
                    {niches.map((n) => (
                        <span
                            key={n}
                            data-testid={`stat-niche-${n}`}
                            className="rounded-full bg-ember-500/15 px-3 py-1 text-xs uppercase tracking-[0.15em] text-ember-500"
                        >
                            {n}
                        </span>
                    ))}
                </div>
            </div>

            <div className="rounded-md border border-white/10 bg-card p-7 md:col-span-3">
                <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Base rate
                    </p>
                    <IndianRupee className="h-4 w-4 text-ember-500" />
                </div>
                <div className="mt-6 flex items-baseline font-serif text-4xl md:text-5xl">
                    {profile?.base_rate != null ? (
                        <>
                            <IndianRupee className="h-6 w-6 text-ember-500 md:h-7 md:w-7" />
                            {formatRupees(profile.base_rate)}
                        </>
                    ) : (
                        <span className="text-muted-foreground">—</span>
                    )}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                    Per collab · edit any time
                </p>
            </div>
        </section>
    );
};

function SubmitContentDialog({ open, onOpenChange, collab, onSubmitted }) {
    const [urls, setUrls] = useState([""]);
    const [err, setErr] = useState("");
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        if (open) {
            const initial =
                collab?.content_urls && collab.content_urls.length > 0
                    ? [...collab.content_urls]
                    : collab?.content_url
                    ? [collab.content_url]
                    : [""];
            setUrls(initial.length ? initial : [""]);
            setErr("");
        }
    }, [open, collab]);

    const setAt = (i, v) =>
        setUrls((prev) => prev.map((u, j) => (j === i ? v : u)));
    const addRow = () => setUrls((prev) => [...prev, ""]);
    const removeAt = (i) =>
        setUrls((prev) => (prev.length <= 1 ? [""] : prev.filter((_, j) => j !== i)));

    const submit = async (e) => {
        e.preventDefault();
        setErr("");
        const clean = [];
        for (const raw of urls) {
            const u = (raw || "").trim();
            if (!u) continue;
            if (!/^https?:\/\/.+\..+/i.test(u)) {
                setErr("Every URL must start with http:// or https:// and look like a real link.");
                return;
            }
            if (!clean.includes(u)) clean.push(u);
        }
        if (clean.length === 0) {
            setErr("Paste at least one link to your published post or reel.");
            return;
        }
        if (clean.length > 25) {
            setErr("You can submit up to 25 URLs at a time.");
            return;
        }
        setBusy(true);
        try {
            await api.post(
                `/creator/collaborations/${collab.id}/submit_content`,
                { content_urls: clean },
            );
            toast.success(
                clean.length === 1
                    ? "Content submitted — the WeAre team will review it"
                    : `${clean.length} links submitted — the WeAre team will review them`,
            );
            onOpenChange(false);
            onSubmitted?.();
        } catch (e) {
            setErr(formatApiError(e));
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid="submit-content-dialog"
                className="max-w-lg rounded-md border border-white/10 bg-card"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Submit content
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        {collab?.campaign_title}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm text-muted-foreground">
                        Paste every published link — reel, carousel, stories archive.
                        Add as many as your deliverable calls for.
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={submit} noValidate className="mt-4 space-y-4">
                    <div className="space-y-3">
                        {urls.map((u, i) => (
                            <div key={i} className="space-y-1">
                                <Label
                                    htmlFor={`sc-url-${i}`}
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    URL {i + 1}
                                </Label>
                                <div className="relative">
                                    <LinkIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id={`sc-url-${i}`}
                                        data-testid={
                                            i === 0
                                                ? "submit-content-url-input"
                                                : `submit-content-url-input-${i}`
                                        }
                                        type="url"
                                        inputMode="url"
                                        value={u}
                                        onChange={(e) => setAt(i, e.target.value)}
                                        className="h-11 border-white/10 bg-background/60 pl-9 pr-10 focus-visible:ring-ember-500"
                                        placeholder="https://instagram.com/p/..."
                                    />
                                    {urls.length > 1 && (
                                        <button
                                            type="button"
                                            aria-label={`Remove URL ${i + 1}`}
                                            data-testid={`submit-content-remove-${i}`}
                                            onClick={() => removeAt(i)}
                                            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-muted-foreground transition-colors duration-200 hover:bg-white/5 hover:text-red-300"
                                        >
                                            <XIcon className="h-3.5 w-3.5" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>

                    <button
                        type="button"
                        data-testid="submit-content-add-url"
                        onClick={addRow}
                        disabled={urls.length >= 25}
                        className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-transparent px-3 py-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 disabled:opacity-40"
                    >
                        <PlusIcon className="h-3.5 w-3.5" />
                        Add another URL
                    </button>

                    {err && (
                        <p
                            data-testid="submit-content-error"
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
                                data-testid="submit-content-cancel"
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            data-testid="submit-content-submit"
                            disabled={busy}
                            className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {busy ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Submitting…
                                </>
                            ) : (
                                <>
                                    <Send className="mr-2 h-4 w-4" />
                                    Submit content
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

const ApplicationsSection = ({ applications, onRefresh }) => {
    const [dialog, setDialog] = useState({ open: false, collab: null });
    const openFor = (a) => setDialog({ open: true, collab: a });
    return (
        <section
            data-testid="applications-section"
            className="mt-14"
        >
            <div className="flex items-baseline justify-between">
                <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        My applications
                    </p>
                    <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                        Every brief you've pitched on.
                    </h2>
                </div>
                <span className="text-xs text-muted-foreground">
                    {applications.length}{" "}
                    {applications.length === 1 ? "application" : "applications"}
                </span>
            </div>

            <div className="mt-8 overflow-hidden rounded-md border border-white/10 bg-card">
                {applications.length === 0 ? (
                    <div
                        data-testid="applications-empty"
                        className="flex flex-col items-center gap-3 px-6 py-16 text-center"
                    >
                        <Compass className="h-6 w-6 text-ember-500" />
                        <p className="font-serif text-2xl">
                            You haven't applied to anything yet.
                        </p>
                        <p className="max-w-md text-sm text-muted-foreground">
                            Browse the live campaign feed and pitch on the ones that fit you.
                        </p>
                        <Link
                            to="/campaigns"
                            data-testid="applications-browse-link"
                            className="mt-4"
                        >
                            <Button className="rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                Browse campaigns
                            </Button>
                        </Link>
                    </div>
                ) : (
                    <ul className="divide-y divide-white/10">
                        {applications.map((a) => {
                            // The API decides when submission is open, so the button
                            // never appears for a state the server will refuse.
                            const canSubmit =
                                a.can_submit_content ?? a.state === "attended";
                            return (
                                <li
                                    key={a.id}
                                    data-testid={`application-row-${a.id}`}
                                    className="flex flex-col gap-4 px-5 py-5 transition-colors duration-200 md:flex-row md:items-center md:gap-6 md:px-6 md:py-6"
                                >
                                    <Link
                                        to={`/campaigns/${a.campaign_id}`}
                                        className="group flex flex-1 min-w-0 flex-col gap-1 hover:text-ember-500"
                                    >
                                        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                            {a.brand_name || "Brand"}
                                            {a.area ? ` · ${a.area}` : ""}
                                            {a.category ? ` · ${CAT_LABEL[a.category] || a.category}` : ""}
                                        </div>
                                        <div className="mt-0.5 truncate font-serif text-xl leading-tight text-foreground group-hover:text-ember-500">
                                            {a.campaign_title || "Untitled campaign"}
                                        </div>
                                        <div className="mt-2 text-xs text-muted-foreground">
                                            Applied {formatDate(a.created_at)}
                                        </div>
                                        {a.scheduled_at && (
                                            <div
                                                data-testid={`application-slot-${a.id}`}
                                                className="mt-2 inline-flex items-center gap-1.5 text-xs text-sky-300"
                                            >
                                                <CalendarClock className="h-3.5 w-3.5" />
                                                {formatDateTime(a.scheduled_at)}
                                                {a.location_note ? ` · ${a.location_note}` : ""}
                                            </div>
                                        )}
                                        {a.revision_note && (
                                            <div
                                                data-testid={`application-revision-${a.id}`}
                                                className="mt-2 rounded-md border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs leading-relaxed text-amber-200"
                                            >
                                                <span className="uppercase tracking-[0.15em]">
                                                    Changes asked for
                                                </span>
                                                <br />
                                                {a.revision_note}
                                            </div>
                                        )}
                                        {a.exit_reason && (
                                            <div
                                                data-testid={`application-exit-${a.id}`}
                                                className="mt-2 text-xs leading-relaxed text-muted-foreground"
                                            >
                                                {a.exit_reason}
                                            </div>
                                        )}
                                    </Link>

                                    <div className="flex flex-col items-stretch gap-2 md:items-end md:min-w-[220px]">
                                        <div className="flex items-baseline font-serif text-2xl md:justify-end">
                                            <IndianRupee className="h-4 w-4 text-ember-500" />
                                            {formatRupees(a.quoted_rate)}
                                        </div>
                                        <StatePill state={a.state} />
                                        {canSubmit && (
                                            <Button
                                                data-testid={`submit-content-btn-${a.id}`}
                                                onClick={() => openFor(a)}
                                                className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                                            >
                                                <Send className="mr-1.5 h-4 w-4" />
                                                {a.state === "content_submitted"
                                                    ? "Edit links"
                                                    : "Submit content"}
                                            </Button>
                                        )}
                                        {a.content_urls && a.content_urls.length > 0 && (
                                            <div className="flex flex-wrap gap-1.5 md:justify-end">
                                                {a.content_urls.map((u, i) => (
                                                    <a
                                                        key={u + i}
                                                        href={u}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        data-testid={
                                                            i === 0
                                                                ? `application-content-link-${a.id}`
                                                                : `application-content-link-${a.id}-${i}`
                                                        }
                                                        className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-background/60 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.15em] text-ember-500 transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-400"
                                                    >
                                                        <LinkIcon className="h-3 w-3" />
                                                        Post {i + 1}
                                                        <ExternalLink className="h-3 w-3" />
                                                    </a>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>

            <SubmitContentDialog
                open={dialog.open}
                onOpenChange={(v) => setDialog((d) => ({ ...d, open: v }))}
                collab={dialog.collab}
                onSubmitted={onRefresh}
            />
        </section>
    );
};

const UpcomingSection = ({ upcoming }) => (
    <section data-testid="upcoming-section" className="mt-14">
        <div className="flex items-baseline justify-between">
            <div>
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Upcoming
                </p>
                <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                    Slots on your calendar.
                </h2>
            </div>
            <span className="text-xs text-muted-foreground">
                {upcoming.length} booked
            </span>
        </div>
        <div className="mt-8 rounded-md border border-white/10 bg-card">
            {upcoming.length === 0 ? (
                <div
                    data-testid="upcoming-empty"
                    className="flex items-center gap-4 px-6 py-10 text-sm text-muted-foreground"
                >
                    <CalendarClock className="h-5 w-5 flex-none text-ember-500" />
                    <p>
                        Nothing on the calendar yet. Once a brand books your slot, it
                        will show up here.
                    </p>
                </div>
            ) : (
                <ul className="divide-y divide-white/10">
                    {upcoming.map((u) => (
                        <li key={u.id} data-testid={`upcoming-row-${u.id}`}>
                            <Link
                                to={`/campaigns/${u.campaign_id}`}
                                className="flex flex-col gap-3 px-6 py-5 transition-colors duration-200 hover:bg-white/5 md:flex-row md:items-center md:gap-6"
                            >
                                <div className="flex-1">
                                    <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        {u.brand_name || "Brand"}
                                        {u.area ? ` · ${u.area}` : ""}
                                    </div>
                                    <div className="mt-1 font-serif text-xl leading-tight">
                                        {u.campaign_title}
                                    </div>
                                    {u.scheduled_at && (
                                        <div
                                            data-testid={`upcoming-when-${u.id}`}
                                            className="mt-2 inline-flex items-center gap-1.5 text-sm text-sky-300"
                                        >
                                            <CalendarClock className="h-4 w-4" />
                                            {formatDateTime(u.scheduled_at)}
                                            {u.location_note ? (
                                                <span className="text-muted-foreground">
                                                    · {u.location_note}
                                                </span>
                                            ) : null}
                                        </div>
                                    )}
                                </div>
                                <StatePill state={u.state} />
                            </Link>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    </section>
);

const PaymentsSection = ({ payments, inPaymentCollabs }) => {
    const totalPaid = payments
        .filter((p) => p.state === "paid")
        .reduce((sum, p) => sum + (typeof p.creator_payout === "number" ? p.creator_payout : 0), 0);
    const items = [
        ...payments.map((p) => ({
            id: p.id,
            campaign_id: null,
            campaign_title: p.campaign_title,
            brand_name: p.brand_name,
            amount: p.creator_payout ?? p.agreed_amount,
            state: p.state,
            paid_at: p.paid_at,
        })),
        ...inPaymentCollabs.map((c) => ({
            id: c.id,
            campaign_id: c.campaign_id,
            campaign_title: c.campaign_title,
            brand_name: c.brand_name,
            amount: c.agreed_amount ?? c.quoted_rate,
            state: "in_payment",
            paid_at: null,
        })),
    ];

    return (
        <section data-testid="payments-section" className="mt-14">
            <div className="flex items-baseline justify-between">
                <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Payments
                    </p>
                    <h2 className="mt-3 font-serif text-3xl leading-none tracking-tight md:text-4xl">
                        Where your money lives.
                    </h2>
                </div>
                {totalPaid > 0 && (
                    <div className="text-right">
                        <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            Paid to date
                        </div>
                        <div className="mt-1 flex items-baseline font-serif text-3xl">
                            <IndianRupee className="h-5 w-5 text-ember-500" />
                            {formatRupees(totalPaid)}
                        </div>
                    </div>
                )}
            </div>

            <div className="mt-8 rounded-md border border-white/10 bg-card">
                {items.length === 0 ? (
                    <div
                        data-testid="payments-empty"
                        className="flex items-center gap-4 px-6 py-10 text-sm text-muted-foreground"
                    >
                        <Wallet className="h-5 w-5 flex-none text-ember-500" />
                        <p>
                            No payouts yet. Once a brand approves your content, the
                            payment shows up here.
                        </p>
                    </div>
                ) : (
                    <ul className="divide-y divide-white/10">
                        {items.map((p) => (
                            <li
                                key={p.id}
                                data-testid={`payment-row-${p.id}`}
                                className="flex flex-col gap-3 px-6 py-5 md:flex-row md:items-center md:gap-6"
                            >
                                <div className="flex-1">
                                    <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        {p.brand_name || "Brand"}
                                    </div>
                                    <div className="mt-1 font-serif text-xl leading-tight">
                                        {p.campaign_title || "—"}
                                    </div>
                                    {p.paid_at && (
                                        <div className="mt-1 text-xs text-muted-foreground">
                                            Paid {formatDate(p.paid_at)}
                                        </div>
                                    )}
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                    <div className="flex items-baseline font-serif text-2xl">
                                        <IndianRupee className="h-4 w-4 text-ember-500" />
                                        {formatRupees(p.amount)}
                                    </div>
                                    <StatePill state={p.state} />
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </section>
    );
};

// ---------------------------------------------------------------------------
// Verification banner (post-onboarding welcome)
// ---------------------------------------------------------------------------

const OnboardedBanner = ({ visible }) => {
    if (!visible) return null;
    return (
        <div
            data-testid="just-onboarded-banner"
            className="mt-8 flex items-start gap-3 rounded-md border border-ember-500/30 bg-ember-500/10 p-4 text-sm text-ember-500/90"
        >
            <Sparkles className="mt-0.5 h-4 w-4 flex-none" />
            <p>
                Thanks — your profile is with the WeAre team. Reviews usually finish
                within 48 hours, and briefs open up to you the moment you're approved.
            </p>
        </div>
    );
};

/**
 * The two things that block a creator from earning: not being verified yet, and
 * having no payout details on file. Both used to be silent.
 */
const StatusBanners = ({ profile }) => {
    const status = profile?.verification_status;
    return (
        <div className="mt-8 space-y-3">
            {status === "pending" && (
                <div
                    data-testid="verification-pending-banner"
                    className="flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200"
                >
                    <Clock className="mt-0.5 h-4 w-4 flex-none" />
                    <p>
                        Your profile is under review. You'll be able to pitch on briefs
                        as soon as the team approves it — usually within 48 hours.
                    </p>
                </div>
            )}
            {status === "rejected" && (
                <div
                    data-testid="verification-rejected-banner"
                    className="flex items-start gap-3 rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200"
                >
                    <XCircle className="mt-0.5 h-4 w-4 flex-none" />
                    <p>
                        Your profile wasn't approved yet.{" "}
                        <Link
                            to="/onboarding/creator"
                            className="underline underline-offset-4 hover:no-underline"
                        >
                            Update it
                        </Link>{" "}
                        and we'll take another look.
                    </p>
                </div>
            )}
            {status === "verified" && profile?.pending_review && (
                <div
                    data-testid="verification-changes-banner"
                    className="flex items-start gap-3 rounded-md border border-sky-500/30 bg-sky-500/10 p-4 text-sm text-sky-200"
                >
                    <Clock className="mt-0.5 h-4 w-4 flex-none" />
                    <p>
                        You're still live and visible to brands. We're just taking a
                        second look at the details you changed.
                    </p>
                </div>
            )}
            {status === "verified" && !profile?.payout_ready && (
                <div
                    data-testid="payout-missing-banner"
                    className="flex items-start gap-3 rounded-md border border-ember-500/30 bg-ember-500/10 p-4 text-sm text-ember-500/90"
                >
                    <Wallet className="mt-0.5 h-4 w-4 flex-none" />
                    <p>
                        Add your UPI ID and PAN so we can pay you — we can't release a
                        payout without them.{" "}
                        <Link
                            to="/onboarding/creator"
                            data-testid="payout-missing-link"
                            className="underline underline-offset-4 hover:no-underline"
                        >
                            Add payout details
                        </Link>
                    </p>
                </div>
            )}
        </div>
    );
};

const CreatorDashboard = ({ user, justOnboarded }) => {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");

    const load = React.useCallback(async () => {
        try {
            const { data } = await api.get("/creator/dashboard");
            setData(data);
        } catch (err) {
            setError(err?.response?.data?.detail || "Failed to load dashboard");
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    return (
        <div data-testid="dashboard-page" className="min-h-screen bg-background">
            <Navbar />
            <main className="mx-auto max-w-7xl px-6 py-12 md:py-16">
                {!data && !error && (
                    <div className="grid place-items-center py-24 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin" />
                    </div>
                )}
                {error && (
                    <p
                        data-testid="dashboard-error"
                        className="text-sm text-destructive"
                    >
                        {error}
                    </p>
                )}
                {data && (
                    <>
                        <CreatorHeader user={user} profile={data.profile} />
                        <OnboardedBanner visible={justOnboarded} />
                        <StatusBanners profile={data.profile} />
                        <StatsPanel profile={data.profile} />
                        <ApplicationsSection applications={data.applications} onRefresh={load} />
                        <UpcomingSection upcoming={data.upcoming} />
                        <PaymentsSection
                            payments={data.payments}
                            inPaymentCollabs={data.in_payment_collaborations || []}
                        />
                        <div className="mt-16 rounded-md border border-white/10 bg-card/40 p-6 text-sm text-muted-foreground">
                            <span className="text-foreground">Signed in as</span>{" "}
                            {/* Accounts created over WhatsApp have no email. */}
                            {user.email || user.phone || user.name} ·{" "}
                            <span className="uppercase tracking-[0.15em] text-ember-500">
                                {user.role}
                            </span>
                        </div>
                    </>
                )}
            </main>
        </div>
    );
};

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export default function Dashboard() {
    const { user } = useAuth();
    const location = useLocation();
    if (!user || user === false) return null;
    const justOnboarded = Boolean(location.state?.justOnboarded);
    if (user.role === "creator") {
        return <CreatorDashboard user={user} justOnboarded={justOnboarded} />;
    }
    if (user.role === "brand") {
        return <BrandDashboardView user={user} />;
    }
    // Admins have no dashboard of their own — the console is their home.
    return <Navigate to={homePathFor(user.role)} replace />;
}
