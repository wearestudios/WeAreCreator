// Brand onboarding, and the verification that follows it.
//
// Two steps on one page, in the order they matter. The top half is the
// thirty-second setup that gets a brand as far as drafting a brief. The bottom
// half is verification — the business details a reviewer needs and the
// documents they get checked against — which is what a brief has to clear
// before it reaches a single creator.
//
// They are on one page rather than two because the second is invisible
// otherwise: an unverified brand can draft all day and only discovers the wall
// when it tries to publish. Saving is partial (`PUT /brand/profile` writes only
// what you send), so the two halves can be filled in on different days;
// submitting is the thing that demands the full set, and it names what is
// missing rather than greying out a button.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { notifySuccess } from "@/lib/feedback";
import {
    ArrowRight,
    Building2,
    CheckCircle2,
    Clock,
    ExternalLink,
    Loader2,
    MapPin,
    Save,
    ShieldAlert,
    ShieldCheck,
    Send,
    X,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Navbar } from "@/components/Navbar";
import {
    FormPageSkeleton,
    LoadingAnnouncement,
} from "@/components/data/PageSkeleton";
import VerificationDocuments, {
    VerificationDocumentsSkeleton,
} from "@/components/brand/VerificationDocuments";
import { BRAND_LOGO, BRAND_PAGE, BRAND_VERIFICATION as IDS } from "@/constants/testIds";
import AddressPicker from "@/components/AddressPicker";
import { brandPageUrl } from "@/lib/brandPage";
import { INDIAN_CITIES } from "@/lib/taxonomy";
// Fallbacks only: the server ships these lists on the profile response, so a
// dropdown can never offer a value the API refuses. These stand in for the
// first paint, before that response lands.
import {
    ANY_TIER,
    BUDGET_BANDS,
    CONTENT_TYPES,
    FOLLOWER_TIERS,
} from "@/lib/followerTiers";

const FOLLOWER_TIER_OPTIONS = [...FOLLOWER_TIERS, ANY_TIER];
import ImageUploadField, {
    FALLBACK_IMAGE_MIMES,
    FALLBACK_MAX_IMAGE_BYTES,
} from "@/components/ImageUploadField";
import { IST } from "@/lib/time";

// The full set the server accepts (CATEGORY_LITERAL). This used to be four of
// the eight, so a fashion, travel, wellness or real-estate brand had to file
// itself as "Lifestyle" — and that is the word its public page then prints.
const CATEGORY_OPTIONS = [
    { value: "fnb", label: "F&B" },
    { value: "hospitality", label: "Hospitality" },
    { value: "retail", label: "Retail" },
    { value: "real_estate", label: "Real estate" },
    { value: "fashion", label: "Fashion" },
    { value: "travel", label: "Travel" },
    { value: "wellness", label: "Wellness" },
    { value: "lifestyle", label: "Lifestyle" },
];

// Mirrors the server's `BusinessType`. A value not in this list is a 422.
const BUSINESS_TYPE_OPTIONS = [
    { value: "sole_proprietorship", label: "Sole proprietorship" },
    { value: "partnership", label: "Partnership" },
    { value: "llp", label: "LLP" },
    { value: "private_limited", label: "Private limited" },
    { value: "public_limited", label: "Public limited" },
    { value: "trust", label: "Trust" },
    { value: "society", label: "Society" },
    { value: "other", label: "Other" },
];

const SUGGESTED_AREAS = [
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
    "Chandigarh",
    "Kochi",
];

const normalise = (v) => v.trim().replace(/\s+/g, " ");

/** Loose on purpose — the server has the authoritative EmailStr check, and a
 *  clever regex here only ever rejects somebody's real address. */
const looksLikeEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());

/**
 * How the four verification states read to the person in them.
 *
 * `unsubmitted` deliberately has no alarm colour: a brand that signed up ten
 * minutes ago has done nothing wrong, and painting the screen amber on arrival
 * teaches people to ignore amber.
 */
const STATE_PRESENTATION = {
    unsubmitted: {
        Icon: ShieldCheck,
        tone: "border-white/10 bg-card/60 text-muted-foreground",
        accent: "text-ember-500",
        title: "Not sent for verification yet",
        body: "Fill in the business details below and upload one document. We usually come back within 48 hours.",
    },
    pending_verification: {
        Icon: Clock,
        tone: "border-ember-500/25 bg-ember-500/10 text-ember-500/90",
        accent: "text-ember-500",
        title: "With the WeAre team",
        body: "We're checking your business out. You can keep drafting briefs in the meantime — they just can't go live until this clears.",
    },
    verified: {
        Icon: CheckCircle2,
        tone: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
        accent: "text-emerald-300",
        title: "Verified",
        body: "Your briefs can go live and you can reach creators directly.",
    },
    rejected: {
        Icon: ShieldAlert,
        tone: "border-destructive/40 bg-destructive/10 text-destructive",
        accent: "text-destructive",
        title: "We couldn't verify this yet",
        body: "Fix what's noted below and send it again — resubmitting starts clean.",
    },
};

