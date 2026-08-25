// The brief, in pieces somebody can tick off.
//
// **The narrative box was the whole brief**, and everything a brand actually
// cared about went into it as prose: tag us, don't film the queue, use this
// hashtag, here's the logo. A creator read it once, shot the thing, and the
// mismatch surfaced at draft review — after the shoot, when the fix is a
// reshoot rather than a sentence.
//
// One component on four surfaces: the campaign page (before applying), the
// creator's own row (while they are making it), the reviewer's screen (when
// they are checking it) and the manager's brief panel (standing in the room).
// It **never asks what role is looking** — everything it draws is decided
// server-side by `_brief_details`, which omits a field nobody filled in, so an
// unstated don't is absent rather than an empty heading.
import React from "react";
import { AtSign, Check, Hash, Link2, MessageSquareQuote, X } from "lucide-react";

import { BRIEF as IDS } from "@/constants/testIds";
import {
    BRIEF_LIST_FIELDS,
    briefChecklistCount,
    hasBriefDetails,
} from "@/lib/briefDetails";

const ICONS = {
    brief_dos: Check,
    brief_donts: X,
    mandatory_hashtags: Hash,
    mandatory_mentions: AtSign,
};

// Do's read green and don'ts read red; the two tag lists are neutral, because
// a hashtag is not a warning. Ember stays out of it — on this platform ember
// is the primary action, and a checklist is something to read.
const TONES = {
    brief_dos: "text-emerald-300/90",
    brief_donts: "text-rose-300/90",
    mandatory_hashtags: "text-foreground/80",
    mandatory_mentions: "text-foreground/80",
};

function Group({ field, rows }) {
    if (!rows?.length) return null;
    const Icon = ICONS[field];
    return (
        <div data-testid={IDS.group(field)}>
            <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {Icon && <Icon aria-hidden="true" className="h-3 w-3" />}
                {BRIEF_LIST_FIELDS[field]}
            </p>
            <ul className="mt-1.5 space-y-1">
                {rows.map((line, i) => (
                    <li
                        key={`${line}-${i}`}
                        data-testid={IDS.line(field, i)}
                        className={`text-sm leading-relaxed ${TONES[field] || ""}`}
                    >
                        {line}
                    </li>
                ))}
            </ul>
        </div>
    );
}

/**
 * @param {object} details — the server's `brief_details` block.
 * @param {string} title — the heading. Defaults to the reader-neutral one.
 * @param {boolean} compact — drop the surface, for embedding inside a card
 *   that already has one.
 */
export default function BriefChecklist({
    details,
    title = "What to check",
    compact = false,
    className = "",
}) {
    // Nothing stated is nothing to draw. A heading over an empty box reads as
    // a fact about the brand rather than a question nobody answered.
    if (!hasBriefDetails(details)) return null;

    const count = briefChecklistCount(details);
    const assets = details.brand_assets || [];
    const body = (
        <>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    {title}
                </p>
                {count > 0 && (
                    <p
                        data-testid={IDS.count}
                        className="text-xs text-muted-foreground"
                    >
                        {count} {count === 1 ? "thing" : "things"} to get right
                    </p>
                )}
            </div>

            <div className="mt-3 grid gap-4 sm:grid-cols-2">
                {Object.keys(BRIEF_LIST_FIELDS).map((field) => (
                    <Group key={field} field={field} rows={details[field]} />
                ))}
            </div>

            {details.caption_guidance && (
                <div className="mt-4 border-t border-white/10 pt-3">
                    <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        <MessageSquareQuote aria-hidden="true" className="h-3 w-3" />
                        Caption
                    </p>
                    <p
                        data-testid={IDS.caption}
                        className="mt-1.5 whitespace-pre-line text-sm leading-relaxed"
                    >
                        {details.caption_guidance}
                    </p>
                </div>
            )}

            {assets.length > 0 && (
                <div
                    data-testid={IDS.assets}
                    className="mt-4 border-t border-white/10 pt-3"
                >
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Brand assets
                    </p>
                    <ul className="mt-1.5 space-y-1">
                        {assets.map((asset, i) => (
                            <li key={asset.url}>
                                {/* The label is what renders — a bare URL in a
                                    list is a link somebody has to open to find
                                    out what it is. `noopener` because these
                                    point wherever the brand typed. */}
                                <a
                                    href={asset.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    data-testid={IDS.asset(i)}
                                    className="inline-flex min-h-[2.25rem] items-center gap-1.5 text-sm text-ember-500 transition-colors duration-150 hover:text-ember-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                                >
                                    <Link2 aria-hidden="true" className="h-3.5 w-3.5" />
                                    {asset.label}
                                </a>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </>
    );

    if (compact) {
        return (
            <div data-testid={IDS.checklist} className={className}>
                {body}
            </div>
        );
    }
    return (
        <section
            data-testid={IDS.checklist}
            className={`rounded-md border border-white/10 bg-card p-5 grain-surface sm:p-6 ${className}`}
        >
            {body}
        </section>
    );
}
