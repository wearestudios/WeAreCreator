// The creator profile builder.
//
// Signup asks for a name and a WhatsApp number and stops. Everything a brand
// actually shortlists on gets built here instead, and the two rules that shape
// this page follow from that:
//
//   1. Nothing is required to save. Somebody filling this in on a phone
//      between two things should be able to put down what they have and come
//      back — a form that refuses half an answer just gets abandoned with
//      nothing saved at all.
//   2. Saving is not submitting. The team only sees a profile when the creator
//      says it's ready, which the server only allows at 100%. That is why the
//      progress ring is the loudest thing on the page: it is the actual gate,
//      not decoration.
//
// The percentage and the missing list both come from the server, so the submit
// button and the rule behind it can never disagree.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { motion, useReducedMotion } from "framer-motion";
import {
    ArrowRight,
    Check,
    Instagram,
    Loader2,
    MapPin,
    Save,
    ShieldCheck,
    Upload,
    Users,
    Wallet,
    X,
    Youtube,
    IndianRupee,
    Image as ImageIcon,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError, mediaUrl } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Navbar } from "@/components/Navbar";
import { CREATOR_ONBOARDING as IDS } from "@/constants/testIds";

const SUGGESTED_NICHES = [
    "cafe", "brunch", "bakery", "fine dining", "coffee", "dessert",
    "brewery", "cocktails", "home chef", "healthy", "street food",
];

// What they make, as opposed to what they cover for a brand.
const SUGGESTED_GENRES = [
    "food", "travel", "lifestyle", "fashion", "comedy", "fitness",
    "beauty", "tech", "parenting", "music",
];

const SUGGESTED_CITIES = [
    "Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad", "Pune", "Chennai",
    "Kolkata", "Goa", "Ahmedabad", "Jaipur", "Chandigarh", "Kochi",
];

const PLATFORMS = [
    { value: "instagram", label: "Instagram", Icon: Instagram },
    { value: "youtube", label: "YouTube", Icon: Youtube },
];

const normalise = (v) => v.trim().toLowerCase().replace(/\s+/g, " ");

// Mirrors MAX_UPLOAD_MB on the server; checked here only to fail fast.
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

// ---------------------------------------------------------------------------
// Pieces
// ---------------------------------------------------------------------------

const RADIUS = 26;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const Ring = ({ percent }) => {
    const still = useReducedMotion();
    const offset = CIRCUMFERENCE * (1 - Math.max(0, Math.min(100, percent)) / 100);
    return (
        <div
            data-testid={IDS.ring}
            role="img"
            aria-label={`Profile ${percent}% complete`}
            className="relative h-16 w-16 flex-none"
        >
            <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
                <circle cx="32" cy="32" r={RADIUS} fill="none" strokeWidth="3" className="stroke-white/10" />
                <motion.circle
                    cx="32"
                    cy="32"
                    r={RADIUS}
                    fill="none"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeDasharray={CIRCUMFERENCE}
                    className="stroke-ember-500"
                    initial={false}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: still ? 0 : 0.6, ease: [0.22, 1, 0.36, 1] }}
                />
            </svg>
            <span
                data-testid={IDS.percent}
                className="absolute inset-0 grid place-items-center font-serif text-base"
            >
                {percent}%
            </span>
        </div>
    );
};

const Section = ({ id, title, note, children }) => (
    <section data-testid={IDS.section(id)} className="space-y-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{title}</p>
            {note && <span className="text-xs text-muted-foreground/80">{note}</span>}
        </div>
        {children}
    </section>
);

