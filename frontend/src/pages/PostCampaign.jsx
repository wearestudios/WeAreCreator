import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
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
import { Navbar } from "@/components/Navbar";
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

const CATEGORY_OPTIONS = [
    { value: "fnb", label: "F&B" },
    { value: "hospitality", label: "Hospitality" },
    { value: "retail", label: "Retail" },
    { value: "real_estate", label: "Real Estate" },
    { value: "fashion", label: "Fashion" },
    { value: "travel", label: "Travel" },
    { value: "wellness", label: "Wellness" },
    { value: "lifestyle", label: "Lifestyle" },
];

// An ISO timestamp back into the yyyy-mm-dd an <input type="date"> expects.
const toDateInput = (iso) => {
    if (!iso) return "";
    try {
        return new Date(iso).toISOString().slice(0, 10);
    } catch {
        return "";
    }
};

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
    const [deliverables, setDeliverables] = useState("");
    const [budget, setBudget] = useState("");
    const [category, setCategory] = useState("");
    const [area, setArea] = useState("");
    const [creatorsNeeded, setCreatorsNeeded] = useState("1");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
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
                    setDeliverables(data.deliverables || "");
                    setBudget(
                        data.budget_per_creator == null
                            ? ""
                            : String(data.budget_per_creator),
                    );
                    setCategory(data.category || "");
                    setArea(data.area || "");
                    setCreatorsNeeded(String(data.creators_needed ?? 1));
                    setStartDate(toDateInput(data.start_date));
                    setEndDate(toDateInput(data.end_date));
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

    const validateBase = () => {
        if (!title.trim()) return "Please enter a campaign title.";
        if (!brief.trim()) return "Please add a brief.";
        if (!deliverables.trim()) return "What deliverables are you expecting?";
        const budgetNum = Number(budget);
        if (!Number.isFinite(budgetNum) || budgetNum < 0)
            return "Please enter a valid budget per creator.";
        if (!category) return "Please pick a category.";
        if (!area) return "Please pick an area.";
        const needed = Number(creatorsNeeded);
        if (!Number.isFinite(needed) || needed < 1)
            return "How many creators do you need?";
        if (startDate && endDate && new Date(endDate) < new Date(startDate))
            return "End date cannot be before the start date.";
        return null;
    };

    const buildPayload = (status) => ({
        title: title.trim(),
        brief: brief.trim(),
        deliverables: deliverables.trim(),
        budget_per_creator: Number(budget),
        category,
        area,
        creators_needed: Math.max(1, Number(creatorsNeeded) || 1),
        start_date: startDate ? new Date(startDate).toISOString() : null,
        end_date: endDate ? new Date(endDate).toISOString() : null,
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
                const { status: _ignored, ...changes } = buildPayload(status);
                await api.put(`/brand/campaigns/${editingId}`, changes);
                // Saving an edit on a draft and submitting should do both.
                if (!isDraft && existing?.status === "draft") {
                    await api.post(`/brand/campaigns/${editingId}/publish`);
                    toast.success("Sent for review — we'll publish it once we've read it");
                } else {
                    toast.success("Campaign updated");
                }
                navigate("/dashboard", { replace: true });
                return;
            }

            const { data } = await api.post("/brand/campaigns", buildPayload(status));
            toast.success(
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
        return (
            <div className="grid min-h-screen place-items-center bg-background text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
            </div>
        );
    }

    return (
        <div
            data-testid="post-campaign-page"
            className="min-h-screen bg-background text-foreground"
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
                <h1 className="mt-3 font-serif text-4xl leading-none tracking-tight md:text-5xl">
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
                            <Label htmlFor="pc-deliverables" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Deliverables
                            </Label>
                            <Textarea
                                id="pc-deliverables"
                                data-testid="pc-deliverables-input"
                                rows={2}
                                maxLength={1000}
                                value={deliverables}
                                onChange={(e) => setDeliverables(e.target.value)}
                                className="mt-2 min-h-[92px] border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="e.g. 1 Instagram reel (30-45s) + 3 stories, tag @yourbrand"
                            />
                        </div>
                    </section>

                    <section className="space-y-5">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            Money & scope
                        </p>
                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label htmlFor="pc-budget" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Budget per creator
                                </Label>
                                <div className="relative mt-2">
                                    <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        id="pc-budget"
                                        data-testid="pc-budget-input"
                                        type="number"
                                        min="0"
                                        step="500"
                                        value={budget}
                                        onChange={(e) => setBudget(e.target.value)}
                                        className="h-11 border-white/10 bg-card/60 pl-9 focus-visible:ring-ember-500"
                                        placeholder="e.g. 8000"
                                    />
                                </div>
                                <p className="mt-2 text-xs text-muted-foreground">
                                    Creators receive 100% of this amount. Platform fee is charged to you on top.
                                </p>
                            </div>
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

                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <Label htmlFor="pc-start" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                    Start date
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
                                    End date
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