function StateBanner({ state, reason, submittedAt }) {
    const p = STATE_PRESENTATION[state] || STATE_PRESENTATION.unsubmitted;
    const { Icon } = p;
    return (
        <div
            data-testid={IDS.stateBanner}
            data-state={state}
            className={"rounded-md border p-5 " + p.tone}
        >
            <div className="flex items-start gap-3">
                <Icon className={"mt-0.5 h-4 w-4 flex-none " + p.accent} />
                <div className="min-w-0">
                    <p className="text-xs uppercase tracking-[0.2em]">{p.title}</p>
                    <p className="mt-2 text-sm leading-relaxed">{p.body}</p>
                    {/* The reason we refused, quoted. "Not verified" on its own
                      * just generates a support email. */}
                    {state === "rejected" && reason && (
                        <p
                            data-testid={IDS.rejectionReason}
                            className="mt-3 rounded-md bg-destructive/10 p-3 text-sm leading-relaxed"
                        >
                            {reason}
                        </p>
                    )}
                    {state === "pending_verification" && submittedAt && (
                        <p className="mt-2 text-xs opacity-80">
                            Sent{" "}
                            {new Date(submittedAt).toLocaleDateString("en-IN", {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
            timeZone: IST,
                            })}
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
}

/** A labelled text field with its own error line, shown once it's been left. */
function Field({
    name,
    label,
    value,
    onChange,
    onBlur,
    problem,
    hint,
    Icon,
    multiline = false,
    ...rest
}) {
    const Control = multiline ? Textarea : Input;
    return (
        <div>
            <Label
                htmlFor={`bv-${name}`}
                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
            >
                {label}
            </Label>
            <div className="relative mt-2">
                {Icon && !multiline && (
                    <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                )}
                <Control
                    id={`bv-${name}`}
                    data-testid={IDS.field(name)}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onBlur={onBlur}
                    aria-invalid={problem ? "true" : undefined}
                    aria-describedby={problem ? `bv-${name}-error` : undefined}
                    className={
                        (multiline
                            ? "min-h-[92px] border-white/10 bg-card/60 "
                            : "h-11 border-white/10 bg-card/60 ") +
                        (Icon && !multiline ? "pl-9 " : "") +
                        (problem
                            ? "border-destructive/60 focus-visible:ring-destructive"
                            : "focus-visible:ring-ember-500")
                    }
                    {...rest}
                />
            </div>
            {problem ? (
                <p
                    id={`bv-${name}-error`}
                    data-testid={IDS.fieldError(name)}
                    className="mt-2 text-xs text-destructive"
                >
                    {problem}
                </p>
            ) : (
                hint && <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
            )}
        </div>
    );
}

export default function BrandOnboarding() {
    const { user, refresh } = useAuth();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState("");
    const [saving, setSaving] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [submitError, setSubmitError] = useState("");
    const [verification, setVerification] = useState(null);

    // Basics
    const [businessName, setBusinessName] = useState("");
    const [category, setCategory] = useState("");
    const [areas, setAreas] = useState([]);
    const [areaInput, setAreaInput] = useState("");

    // The business, as a reviewer has to be able to match it to a document.
    const [legalName, setLegalName] = useState("");
    const [businessType, setBusinessType] = useState("");
    const [registeredAddress, setRegisteredAddress] = useState("");
    const [gstNumber, setGstNumber] = useState("");
    const [website, setWebsite] = useState("");

    // The person asking on its behalf.
    const [contactName, setContactName] = useState("");
    const [contactDesignation, setContactDesignation] = useState("");
    const [contactEmail, setContactEmail] = useState("");
    // The logo uploads against its own route the moment it is picked, rather
    // than riding on Save — it is a file, not a field, and there is no partial
    // save of half a picture.
    const [logoUrl, setLogoUrl] = useState(null);
    const [uploads, setUploads] = useState(null);
    // The creator-facing half. None of it is evidence of anything, so none of
    // it is locked once verified and none of it is required to submit — it is
    // what a creator reads on the brand's public page.
    const [tagline, setTagline] = useState("");
    const [about, setAbout] = useState("");
    const [city, setCity] = useState("");
    const [outlets, setOutlets] = useState([]);
    // What they're looking for. A standing preference rather than a line on
    // one brief — it feeds the ranking on every campaign this brand posts.
    // None of it is required to submit for verification: it is what we rank
    // on, not evidence of anything.
    const [contentTypes, setContentTypes] = useState([]);
    const [followerTier, setFollowerTier] = useState("");
    const [budgetBand, setBudgetBand] = useState("");
    // The option lists come from the server on the same response, so a
    // dropdown can never offer a value the API refuses.
    const [prefOptions, setPrefOptions] = useState(null);

    const [touched, setTouched] = useState({});
    const touch = (k) => setTouched((t) => ({ ...t, [k]: true }));

    const addOutlet = () =>
        setOutlets((rows) => [
            ...rows,
            { name: "", address: "", area: "", city: city || "", lat: null, lng: null },
        ]);
    const patchOutlet = (i, patch) =>
        setOutlets((rows) => rows.map((r, n) => (n === i ? { ...r, ...patch } : r)));
    const removeOutlet = (i) => setOutlets((rows) => rows.filter((_, n) => n !== i));

    // True only when this is a genuinely empty profile. It decides where Save
    // goes: a brand arriving from signup expects to land on the dashboard,
    // while one who came back to fix its address expects to stay put and see
    // the rest of the screen.
    const firstRun = useRef(false);

    const applyProfile = useCallback(
        (data, { seedFirstRun = false } = {}) => {
            if (seedFirstRun) firstRun.current = !data.business_name;
            setBusinessName(data.business_name || user?.name || "");
            setCategory(data.category || "");
            setAreas(data.areas || []);
            setLegalName(data.legal_entity_name || "");
            setBusinessType(data.business_type || "");
            setRegisteredAddress(data.registered_address || "");
            setGstNumber(data.gst_number || "");
            setWebsite(data.website || "");
            setContactName(data.contact_person_name || user?.name || "");
            setContactDesignation(data.contact_person_designation || "");
            setContactEmail(data.contact_email || "");
            setLogoUrl(data.logo_url || null);
            setUploads(data.uploads || null);
            setTagline(data.tagline || "");
            setAbout(data.about || "");
            setCity(data.city || "");
            setOutlets(data.outlets || []);
            setContentTypes(data.content_types || []);
            setFollowerTier(data.preferred_follower_tier || "");
            setBudgetBand(data.typical_budget_band || "");
            setPrefOptions(data.preferences || null);
            setVerification(data.verification || null);
        },
        [user],
    );

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.get("/brand/profile");
                if (cancelled) return;
                applyProfile(data, { seedFirstRun: true });
            } catch (e) {
                if (!cancelled) setLoadError(formatApiError(e));
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [applyProfile]);

    /** Refetch after an upload or a delete, so the count and `can_submit`
     *  come from the server rather than being guessed at locally. */
    const reloadVerification = useCallback(async () => {
        try {
            const { data } = await api.get("/brand/profile");
            setVerification(data.verification || null);
        } catch {
            /* the list on screen is still the last known good one */
        }
    }, []);

    const addArea = useCallback((raw) => {
        const value = normalise(raw);
        if (!value) return;
        setAreas((prev) => (prev.includes(value) ? prev : [...prev, value]));
        setAreaInput("");
    }, []);

    const removeArea = (v) => setAreas((prev) => prev.filter((a) => a !== v));

    const onAreaKeyDown = (e) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            addArea(areaInput);
        } else if (e.key === "Backspace" && areaInput === "" && areas.length > 0) {
            removeArea(areas[areas.length - 1]);
        }
    };

    const suggestions = useMemo(
        () => SUGGESTED_AREAS.filter((s) => !areas.includes(s)),
        [areas],
    );

    const emailProblem =
        contactEmail.trim() && !looksLikeEmail(contactEmail)
            ? "That doesn't look like an email address."
            : null;

    const state = verification?.state || "unsubmitted";
    const isVerified = state === "verified";
    const isPending = state === "pending_verification";
    // Pending is not frozen — a brand that spots a typo while we're reading
    // should fix it, and editing keeps working in every state but verified.
    const fieldsLocked = isVerified;

    /** Every required value as it stands on screen, keyed the way the server
     *  names it. The checklist is filtered through this, because a list that
     *  only reads the last save tells somebody who has just filled seven boxes
     *  that seven boxes are empty. */
    const liveValues = {
        business_name: businessName,
        legal_entity_name: legalName,
        business_type: businessType,
        category,
        registered_address: registeredAddress,
        contact_person_name: contactName,
        contact_person_designation: contactDesignation,
        contact_email: contactEmail,
    };

    /**
     * Write what is on screen.
     *
     * One implementation, two callers: the Save button, and `Send for
     * verification`, which has to persist the boxes before a route that reads
     * the stored profile can judge them. Returns false when it refused, so
     * the submit can stop rather than sending a half-filled profile.
     */
    const saveProfile = async ({ silent = false } = {}) => {
        setError("");
        if (!businessName.trim()) {
            touch("business_name");
            setError("Please enter your business name.");
            return false;
        }
        if (!category) {
            setError("Please pick a category.");
            return false;
        }
        if (areas.length === 0) {
            setError("Add at least one area or city you operate in.");
            return false;
        }
        if (emailProblem) {
            touch("contact_email");
            setError(emailProblem);
            return false;
        }
        setSaving(true);
        try {
            // A partial save: every key here is one the person could see on
            // screen, and an empty one is an explicit "I have not filled this
            // in", not an accidental blanking of something else.
            const { data } = await api.put("/brand/profile", {
                business_name: businessName,
                category,
                areas,
                tagline: tagline.trim() || null,
                about: about.trim() || null,
                city: city || null,
                // Blank rows are dropped server-side; sending them is how a
                // repeater with an empty last row normally behaves.
                outlets,
                content_types: contentTypes,
                // "" means the question is unanswered, which is not the same
                // as "any" — a brand that said "any" told us it doesn't mind.
                preferred_follower_tier: followerTier || null,
                typical_budget_band: budgetBand || null,
                legal_entity_name: legalName.trim() || null,
                business_type: businessType || null,
                registered_address: registeredAddress.trim() || null,
                gst_number: gstNumber.trim() || null,
                website: website.trim() || null,
                contact_person_name: contactName.trim() || null,
                contact_person_designation: contactDesignation.trim() || null,
                contact_email: contactEmail.trim() || null,
            });
            await refresh();
            setVerification(data?.verification || null);
            if (!silent) notifySuccess("Brand profile saved");
            if (!silent && firstRun.current) {
                navigate("/dashboard", {
                    replace: true,
                    state: { justOnboarded: true },
                });
            }
            return true;
        } catch (err) {
            setError(formatApiError(err));
            return false;
        } finally {
            setSaving(false);
        }
    };

    const onSave = async (e) => {
        if (e) e.preventDefault();
        await saveProfile();
    };

    const onSubmitForVerification = async () => {
        setSubmitError("");
        setSubmitting(true);
        try {
            // **Save what is on screen first.** The submit route judges the
            // stored profile, so a person who filled the boxes and pressed the
            // button they were looking at used to be told the boxes were
            // empty. The Save button is two hundred pixels up the page in a
            // different section; noticing it is not the price of submitting.
            if (!(await saveProfile({ silent: true }))) {
                setSubmitError("Fix the details above, then send it.");
                return;
            }
            // The route answers with the verification block itself.
            const { data } = await api.post("/brand/verification/submit");
            setVerification(data || null);
            notifySuccess("Sent for verification");
        } catch (err) {
            // The server names what is still missing; that sentence is more
            // use than anything this screen could reconstruct.
            setSubmitError(formatApiError(err));
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div
                data-testid="brand-onboarding-loading"
                className="min-h-screen bg-background grain-page"
            >
                <Navbar />
                <main className="mx-auto max-w-3xl px-6 py-14 md:py-20">
                    <LoadingAnnouncement>Loading your brand…</LoadingAnnouncement>
                    <FormPageSkeleton
                        testid={IDS.skeleton}
                        sections={[{ fields: 2 }, { fields: 1 }]}
                        actions={1}
                    />
                    <div className="mt-8 border-t border-white/10 pt-8">
                        <VerificationDocumentsSkeleton />
                    </div>
                </main>
            </div>
        );
    }

    // **The server names what is required; the screen knows what is in the
    // boxes.** Keeping the labels from the server means the vocabulary stays
    // one vocabulary; filtering on the live value means a field disappears
    // from the list the moment it is filled rather than the moment it is
    // saved. The two were the same thing only if you pressed Save between
    // filling a box and looking down — which is exactly the trap this was.
    const required = verification?.missing_fields || [];
    const missing = required.filter((m) => !String(liveValues[m.field] ?? "").trim());
    // Filled on screen, not yet on the server. `Send for verification` saves
    // these first rather than refusing on their account.
    const unsavedCount = required.length - missing.length;
    const canSubmit =
        missing.length === 0 &&
        (verification?.document_count || 0) > 0 &&
        !isVerified &&
        !saving &&
        !submitting;

    return (
        <div
            data-testid="brand-onboarding-page"
            className="min-h-screen bg-background grain-page"
        >
            <Navbar />
            <main className="mx-auto max-w-3xl px-6 py-14 md:py-20">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Brand · Onboarding
                </p>
                <h1 className="mt-4 font-serif text-fluid-5xl leading-none tracking-tight">
                    Tell us about your brand.
                </h1>
                <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground">
                    The first two fields are enough to start drafting a brief.
                    Verification is what lets one go live in front of creators —
                    do it now or come back to it.
                </p>

                {/* Somebody filling this in should be able to look at what
                    creators will see. The page only exists once we have
                    verified the business, so the link only appears then. */}
                {isVerified && user?.id && (
                    <a
                        href={brandPageUrl(user.id)}
                        target="_blank"
                        rel="noopener"
                        data-testid={BRAND_PAGE.preview}
                        className="mt-6 inline-flex min-h-[2.75rem] items-center gap-2 text-sm text-ember-500 transition-colors duration-200 hover:text-ember-400"
                    >
                        <ExternalLink className="h-4 w-4" />
                        View your public page
                    </a>
                )}

                {loadError && (
                    <p className="mt-6 text-sm text-destructive">{loadError}</p>
                )}

                <div className="mt-10">
                    <StateBanner
                        state={state}
                        reason={verification?.verification_reason}
                        submittedAt={verification?.submitted_at}
                    />
                </div>

                <form onSubmit={onSave} noValidate className="mt-10 space-y-10">
                    <section className="space-y-5">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            Basics
                        </p>

                        <Field
                            name="business_name"
                            label="Business name"
                            value={businessName}
                            onChange={setBusinessName}
                            onBlur={() => touch("business_name")}
                            problem={
                                touched.business_name && !businessName.trim()
                                    ? "Your business name is required."
                                    : null
                            }
                            Icon={Building2}
                            maxLength={140}
                            disabled={fieldsLocked}
                            placeholder="e.g. Blue Tokai Coffee Roasters"
                        />

                        {/* Not locked with the rest once verified: a logo is
                            how a brand is recognised, not evidence of who it
                            is, and a rebrand should not need a support ticket. */}
                        <ImageUploadField
                            label="Logo"
                            hint="Shown wherever your brand is named — on your briefs, in a creator's applications, and in our console. A square PNG with a transparent background looks best."
                            shape="square"
                            value={logoUrl}
                            onChange={setLogoUrl}
                            endpoint="/brand/profile/logo"
                            responseKey="logo_url"
                            maxBytes={
                                uploads?.max_image_bytes || FALLBACK_MAX_IMAGE_BYTES
                            }
                            acceptedMimes={
                                uploads?.accepted_image_mime_types || FALLBACK_IMAGE_MIMES
                            }
                            testids={{
                                input: BRAND_LOGO.input,
                                choose: BRAND_LOGO.choose,
                                remove: BRAND_LOGO.remove,
                                preview: BRAND_LOGO.preview,
                                error: BRAND_LOGO.error,
                            }}
                        />

                        <div>
                            <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Category
                            </Label>
                            <Select
                                value={category}
                                onValueChange={setCategory}
                                disabled={fieldsLocked}
                            >
                                <SelectTrigger
                                    data-testid="brand-onb-category-trigger"
                                    className="mt-2 h-11 border-white/10 bg-card/60"
                                >
                                    <SelectValue placeholder="Pick a category" />
                                </SelectTrigger>
                                <SelectContent>
                                    {CATEGORY_OPTIONS.map((c) => (
                                        <SelectItem
                                            key={c.value}
                                            value={c.value}
                                            data-testid={`brand-onb-category-${c.value}`}
                                        >
                                            {c.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div>
                            <Label
                                htmlFor="brand-tagline"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                In one line
                            </Label>
                            <Input
                                id="brand-tagline"
                                data-testid="brand-onb-tagline-input"
                                maxLength={90}
                                value={tagline}
                                onChange={(e) => setTagline(e.target.value)}
                                className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="Third-wave coffee roastery, six cafés across Bengaluru"
                            />
                            {/* This is the line that goes on every campaign
                                card you post. A card carrying only a name
                                makes every unfamiliar brand look the same,
                                which is most of them to most creators. */}
                            <p className="mt-2 flex items-baseline justify-between gap-3 text-xs text-muted-foreground">
                                <span>Shown on every campaign card you post.</span>
                                <span className="flex-none tabular-nums">
                                    {tagline.length}/90
                                </span>
                            </p>
                        </div>

                        <div>
                            <Label
                                htmlFor="brand-about"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                About your business
                            </Label>
                            <Textarea
                                id="brand-about"
                                data-testid={BRAND_PAGE.about}
                                rows={4}
                                maxLength={1500}
                                value={about}
                                onChange={(e) => setAbout(e.target.value)}
                                className="mt-2 min-h-[120px] border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="What you make or serve, how long you've been going, what you're known for. Creators read this before deciding whether to pitch."
                            />
                            <p className="mt-2 text-xs text-muted-foreground">
                                Shown on your public page. Not part of verification —
                                write it in your own words.
                            </p>
                        </div>

                        <div>
                            <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Home city
                            </Label>
                            {/* A closed list, the same one creators and campaigns
                                use. Free text cannot be reconciled: "Bangalore"
                                and "Bengaluru " are two cities to a filter. */}
                            <Select value={city} onValueChange={setCity}>
                                <SelectTrigger
                                    data-testid={BRAND_PAGE.city}
                                    className="mt-2 h-11 border-white/10 bg-card/60"
                                >
                                    <SelectValue placeholder="Pick a city" />
                                </SelectTrigger>
                                <SelectContent>
                                    {INDIAN_CITIES.map((c) => (
                                        <SelectItem key={c} value={c}>
                                            {c}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </section>

                    <section className="space-y-4">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Outlets
                            </p>
                            <span className="text-xs text-muted-foreground">
                                Shown publicly — optional
                            </span>
                        </div>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                            The places a creator would actually turn up to. Your
                            registered address stays private and is never shown here.
                        </p>

                        {outlets.map((o, i) => (
                            <div
                                key={i}
                                data-testid={BRAND_PAGE.outlet(i)}
                                className="rounded-md border border-white/10 bg-card/60 p-4 space-y-4"
                            >
                                <div className="flex items-start gap-3">
                                    <Input
                                        data-testid={BRAND_PAGE.outletName(i)}
                                        value={o.name || ""}
                                        maxLength={140}
                                        onChange={(e) => patchOutlet(i, { name: e.target.value })}
                                        className="h-11 border-white/10 bg-transparent focus-visible:ring-ember-500"
                                        placeholder="e.g. Indiranagar"
                                    />
                                    <button
                                        type="button"
                                        data-testid={BRAND_PAGE.outletRemove(i)}
                                        onClick={() => removeOutlet(i)}
                                        aria-label={`Remove outlet ${i + 1}`}
                                        className="grid h-11 w-11 flex-none place-items-center rounded-full text-muted-foreground transition-colors duration-200 hover:text-red-300"
                                    >
                                        <X className="h-4 w-4" />
                                    </button>
                                </div>
                                {/* The same control the creator's address uses:
                                    Places autocomplete plus a draggable pin, and a
                                    plain textarea when there is no API key. */}
                                <AddressPicker
                                    address={o.address || ""}
                                    lat={o.lat ?? null}
                                    lng={o.lng ?? null}
                                    placeId={o.place_id || null}
                                    testid={BRAND_PAGE.outletAddress(i)}
                                    note="Shown on your public page, so creators know where to turn up."
                                    onChange={(patch) =>
                                        patchOutlet(i, {
                                            ...("address" in patch ? { address: patch.address } : {}),
                                            ...("lat" in patch ? { lat: patch.lat } : {}),
                                            ...("lng" in patch ? { lng: patch.lng } : {}),
                                            ...("placeId" in patch
                                                ? { place_id: patch.placeId }
                                                : {}),
                                        })
                                    }
                                />
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <Input
                                        value={o.area || ""}
                                        maxLength={120}
                                        onChange={(e) => patchOutlet(i, { area: e.target.value })}
                                        className="h-11 border-white/10 bg-transparent focus-visible:ring-ember-500"
                                        placeholder="Neighbourhood"
                                    />
                                    <Select
                                        value={o.city || ""}
                                        onValueChange={(v) => patchOutlet(i, { city: v })}
                                    >
                                        <SelectTrigger className="h-11 border-white/10 bg-transparent">
                                            <SelectValue placeholder="City" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {INDIAN_CITIES.map((c) => (
                                                <SelectItem key={c} value={c}>
                                                    {c}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                        ))}

                        <Button
                            type="button"
                            variant="outline"
                            data-testid={BRAND_PAGE.outletAdd}
                            onClick={addOutlet}
                            className="h-11 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                        >
                            <MapPin className="mr-2 h-4 w-4" />
                            Add an outlet
                        </Button>
                    </section>

                    {/* What you're looking for. Not evidence of anything and
                        not required to submit — it is what the ranking uses,
                        so a brand that answers it gets a shortlist matched to
                        the work it actually commissions rather than one
                        inferred from a budget. */}
                    <section className="space-y-5">
                        <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                What you're looking for
                            </p>
                            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                All optional. Answer what you know and we'll rank
                                creator suggestions on it — you can change any of it
                                later.
                            </p>
                        </div>

                        <div>
                            <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Content you need
                            </Label>
                            <div className="mt-3 flex flex-wrap gap-2">
                                {(prefOptions?.content_types || CONTENT_TYPES).map((c) => {
                                    const on = contentTypes.includes(c.value);
                                    return (
                                        <button
                                            key={c.value}
                                            type="button"
                                            role="switch"
                                            aria-checked={on}
                                            data-testid={`brand-onb-content-${c.value}`}
                                            onClick={() =>
                                                setContentTypes((prev) =>
                                                    on
                                                        ? prev.filter((v) => v !== c.value)
                                                        : [...prev, c.value],
                                                )
                                            }
                                            className={
                                                "min-h-[2.75rem] rounded-full border px-4 text-sm transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
                                                (on
                                                    ? "border-ember-500 bg-ember-500/15 text-ember-500"
                                                    : "border-white/10 bg-card/60 text-muted-foreground hover:border-white/25")
                                            }
                                        >
                                            {c.label}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Creator size you work with
                                </Label>
                                <Select value={followerTier} onValueChange={setFollowerTier}>
                                    <SelectTrigger
                                        data-testid="brand-onb-tier-trigger"
                                        className="mt-2 h-11 border-white/10 bg-card/60 focus:ring-ember-500"
                                    >
                                        <SelectValue placeholder="No preference yet" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {(prefOptions?.follower_tiers || FOLLOWER_TIER_OPTIONS).map(
                                            (t) => (
                                                <SelectItem
                                                    key={t.value}
                                                    value={t.value}
                                                    data-testid={`brand-onb-tier-${t.value}`}
                                                >
                                                    {t.label}
                                                    {t.range ? ` · ${t.range}` : ""}
                                                </SelectItem>
                                            ),
                                        )}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div>
                                <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Typical budget per creator
                                </Label>
                                <Select value={budgetBand} onValueChange={setBudgetBand}>
                                    <SelectTrigger
                                        data-testid="brand-onb-budget-trigger"
                                        className="mt-2 h-11 border-white/10 bg-card/60 focus:ring-ember-500"
                                    >
                                        <SelectValue placeholder="Not sure yet" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {(prefOptions?.budget_bands || BUDGET_BANDS).map((b) => (
                                            <SelectItem
                                                key={b.value}
                                                value={b.value}
                                                data-testid={`brand-onb-budget-${b.value}`}
                                            >
                                                {b.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {/* A band, not a number: a figure here would
                                    read as a commitment and get argued about.
                                    It stands in for the fee when a brief has
                                    none of its own. */}
                                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                    A guide for ranking, never quoted to a creator.
                                </p>
                            </div>
                        </div>
                    </section>

                    <section className="space-y-4">
                        <div className="flex items-baseline justify-between">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Cities &amp; areas you operate in
                            </p>
                            <span className="text-xs text-muted-foreground">
                                Pick or type — add several
                            </span>
                        </div>
                        <div
                            data-testid="brand-onb-areas-editor"
                            className="rounded-md border border-white/10 bg-card/60 p-3 focus-within:border-ember-500/50"
                        >
                            <div className="flex flex-wrap gap-2">
                                {areas.map((a) => (
                                    <span
                                        key={a}
                                        data-testid={`brand-onb-area-chip-${a}`}
                                        className="group inline-flex items-center gap-1.5 rounded-full bg-ember-500/15 px-3 py-1 text-xs uppercase tracking-[0.15em] text-ember-500"
                                    >
                                        <MapPin className="h-3 w-3" />
                                        {a}
                                        {!fieldsLocked && (
                                            <button
                                                type="button"
                                                onClick={() => removeArea(a)}
                                                aria-label={`Remove ${a}`}
                                                className="rounded-full p-0.5 opacity-70 hover:opacity-100"
                                            >
                                                <X className="h-3 w-3" />
                                            </button>
                                        )}
                                    </span>
                                ))}
                                <input
                                    data-testid="brand-onb-areas-input"
                                    value={areaInput}
                                    onChange={(e) => setAreaInput(e.target.value)}
                                    onKeyDown={onAreaKeyDown}
                                    onBlur={() =>
                                        areaInput.trim() && addArea(areaInput)
                                    }
                                    disabled={fieldsLocked}
                                    className="min-w-[140px] flex-1 bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground"
                                    placeholder={
                                        areas.length === 0
                                            ? "e.g. Bengaluru — press Enter"
                                            : "Add another…"
                                    }
                                />
                            </div>
                        </div>
                        {/* Nothing added yet, and nothing left to suggest, is a
                          * real state on a page where the field looks like a
                          * text box that swallowed the input. */}
                        {areas.length === 0 && suggestions.length === 0 && (
                            <p className="text-xs text-muted-foreground">
                                Type a city and press Enter to add it.
                            </p>
                        )}
                        {suggestions.length > 0 && !fieldsLocked && (
                            <div className="flex flex-wrap gap-2">
                                {suggestions.map((s) => (
                                    <button
                                        key={s}
                                        type="button"
                                        onClick={() => addArea(s)}
                                        data-testid={`brand-onb-area-suggest-${s.replace(/\s+/g, "-")}`}
                                        className="rounded-full border border-white/10 bg-transparent px-3 py-1 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                                    >
                                        + {s}
                                    </button>
                                ))}
                            </div>
                        )}
                    </section>

                    <section className="space-y-5 border-t border-white/10 pt-10">
                        <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                The business
                            </p>
                            <p className="mt-2 max-w-xl text-xs leading-relaxed text-muted-foreground">
                                What a reviewer checks your documents against.
                                The name on the paperwork is often not the name
                                on the door — we need both.
                            </p>
                        </div>

                        <Field
                            name="legal_entity_name"
                            label="Legal entity name"
                            value={legalName}
                            onChange={setLegalName}
                            maxLength={200}
                            disabled={fieldsLocked}
                            placeholder="e.g. Blue Tokai Coffee Roasters Pvt Ltd"
                            hint="Exactly as it appears on your registration."
                        />

                        <div>
                            <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Business type
                            </Label>
                            <Select
                                value={businessType}
                                onValueChange={setBusinessType}
                                disabled={fieldsLocked}
                            >
                                <SelectTrigger
                                    data-testid={IDS.field("business_type")}
                                    className="mt-2 h-11 border-white/10 bg-card/60"
                                >
                                    <SelectValue placeholder="Pick one" />
                                </SelectTrigger>
                                <SelectContent>
                                    {BUSINESS_TYPE_OPTIONS.map((b) => (
                                        <SelectItem
                                            key={b.value}
                                            value={b.value}
                                            data-testid={`brand-verification-business-type-${b.value}`}
                                        >
                                            {b.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <Field
                            name="registered_address"
                            label="Registered address"
                            value={registeredAddress}
                            onChange={setRegisteredAddress}
                            multiline
                            rows={3}
                            maxLength={500}
                            disabled={fieldsLocked}
                            placeholder="The address on your registration paperwork"
                        />

                        <div className="grid gap-5 md:grid-cols-2">
                            <Field
                                name="gst_number"
                                label="GST number (optional)"
                                value={gstNumber}
                                onChange={setGstNumber}
                                maxLength={15}
                                disabled={fieldsLocked}
                                placeholder="15 characters"
                                hint="Plenty of real businesses have none."
                            />
                            <Field
                                name="website"
                                label="Website (optional)"
                                value={website}
                                onChange={setWebsite}
                                maxLength={300}
                                disabled={fieldsLocked}
                                placeholder="https://"
                            />
                        </div>
                    </section>

                    <section className="space-y-5 border-t border-white/10 pt-10">
                        <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Who's asking
                            </p>
                            <p className="mt-2 max-w-xl text-xs leading-relaxed text-muted-foreground">
                                This account is one named person at the
                                business. Your WhatsApp number is already your
                                login — this is the rest of it.
                            </p>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                            <Field
                                name="contact_person_name"
                                label="Your full name"
                                value={contactName}
                                onChange={setContactName}
                                maxLength={140}
                                disabled={fieldsLocked}
                            />
                            <Field
                                name="contact_person_designation"
                                label="Your designation"
                                value={contactDesignation}
                                onChange={setContactDesignation}
                                maxLength={140}
                                disabled={fieldsLocked}
                                placeholder="e.g. Marketing lead"
                            />
                        </div>

                        <Field
                            name="contact_email"
                            label="Work email"
                            type="email"
                            inputMode="email"
                            value={contactEmail}
                            onChange={setContactEmail}
                            onBlur={() => touch("contact_email")}
                            problem={touched.contact_email ? emailProblem : null}
                            disabled={fieldsLocked}
                            placeholder="you@yourbusiness.com"
                            hint="An address on your own domain is the quickest thing for us to check."
                        />
                    </section>

                    {error && (
                        <p
                            data-testid={IDS.saveError}
                            className="text-sm text-destructive"
                        >
                            {error}
                        </p>
                    )}

                    {!fieldsLocked && (
                        <div className="flex flex-col-reverse items-stretch gap-3 border-t border-white/10 pt-8 md:flex-row md:items-center md:justify-between">
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <ShieldCheck className="h-4 w-4 flex-none text-ember-500" />
                                Saving keeps what you've filled in — you don't
                                have to finish in one go.
                            </div>
                            <Button
                                type="submit"
                                data-testid={IDS.saveBtn}
                                disabled={saving}
                                className="group h-12 rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400"
                            >
                                {saving ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Saving…
                                    </>
                                ) : firstRun.current ? (
                                    <>
                                        Save &amp; continue
                                        <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                    </>
                                ) : (
                                    <>
                                        <Save className="mr-2 h-4 w-4" />
                                        Save details
                                    </>
                                )}
                            </Button>
                        </div>
                    )}
                </form>

                {/* Documents sit outside the form: each one uploads on its own
                  * the moment it is chosen, so putting them inside a form with
                  * a Save button would imply they are waiting for it. */}
                <div className="mt-12 border-t border-white/10 pt-10">
                    {verification ? (
                        <VerificationDocuments
                            verification={verification}
                            onChanged={reloadVerification}
                            readOnly={isVerified}
                        />
                    ) : (
                        <VerificationDocumentsSkeleton />
                    )}
                </div>

                {!isVerified && (
                    <div className="mt-10 border-t border-white/10 pt-10">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            {isPending ? "Already with us" : "Send it to us"}
                        </p>

                        {/* Named, not implied. A greyed-out button with no
                          * explanation is the single most common way a form
                          * becomes a support ticket. */}
                        {missing.length > 0 && (
                            <div
                                data-testid={IDS.missingList}
                                className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/10 p-4"
                            >
                                <p className="text-xs uppercase tracking-[0.15em] text-amber-200">
                                    Still needed before we can check you
                                </p>
                                <ul className="mt-3 space-y-1.5">
                                    {missing.map((m) => (
                                        <li
                                            key={m.field}
                                            data-testid={IDS.missingField(m.field)}
                                            className="text-sm text-amber-100/90"
                                        >
                                            · {m.label}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Filled on screen, not yet on the server. Saying so
                          * is the difference between "it ignored me" and "it
                          * has them, it just hasn't written them down". */}
                        {unsavedCount > 0 && (
                            <p
                                data-testid={IDS.unsavedNote}
                                className="mt-4 text-sm text-muted-foreground"
                            >
                                {unsavedCount === 1
                                    ? "One detail is filled in but not saved yet"
                                    : `${unsavedCount} details are filled in but not saved yet`}
                                {" — sending will save them."}
                            </p>
                        )}

                        {missing.length === 0 &&
                            (verification?.document_count || 0) === 0 && (
                                <p
                                    data-testid={IDS.submitBlocked}
                                    className="mt-4 text-sm text-amber-200"
                                >
                                    Everything's filled in — upload one document
                                    above and you're ready to send.
                                </p>
                            )}

                        {submitError && (
                            <p
                                data-testid={IDS.submitError}
                                className="mt-4 text-sm text-destructive"
                            >
                                {submitError}
                            </p>
                        )}

                        <Button
                            type="button"
                            data-testid={IDS.submitBtn}
                            onClick={onSubmitForVerification}
                            disabled={!canSubmit}
                            className="mt-6 h-12 w-full rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400 disabled:opacity-50 md:w-auto"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Sending…
                                </>
                            ) : (
                                <>
                                    <Send className="mr-2 h-4 w-4" />
                                    {isPending
                                        ? "Send again"
                                        : "Send for verification"}
                                </>
                            )}
                        </Button>
                    </div>
                )}
            </main>
        </div>
    );
}
