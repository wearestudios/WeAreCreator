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
import { EXECUTION_OPTIONS, weareRunReason } from "@/lib/execution";
import { dayKey, timeKey } from "@/lib/time";
import { VISIBILITY_OPTIONS } from "@/lib/visibility";
import { BUDGET, COVER, EXECUTION, VISIBILITY } from "@/constants/testIds";
import { Navbar } from "@/components/Navbar";
import CampaignTemplates from "@/components/brand/CampaignTemplates";
import ShootPreferences from "@/components/campaign/ShootPreferences";
import {
    DEFAULT_DISCLOSURE,
    DEFAULT_USAGE_RIGHTS,
    DISCLOSURE_LABELS,
    USAGE_RIGHTS,
    needsDuration,
} from "@/lib/campaignTerms";
import { BRIEF_DETAIL_FIELDS } from "@/lib/briefDetails";
import BriefDetailsEditor, {
    emptyBriefDetails,
    fromBriefDetails,
    toBriefDetails,
} from "@/components/campaign/BriefDetailsEditor";
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
import PublishGate from "@/components/brand/PublishGate";
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
    // The checkable half of the brief. Optional in every direction — a brand
    // that fills none of it posts a perfectly good brief.
    const [briefDetails, setBriefDetails] = useState(emptyBriefDetails());
    const [budget, setBudget] = useState("");
    // The cap on the whole brief. Empty string is "no cap" — the payload
    // turns it into `null`, which is what the server reads as unlimited.
    const [totalBudget, setTotalBudget] = useState("");
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
    // **Off by default, unlike the draft gate.** On most briefs a booking is
    // the creator picking one of the manager's own published slots, and asking
    // somebody to confirm that is asking them to agree with themselves.
    const [requiresSlotConfirmation, setRequiresSlotConfirmation] = useState(false);
    // **Personal table only.** These two ask which weekdays are out and which
    // hours suit, which are questions only worth asking when the *creator*
    // picks the time. They used to render on every type, so a launch — one
    // evening, everybody at once — was asked both, and brands answered
    // because a form that asks looks like a form that needs an answer.
    const [restrictedDays, setRestrictedDays] = useState([]);
    const [shootWindows, setShootWindows] = useState([]);
    const [category, setCategory] = useState("");
    const [area, setArea] = useState("");
    const [creatorsNeeded, setCreatorsNeeded] = useState("1");
    // The type decides which date fields exist — see the server's validator.
    const [campaignType, setCampaignType] = useState("personal_table");
    const [eventDate, setEventDate] = useState("");
    // Launch: the day is not enough — "everybody at once" needs the hour they
    // all arrive at. Duration is optional; plenty of launches run until they
    // run out.
    const [eventTime, setEventTime] = useState("");
    const [durationMinutes, setDurationMinutes] = useState("");
    // Group event: the timetable, which on this type *is* the brief.
    const [sittings, setSittings] = useState([{ time: "", capacity: "4" }]);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    // The cover, which has two lives. On an existing campaign it uploads
    // straight away against its own route. On a new one there is no id to
    // upload against yet, so the File waits here and goes up the moment the
    // campaign is created.
    const [coverUrl, setCoverUrl] = useState(null);
    const [pendingCover, setPendingCover] = useState(null);
    // **Both default rather than starting blank.** Every brief here is a
    // material connection, so the undecided answer on disclosure is "disclose";
    // and a brief that never mentioned usage granted nothing beyond a repost,
    // so that is what the picker opens on.
    const [requiredDisclosure, setRequiredDisclosure] = useState(DEFAULT_DISCLOSURE);
    const [usageRights, setUsageRights] = useState(DEFAULT_USAGE_RIGHTS);
    const [usageDuration, setUsageDuration] = useState("");
    const [venueAddress, setVenueAddress] = useState("");
    const [venueInstructions, setVenueInstructions] = useState("");
    const [onSiteContact, setOnSiteContact] = useState("");
    const [submitting, setSubmitting] = useState(false);

    /**
     * Fill the form in from a saved template.
     *
     * **Every field except the dates**, which is what makes a template a
     * template: the brief is the same and the day is different. Written as a
     * table rather than a chain of ifs so a field added to the form and not
     * here is visible as an absence rather than buried in a branch.
     *
     * Each setter is called only when the template actually carries the field.
     * A template saved before a field existed must not blank it — "the
     * template does not mention this" is a different thing from "the template
     * says leave it empty".
     */
    const applyTemplate = (fields) => {
        const apply = (key, setter, transform) => {
            if (fields?.[key] === undefined || fields?.[key] === null) return;
            setter(transform ? transform(fields[key]) : fields[key]);
        };
        apply("title", setTitle);
        apply("brief", setBrief);
        apply("deliverable_items", setDeliverables, (items) => ({
            ...emptyDeliverables(),
            ...Object.fromEntries(items.map((i) => [i.type, i.quantity])),
        }));
        apply("budget_per_creator", setBudget, String);
        apply("total_budget", setTotalBudget, String);
        apply("compensation_type", setCompensationType);
        apply("execution_owner", setExecutionOwner);
        apply("visibility", setVisibility);
        apply("requires_draft_approval", setRequiresDraft, Boolean);
        apply("requires_slot_confirmation", setRequiresSlotConfirmation, Boolean);
        apply("restricted_days", setRestrictedDays);
        apply("shoot_windows", setShootWindows);
        apply("category", setCategory);
        apply("area", setArea);
        apply("creators_needed", setCreatorsNeeded, String);
        apply("campaign_type", setCampaignType);
        apply("venue_address", setVenueAddress);
        apply("venue_instructions", setVenueInstructions);
        apply("on_site_contact", setOnSiteContact);
        // A brand that always asks for the same hashtag and always says the
        // same don't is exactly the brand that saves a template. Applied one
        // field at a time through the functional setter, so five `apply`
        // calls in a row cannot each overwrite the last one's work from a
        // stale copy of the object.
        BRIEF_DETAIL_FIELDS.forEach((key) =>
            apply(key, (val) => setBriefDetails((d) => ({ ...d, [key]: val }))),
        );
        // Dates are deliberately untouched — see the note on the picker.
    };
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
                    // Re-seeded for the same reason the deliverables are: an
                    // edit round trip that dropped these would blank a
                    // brief's hashtags every time somebody fixed its title.
                    setBriefDetails(fromBriefDetails(data.brief_details));
                    setBudget(
                        data.budget_per_creator == null
                            ? ""
                            : String(data.budget_per_creator),
                    );
                    // Re-seeded like everything else here: a round trip that
                    // dropped it would clear a brand's cap every time somebody
                    // fixed a typo in the title.
                    setTotalBudget(
                        data.total_budget == null ? "" : String(data.total_budget),
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
                    setRequiresSlotConfirmation(
                        Boolean(data.requires_slot_confirmation)
                    );
                    setRestrictedDays(data.restricted_days || []);
                    setShootWindows(data.shoot_windows || []);
                    setCreatorsNeeded(String(data.creators_needed ?? 1));
                    setCampaignType(data.campaign_type || "personal_table");
                    setEventDate(toDateInput(data.event_date));
                    // **Re-seeded, or an edit rewrites the schedule.** The
                    // same trap the venue fields fell into: `buildPayload`
                    // sends these for the type, so a form that loaded without
                    // them would save a launch back with no start time and a
                    // group event with an empty timetable.
                    setEventTime(
                        data.campaign_type === "launch" ? timeKey(data.event_date) : "",
                    );
                    setDurationMinutes(
                        data.duration_minutes != null ? String(data.duration_minutes) : "",
                    );
                    if (data.campaign_type === "group_event") {
                        const rows = (data.sittings || []).map((r) => ({
                            time: timeKey(r.starts_at),
                            capacity: String(r.capacity ?? 4),
                            // A sitting somebody already holds a seat in
                            // survives a rewrite server-side; saying so here
                            // stops a brand deleting a row and wondering why
                            // it came back.
                            booked: Number(r.booked_count || 0),
                        }));
                        setSittings(rows.length ? rows : [{ time: "", capacity: "4" }]);
                    }
                    setStartDate(toDateInput(data.start_date));
                    setEndDate(toDateInput(data.end_date));
                    // These three were never loaded, and buildPayload sends
                    // them unconditionally — so opening a campaign for any
                    // edit and saving wiped the venue, the arrival
                    // instructions and the on-site contact, which are the
                    // three things a creator needs to turn up.
                    setCoverUrl(data.cover_image_url || null);
                    setRequiredDisclosure(
                        data.required_disclosure || DEFAULT_DISCLOSURE,
                    );
                    setUsageRights(data.usage?.kind || DEFAULT_USAGE_RIGHTS);
                    setUsageDuration(
                        data.usage?.duration_days != null
                            ? String(data.usage.duration_days)
                            : "",
                    );
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

    // Whether this brief is ours to run whatever the picker says, and why. The
    // threshold comes from the server on `GET /brand/profile` — it is an
    // operating decision an admin can change, and a copy of the number here
    // would be a form arguing with the route it posts to. Absent, the reader
    // simply never fires the size rule; the launch rule needs no number.
    const weareRun = weareRunReason({
        campaignType,
        creatorsNeeded,
        threshold: brandProfile?.execution?.large_campaign_threshold,
    });

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
        if (needsDuration(usageRights) && !Number(usageDuration))
            return "Paid usage runs for a set period — say how many days.";
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
        } else if (campaignType === "launch" && !eventTime) {
            // Everybody arrives at once, so the hour is the arrangement.
            return "Pick the time it starts.";
        } else if (campaignType === "group_event") {
            const filled = sittings.filter((r) => r.time);
            if (!filled.length)
                return "A group event runs in sittings — add at least one time.";
            if (new Set(filled.map((r) => r.time)).size !== filled.length)
                return "Two sittings can't start at the same time.";
        }
        return null;
    };

    const buildPayload = (status) => ({
        title: title.trim(),
        brief: brief.trim(),
        deliverable_items: toDeliverableItems(deliverables),
        // Always every key. The server reads an omitted one as "leave it
        // alone" and an empty list as "clear it", so a payload carrying only
        // what was typed could add a hashtag and never remove one.
        ...toBriefDetails(briefDetails),
        // Both omitted on a barter campaign: the field isn't rendered, so
        // Number("") would silently write the fee down to zero.
        ...(isBarter
            ? {}
            : {
                  budget_per_creator: Number(budget),
                  // **Explicitly `null` when cleared, never omitted.** The
                  // edit handler reads an omitted key as "leave it alone" and
                  // a null as "clear it", so a brand removing a cap it set by
                  // mistake needs the null to actually travel.
                  total_budget:
                      String(totalBudget).trim() === "" ? null : Number(totalBudget),
                  compensation_type: compensationType,
                  // **Agreeing with the rule rather than being overridden by
                  // it.** The create path would force `weare` anyway, but the
                  // edit path refuses a write that takes such a campaign back
                  // — so a form that kept sending the picker's old value would
                  // 422 the whole save on a field it is no longer showing.
                  execution_owner: weareRun ? "weare" : executionOwner,
              }),
        visibility,
        requires_draft_approval: requiresDraft,
        requires_slot_confirmation: requiresSlotConfirmation,
        // **Only the fields this type has.** The server refuses the rest
        // outright (`_SCHEDULING_BY_TYPE`), so sending them on the wrong type
        // is a 422 rather than a field quietly stored and never read.
        ...(campaignType === "personal_table"
            ? {
                  restricted_days: restrictedDays,
                  // Presets travel as a bare key; only a custom window carries
                  // times, because the server owns what "lunch" means.
                  shoot_windows: shootWindows.map((w) =>
                      w.key === "custom"
                          ? { key: "custom", start: w.start, end: w.end }
                          : { key: w.key },
                  ),
              }
            : {}),
        ...(campaignType === "launch" && durationMinutes
            ? { duration_minutes: Number(durationMinutes) }
            : {}),
        ...(campaignType === "group_event"
            ? {
                  sittings: sittings
                      .filter((r) => r.time)
                      .map((r) => ({
                          starts_at: new Date(`${eventDate}T${r.time}`).toISOString(),
                          capacity: Math.max(1, Number(r.capacity) || 1),
                      })),
              }
            : {}),
        required_disclosure: requiredDisclosure,
        usage_rights: usageRights,
        // The server refuses a period on a grant that has none, so this is
        // omitted rather than sent as null on the other two.
        ...(needsDuration(usageRights)
            ? { usage_duration_days: Number(usageDuration) || null }
            : {}),
        category,
        area,
        creators_needed: Math.max(1, Number(creatorsNeeded) || 1),
        campaign_type: campaignType,
        // A launch's `event_date` carries the start time, because the day and
        // the hour are one arrangement. A group event's is the day; its
        // sittings carry the times.
        event_date:
            campaignType !== "personal_table" && eventDate
                ? new Date(
                      campaignType === "launch" && eventTime
                          ? `${eventDate}T${eventTime}`
                          : eventDate,
                  ).toISOString()
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

                {/* **Above the form, and only on a new brief.** A template
                    picker below the fields is one somebody finds after they
                    have filled them in, which is the one moment it is worth
                    nothing; and offering "start from a template" on an edit
                    would mean overwriting a live brief from a saved one. */}
                {!isEditing && (
                    <div className="mt-6">
                        <CampaignTemplates onUse={applyTemplate} />
                    </div>
                )}

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
                            <div className="space-y-5">
                                <div className="grid gap-5 md:grid-cols-3">
                                    <div>
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
                                    </div>

                                    {/* A launch is one moment, so the hour is
                                        part of the arrangement rather than
                                        something a manager fills in later. */}
                                    {campaignType === "launch" && (
                                        <>
                                            <div>
                                                <Label htmlFor="pc-event-time" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                                    Starts at
                                                </Label>
                                                <Input
                                                    id="pc-event-time"
                                                    data-testid="pc-event-time-input"
                                                    type="time"
                                                    value={eventTime}
                                                    onChange={(e) => setEventTime(e.target.value)}
                                                    className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                                />
                                            </div>
                                            <div>
                                                <Label htmlFor="pc-duration" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                                    Runs for (optional)
                                                </Label>
                                                <Input
                                                    id="pc-duration"
                                                    data-testid="pc-duration-input"
                                                    type="number"
                                                    min={15}
                                                    max={1440}
                                                    step={15}
                                                    placeholder="Minutes"
                                                    value={durationMinutes}
                                                    onChange={(e) => setDurationMinutes(e.target.value)}
                                                    className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                                />
                                            </div>
                                        </>
                                    )}
                                </div>

                                {/* **The timetable is the brief on this
                                    type.** "Three sittings, six creators
                                    each" is what the brand is buying and what
                                    a creator is deciding whether they can
                                    make, so it is set here rather than left
                                    to the manager after approval. */}
                                {campaignType === "group_event" && (
                                    <div data-testid="pc-sittings">
                                        <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                            Sittings
                                        </Label>
                                        <div className="mt-2 space-y-2">
                                            {sittings.map((row, i) => (
                                                <div key={i} className="flex flex-wrap items-center gap-2">
                                                    <Input
                                                        type="time"
                                                        aria-label={`Sitting ${i + 1} time`}
                                                        data-testid={`pc-sitting-time-${i}`}
                                                        value={row.time}
                                                        onChange={(e) => {
                                                            const next = [...sittings];
                                                            next[i] = { ...next[i], time: e.target.value };
                                                            setSittings(next);
                                                        }}
                                                        className="h-11 w-36 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                                    />
                                                    <Input
                                                        type="number"
                                                        min={1}
                                                        aria-label={`Sitting ${i + 1} places`}
                                                        data-testid={`pc-sitting-capacity-${i}`}
                                                        value={row.capacity}
                                                        onChange={(e) => {
                                                            const next = [...sittings];
                                                            next[i] = { ...next[i], capacity: e.target.value };
                                                            setSittings(next);
                                                        }}
                                                        className="h-11 w-24 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                                    />
                                                    <span className="text-xs text-muted-foreground">places</span>
                                                    {sittings.length > 1 && (
                                                        <button
                                                            type="button"
                                                            data-testid={`pc-sitting-remove-${i}`}
                                                            onClick={() =>
                                                                setSittings(sittings.filter((_, j) => j !== i))
                                                            }
                                                            className="min-h-[2.75rem] text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-foreground sm:min-h-0"
                                                        >
                                                            Remove
                                                        </button>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                        <button
                                            type="button"
                                            data-testid="pc-sitting-add"
                                            onClick={() =>
                                                setSittings([...sittings, { time: "", capacity: "4" }])
                                            }
                                            className="mt-2 inline-flex min-h-[2.75rem] items-center text-xs uppercase tracking-[0.15em] text-ember-500 transition-colors duration-200 hover:text-ember-400 sm:min-h-0"
                                        >
                                            Add a sitting
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* **What the post has to say, and what happens to
                            it afterwards.** Sits with the brief rather than in
                            a settings drawer: these are two of the three
                            things that decide whether a creator takes the job,
                            and a usage grant discovered at delivery is a
                            renegotiation nobody has leverage in. */}
                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label
                                    htmlFor="pc-disclosure"
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    Disclosure the post must carry
                                </Label>
                                <select
                                    id="pc-disclosure"
                                    data-testid="pc-disclosure"
                                    value={requiredDisclosure}
                                    onChange={(e) => setRequiredDisclosure(e.target.value)}
                                    className="mt-2 h-11 w-full rounded-md border border-white/10 bg-card/60 px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                                >
                                    {Object.entries(DISCLOSURE_LABELS).map(([k, label]) => (
                                        <option key={k} value={k}>
                                            {label}
                                        </option>
                                    ))}
                                </select>
                                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                    Required on every brief — a gifted post is an ad too.
                                    Confirmed again at review before anything is approved.
                                </p>
                            </div>

                            <div>
                                <Label
                                    htmlFor="pc-usage"
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    What you may do with the content
                                </Label>
                                <select
                                    id="pc-usage"
                                    data-testid="pc-usage"
                                    value={usageRights}
                                    onChange={(e) => {
                                        setUsageRights(e.target.value);
                                        if (!needsDuration(e.target.value)) setUsageDuration("");
                                    }}
                                    className="mt-2 h-11 w-full rounded-md border border-white/10 bg-card/60 px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                                >
                                    {Object.entries(USAGE_RIGHTS).map(([k, label]) => (
                                        <option key={k} value={k}>
                                            {label}
                                        </option>
                                    ))}
                                </select>
                                {/* The period appears only where it means
                                    something. Open-ended paid usage is a
                                    buyout under a smaller name, so the server
                                    refuses it and the form asks. */}
                                {needsDuration(usageRights) && (
                                    <div className="mt-3">
                                        <Label
                                            htmlFor="pc-usage-days"
                                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                        >
                                            For how many days
                                        </Label>
                                        <Input
                                            id="pc-usage-days"
                                            data-testid="pc-usage-days"
                                            type="number"
                                            min={1}
                                            max={3650}
                                            placeholder="e.g. 90"
                                            value={usageDuration}
                                            onChange={(e) => setUsageDuration(e.target.value)}
                                            className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                        />
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* **Personal table only**, because it is the only
                            type where the creator picks the time — and so the
                            only one where "not Mondays" and "afternoons only"
                            are answerable. The server refuses these two on the
                            other types outright, so this is the form agreeing
                            with the API rather than deciding on its own. */}
                        {campaignType === "personal_table" && (
                            <ShootPreferences
                                days={restrictedDays}
                                windows={shootWindows}
                                onChange={({ days, windows }) => {
                                    setRestrictedDays(days);
                                    setShootWindows(windows);
                                }}
                            />
                        )}
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
                                placeholder="e.g. Two reels for the spring range"
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
                            {/* The copy used to send tags to the brief box.
                                They have their own fields now — a hashtag
                                buried in a paragraph is one a creator reads
                                once and a reviewer cannot check against. */}
                            <p className="mt-1 text-xs text-muted-foreground">
                                How many of each. Tags, do's and don'ts have
                                their own fields below.
                            </p>
                            <div className="mt-3">
                                <DeliverablePicker
                                    value={deliverables}
                                    onChange={setDeliverables}
                                    testid="pc-deliverables"
                                />
                            </div>
                        </div>
                        {/* Directly under the deliverables, because it is the
                            other half of "what are you asking for" — and
                            collapsed, because a brief with none of it is a
                            perfectly good brief and six empty boxes here read
                            as six more things to do before posting. */}
                        <BriefDetailsEditor
                            value={briefDetails}
                            onChange={setBriefDetails}
                        />
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
                            and how much of it they do themselves.

                            **Except on the two shapes that are ours by rule.**
                            A launch and a brief for more than the threshold
                            come to our team whatever is picked, and the server
                            forces it — so the picker is *replaced* by the
                            reason rather than left up with a choice that would
                            be quietly overridden. Said as the offer it is: a
                            manager on the campaign where it matters, not a
                            control taken away. */}
                        <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                Who runs it
                            </p>
                            {weareRun ? (
                                <div
                                    data-testid={EXECUTION.weareRun}
                                    className="mt-3 rounded-md border border-ember-500/40 bg-ember-500/10 p-5"
                                >
                                    <p className="text-sm text-ember-500">{weareRun.title}</p>
                                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                                        {weareRun.line}
                                    </p>
                                </div>
                            ) : (
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
                            )}
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

                            {/* And the booking handshake, which is the same
                                shape of question one step earlier. Off unless
                                the venue really does have to check the day —
                                see `_requires_slot_confirmation`. */}
                            <label
                                htmlFor="pc-slot-confirmation"
                                className={
                                    "mt-3 flex min-h-[2.75rem] cursor-pointer items-start gap-3 rounded-md border p-5 transition-colors duration-200 " +
                                    (requiresSlotConfirmation
                                        ? "border-ember-500 bg-ember-500/10"
                                        : "border-white/10 bg-card/60 hover:border-white/25")
                                }
                            >
                                <input
                                    id="pc-slot-confirmation"
                                    data-testid="pc-slot-confirmation"
                                    type="checkbox"
                                    checked={requiresSlotConfirmation}
                                    onChange={(e) =>
                                        setRequiresSlotConfirmation(e.target.checked)
                                    }
                                    className="mt-0.5 h-4 w-4 flex-none accent-ember-500"
                                />
                                <span className="min-w-0">
                                    <span
                                        className={
                                            "block text-sm " +
                                            (requiresSlotConfirmation
                                                ? "text-ember-500"
                                                : "text-foreground")
                                        }
                                    >
                                        Confirm each booking yourself
                                    </span>
                                    <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">
                                        Leave this off and a creator who books a slot
                                        is booked. Turn it on where the venue has to
                                        check the day first — you'll answer each
                                        request, and they're told it's pending until
                                        you do.
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

                        {/* **The cap on the whole brief, and it is optional.**
                          * Deliberately not prefilled with fee × headcount:
                          * that product is what the brief would cost if every
                          * place filled at the list price, and on a negotiated
                          * brief — the one this most exists for — it will not.
                          * A number the form guessed is a number nobody chose.
                          * Absent on a barter brief, where nothing draws down. */}
                        {!isBarter && (
                            <div className="max-w-sm">
                                <Label
                                    htmlFor="pc-total-budget"
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    Total campaign budget (optional)
                                </Label>
                                <div className="relative mt-2">
                                    <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="pc-total-budget"
                                        data-testid={BUDGET.input}
                                        type="number"
                                        inputMode="numeric"
                                        min="0"
                                        step="1000"
                                        value={totalBudget}
                                        onChange={(e) => setTotalBudget(e.target.value)}
                                        className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. 80000"
                                    />
                                </div>
                                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                    Agreed fees draw down against this as creators are
                                    taken on, and we stop you going past it. Somebody who
                                    cancels or withdraws releases theirs. Leave it empty
                                    for no cap.
                                </p>
                            </div>
                        )}

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

                    {/* **Beside the button, not after it.** The refusal was
                        always correct and always arrived as a toast, after the
                        work, naming the state rather than the fix. */}
                    <PublishGate
                        verification={brandProfile?.verification}
                        trust={brandProfile?.trust}
                    />

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
                            // Disabled rather than allowed-and-refused: the
                            // explanation is on screen directly above it, so a
                            // greyed button here is a fact somebody can read
                            // rather than a dead end.
                            disabled={
                                submitting ||
                                savingDraft ||
                                (brandProfile?.verification &&
                                    brandProfile.verification.state !== "verified")
                            }
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
