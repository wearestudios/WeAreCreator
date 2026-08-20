import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { notifyError, notifySuccess } from "@/lib/feedback";
import {
    ArrowLeft,
    ArrowRight,
    CalendarDays,
    IndianRupee,
    Loader2,
    Save,
    Send,
    Users,
} from "lucide-react";
import { api, formatApiError } from "@/lib/api";
// Note what is imported: the brand list, never the full one. Barter is a WeAre
// arrangement and the server refuses it on this route — the option is absent
// from this form rather than present and disabled, so there is nothing here to
// enable with a devtools attribute edit.
import { BRAND_COMPENSATION_OPTIONS } from "@/lib/compensation";
import { CATEGORY_OPTIONS } from "@/lib/categories";
import { EXECUTION_OPTIONS } from "@/lib/execution";
import { dayKey } from "@/lib/time";
import { VISIBILITY_OPTIONS } from "@/lib/visibility";
import { COVER, EXECUTION, VISIBILITY } from "@/constants/testIds";
import { Navbar } from "@/components/Navbar";
import ShootPreferences from "@/components/campaign/ShootPreferences";
import DeliverablePicker, {
    emptyDeliverables,
    fromDeliverableItems,
    toDeliverableItems,
} from "@/components/DeliverablePicker";
import ImageUploadField, {
    FALLBACK_IMAGE_MIMES,
    FALLBACK_MAX_IMAGE_BYTES,
} from "@/components/ImageUploadField";
import {
    FormPageSkeleton,
    LoadingAnnouncement,
} from "@/components/data/PageSkeleton";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

// An ISO timestamp back into the yyyy-mm-dd an <input type="date"> expects.
//
// **The IST date, not the UTC one.** `toISOString()` is UTC, so an event at
// 00:30 on the 1st reads back as the 31st and the brand re-saves the wrong
// day without touching the field.
const toDateInput = (iso) => dayKey(iso);

