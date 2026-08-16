import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { notifySuccess } from "@/lib/feedback";
import {
    ArrowRight,
    Building2,
    Loader2,
    MapPin,
    ShieldCheck,
    X,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Navbar } from "@/components/Navbar";

const CATEGORY_OPTIONS = [
    { value: "fnb", label: "F&B" },
    { value: "hospitality", label: "Hospitality" },
    { value: "retail", label: "Retail" },
    { value: "lifestyle", label: "Lifestyle" },
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

export default function BrandOnboarding() {
    const { user, refresh } = useAuth();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    const [businessName, setBusinessName] = useState("");
    const [category, setCategory] = useState("");
    const [areas, setAreas] = useState([]);
    const [areaInput, setAreaInput] = useState("");

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.get("/brand/profile");
                if (cancelled) return;
                setBusinessName(data.business_name || user?.name || "");
                setCategory(data.category || "");
                setAreas(data.areas || []);
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

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        if (!businessName.trim()) return setError("Please enter your business name.");
        if (!category) return setError("Please pick a category.");
        if (areas.length === 0)
            return setError("Add at least one area or city you operate in.");
        setSubmitting(true);
        try {
            await api.put("/brand/profile", {
                business_name: businessName,
                category,
                areas,
            });
            await refresh();
            notifySuccess("Brand profile saved");
            navigate("/dashboard", { replace: true, state: { justOnboarded: true } });
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="grid min-h-screen place-items-center bg-background text-muted-foreground grain-page">
                <Loader2 className="h-5 w-5 animate-spin" />
            </div>
        );
    }

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
                    A quick 30-second setup and you'll be ready to post your first
                    paid campaign.
                </p>

                <form onSubmit={onSubmit} className="mt-12 space-y-8">
                    <section className="space-y-5">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            Basics
                        </p>

                        <div>
                            <Label
                                htmlFor="biz-name"
                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                            >
                                Business name
                            </Label>
                            <div className="relative mt-2">
                                <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    id="biz-name"
                                    data-testid="brand-onb-name-input"
                                    value={businessName}
                                    onChange={(e) => setBusinessName(e.target.value)}
                                    required
                                    maxLength={140}
                                    className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                    placeholder="e.g. Blue Tokai Coffee Roasters"
                                />
                            </div>
                        </div>

                        <div>
                            <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Category
                            </Label>
                            <Select value={category} onValueChange={setCategory}>
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
                    </section>

                    <section className="space-y-4">
                        <div className="flex items-baseline justify-between">
                            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Cities & areas you operate in
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
                                        <button
                                            type="button"
                                            onClick={() => removeArea(a)}
                                            aria-label={`Remove ${a}`}
                                            className="rounded-full p-0.5 opacity-70 hover:opacity-100"
                                        >
                                            <X className="h-3 w-3" />
                                        </button>
                                    </span>
                                ))}
                                <input
                                    data-testid="brand-onb-areas-input"
                                    value={areaInput}
                                    onChange={(e) => setAreaInput(e.target.value)}
                                    onKeyDown={onAreaKeyDown}
                                    onBlur={() => areaInput.trim() && addArea(areaInput)}
                                    className="min-w-[140px] flex-1 bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground"
                                    placeholder={
                                        areas.length === 0
                                            ? "e.g. Bengaluru — press Enter"
                                            : "Add another…"
                                    }
                                />
                            </div>
                        </div>
                        {suggestions.length > 0 && (
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

                    {error && (
                        <p
                            data-testid="brand-onb-error"
                            className="text-sm text-destructive"
                        >
                            {error}
                        </p>
                    )}

                    <div className="flex flex-col-reverse items-stretch gap-3 border-t border-white/10 pt-8 md:flex-row md:items-center md:justify-between">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <ShieldCheck className="h-4 w-4 text-ember-500" />
                            Every brand is verified by the WeAre team before campaigns go live.
                        </div>
                        <Button
                            type="submit"
                            data-testid="brand-onb-submit-btn"
                            disabled={submitting}
                            className="group h-12 rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving…
                                </>
                            ) : (
                                <>
                                    Save & continue
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
