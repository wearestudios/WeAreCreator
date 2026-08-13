import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
    ArrowRight,
    Instagram,
    Loader2,
    MapPin,
    Users,
    IndianRupee,
    X,
    ShieldCheck,
    Wallet,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Navbar } from "@/components/Navbar";

const SUGGESTED_NICHES = [
    "cafe",
    "brunch",
    "bakery",
    "fine dining",
    "lifestyle",
    "coffee",
    "dessert",
    "brewery",
    "cocktails",
    "home chef",
    "healthy",
    "street food",
    "fashion",
    "wellness",
];

const SUGGESTED_CITIES = [
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

const normalise = (v) => v.trim().toLowerCase().replace(/\s+/g, " ");

export default function CreatorOnboarding() {
    const { user, refresh } = useAuth();
    const navigate = useNavigate();

    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    const [name, setName] = useState("");
    const [instagramHandle, setInstagramHandle] = useState("");
    const [instagramUrl, setInstagramUrl] = useState("");
    const [email, setEmail] = useState("");
    const [city, setCity] = useState("");
    const [address, setAddress] = useState("");
    const [niches, setNiches] = useState([]);
    const [nicheInput, setNicheInput] = useState("");
    const [baseRate, setBaseRate] = useState("");
    const [followerCount, setFollowerCount] = useState("");
    const [payoutUpi, setPayoutUpi] = useState("");
    const [payoutAccountName, setPayoutAccountName] = useState("");
    const [pan, setPan] = useState("");
    const [gstin, setGstin] = useState("");
    const [vettingStatus, setVettingStatus] = useState("pending");

    // Prefill from the existing stub / previous submission.
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.get("/creator/profile");
                if (cancelled) return;
                setName(data.name || user?.name || "");
                setInstagramHandle(data.instagram_handle || "");
                setInstagramUrl(data.instagram_profile_url || "");
                setEmail(data.email || user?.email || "");
                setCity(data.city || "");
                setAddress(data.address || "");
                setNiches(data.niches || []);
                setBaseRate(
                    data.base_rate === null || data.base_rate === undefined
                        ? ""
                        : String(data.base_rate),
                );
                setFollowerCount(
                    data.follower_count === null || data.follower_count === undefined
                        ? ""
                        : String(data.follower_count),
                );
                setPayoutUpi(data.payout_upi || "");
                setPayoutAccountName(data.payout_account_name || "");
                setPan(data.pan || "");
                setGstin(data.gstin || "");
                setVettingStatus(data.vetting_status || "pending");
            } catch (e) {
                setError(formatApiError(e));
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [user]);

    const addNiche = useCallback(
        (raw) => {
            const value = normalise(raw);
            if (!value) return;
            setNiches((prev) => (prev.includes(value) ? prev : [...prev, value]));
            setNicheInput("");
        },
        [],
    );

    const removeNiche = (value) =>
        setNiches((prev) => prev.filter((n) => n !== value));

    const onNicheKeyDown = (e) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            addNiche(nicheInput);
        } else if (
            e.key === "Backspace" &&
            nicheInput === "" &&
            niches.length > 0
        ) {
            removeNiche(niches[niches.length - 1]);
        }
    };

    const remainingSuggestions = useMemo(
        () => SUGGESTED_NICHES.filter((s) => !niches.includes(s)),
        [niches],
    );

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        if (niches.length === 0) {
            setError("Please add at least one niche so brands can find you.");
            return;
        }
        setSubmitting(true);
        try {
            await api.put("/creator/profile", {
                name,
                instagram_handle: instagramHandle,
                instagram_profile_url: instagramUrl,
                email,
                city: city.trim() || null,
                address,
                niches,
                base_rate: baseRate === "" ? null : Number(baseRate),
                follower_count:
                    followerCount === "" ? null : Number(followerCount),
                payout_upi: payoutUpi.trim() || null,
                payout_account_name: payoutAccountName.trim() || null,
                pan: pan.trim() || null,
                gstin: gstin.trim() || null,
            });
            await refresh(); // pick up any name change
            toast.success(
                vettingStatus === "vetted"
                    ? "Profile updated"
                    : "Profile submitted for review",
            );
            navigate("/dashboard", { replace: true, state: { justOnboarded: true } });
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="grid min-h-screen place-items-center bg-background text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
            </div>
        );
    }

    return (
        <div
            data-testid="creator-onboarding-page"
            className="min-h-screen bg-background"
        >
            <Navbar />
            <main className="mx-auto max-w-3xl px-6 py-14 md:py-20">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Creator · Onboarding
                </p>
                <h1 className="mt-4 font-serif text-4xl leading-none tracking-tight md:text-5xl">
                    Tell us about you.
                </h1>
                <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted-foreground">
                    {vettingStatus === "vetted"
                        ? "You're vetted, so you stay live while you edit. Changing your name, handle or city means we'll take another look — you won't drop off the directory in the meantime."
                        : "This becomes your creator profile on WeAre. The team reviews it — usually within 48 hours — and you can pitch on briefs as soon as you're approved."}
                </p>

                <form onSubmit={onSubmit} className="mt-12 space-y-8">
                    {/* Basics */}
                    <section className="space-y-5">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            Basics
                        </p>
                        <div>
                            <Label htmlFor="name" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Full name
                            </Label>
                            <Input
                                id="name"
                                data-testid="onboarding-name-input"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                required
                                maxLength={120}
                                className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="e.g. Priya Rao"
                            />
                        </div>
                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label htmlFor="ig-handle" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Instagram handle
                                </Label>
                                <div className="relative mt-2">
                                    <Instagram className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="ig-handle"
                                        data-testid="onboarding-ig-handle-input"
                                        value={instagramHandle}
                                        onChange={(e) => setInstagramHandle(e.target.value)}
                                        required
                                        className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="@your.handle"
                                    />
                                </div>
                            </div>
                            <div>
                                <Label htmlFor="ig-url" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Instagram profile URL
                                </Label>
                                <Input
                                    id="ig-url"
                                    data-testid="onboarding-ig-url-input"
                                    type="url"
                                    value={instagramUrl}
                                    onChange={(e) => setInstagramUrl(e.target.value)}
                                    required
                                    className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                    placeholder="https://instagram.com/…"
                                />
                            </div>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label htmlFor="email" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Email
                                </Label>
                                <Input
                                    id="email"
                                    data-testid="onboarding-email-input"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                    className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                    placeholder="you@studio.in"
                                />
                            </div>
                            <div>
                                <Label htmlFor="city" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    City
                                </Label>
                                <Input
                                    id="city"
                                    data-testid="onboarding-city-input"
                                    list="city-suggestions"
                                    value={city}
                                    onChange={(e) => setCity(e.target.value)}
                                    required
                                    maxLength={80}
                                    className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                    placeholder="e.g. Bengaluru"
                                />
                                <datalist id="city-suggestions">
                                    {SUGGESTED_CITIES.map((c) => (
                                        <option value={c} key={c} />
                                    ))}
                                </datalist>
                            </div>
                        </div>

                        <div>
                            <Label htmlFor="address" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Neighbourhood / address
                            </Label>
                            <div className="relative mt-2">
                                <MapPin className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
                                <Textarea
                                    id="address"
                                    data-testid="onboarding-address-input"
                                    value={address}
                                    onChange={(e) => setAddress(e.target.value)}
                                    required
                                    rows={2}
                                    className="min-h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                    placeholder="Neighbourhood or short address so brands can plan visits"
                                />
                            </div>
                        </div>
                    </section>

                    {/* Niches */}
                    <section className="space-y-4">
                        <div className="flex items-baseline justify-between">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Your niches
                            </p>
                            <span className="text-xs text-muted-foreground">
                                Pick or type — add several
                            </span>
                        </div>
                        <div
                            data-testid="onboarding-niches-editor"
                            className="rounded-md border border-white/10 bg-card/60 p-3 focus-within:border-ember-500/50"
                        >
                            <div className="flex flex-wrap gap-2">
                                {niches.map((n) => (
                                    <span
                                        key={n}
                                        data-testid={`niche-chip-${n}`}
                                        className="group inline-flex items-center gap-1.5 rounded-full bg-ember-500/15 px-3 py-1 text-xs uppercase tracking-[0.15em] text-ember-500"
                                    >
                                        {n}
                                        <button
                                            type="button"
                                            onClick={() => removeNiche(n)}
                                            aria-label={`Remove ${n}`}
                                            className="rounded-full p-0.5 opacity-70 transition-opacity duration-200 hover:opacity-100"
                                        >
                                            <X className="h-3 w-3" />
                                        </button>
                                    </span>
                                ))}
                                <input
                                    data-testid="onboarding-niches-input"
                                    value={nicheInput}
                                    onChange={(e) => setNicheInput(e.target.value)}
                                    onKeyDown={onNicheKeyDown}
                                    onBlur={() => {
                                        if (nicheInput.trim()) addNiche(nicheInput);
                                    }}
                                    className="min-w-[140px] flex-1 bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground"
                                    placeholder={
                                        niches.length === 0
                                            ? "e.g. cafe, brunch — press Enter"
                                            : "Add another…"
                                    }
                                />
                            </div>
                        </div>
                        {remainingSuggestions.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                                {remainingSuggestions.map((s) => (
                                    <button
                                        type="button"
                                        key={s}
                                        onClick={() => addNiche(s)}
                                        data-testid={`niche-suggest-${s.replace(/\s+/g, "-")}`}
                                        className="rounded-full border border-white/10 bg-transparent px-3 py-1 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                                    >
                                        + {s}
                                    </button>
                                ))}
                            </div>
                        )}
                    </section>

                    {/* Optional */}
                    <section className="space-y-5">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            Optional — helps brands price fairly
                        </p>
                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label htmlFor="base-rate" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Base rate per collab
                                </Label>
                                <div className="relative mt-2">
                                    <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="base-rate"
                                        data-testid="onboarding-base-rate-input"
                                        type="number"
                                        min="0"
                                        step="100"
                                        value={baseRate}
                                        onChange={(e) => setBaseRate(e.target.value)}
                                        className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. 5000"
                                    />
                                </div>
                            </div>
                            <div>
                                <Label htmlFor="followers" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Instagram followers (self-reported)
                                </Label>
                                <div className="relative mt-2">
                                    <Users className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="followers"
                                        data-testid="onboarding-followers-input"
                                        type="number"
                                        min="0"
                                        step="100"
                                        value={followerCount}
                                        onChange={(e) => setFollowerCount(e.target.value)}
                                        className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. 12400"
                                    />
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Payout — asked for here so the money can actually move later */}
                    <section className="space-y-5">
                        <div className="flex items-baseline justify-between">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Getting paid
                            </p>
                            <span className="text-xs text-muted-foreground">
                                Needed before your first payout
                            </span>
                        </div>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                            You can add these later, but we can't release a payment
                            without them. Only the WeAre team ever sees this — brands
                            never do.
                        </p>
                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label htmlFor="payout-upi" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    UPI ID
                                </Label>
                                <div className="relative mt-2">
                                    <Wallet className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="payout-upi"
                                        data-testid="onboarding-upi-input"
                                        value={payoutUpi}
                                        onChange={(e) => setPayoutUpi(e.target.value)}
                                        maxLength={120}
                                        className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. priya@okhdfcbank"
                                    />
                                </div>
                            </div>
                            <div>
                                <Label htmlFor="payout-name" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Name on the account
                                </Label>
                                <Input
                                    id="payout-name"
                                    data-testid="onboarding-payout-name-input"
                                    value={payoutAccountName}
                                    onChange={(e) => setPayoutAccountName(e.target.value)}
                                    maxLength={140}
                                    className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                    placeholder="As it appears on your bank account"
                                />
                            </div>
                        </div>
                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label htmlFor="payout-pan" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    PAN
                                </Label>
                                <Input
                                    id="payout-pan"
                                    data-testid="onboarding-pan-input"
                                    value={pan}
                                    onChange={(e) => setPan(e.target.value.toUpperCase())}
                                    maxLength={10}
                                    className="mt-2 h-11 border-white/10 bg-card/60 uppercase focus-visible:ring-ember-500"
                                    placeholder="ABCDE1234F"
                                />
                                <p className="mt-2 text-xs text-muted-foreground">
                                    Required for TDS on your payout.
                                </p>
                            </div>
                            <div>
                                <Label htmlFor="payout-gstin" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    GSTIN (optional)
                                </Label>
                                <Input
                                    id="payout-gstin"
                                    data-testid="onboarding-gstin-input"
                                    value={gstin}
                                    onChange={(e) => setGstin(e.target.value.toUpperCase())}
                                    maxLength={15}
                                    className="mt-2 h-11 border-white/10 bg-card/60 uppercase focus-visible:ring-ember-500"
                                    placeholder="29ABCDE1234F1Z5"
                                />
                                <p className="mt-2 text-xs text-muted-foreground">
                                    Only if you're GST-registered.
                                </p>
                            </div>
                        </div>
                    </section>

                    {error && (
                        <p
                            data-testid="onboarding-error"
                            className="text-sm text-destructive"
                        >
                            {error}
                        </p>
                    )}

                    <div className="flex flex-col-reverse items-stretch gap-3 border-t border-white/10 pt-8 md:flex-row md:items-center md:justify-between">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <ShieldCheck className="h-4 w-4 text-ember-500" />
                            {vettingStatus === "vetted"
                                ? "You stay live while we review any changes."
                                : "Your profile is reviewed by the WeAre team before going live."}
                        </div>
                        <Button
                            type="submit"
                            data-testid="onboarding-submit-btn"
                            disabled={submitting}
                            className="group h-12 rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Submitting…
                                </>
                            ) : (
                                <>
                                    {vettingStatus === "vetted"
                                        ? "Save changes"
                                        : "Submit for review"}
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