export default function PostCampaign() {
    const navigate = useNavigate();
    // Same form, two jobs: /campaigns/new creates, /campaigns/:id/edit corrects.
    const { id: editingId } = useParams();
    const isEditing = Boolean(editingId);

    const [brandProfile, setBrandProfile] = useState(null);
    const [loadingProfile, setLoadingProfile] = useState(true);
    const [existing, setExisting] = useState(null);

    const [title, setTitle] = useState("");
    const [brief, setBrief] = useState("");
    // The structured ask, as `{reel: 1, story: 3}`. This was a free-text box;
    // see `lib/deliverables.js` for why it stopped being one.
    const [deliverables, setDeliverables] = useState(emptyDeliverables());
    const [budget, setBudget] = useState("");
    // Fixed or negotiated. A brand brief is paid work either way.
    const [compensationType, setCompensationType] = useState("fixed");
    // Defaults to the brand running it: posting a brief means running it
    // unless you say otherwise, and a campaign quietly landing in the WeAre
    // queue is work nobody agreed to. Mirrors DEFAULT_EXECUTION_OWNER.
    const [executionOwner, setExecutionOwner] = useState("brand");
    // Public unless the brand says otherwise — an invite-only brief that
    // nobody meant to hide is merely unfindable, which is worse than wrong.
    const [visibility, setVisibility] = useState("public");
    // On by default here for the same reason the server defaults it on for a
    // brand-run brief: whoever is paying for the work should see it before
    // the creator's audience does. Off is a deliberate choice to make.
    const [requiresDraft, setRequiresDraft] = useState(true);
    // When the venue can take people. Both default to "no restriction",
    // which is what most briefs mean.
    const [restrictedDays, setRestrictedDays] = useState([]);
    const [shootWindows, setShootWindows] = useState([]);
    const [category, setCategory] = useState("");
    const [area, setArea] = useState("");
    const [creatorsNeeded, setCreatorsNeeded] = useState("1");
    // The type decides which date fields exist — see the server's validator.
    const [campaignType, setCampaignType] = useState("personal_table");
    const [eventDate, setEventDate] = useState("");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    // The cover, which has two lives. On an existing campaign it uploads
    // straight away against its own route. On a new one there is no id to
    // upload against yet, so the File waits here and goes up the moment the
    // campaign is created.
    const [coverUrl, setCoverUrl] = useState(null);
    const [pendingCover, setPendingCover] = useState(null);
    const [venueAddress, setVenueAddress] = useState("");
    const [venueInstructions, setVenueInstructions] = useState("");
    const [onSiteContact, setOnSiteContact] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [savingDraft, setSavingDraft] = useState(false);
    const [error, setError] = useState("");

    // Preload the brand profile so we can pre-fill area + category and offer area suggestions.
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.get("/brand/profile");
                if (cancelled) return;
                setBrandProfile(data);
                if (!isEditing) {
                    if (data?.category) setCategory(data.category);
                    if (data?.areas?.length === 1) setArea(data.areas[0]);
                }
            } catch {
                /* the form still works without the profile */
            }

            if (isEditing) {
                try {
                    const { data } = await api.get(`/campaigns/${editingId}`);
                    if (cancelled) return;
                    setExisting(data);
                    setTitle(data.title || "");
                    setBrief(data.brief || "");
                    // Re-seeded from the structure so an edit round trip
                    // doesn't quietly clear what the brief asks for. A brief
                    // posted before the field existed comes back with no items
                    // and starts empty, which is the honest state — its
                    // sentence is still on the campaign until this is saved.
                    setDeliverables(fromDeliverableItems(data.deliverable_items));
                    setBudget(
                        data.budget_per_creator == null
                            ? ""
                            : String(data.budget_per_creator),
                    );
                    setCategory(data.category || "");
                    setArea(data.area || "");
                    // A campaign WeAre set to barter keeps that value here so
                    // the form never round-trips it back to "fixed".
                    setCompensationType(data.compensation_type || "fixed");
                    setExecutionOwner(data.execution_owner || "brand");
                    setVisibility(data.visibility === "private" ? "private" : "public");
                    // Re-seeded rather than defaulted, or fixing a typo on a
                    // brief that doesn't review drafts would quietly turn the
                    // stage on for everybody already working it.
                    setRequiresDraft(Boolean(data.requires_draft_approval));
                    setRestrictedDays(data.restricted_days || []);
                    setShootWindows(data.shoot_windows || []);
                    setCreatorsNeeded(String(data.creators_needed ?? 1));
                    setCampaignType(data.campaign_type || "personal_table");
                    setEventDate(toDateInput(data.event_date));
                    setStartDate(toDateInput(data.start_date));
                    setEndDate(toDateInput(data.end_date));
                    // These three were never loaded, and buildPayload sends
                    // them unconditionally — so opening a campaign for any
                    // edit and saving wiped the venue, the arrival
                    // instructions and the on-site contact, which are the
                    // three things a creator needs to turn up.
                    setCoverUrl(data.cover_image_url || null);
                    setVenueAddress(data.venue_address || "");
                    setVenueInstructions(data.venue_instructions || "");
                    setOnSiteContact(data.on_site_contact || "");
                } catch (err) {
                    if (!cancelled) setError(formatApiError(err));
                }
            }

            if (!cancelled) setLoadingProfile(false);
        })();
        return () => {
            cancelled = true;
        };
    }, [isEditing, editingId]);

    const areaOptions = useMemo(() => {
        const list = brandProfile?.areas?.length
            ? brandProfile.areas
            : [
                  "Bengaluru",
                  "Mumbai",
                  "Delhi NCR",
                  "Hyderabad",
                  "Pune",
                  "Chennai",
                  "Kolkata",
                  "Goa",
                  "Ahmedabad",
                  "Jaipur",
              ];
        return list;
    }, [brandProfile]);

    // Only ever true on a campaign WeAre converted — this form cannot set it.
    // The brand edit route refuses any write to the compensation of a barter
    // campaign, so sending one would fail the whole save over a field the brand
    // was never shown.
    const isBarter = compensationType === "barter";

    const validateBase = () => {
        if (!title.trim()) return "Please enter a campaign title.";
        if (!brief.trim()) return "Please add a brief.";
        if (toDeliverableItems(deliverables).length === 0)
            return "What are you asking for? Pick at least one deliverable.";
        if (!isBarter) {
            const budgetNum = Number(budget);
            if (!Number.isFinite(budgetNum) || budgetNum < 0)
                return "Please enter a valid budget per creator.";
        }
        if (!category) return "Please pick a category.";
        if (!area) return "Please pick an area.";
        const needed = Number(creatorsNeeded);
        if (!Number.isFinite(needed) || needed < 1)
            return "How many creators do you need?";
        if (campaignType === "personal_table") {
            if (!startDate || !endDate)
                return "A personal table runs over a window — pick both dates.";
            if (new Date(endDate) < new Date(startDate))
                return "End date cannot be before the start date.";
        } else if (!eventDate) {
            return "Pick the day the event happens.";
        }
        return null;
    };

    const buildPayload = (status) => ({
        title: title.trim(),
        brief: brief.trim(),
        deliverable_items: toDeliverableItems(deliverables),
        // Both omitted on a barter campaign: the field isn't rendered, so
        // Number("") would silently write the fee down to zero.
        ...(isBarter
            ? {}
            : {
                  budget_per_creator: Number(budget),
                  compensation_type: compensationType,
                  execution_owner: executionOwner,
              }),
        visibility,
        requires_draft_approval: requiresDraft,
        restricted_days: restrictedDays,
        // Presets travel as a bare key; only a custom window carries times,
        // because the server owns what "lunch" means.
        shoot_windows: shootWindows.map((w) =>
            w.key === "custom" ? { key: "custom", start: w.start, end: w.end } : { key: w.key },
        ),
        category,
        area,
        creators_needed: Math.max(1, Number(creatorsNeeded) || 1),
        campaign_type: campaignType,
        event_date:
            campaignType !== "personal_table" && eventDate
                ? new Date(eventDate).toISOString()
                : null,
        start_date:
            campaignType === "personal_table" && startDate
                ? new Date(startDate).toISOString()
                : null,
        end_date:
            campaignType === "personal_table" && endDate
                ? new Date(endDate).toISOString()
                : null,
        venue_address: venueAddress.trim() || null,
        venue_instructions: venueInstructions.trim() || null,
        on_site_contact: onSiteContact.trim() || null,
        status,
    });

    const submit = async (e, status) => {
        if (e) e.preventDefault();
        setError("");
        const problem = validateBase();
        if (problem) {
            setError(problem);
            return;
        }
        const isDraft = status === "draft";
        (isDraft ? setSavingDraft : setSubmitting)(true);
        try {
            if (isEditing) {
                const { status: _ignored, campaign_type: _fixed, ...changes } =
                    buildPayload(status);
                await api.put(`/brand/campaigns/${editingId}`, changes);
                // Saving an edit on a draft and submitting should do both.
                if (!isDraft && existing?.status === "draft") {
                    await api.post(`/brand/campaigns/${editingId}/publish`);
                    notifySuccess("Sent for review — we'll publish it once we've read it");
                } else {
                    notifySuccess("Campaign updated");
                }
                navigate("/dashboard", { replace: true });
                return;
            }

            const { data } = await api.post("/brand/campaigns", buildPayload(status));
            if (pendingCover) {
                const body = new FormData();
                body.append("file", pendingCover);
                try {
                    await api.post(`/brand/campaigns/${data.id}/cover`, body, {
                        headers: { "Content-Type": undefined },
                    });
                } catch {
                    // The brief exists and is the thing that mattered. Losing
                    // it over a picture, and making somebody retype the whole
                    // form, would be the wrong trade — the cover can be added
                    // from the edit screen.
                    notifyError("Campaign saved, but the cover image didn't upload. Add it from Edit.");
                }
            }
            notifySuccess(
                isDraft
                    ? "Draft saved to your dashboard"
                    : "Sent for review — we'll publish it once we've read it",
            );
            navigate("/dashboard", { replace: true, state: { newCampaignId: data.id } });
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            (isDraft ? setSavingDraft : setSubmitting)(false);
        }
    };

    if (loadingProfile) {
        // The real page is Navbar + max-w-3xl main, so the skeleton is too. The
        // old version centred a spinner in the whole viewport, which meant the
        // form did not so much arrive as replace a different page.
        return (
            <div
                data-testid="post-campaign-loading"
                className="min-h-screen bg-background text-foreground grain-page"
            >
                <Navbar />
                <main className="mx-auto max-w-3xl px-6 py-12 md:py-16">
                    <LoadingAnnouncement>
                        {isEditing ? "Loading campaign…" : "Loading the form…"}
                    </LoadingAnnouncement>
                    <Skeleton className="h-3 w-24" aria-hidden="true" />
                    <div className="mt-6">
                        <FormPageSkeleton
                            testid="post-campaign-skeleton"
                            sections={[
                                // The type picker: three cards, then the dates.
                                { fields: 1, columns: false },
                                { fields: 3 },
                                { fields: 2, columns: true },
                                { fields: 2, columns: true },
                            ]}
                        />
                    </div>
                </main>
            </div>
        );
    }

    return (
        <div
            data-testid="post-campaign-page"
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <Navbar />
            <main className="mx-auto max-w-3xl px-6 py-12 md:py-16">
                <button
                    type="button"
                    onClick={() => navigate("/dashboard")}
                    data-testid="post-back-btn"
                    className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.2em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Dashboard
                </button>

                <p className="mt-6 text-xs uppercase tracking-[0.2em] text-ember-500">
                    {isEditing ? "Edit campaign" : "New campaign"}
                </p>
                <h1 className="mt-3 font-serif text-fluid-5xl leading-none tracking-tight">
                    {isEditing ? "Change the brief." : "Post a paid brief."}
                </h1>
                <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground">
                    {isEditing
                        ? existing?.status === "draft"
                            ? "This is still a draft — nobody can see it yet. Send it for review when you're ready."
                            : "This brief is live. Changes show up on the creator feed straight away."
                        : "We read every brief before it goes out, usually the same day. Save as a draft if you want to polish it first."}
                </p>

                <form
                    onSubmit={(e) => submit(e, "pending_review")}
                    noValidate
                    className="mt-12 space-y-8"
                >
                    <section className="space-y-5">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            What kind of campaign
                        </p>
                        <div data-testid="pc-type-picker" className="grid gap-3 sm:grid-cols-3">
                            {[
                                {
                                    value: "launch",
                                    label: "Launch",
                                    blurb: "One day. Everyone comes at once.",
                                },
                                {
                                    value: "group_event",
                                    label: "Group event",
                                    blurb: "One day, in timed groups.",
                                },
                                {
                                    value: "personal_table",
                                    label: "Personal table",
                                    blurb: "A window creators book into.",
                                },
                            ].map((opt) => {
                                const on = campaignType === opt.value;
                                return (
                                    <button
                                        key={opt.value}
                                        type="button"
                                        aria-pressed={on}
                                        disabled={isEditing}
                                        data-testid={`pc-type-${opt.value}`}
                                        onClick={() => setCampaignType(opt.value)}
                                        className={
                                            "rounded-md border p-5 text-left transition-colors duration-200 disabled:opacity-50 " +
                                            (on
                                                ? "border-ember-500 bg-ember-500/10"
                                                : "border-white/10 bg-card/60 hover:border-white/25")
                                        }
                                    >
                                        <span
                                            className={
                                                "block text-sm " +
                                                (on ? "text-ember-500" : "text-foreground")
                                            }
                                        >
                                            {opt.label}
                                        </span>
                                        <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">
                                            {opt.blurb}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                        {isEditing && (
                            <p className="text-xs text-muted-foreground">
                                The type is fixed once a campaign exists — it decides which
                                dates the brief carries.
                            </p>
                        )}

                        {/* Only the dates this type actually has. */}
                        {campaignType === "personal_table" ? (
                            <div className="grid gap-5 md:grid-cols-2">
                                <div>
                                    <Label htmlFor="pc-start" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                        Bookable from
                                    </Label>
                                    <div className="relative mt-2">
                                        <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            id="pc-start"
                                            data-testid="pc-start-input"
                                            type="date"
                                            value={startDate}
                                            onChange={(e) => setStartDate(e.target.value)}
                                            className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        />
                                    </div>
                                </div>
                                <div>
                                    <Label htmlFor="pc-end" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                        Until
                                    </Label>
                                    <div className="relative mt-2">
                                        <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            id="pc-end"
                                            data-testid="pc-end-input"
                                            type="date"
                                            value={endDate}
                                            onChange={(e) => setEndDate(e.target.value)}
                                            className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        />
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="md:max-w-xs">
                                <Label htmlFor="pc-event" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Which day
                                </Label>
                                <div className="relative mt-2">
                                    <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="pc-event"
                                        data-testid="pc-event-input"
                                        type="date"
                                        value={eventDate}
                                        onChange={(e) => setEventDate(e.target.value)}
                                        className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                    />
                                </div>
                                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                    Your campaign manager sets the individual time slots once
                                    the brief is approved.
                                </p>
                            </div>
                        )}

                        {/* Which days and hours the venue can actually take
                            people. Sits with the dates because it is the same
                            question at a finer grain — and because a manager
                            setting slots reads both together. */}
                        <ShootPreferences
                            days={restrictedDays}
                            windows={shootWindows}
                            onChange={({ days, windows }) => {
                                setRestrictedDays(days);
                                setShootWindows(windows);
                            }}
                        />
                    </section>

                    <section className="space-y-5">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            The brief
                        </p>
                        <div>
                            <Label htmlFor="pc-title" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Campaign title
                            </Label>
                            <Input
                                id="pc-title"
                                data-testid="pc-title-input"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                maxLength={140}
                                className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="e.g. Weekend brunch reel — new menu launch"
                            />
                        </div>
                        <div>
                            <Label htmlFor="pc-brief" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Brief
                            </Label>
                            <Textarea
                                id="pc-brief"
                                data-testid="pc-brief-input"
                                rows={5}
                                maxLength={5000}
                                value={brief}
                                onChange={(e) => setBrief(e.target.value)}
                                className="mt-2 min-h-[140px] border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="What the campaign is about, the vibe you're after, dates, and anything creators should know upfront."
                            />
                        </div>
                        <div>
                            <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Deliverables
                            </Label>
                            {/* Counted, not written. Anything about *how* —
                                a hashtag, a handle to tag, a turnaround —
                                belongs in the brief above, which is the field
                                a creator reads before deciding. */}
                            <p className="mt-1 text-xs text-muted-foreground">
                                How many of each. Tags, turnaround and anything
                                else you want go in the brief.
                            </p>
                            <div className="mt-3">
                                <DeliverablePicker
                                    value={deliverables}
                                    onChange={setDeliverables}
                                    testid="pc-deliverables"
                                />
                            </div>
                        </div>
                        <div>
                            {/* Optional, and said so: a brief with no picture
                                still gets a generated cover, so this is never
                                the thing standing between a brand and posting. */}
                            <ImageUploadField
                                label="Cover image (optional)"
                                hint="Shown on the brief in the app and on the link when it's shared. Landscape, 16:9 — a photo of the place or the product works best."
                                shape="cover"
                                value={coverUrl}
                                onChange={setCoverUrl}
                                onFile={setPendingCover}
                                endpoint={
                                    isEditing
                                        ? `/brand/campaigns/${editingId}/cover`
                                        : undefined
                                }
                                responseKey="cover_image_url"
                                maxBytes={
                                    brandProfile?.uploads?.max_image_bytes ||
                                    FALLBACK_MAX_IMAGE_BYTES
                                }
                                acceptedMimes={
                                    brandProfile?.uploads?.accepted_image_mime_types ||
                                    FALLBACK_IMAGE_MIMES
                                }
                                testids={{
                                    input: COVER.input,
                                    choose: COVER.choose,
                                    remove: COVER.remove,
                                    preview: COVER.preview,
                                    error: COVER.error,
                                }}
                            />
                        </div>
                    </section>

                    <section className="space-y-5">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            Money & scope
                        </p>

                        {isBarter ? (
                            // Only reachable on a campaign WeAre converted. Say
                            // so plainly rather than showing a picker that the
                            // server would refuse.
                            <div
                                data-testid="pc-compensation-barter-note"
                                className="rounded-md border border-white/10 bg-card/60 p-5"
                            >
                                <p className="text-sm text-ember-500">Barter</p>
                                <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                                    We set this campaign up as barter. The rest of the brief
                                    is yours to edit — talk to us if you want it paid.
                                </p>
                            </div>
                        ) : (
                            <div
                                data-testid="pc-compensation-picker"
                                role="radiogroup"
                                aria-label="How creators are paid"
                                className="grid gap-3 sm:grid-cols-2"
                            >
                                {BRAND_COMPENSATION_OPTIONS.map((opt) => {
                                    const on = compensationType === opt.value;
                                    return (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            role="radio"
                                            aria-checked={on}
                                            data-testid={`pc-compensation-${opt.value}`}
                                            onClick={() => setCompensationType(opt.value)}
                                            className={
                                                "min-h-[2.75rem] rounded-md border p-5 text-left transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
                                                (on
                                                    ? "border-ember-500 bg-ember-500/10"
                                                    : "border-white/10 bg-card/60 hover:border-white/25")
                                            }
                                        >
                                            <span
                                                className={
                                                    "block text-sm " +
                                                    (on ? "text-ember-500" : "text-foreground")
                                                }
                                            >
                                                {opt.label}
                                            </span>
                                            <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">
                                                {opt.blurb}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        )}

                        {/* Who runs it. Asked here, next to how it pays,
                            because the two together are what a brand is
                            actually deciding when it posts: what this costs
                            and how much of it they do themselves. */}
                        <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                Who runs it
                            </p>
                            <div
                                data-testid={EXECUTION.picker}
                                role="radiogroup"
                                aria-label="Who runs this campaign"
                                className="mt-3 grid gap-3 sm:grid-cols-2"
                            >
                                {EXECUTION_OPTIONS.map((opt) => {
                                    const on = executionOwner === opt.value;
                                    return (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            role="radio"
                                            aria-checked={on}
                                            data-testid={EXECUTION.pickerOption(opt.value)}
                                            onClick={() => setExecutionOwner(opt.value)}
                                            className={
                                                "min-h-[2.75rem] rounded-md border p-5 text-left transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
                                                (on
                                                    ? "border-ember-500 bg-ember-500/10"
                                                    : "border-white/10 bg-card/60 hover:border-white/25")
                                            }
                                        >
                                            <span
                                                className={
                                                    "block text-sm " +
                                                    (on ? "text-ember-500" : "text-foreground")
                                                }
                                            >
                                                {opt.label}
                                            </span>
                                            <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">
                                                {opt.hint}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div>
                            <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Who can find this brief
                            </Label>
                            <div
                                data-testid={VISIBILITY.picker}
                                role="radiogroup"
                                aria-label="Who can find this brief"
                                className="mt-3 grid gap-3 sm:grid-cols-2"
                            >
                                {VISIBILITY_OPTIONS.map((opt) => {
                                    const on = visibility === opt.value;
                                    return (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            role="radio"
                                            aria-checked={on}
                                            data-testid={VISIBILITY.option(opt.value)}
                                            onClick={() => setVisibility(opt.value)}
                                            className={
                                                "min-h-[2.75rem] rounded-md border p-5 text-left transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
                                                (on
                                                    ? "border-ember-500 bg-ember-500/10"
                                                    : "border-white/10 bg-card/60 hover:border-white/25")
                                            }
                                        >
                                            <span
                                                className={
                                                    "block text-sm " +
                                                    (on ? "text-ember-500" : "text-foreground")
                                                }
                                            >
                                                {opt.label}
                                            </span>
                                            <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">
                                                {opt.hint}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                            {visibility === "private" && (
                                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                    Invite creators from the campaign page once it's
                                    live — nobody else will ever see it, and it won't
                                    have a public share page.
                                </p>
                            )}
                        </div>

                        {/* The draft gate. A checkbox rather than a two-card
                            picker: unlike execution owner and visibility this
                            has an obvious default and no second story to
                            tell. */}
                        <div>
                            <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Before anything is published
                            </Label>
                            <label
                                htmlFor="pc-requires-draft"
                                className={
                                    "mt-3 flex min-h-[2.75rem] cursor-pointer items-start gap-3 rounded-md border p-5 transition-colors duration-200 " +
                                    (requiresDraft
                                        ? "border-ember-500 bg-ember-500/10"
                                        : "border-white/10 bg-card/60 hover:border-white/25")
                                }
                            >
                                <input
                                    id="pc-requires-draft"
                                    data-testid="pc-requires-draft"
                                    type="checkbox"
                                    checked={requiresDraft}
                                    onChange={(e) => setRequiresDraft(e.target.checked)}
                                    className="mt-0.5 h-4 w-4 flex-none accent-ember-500"
                                />
                                <span className="min-w-0">
                                    <span
                                        className={
                                            "block text-sm " +
                                            (requiresDraft ? "text-ember-500" : "text-foreground")
                                        }
                                    >
                                        Review the draft first
                                    </span>
                                    <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">
                                        The creator sends the cut for approval after
                                        the shoot. Nothing goes live until you've said
                                        yes — or asked for a change. Leave it off and
                                        they post, then send you the link.
                                    </span>
                                </span>
                            </label>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                            {/* A barter brief has no cash figure to set, so the
                              * field is gone rather than sitting there at zero.
                              * Whatever budget the campaign was posted with is
                              * left untouched — see buildPayload. */}
                            {!isBarter && (
                                <div>
                                    <Label htmlFor="pc-budget" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                        {compensationType === "negotiated"
                                            ? "Budget per creator (guide)"
                                            : "Budget per creator"}
                                    </Label>
                                    <div className="relative mt-2">
                                        <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            id="pc-budget"
                                            data-testid="pc-budget-input"
                                            type="number"
                                            inputMode="numeric"
                                            min="0"
                                            step="500"
                                            value={budget}
                                            onChange={(e) => setBudget(e.target.value)}
                                            className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                            placeholder="e.g. 8000"
                                        />
                                    </div>
                                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                        {compensationType === "negotiated"
                                            ? "Shown to creators as a guide. You agree the actual fee with each one, and we record it against their application."
                                            : "Creators receive 100% of this amount. Platform fee is charged to you on top."}
                                    </p>
                                </div>
                            )}
                            <div>
                                <Label htmlFor="pc-needed" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Creators needed
                                </Label>
                                <div className="relative mt-2">
                                    <Users className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="pc-needed"
                                        data-testid="pc-needed-input"
                                        type="number"
                                        min="1"
                                        max="100"
                                        step="1"
                                        value={creatorsNeeded}
                                        onChange={(e) => setCreatorsNeeded(e.target.value)}
                                        className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Category
                                </Label>
                                <Select value={category} onValueChange={setCategory}>
                                    <SelectTrigger
                                        data-testid="pc-category-trigger"
                                        className="mt-2 h-11 border-white/10 bg-card/60"
                                    >
                                        <SelectValue placeholder="Pick a category" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {CATEGORY_OPTIONS.map((c) => (
                                            <SelectItem
                                                key={c.value}
                                                value={c.value}
                                                data-testid={`pc-category-${c.value}`}
                                            >
                                                {c.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Area
                                </Label>
                                <Select value={area} onValueChange={setArea}>
                                    <SelectTrigger
                                        data-testid="pc-area-trigger"
                                        className="mt-2 h-11 border-white/10 bg-card/60"
                                    >
                                        <SelectValue placeholder="Pick an area" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {areaOptions.map((a) => (
                                            <SelectItem
                                                key={a}
                                                value={a}
                                                data-testid={`pc-area-${a.replace(/\s+/g, "-")}`}
                                            >
                                                {a}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="space-y-5 border-t border-white/10 pt-6">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                The venue (optional for now)
                            </p>
                            <div>
                                <Label htmlFor="pc-venue" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Address
                                </Label>
                                <Input
                                    id="pc-venue"
                                    data-testid="pc-venue-input"
                                    value={venueAddress}
                                    onChange={(e) => setVenueAddress(e.target.value)}
                                    maxLength={500}
                                    placeholder="Where creators should show up"
                                    className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                />
                            </div>
                            <div className="grid gap-5 md:grid-cols-2">
                                <div>
                                    <Label htmlFor="pc-venue-notes" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                        Arrival instructions
                                    </Label>
                                    <Input
                                        id="pc-venue-notes"
                                        data-testid="pc-venue-instructions-input"
                                        value={venueInstructions}
                                        onChange={(e) => setVenueInstructions(e.target.value)}
                                        maxLength={1000}
                                        placeholder="e.g. Ask for the events desk"
                                        className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                    />
                                </div>
                                <div>
                                    <Label htmlFor="pc-onsite" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                        On-site contact
                                    </Label>
                                    <Input
                                        id="pc-onsite"
                                        data-testid="pc-onsite-contact-input"
                                        value={onSiteContact}
                                        onChange={(e) => setOnSiteContact(e.target.value)}
                                        maxLength={200}
                                        placeholder="Name and number at the venue"
                                        className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                    />
                                </div>
                            </div>
                        </div>
                    </section>

                    {error && (
                        <p data-testid="pc-error" className="text-sm text-destructive">
                            {error}
                        </p>
                    )}

                    <div className="flex flex-col-reverse items-stretch gap-3 border-t border-white/10 pt-8 md:flex-row md:items-center md:justify-between">
                        {/* On a live campaign there's no draft to save back to. */}
                        {(!isEditing || existing?.status === "draft") && (
                            <Button
                                type="button"
                                variant="outline"
                                data-testid="pc-save-draft-btn"
                                onClick={(e) => submit(e, "draft")}
                                disabled={submitting || savingDraft}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                {savingDraft ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Saving…
                                    </>
                                ) : (
                                    <>
                                        <Save className="mr-2 h-4 w-4" />
                                        {isEditing ? "Save draft" : "Save as draft"}
                                    </>
                                )}
                            </Button>
                        )}
                        <Button
                            type="submit"
                            data-testid="pc-publish-btn"
                            disabled={submitting || savingDraft}
                            className="group h-12 rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400 md:ml-auto"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {isEditing && existing?.status !== "draft"
                                        ? "Saving…"
                                        : "Sending…"}
                                </>
                            ) : (
                                <>
                                    <Send className="mr-2 h-4 w-4" />
                                    {isEditing
                                        ? existing?.status === "draft"
                                            ? "Send for review"
                                            : "Save changes"
                                        : "Send for review"}
                                    <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                </>
                            )}
                        </Button>
                    </div>
                </form>
            </main>
        </div>
    );
}
