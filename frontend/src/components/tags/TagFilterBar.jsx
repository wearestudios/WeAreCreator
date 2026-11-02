// Filters on stored tags: niche, language, area, format, follower tier and
// reliability. One bar for the applicant board and the suggestions panel, so
// a brand narrows both lists in the same words. Every value is a key the
// server already stores — a filter is a query, never a model call.
import React from "react";
import { X } from "lucide-react";

import { AREAS, FORMATS, LANGUAGES, NICHE_LABELS } from "@/lib/niches";

const TIERS = { micro: "Micro (1K–10K)", mid: "Mid (10K–100K)", macro: "Macro (100K+)" };
const RELIABILITY = { strong: "Consistently delivers", steady: "Reliable", mixed: "Some missed commitments", new: "New here" };

const FIELDS = [
    { key: "niche", label: "Niche", options: NICHE_LABELS },
    { key: "language", label: "Language", options: LANGUAGES },
    { key: "area", label: "Area", options: AREAS },
    { key: "format", label: "Format", options: FORMATS },
    { key: "tier", label: "Followers", options: TIERS },
    { key: "reliability", label: "Reliability", options: RELIABILITY },
];

export default function TagFilterBar({ value, onChange, className = "", only = null }) {
    // A panel that already has its own niche or follower controls passes
    // `only` so the same question is never asked twice on one screen.
    const fields = only ? FIELDS.filter((f) => only.includes(f.key)) : FIELDS;
    const active = Object.keys(value).filter((k) => value[k]);
    const set = (key, v) => {
        const next = { ...value };
        if (v) next[key] = v;
        else delete next[key];
        onChange(next);
    };
    return (
        <div data-testid="tag-filters" className={`flex flex-wrap items-center gap-2 ${className}`}>
            {fields.map(({ key, label, options }) => (
                <label key={key} className="inline-flex items-center">
                    <span className="sr-only">{label}</span>
                    <select
                        value={value[key] || ""}
                        onChange={(e) => set(key, e.target.value)}
                        data-testid={`tag-filter-${key}`}
                        className="h-9 rounded-md border border-input bg-card px-2.5 text-meta focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                        <option value="">{label}: any</option>
                        {Object.entries(options).map(([k, l]) => (
                            <option key={k} value={k}>{l}</option>
                        ))}
                    </select>
                </label>
            ))}
            {active.length ? (
                <button
                    type="button"
                    onClick={() => onChange({})}
                    data-testid="tag-filters-clear"
                    className="inline-flex items-center gap-1 text-meta text-muted-foreground underline underline-offset-4"
                >
                    <X className="h-3.5 w-3.5" /> Clear
                </button>
            ) : null}
        </div>
    );
}
