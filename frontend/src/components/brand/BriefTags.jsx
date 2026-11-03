// The brief's tags — what it is about, the language it wants, where it is.
//
// **Nothing applies without the brand.** After a brief is saved the model
// suggests tags in the background; they arrive here as dashed chips, and only
// the ones the brand ticks and confirms become the brief's tags, which is what
// creators are matched against. The area is suggested only when the venue text
// names one.
import React, { useCallback, useEffect, useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { AREAS, LANGUAGES, NICHE_LABELS, labelOf } from "@/lib/niches";
import { Button } from "@/components/ui/button";

const KINDS = [
    { key: "niche", label: "What it's about", options: NICHE_LABELS },
    { key: "languages", label: "Language", options: LANGUAGES },
    { key: "areas", label: "Area", options: AREAS },
];

export default function BriefTags({ campaignId }) {
    const [data, setData] = useState(null);
    const [picked, setPicked] = useState(null);
    const [busy, setBusy] = useState(false);
    const [showAll, setShowAll] = useState(false);

    const adopt = useCallback((payload) => {
        setData(payload);
        setPicked({
            niche: [...(payload.confirmed?.niche || [])],
            languages: [...(payload.confirmed?.languages || [])],
            areas: [...(payload.confirmed?.areas || [])],
        });
    }, []);

    useEffect(() => {
        api.get(`/brand/campaigns/${campaignId}/tags`).then((r) => adopt(r.data)).catch(() => setData(false));
    }, [campaignId, adopt]);

    if (data === false || !data || !picked) return null;

    const toggle = (kind, key) =>
        setPicked((p) => ({
            ...p,
            [kind]: p[kind].includes(key) ? p[kind].filter((k) => k !== key) : [...p[kind], key],
        }));

    const confirm = async () => {
        setBusy(true);
        try {
            adopt((await api.put(`/brand/campaigns/${campaignId}/tags`, picked)).data);
            notifySuccess("Tags confirmed");
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    const suggest = async () => {
        setBusy(true);
        try {
            adopt((await api.post(`/brand/campaigns/${campaignId}/tags/suggest`, {})).data);
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    return (
        <section data-testid="brief-tags" className="rounded-lg border border-border bg-card p-card-sm md:p-card">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="font-bold text-h3">Tags creators are matched on</h2>
                    <p className="mt-1 max-w-measure text-meta text-muted-foreground">
                        Suggestions are dashed. Tick the ones that fit and confirm — nothing applies until you do.
                    </p>
                </div>
                {data.ai_on ? (
                    <Button variant="outline" size="sm" onClick={suggest} disabled={busy} data-testid="brief-tags-suggest">
                        <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
                        Suggest again
                    </Button>
                ) : null}
            </div>
            {KINDS.map(({ key, label, options }) => {
                const suggested = data.suggested?.[key] || [];
                const shown = new Set([...picked[key], ...suggested]);
                const rest = showAll ? Object.keys(options).filter((k) => !shown.has(k)) : [];
                return (
                    <fieldset key={key} className="mt-5">
                        <legend className="text-meta font-medium">{label}</legend>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                            {[...shown, ...rest].map((k) => {
                                const on = picked[key].includes(k);
                                const isSuggestion = suggested.includes(k) && !on;
                                return (
                                    <button
                                        key={k}
                                        type="button"
                                        aria-pressed={on}
                                        onClick={() => toggle(key, k)}
                                        data-testid={`brief-tag-${key}-${k}`}
                                        className={`inline-flex items-center gap-1 rounded-pill border px-3 py-1 text-meta transition-colors duration-200 ${
                                            on
                                                ? "border-primary bg-primary text-primary-foreground"
                                                : isSuggestion
                                                    ? "border-dashed border-foreground/40 bg-card"
                                                    : "border-border bg-card"
                                        }`}
                                    >
                                        {isSuggestion ? <Sparkles className="h-3 w-3" aria-label="Suggested" /> : null}
                                        {labelOf(key, k)}
                                    </button>
                                );
                            })}
                        </div>
                    </fieldset>
                );
            })}
            <div className="mt-5 flex flex-wrap items-center gap-3">
                <Button onClick={confirm} disabled={busy} data-testid="brief-tags-confirm">
                    Confirm tags
                </Button>
                <button
                    type="button"
                    onClick={() => setShowAll((v) => !v)}
                    className="text-meta text-muted-foreground underline underline-offset-4"
                >
                    {showAll ? "Show fewer" : "Choose from the full list"}
                </button>
            </div>
        </section>
    );
}
