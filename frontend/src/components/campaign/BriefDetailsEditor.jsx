// The brand's half of the structured brief.
//
// **Everything here used to go into the narrative box** — tag us, don't film
// the queue, use this hashtag, here's the logo — where it was prose a creator
// read once, and the mismatch surfaced at draft review after the shoot.
//
// The whole section is optional and stays collapsed until somebody opens it.
// A brief with none of this is a perfectly good brief; six empty boxes above
// the deliverables would read as six more things a brand has to do before it
// can post, which is how a form stops being filled in at all.
import React, { useState } from "react";
import { ChevronDown, Plus, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BRIEF as IDS } from "@/constants/testIds";
import {
    BRIEF_FIELD_HINTS,
    BRIEF_LIST_FIELDS,
    BRIEF_SIGILS,
    MAX_BRIEF_ASSETS,
    MAX_BRIEF_LIST_ITEMS,
    normaliseBriefLine,
} from "@/lib/briefDetails";

/** The empty shape, so a caller never has to spell the field names out. */
export function emptyBriefDetails() {
    return {
        brief_dos: [],
        brief_donts: [],
        mandatory_hashtags: [],
        mandatory_mentions: [],
        caption_guidance: "",
        brand_assets: [],
    };
}

/** Read a campaign's stored block back into the form's shape. */
export function fromBriefDetails(details) {
    const base = emptyBriefDetails();
    if (!details) return base;
    for (const key of Object.keys(BRIEF_LIST_FIELDS)) {
        if (Array.isArray(details[key])) base[key] = [...details[key]];
    }
    if (typeof details.caption_guidance === "string")
        base.caption_guidance = details.caption_guidance;
    if (Array.isArray(details.brand_assets))
        base.brand_assets = details.brand_assets.map((a) => ({ ...a }));
    return base;
}

/**
 * The payload half.
 *
 * **Always every key, never only the filled ones.** The server reads an
 * omitted key as "leave it alone" and an empty list as "clear it", so a form
 * that sent only what was typed could add a hashtag and never remove one.
 */
export function toBriefDetails(value) {
    const v = value || emptyBriefDetails();
    return {
        brief_dos: v.brief_dos || [],
        brief_donts: v.brief_donts || [],
        mandatory_hashtags: v.mandatory_hashtags || [],
        mandatory_mentions: v.mandatory_mentions || [],
        caption_guidance: (v.caption_guidance || "").trim() || null,
        brand_assets: (v.brand_assets || []).filter((a) => (a.url || "").trim()),
    };
}

