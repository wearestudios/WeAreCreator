// What a creator posts about, as tags from one vocabulary — the creator's
// own profile, onboarding, and an admin's correction all use this.
//
// **"Suggested from your posts" is a suggestion until somebody keeps it.**
// The model reads the last 24 captions; its tags sit as chips with Keep and
// Remove beside them. A tag the creator chose overrides the model and survives
// every weekly re-read; one they removed stays removed. Nothing here is free
// text — every option is a key in `lib/niches.js`, and the server drops
// anything else.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Sparkles, X } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { NICHES_BY_CATEGORY, TAG_KINDS, labelOf, optionsFor } from "@/lib/niches";
import { Button } from "@/components/ui/button";

const CATEGORY_NAMES = {
    fnb: "Food & drink",
    hospitality: "Hospitality",
    retail: "Retail",
    real_estate: "Real estate",
    fashion: "Fashion",
    travel: "Travel",
    wellness: "Wellness",
    lifestyle: "Lifestyle",
};

function Chip({ selected, children, onClick, testid }) {
    return (
        <button
            type="button"
            aria-pressed={selected}
            onClick={onClick}
            data-testid={testid}
            className={`rounded-pill border px-3 py-1 text-meta transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                selected
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-foreground hover:border-foreground/40"
            }`}
        >
            {children}
        </button>
    );
}

function Suggestions({ suggestions, onDecide, busy }) {
    const items = [
        ...(suggestions.niche || []).map((n) => ({ kind: "niche", tag: n.tag })),
        ...["languages", "tone", "shoots_in"].flatMap((kind) =>
            (suggestions[kind] || []).map((tag) => ({ kind, tag })),
        ),
    ];
    if (!items.length) return null;
    return (
        <div data-testid="tags-suggestions" className="rounded-lg border border-border bg-muted/40 p-4">
            <p className="flex items-center gap-2 text-meta font-medium">
                <Sparkles className="h-4 w-4 text-muted-foreground" aria-hidden />
                Suggested from your posts
            </p>
            <ul className="mt-3 flex flex-wrap gap-2">
                {items.map(({ kind, tag }) => (
                    <li
                        key={`${kind}-${tag}`}
                        className="inline-flex items-center gap-1 rounded-pill border border-dashed border-border bg-card py-0.5 pl-3 pr-1 text-meta"
                    >
                        {kind === "shoots_in" ? `Shoots in ${labelOf(kind, tag)}` : labelOf(kind, tag)}
                        <button
                            type="button"
                            disabled={busy}
                            onClick={() => onDecide(kind, tag, "accept")}
                            aria-label={`Keep ${labelOf(kind, tag)}`}
                            data-testid={`tags-keep-${kind}-${tag}`}
                            className="rounded-pill p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                        >
                            <Check className="h-3.5 w-3.5" />
                        </button>
                        <button
                            type="button"
                            disabled={busy}
                            onClick={() => onDecide(kind, tag, "remove")}
                            aria-label={`Remove ${labelOf(kind, tag)}`}
                            data-testid={`tags-remove-${kind}-${tag}`}
                            className="rounded-pill p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    </li>
                ))}
            </ul>
            <p className="mt-3 text-meta text-muted-foreground">
                Read from your last posts' captions. Keep what's right; what you remove won't come back.
            </p>
        </div>
    );
}

/**
 * @param endpoint   GET/PUT for the tag set: `/creator/tags`, or the admin's
 *                   `/admin/creators/:id/tags`.
 * @param decide     whether the Keep/Remove chips post to the creator's own
 *                   suggestion route (the creator) or just add to the set
 *                   being edited (an admin).
 */
export default function TagEditor({ endpoint, decide = false, title = "What you post", className = "" }) {
    const [data, setData] = useState(null);
    const [draft, setDraft] = useState(null);
    const [busy, setBusy] = useState(false);

    const adopt = useCallback((payload) => {
        setData(payload);
        setDraft({
            niche: [...(payload.confirmed?.niche || [])],
            languages: [...(payload.confirmed?.languages || [])],
            tone: [...(payload.confirmed?.tone || [])],
            shoots_in: [...(payload.confirmed?.shoots_in || [])],
        });
    }, []);

    useEffect(() => {
        api.get(endpoint).then((res) => adopt(res.data)).catch(() => setData(false));
    }, [endpoint, adopt]);

    const dirty = useMemo(() => {
        if (!data || !draft) return false;
        return TAG_KINDS.some(({ key }) => {
            const a = [...(data.confirmed?.[key] || [])].sort().join();
            const b = [...draft[key]].sort().join();
            return a !== b;
        });
    }, [data, draft]);

    if (data === false) return null;
    if (!data || !draft) {
        return <div aria-hidden className={`h-40 rounded-lg bg-muted ${className}`} />;
    }

    const toggle = (kind, key) =>
        setDraft((d) => ({
            ...d,
            [kind]: d[kind].includes(key) ? d[kind].filter((k) => k !== key) : [...d[kind], key],
        }));

    const save = async () => {
        setBusy(true);
        try {
            const res = await api.put(endpoint, draft);
            adopt(res.data);
            notifySuccess("Saved");
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    const onDecide = async (kind, tag, decision) => {
        if (!decide) {
            if (decision === "accept") toggle(kind, tag);
            return;
        }
        setBusy(true);
        try {
            const res = await api.post(`/creator/tags/suggestions/${kind}/${tag}/${decision}`, {});
            adopt(res.data);
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    return (
        <section data-testid="tag-editor" className={`space-y-5 ${className}`}>
            <div>
                <h2 className="font-serif text-h3">{title}</h2>
                <p className="mt-1 text-meta text-muted-foreground">
                    Briefs are matched on these — what you post about, the languages you post in,
                    and where you shoot.
                    {data.formats?.length
                        ? ` From your posts: mostly ${data.formats.map((f) => labelOf("formats", f)).join(" and ")}.`
                        : ""}
                </p>
            </div>
            <Suggestions suggestions={data.suggestions || {}} onDecide={onDecide} busy={busy} />
            {TAG_KINDS.map(({ key, label }) => (
                <fieldset key={key}>
                    <legend className="text-meta font-medium">{label}</legend>
                    {key === "niche" ? (
                        Object.entries(NICHES_BY_CATEGORY).map(([cat, group]) => (
                            <div key={cat} className="mt-2">
                                <p className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground">
                                    {CATEGORY_NAMES[cat] || cat}
                                </p>
                                <div className="mt-1.5 flex flex-wrap gap-1.5">
                                    {Object.entries(group).map(([k, l]) => (
                                        <Chip key={k} selected={draft.niche.includes(k)} onClick={() => toggle("niche", k)} testid={`tag-niche-${k}`}>
                                            {l}
                                        </Chip>
                                    ))}
                                </div>
                            </div>
                        ))
                    ) : (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                            {optionsFor(key).map(([k, l]) => (
                                <Chip key={k} selected={draft[key].includes(k)} onClick={() => toggle(key, k)} testid={`tag-${key}-${k}`}>
                                    {l}
                                </Chip>
                            ))}
                        </div>
                    )}
                </fieldset>
            ))}
            <Button onClick={save} disabled={busy || !dirty} data-testid="tags-save">
                {busy ? "Saving…" : "Save tags"}
            </Button>
        </section>
    );
}