/** A chip editor for a free-text list with suggestions under it. */
const ChipList = ({ values, onChange, suggestions, editorId, inputId, chipId, suggestId, placeholder }) => {
    const [draft, setDraft] = useState("");

    const add = (raw) => {
        const value = normalise(raw);
        if (!value) return;
        if (!values.includes(value)) onChange([...values, value]);
        setDraft("");
    };
    const remove = (value) => onChange(values.filter((v) => v !== value));

    const onKeyDown = (e) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            add(draft);
        } else if (e.key === "Backspace" && draft === "" && values.length > 0) {
            remove(values[values.length - 1]);
        }
    };

    const remaining = suggestions.filter((s) => !values.includes(s));

    return (
        <div className="space-y-3">
            <div
                data-testid={editorId}
                className="rounded-md border border-white/10 bg-card/60 p-3 focus-within:border-ember-500/50"
            >
                <div className="flex flex-wrap gap-2">
                    {values.map((v) => (
                        <span
                            key={v}
                            data-testid={chipId(v)}
                            className="inline-flex items-center gap-1.5 rounded-full bg-ember-500/15 px-3 py-1 text-xs uppercase tracking-[0.15em] text-ember-500"
                        >
                            {v}
                            <button
                                type="button"
                                onClick={() => remove(v)}
                                aria-label={`Remove ${v}`}
                                className="rounded-full p-0.5 opacity-70 transition-opacity duration-200 hover:opacity-100"
                            >
                                <X className="h-3 w-3" />
                            </button>
                        </span>
                    ))}
                    <input
                        data-testid={inputId}
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={onKeyDown}
                        onBlur={() => draft.trim() && add(draft)}
                        className="min-w-[140px] flex-1 bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground"
                        placeholder={values.length === 0 ? placeholder : "Add another…"}
                    />
                </div>
            </div>
            {remaining.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {remaining.map((s) => (
                        <button
                            type="button"
                            key={s}
                            onClick={() => add(s)}
                            data-testid={suggestId(s.replace(/\s+/g, "-"))}
                            className="rounded-full border border-white/10 bg-transparent px-3 py-1 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                        >
                            + {s}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};

const Field = ({ id, label, hint, children }) => (
    <div>
        <Label htmlFor={id} className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
            {label}
        </Label>
        {children}
        {hint && <p className="mt-2 text-xs text-muted-foreground">{hint}</p>}
    </div>
);

const inputClass = "mt-2 h-12 border-white/10 bg-card/60 focus-visible:ring-ember-500";

// ---------------------------------------------------------------------------

export default function CreatorOnboarding() {
    const { user, refresh } = useAuth();
    const navigate = useNavigate();
    const still = useReducedMotion();

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [completeness, setCompleteness] = useState(null);
    const [verificationStatus, setVerificationStatus] = useState("pending");
    const [submittedAt, setSubmittedAt] = useState(null);

    const [form, setForm] = useState({
        name: "",
        email: "",
        city: "",
        address: "",
        full_address: "",
        genres: [],
        niches: [],
        platforms: [],
        instagram_handle: "",
        instagram_profile_url: "",
        youtube_url: "",
        base_rate: "",
        follower_count: "",
        payout_upi: "",
        payout_account_name: "",
        pan: "",
        gstin: "",
    });
    const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));
    const setText = (key) => (e) => set(key)(e.target.value);

    const [profileImageUrl, setProfileImageUrl] = useState(null);
    const [imageBusy, setImageBusy] = useState(false);
    const [imageError, setImageError] = useState("");
    const fileInputRef = useRef(null);

    const applyProfile = useCallback((data) => {
        setForm({
            name: data.name || "",
            email: data.email || "",
            city: data.city || "",
            address: data.address || "",
            full_address: data.full_address || "",
            genres: data.genres || [],
            niches: data.niches || [],
            platforms: data.platforms || [],
            instagram_handle: data.instagram_handle || "",
            instagram_profile_url: data.instagram_profile_url || "",
            youtube_url: data.youtube_url || "",
            base_rate: data.base_rate ?? "",
            follower_count: data.follower_count ?? "",
            payout_upi: data.payout_upi || "",
            payout_account_name: data.payout_account_name || "",
            pan: data.pan || "",
            gstin: data.gstin || "",
        });
        setProfileImageUrl(data.profile_image_url || null);
        setVerificationStatus(data.verification_status || "pending");
        setSubmittedAt(data.submitted_for_review_at || null);
        setCompleteness(data.profile_completeness || null);
    }, []);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.get("/creator/profile");
                if (cancelled) return;
                applyProfile({ ...data, name: data.name || user?.name || "" });
            } catch (e) {
                if (!cancelled) setError(formatApiError(e));
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [user, applyProfile]);

    // The photo saves on its own, not with the form — a file upload is a
    // different kind of write, and it shouldn't be lost if the form is
    // abandoned. It counts towards completeness, so re-read after it lands.
    const refreshCompleteness = useCallback(async () => {
        try {
            const { data } = await api.get("/creator/profile");
            setCompleteness(data.profile_completeness || null);
        } catch {
            // The ring going stale is not worth an error message.
        }
    }, []);

    const onPickImage = async (e) => {
        const file = e.target.files?.[0];
        e.target.value = ""; // let the same file be re-picked after an error
        if (!file) return;
        setImageError("");
        if (!file.type.startsWith("image/")) {
            setImageError("Please choose an image file.");
            return;
        }
        if (file.size > MAX_IMAGE_BYTES) {
            setImageError("That image is over 5MB. Try a smaller one.");
            return;
        }
        const body = new FormData();
        body.append("file", file);
        setImageBusy(true);
        try {
            const { data } = await api.post("/creator/profile/image", body, {
                headers: { "Content-Type": undefined },
            });
            setProfileImageUrl(data.profile_image_url);
            toast.success("Photo updated");
            refreshCompleteness();
        } catch (err) {
            setImageError(formatApiError(err));
        } finally {
            setImageBusy(false);
        }
    };

    const onRemoveImage = async () => {
        setImageError("");
        setImageBusy(true);
        try {
            await api.delete("/creator/profile/image");
            setProfileImageUrl(null);
            refreshCompleteness();
        } catch (err) {
            setImageError(formatApiError(err));
        } finally {
            setImageBusy(false);
        }
    };

    /** Everything on the form, as the API wants it. Blanks are explicit nulls
     *  so clearing a field actually clears it. */
    const payload = useMemo(
        () => ({
            name: form.name.trim() || null,
            email: form.email.trim() || null,
            city: form.city.trim() || null,
            address: form.address.trim() || null,
            full_address: form.full_address.trim() || null,
            genres: form.genres,
            niches: form.niches,
            platforms: form.platforms,
            instagram_handle: form.instagram_handle.trim() || null,
            instagram_profile_url: form.instagram_profile_url.trim() || null,
            youtube_url: form.youtube_url.trim() || null,
            base_rate: form.base_rate === "" ? null : Number(form.base_rate),
            follower_count: form.follower_count === "" ? null : Number(form.follower_count),
            payout_upi: form.payout_upi.trim() || null,
            payout_account_name: form.payout_account_name.trim() || null,
            pan: form.pan.trim() || null,
            gstin: form.gstin.trim() || null,
        }),
        [form],
    );

    const save = async ({ quiet = false } = {}) => {
        setError("");
        setSaving(true);
        try {
            const { data } = await api.put("/creator/profile", payload);
            applyProfile({ ...data, profile_image_url: data.profile_image_url ?? profileImageUrl });
            await refresh(); // pick up any name change in the navbar
            if (!quiet) toast.success("Saved — come back any time");
            return true;
        } catch (err) {
            setError(formatApiError(err));
            return false;
        } finally {
            setSaving(false);
        }
    };

    const submit = async () => {
        // Save first: submitting what's on screen rather than what was last
        // written is the only behaviour that isn't a trap.
        if (!(await save({ quiet: true }))) return;
        setSubmitting(true);
        setError("");
        try {
            await api.post("/creator/profile/submit-for-review");
            toast.success("Sent to the WeAre team — we'll come back within 48 hours");
            navigate("/dashboard", { replace: true, state: { justOnboarded: true } });
        } catch (err) {
            setError(formatApiError(err));
            refreshCompleteness();
        } finally {
            setSubmitting(false);
        }
    };

    const percent = completeness?.percent ?? 0;
    const missing = completeness?.missing || [];
    const canSubmit = Boolean(completeness?.complete) && verificationStatus !== "verified";
    const onInstagram = form.platforms.includes("instagram");
    const onYouTube = form.platforms.includes("youtube");

    if (loading) {
        return (
            <div data-testid={IDS.page} className="min-h-screen bg-background">
                <Navbar />
                <main data-testid={IDS.skeleton} className="mx-auto max-w-3xl space-y-8 px-5 py-12 md:px-6 md:py-16">
                    <Skeleton className="h-3 w-32" />
                    <Skeleton className="h-10 w-2/3" />
                    <Skeleton className="h-24 w-full rounded-md" />
                    {[0, 1, 2].map((i) => (
                        <div key={i} className="space-y-3">
                            <Skeleton className="h-3 w-24" />
                            <Skeleton className="h-12 w-full rounded-md" />
                            <Skeleton className="h-12 w-full rounded-md" />
                        </div>
                    ))}
                </main>
            </div>
        );
    }

    return (
        <div data-testid={IDS.page} className="min-h-screen bg-background">
            <Navbar />
            <main className="mx-auto max-w-3xl px-5 py-12 md:px-6 md:py-16">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Creator · Your profile
                </p>
                <h1 className="mt-4 font-serif text-4xl leading-none tracking-tight md:text-5xl">
                    Tell us about you.
                </h1>
                <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground">
                    {verificationStatus === "verified"
                        ? "You're verified, so you stay live while you edit. Changing your name, handle or city means we'll take another look — you won't drop off the directory in the meantime."
                        : "Fill in as much as you like and save. Nothing here is required to save, and nobody sees it until you send it to us."}
                </p>

                {/* The gate, made visible. The ring is what decides whether the
                    submit button works, so it sits above the form rather than
                    at the end of it. */}
                <div className="mt-10 flex flex-col gap-5 rounded-md border border-white/10 bg-card p-6 sm:flex-row sm:items-center">
                    <Ring percent={percent} />
                    <div className="min-w-0 flex-1">
                        {completeness?.complete ? (
                            <p className="font-serif text-xl leading-tight">
                                That's everything — send it over when you're ready.
                            </p>
                        ) : (
                            <>
                                <p className="font-serif text-xl leading-tight">
                                    {percent === 0
                                        ? "Let's get you on the directory."
                                        : "Nearly there."}
                                </p>
                                <ul data-testid={IDS.missing} className="mt-3 flex flex-wrap gap-2">
                                    {missing.map((row) => (
                                        <li
                                            key={row.field}
                                            data-testid={IDS.missingItem(row.field)}
                                            className="rounded-full border border-white/10 bg-background/60 px-3 py-1 text-xs text-muted-foreground"
                                        >
                                            {row.label}
                                        </li>
                                    ))}
                                </ul>
                            </>
                        )}
                        {submittedAt && verificationStatus === "pending" && (
                            <p data-testid={IDS.statusNote} className="mt-3 text-xs text-ember-500">
                                Already with the team — reviews usually finish within 48 hours.
                            </p>
                        )}
                    </div>
                </div>

                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        save();
                    }}
                    noValidate
                    className="mt-12 space-y-12"
                >
                    <Section id="you" title="You">
                        <div className="flex flex-wrap items-center gap-5">
                            <div
                                data-testid={IDS.photoPreview}
                                className="grid h-20 w-20 flex-none place-items-center overflow-hidden rounded-md border border-white/10 bg-card/60"
                            >
                                {profileImageUrl ? (
                                    <img src={mediaUrl(profileImageUrl)} alt="Your profile" className="h-full w-full object-cover" />
                                ) : (
                                    <ImageIcon className="h-6 w-6 text-muted-foreground" />
                                )}
                            </div>
                            <div className="min-w-0">
                                <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Profile photo
                                </Label>
                                <div className="mt-2 flex flex-wrap items-center gap-2">
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept="image/jpeg,image/png,image/webp,image/gif"
                                        onChange={onPickImage}
                                        data-testid={IDS.photoInput}
                                        className="hidden"
                                    />
                                    <Button
                                        type="button"
                                        variant="outline"
                                        disabled={imageBusy}
                                        data-testid={IDS.photoUpload}
                                        onClick={() => fileInputRef.current?.click()}
                                        className="h-11 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                                    >
                                        {imageBusy ? (
                                            <>
                                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                Uploading…
                                            </>
                                        ) : (
                                            <>
                                                <Upload className="mr-2 h-4 w-4" />
                                                {profileImageUrl ? "Replace photo" : "Upload photo"}
                                            </>
                                        )}
                                    </Button>
                                    {profileImageUrl && (
                                        <button
                                            type="button"
                                            disabled={imageBusy}
                                            onClick={onRemoveImage}
                                            data-testid={IDS.photoRemove}
                                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-red-300 disabled:opacity-40"
                                        >
                                            Remove
                                        </button>
                                    )}
                                </div>
                                <p className="mt-2 text-xs text-muted-foreground">
                                    JPEG, PNG, WebP or GIF, up to 5MB. Saves on its own.
                                </p>
                                {imageError && (
                                    <p data-testid={IDS.photoError} className="mt-2 text-xs text-destructive">
                                        {imageError}
                                    </p>
                                )}
                            </div>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                            <Field id="name" label="Full name">
                                <Input
                                    id="name"
                                    data-testid={IDS.name}
                                    value={form.name}
                                    onChange={setText("name")}
                                    maxLength={120}
                                    className={inputClass}
                                    placeholder="e.g. Priya Rao"
                                />
                            </Field>
                            <Field id="email" label="Email">
                                <Input
                                    id="email"
                                    data-testid={IDS.email}
                                    type="email"
                                    value={form.email}
                                    onChange={setText("email")}
                                    className={inputClass}
                                    placeholder="you@studio.in"
                                />
                            </Field>
                        </div>
                    </Section>

                    <Section id="where" title="Where you are">
                        <div className="grid gap-5 md:grid-cols-2">
                            <Field id="city" label="City">
                                <Input
                                    id="city"
                                    data-testid={IDS.city}
                                    list="city-suggestions"
                                    value={form.city}
                                    onChange={setText("city")}
                                    maxLength={80}
                                    className={inputClass}
                                    placeholder="e.g. Bengaluru"
                                />
                                <datalist id="city-suggestions">
                                    {SUGGESTED_CITIES.map((c) => (
                                        <option value={c} key={c} />
                                    ))}
                                </datalist>
                            </Field>
                            <Field
                                id="address"
                                label="Neighbourhood"
                                hint="What brands filter on when they're planning a visit."
                            >
                                <div className="relative mt-2">
                                    <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="address"
                                        data-testid={IDS.address}
                                        value={form.address}
                                        onChange={setText("address")}
                                        maxLength={500}
                                        className="h-12 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. Indiranagar"
                                    />
                                </div>
                            </Field>
                        </div>
                        <Field
                            id="full-address"
                            label="Full address"
                            hint="Where product actually gets sent. Only the WeAre team sees this."
                        >
                            <Textarea
                                id="full-address"
                                data-testid={IDS.fullAddress}
                                value={form.full_address}
                                onChange={setText("full_address")}
                                rows={2}
                                maxLength={500}
                                className="mt-2 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="Flat, street, area, city, PIN"
                            />
                        </Field>
                    </Section>

                    <Section id="make" title="What you make" note="Your own work">
                        <ChipList
                            values={form.genres}
                            onChange={set("genres")}
                            suggestions={SUGGESTED_GENRES}
                            editorId={IDS.genres}
                            inputId={IDS.genresInput}
                            chipId={IDS.genreChip}
                            suggestId={IDS.genreSuggest}
                            placeholder="e.g. food, travel — press Enter"
                        />
                    </Section>

                    <Section id="cover" title="What you cover for brands" note="How briefs find you">
                        <ChipList
                            values={form.niches}
                            onChange={set("niches")}
                            suggestions={SUGGESTED_NICHES}
                            editorId={IDS.niches}
                            inputId={IDS.nichesInput}
                            chipId={IDS.nicheChip}
                            suggestId={IDS.nicheSuggest}
                            placeholder="e.g. cafe, brunch — press Enter"
                        />
                    </Section>

                    <Section id="platforms" title="Where you post">
                        <div className="grid gap-3 sm:grid-cols-2">
                            {PLATFORMS.map(({ value, label, Icon }) => {
                                const on = form.platforms.includes(value);
                                return (
                                    <button
                                        type="button"
                                        key={value}
                                        data-testid={IDS.platform(value)}
                                        aria-pressed={on}
                                        onClick={() =>
                                            set("platforms")(
                                                on
                                                    ? form.platforms.filter((p) => p !== value)
                                                    : [...form.platforms, value],
                                            )
                                        }
                                        className={
                                            "flex min-h-[3.5rem] items-center gap-3 rounded-md border px-4 text-left transition-colors duration-200 " +
                                            (on
                                                ? "border-ember-500 bg-ember-500/10 text-ember-500"
                                                : "border-white/10 bg-card/60 text-muted-foreground hover:border-white/25")
                                        }
                                    >
                                        <Icon className="h-4 w-4 flex-none" />
                                        <span className="text-sm">{label}</span>
                                        {on && <Check className="ml-auto h-4 w-4 flex-none" />}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Only the channels they actually picked get asked for.
                            Demanding a YouTube link from somebody who only posts
                            on Instagram would put 100% permanently out of reach,
                            and with it the ability to submit at all. */}
                        {onInstagram && (
                            <motion.div
                                initial={still ? false : { opacity: 0, y: -6 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.25 }}
                                className="grid gap-5 md:grid-cols-2"
                            >
                                <Field id="ig-handle" label="Instagram handle">
                                    <div className="relative mt-2">
                                        <Instagram className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            id="ig-handle"
                                            data-testid={IDS.igHandle}
                                            value={form.instagram_handle}
                                            onChange={setText("instagram_handle")}
                                            className="h-12 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                            placeholder="@your.handle"
                                        />
                                    </div>
                                </Field>
                                <Field id="ig-url" label="Instagram profile link">
                                    <Input
                                        id="ig-url"
                                        data-testid={IDS.igUrl}
                                        type="url"
                                        value={form.instagram_profile_url}
                                        onChange={setText("instagram_profile_url")}
                                        className={inputClass}
                                        placeholder="https://instagram.com/…"
                                    />
                                </Field>
                            </motion.div>
                        )}

                        {onYouTube && (
                            <motion.div
                                initial={still ? false : { opacity: 0, y: -6 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.25 }}
                            >
                                <Field id="yt-url" label="YouTube channel link">
                                    <div className="relative mt-2">
                                        <Youtube className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            id="yt-url"
                                            data-testid={IDS.youtube}
                                            type="url"
                                            value={form.youtube_url}
                                            onChange={setText("youtube_url")}
                                            className="h-12 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                            placeholder="https://youtube.com/@yourchannel"
                                        />
                                    </div>
                                </Field>
                            </motion.div>
                        )}
                    </Section>

                    <Section id="rates" title="Your rate">
                        <div className="grid gap-5 md:grid-cols-2">
                            <Field id="base-rate" label="Base rate per collab">
                                <div className="relative mt-2">
                                    <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="base-rate"
                                        data-testid={IDS.baseRate}
                                        type="number"
                                        min="0"
                                        step="100"
                                        value={form.base_rate}
                                        onChange={setText("base_rate")}
                                        className="h-12 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. 5000"
                                    />
                                </div>
                            </Field>
                            <Field
                                id="followers"
                                label="Followers"
                                hint="Your own figure — brands see it labelled that way."
                            >
                                <div className="relative mt-2">
                                    <Users className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="followers"
                                        data-testid={IDS.followers}
                                        type="number"
                                        min="0"
                                        step="100"
                                        value={form.follower_count}
                                        onChange={setText("follower_count")}
                                        className="h-12 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. 12400"
                                    />
                                </div>
                            </Field>
                        </div>
                    </Section>

                    <Section id="payout" title="Getting paid" note="Not needed to be reviewed">
                        <p className="text-sm leading-relaxed text-muted-foreground">
                            {/* Said plainly so nobody thinks bank details are the
                                price of being looked at. They aren't. */}
                            We can't release a payment without these, but you don't
                            need them to submit your profile. Only the WeAre team ever
                            sees this — brands never do.
                        </p>
                        <div className="grid gap-5 md:grid-cols-2">
                            <Field id="payout-upi" label="UPI ID">
                                <div className="relative mt-2">
                                    <Wallet className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="payout-upi"
                                        data-testid={IDS.upi}
                                        value={form.payout_upi}
                                        onChange={setText("payout_upi")}
                                        maxLength={120}
                                        className="h-12 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. priya@okhdfcbank"
                                    />
                                </div>
                            </Field>
                            <Field id="payout-name" label="Name on the account">
                                <Input
                                    id="payout-name"
                                    data-testid={IDS.payoutName}
                                    value={form.payout_account_name}
                                    onChange={setText("payout_account_name")}
                                    maxLength={140}
                                    className={inputClass}
                                    placeholder="As it appears on your bank account"
                                />
                            </Field>
                        </div>
                        <div className="grid gap-5 md:grid-cols-2">
                            <Field id="payout-pan" label="PAN" hint="Required for TDS on your payout.">
                                <Input
                                    id="payout-pan"
                                    data-testid={IDS.pan}
                                    value={form.pan}
                                    onChange={(e) => set("pan")(e.target.value.toUpperCase())}
                                    maxLength={10}
                                    className={inputClass + " uppercase"}
                                    placeholder="ABCDE1234F"
                                />
                            </Field>
                            <Field id="payout-gstin" label="GSTIN" hint="Only if you're GST-registered.">
                                <Input
                                    id="payout-gstin"
                                    data-testid={IDS.gstin}
                                    value={form.gstin}
                                    onChange={(e) => set("gstin")(e.target.value.toUpperCase())}
                                    maxLength={15}
                                    className={inputClass + " uppercase"}
                                    placeholder="29ABCDE1234F1Z5"
                                />
                            </Field>
                        </div>
                    </Section>

                    {error && (
                        <p data-testid={IDS.error} className="text-sm text-destructive">
                            {error}
                        </p>
                    )}

                    <div className="space-y-4 border-t border-white/10 pt-8">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <ShieldCheck className="h-4 w-4 flex-none text-ember-500" />
                            {verificationStatus === "verified"
                                ? "You stay live while we review any changes."
                                : "Nothing is shared with brands until the team has reviewed your profile."}
                        </div>

                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                            <Button
                                type="submit"
                                variant="outline"
                                data-testid={IDS.save}
                                disabled={saving || submitting}
                                className="h-12 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                {saving ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Saving…
                                    </>
                                ) : (
                                    <>
                                        <Save className="mr-2 h-4 w-4" />
                                        Save progress
                                    </>
                                )}
                            </Button>

                            {verificationStatus !== "verified" && (
                                <Button
                                    type="button"
                                    onClick={submit}
                                    data-testid={IDS.submit}
                                    disabled={!canSubmit || saving || submitting}
                                    className="group h-12 rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400 disabled:opacity-40"
                                >
                                    {submitting ? (
                                        <>
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            Sending…
                                        </>
                                    ) : (
                                        <>
                                            {submittedAt ? "Send again" : "Submit for review"}
                                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                        </>
                                    )}
                                </Button>
                            )}

                            <Link
                                to="/dashboard"
                                data-testid={IDS.later}
                                className="inline-flex min-h-[3rem] items-center text-sm text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                            >
                                Finish later
                            </Link>
                        </div>

                        {!canSubmit && verificationStatus !== "verified" && (
                            <p data-testid={IDS.submitBlocked} className="text-xs text-muted-foreground">
                                {/* The button being dead needs a reason next to
                                    it, or it just reads as broken. */}
                                {missing.length} still to go before you can send this
                                over: {missing.map((m) => m.label).join(", ")}.
                            </p>
                        )}
                    </div>
                </form>
            </main>
        </div>
    );
}