/** One list field: type a line, press Enter or Add, remove with the cross. */
function LineList({ field, rows, onChange }) {
    const [draft, setDraft] = useState("");
    const sigil = BRIEF_SIGILS[field];
    const full = rows.length >= MAX_BRIEF_LIST_ITEMS;

    const add = () => {
        // Normalised the way the server will normalise it, so the chip shows
        // the value that gets stored rather than the one that was typed.
        const line = normaliseBriefLine(field, draft);
        if (!line || rows.includes(line)) {
            setDraft("");
            return;
        }
        onChange([...rows, line]);
        setDraft("");
    };

    return (
        <div>
            <Label
                htmlFor={`brief-${field}`}
                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
            >
                {BRIEF_LIST_FIELDS[field]}
            </Label>
            <p className="mt-1 text-xs text-muted-foreground">
                {BRIEF_FIELD_HINTS[field]}
            </p>
            {rows.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-2">
                    {rows.map((line, i) => (
                        <li
                            key={line}
                            className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-card/60 py-1 pl-3 pr-1.5 text-sm"
                        >
                            {line}
                            <button
                                type="button"
                                aria-label={`Remove ${line}`}
                                data-testid={IDS.remove(field, i)}
                                onClick={() => onChange(rows.filter((_, j) => j !== i))}
                                className="rounded-full p-1.5 text-muted-foreground transition-colors duration-150 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                            >
                                <X aria-hidden="true" className="h-3 w-3" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
            <div className="mt-2 flex gap-2">
                <Input
                    id={`brief-${field}`}
                    data-testid={IDS.input(field)}
                    value={draft}
                    disabled={full}
                    maxLength={200}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                        // Enter adds the line rather than submitting the form —
                        // a brand halfway through a list of don'ts pressing
                        // Enter and posting the brief is the worst version of
                        // this control.
                        if (e.key === "Enter") {
                            e.preventDefault();
                            add();
                        }
                    }}
                    className="h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                    placeholder={full ? "That's the maximum" : sigil ? `${sigil}…` : "Add one"}
                />
                <button
                    type="button"
                    data-testid={IDS.add(field)}
                    onClick={add}
                    disabled={full || !draft.trim()}
                    className="inline-flex min-h-[2.75rem] items-center gap-1.5 rounded-full border border-white/10 px-4 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-150 hover:border-ember-500/40 hover:text-ember-500 disabled:opacity-40"
                >
                    <Plus aria-hidden="true" className="h-3.5 w-3.5" />
                    Add
                </button>
            </div>
        </div>
    );
}

export default function BriefDetailsEditor({ value, onChange }) {
    const v = value || emptyBriefDetails();
    const [open, setOpen] = useState(false);
    const set = (patch) => onChange({ ...v, ...patch });
    const assets = v.brand_assets || [];
    const filled =
        Object.keys(BRIEF_LIST_FIELDS).reduce((n, k) => n + (v[k] || []).length, 0) +
        (v.caption_guidance ? 1 : 0) +
        assets.filter((a) => (a.url || "").trim()).length;

    return (
        <div data-testid={IDS.editor}>
            <button
                type="button"
                onClick={() => setOpen((o) => !o)}
                aria-expanded={open}
                className="flex min-h-[2.75rem] w-full items-center justify-between gap-3 rounded-md border border-white/10 bg-card/60 px-4 text-left transition-colors duration-150 hover:border-ember-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
            >
                <span>
                    <span className="block text-xs uppercase tracking-[0.15em] text-muted-foreground">
                        Rules and tags (optional)
                    </span>
                    <span className="block text-sm text-muted-foreground">
                        {filled > 0
                            ? `${filled} thing${filled === 1 ? "" : "s"} a creator can tick off`
                            : "Do's, don'ts, hashtags, who to tag, caption, assets"}
                    </span>
                </span>
                <ChevronDown
                    aria-hidden="true"
                    className={`h-4 w-4 flex-none text-muted-foreground transition-transform duration-150 ${
                        open ? "rotate-180" : ""
                    }`}
                />
            </button>

            {open && (
                <div className="mt-4 space-y-5 rounded-md border border-white/10 bg-card/40 p-4 sm:p-5">
                    <p className="text-xs leading-relaxed text-muted-foreground">
                        Anything here shows on the brief as a checklist, before a
                        creator applies — and again on the screen where their draft
                        is reviewed. It is what stops a mismatch turning up after
                        the shoot.
                    </p>

                    <div className="grid gap-5 sm:grid-cols-2">
                        {Object.keys(BRIEF_LIST_FIELDS).map((field) => (
                            <LineList
                                key={field}
                                field={field}
                                rows={v[field] || []}
                                onChange={(rows) => set({ [field]: rows })}
                            />
                        ))}
                    </div>

                    <div>
                        <Label
                            htmlFor="brief-caption"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            Caption guidance
                        </Label>
                        <p className="mt-1 text-xs text-muted-foreground">
                            {BRIEF_FIELD_HINTS.caption_guidance}
                        </p>
                        <Textarea
                            id="brief-caption"
                            data-testid={IDS.captionInput}
                            rows={2}
                            maxLength={2000}
                            value={v.caption_guidance || ""}
                            onChange={(e) => set({ caption_guidance: e.target.value })}
                            className="mt-2 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                            placeholder="Mention the offer runs to the end of the month, and keep it short."
                        />
                    </div>

                    <div data-testid={IDS.assets}>
                        <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            Brand assets
                        </Label>
                        <p className="mt-1 text-xs text-muted-foreground">
                            Links to a logo, a pack shot, a font. The label is what a
                            creator sees.
                        </p>
                        <div className="mt-2 space-y-2">
                            {assets.map((asset, i) => (
                                <div key={i} className="flex flex-col gap-2 sm:flex-row">
                                    <Input
                                        data-testid={IDS.assetLabel(i)}
                                        value={asset.label || ""}
                                        maxLength={200}
                                        onChange={(e) =>
                                            set({
                                                brand_assets: assets.map((a, j) =>
                                                    j === i ? { ...a, label: e.target.value } : a,
                                                ),
                                            })
                                        }
                                        className="h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500 sm:w-1/3"
                                        placeholder="Logo pack"
                                    />
                                    <div className="flex flex-1 gap-2">
                                        <Input
                                            data-testid={IDS.assetUrl(i)}
                                            type="url"
                                            inputMode="url"
                                            value={asset.url || ""}
                                            maxLength={500}
                                            onChange={(e) =>
                                                set({
                                                    brand_assets: assets.map((a, j) =>
                                                        j === i ? { ...a, url: e.target.value } : a,
                                                    ),
                                                })
                                            }
                                            className="h-11 flex-1 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                            placeholder="https://…"
                                        />
                                        <button
                                            type="button"
                                            aria-label={`Remove asset ${i + 1}`}
                                            data-testid={IDS.assetRemove(i)}
                                            onClick={() =>
                                                set({
                                                    brand_assets: assets.filter((_, j) => j !== i),
                                                })
                                            }
                                            className="rounded-full p-3 text-muted-foreground transition-colors duration-150 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                                        >
                                            <X aria-hidden="true" className="h-4 w-4" />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                        <button
                            type="button"
                            data-testid={IDS.assetAdd}
                            disabled={assets.length >= MAX_BRIEF_ASSETS}
                            onClick={() =>
                                set({ brand_assets: [...assets, { label: "", url: "" }] })
                            }
                            className="mt-2 inline-flex min-h-[2.75rem] items-center gap-1.5 rounded-full border border-white/10 px-4 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-150 hover:border-ember-500/40 hover:text-ember-500 disabled:opacity-40"
                        >
                            <Plus aria-hidden="true" className="h-3.5 w-3.5" />
                            Add a link
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
