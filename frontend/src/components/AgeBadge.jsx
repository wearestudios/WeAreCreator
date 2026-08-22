// How long this has been sitting, and whether that is too long.
//
// **One component, and it draws what the server sent.** The ageing block —
// the label, whether it is overdue, by how much, which of four tones — is
// computed once on the server against the SLA targets an admin can edit, and
// this renders it. Recomputing any of it here would put a second copy of the
// policy in the browser, and the copy that drifts is always the one being
// looked at.
//
// It renders **nothing** when there is no ageing block. That is not a
// degraded state: half the places this appears have no clock by design — a
// closed collaboration, a verified creator, a slot waiting on a date in the
// future rather than on a person — and a badge saying "waiting 0 minutes"
// about one of them would be an alarm about a field nobody filled in.
import React from "react";
import { AlertTriangle, Clock } from "lucide-react";

/**
 * The visual weight, rising with the tone.
 *
 * **Four steps, not two.** "Fine" and "on fire" leaves nothing to say about
 * the record that is *about* to become a problem — which is the only one
 * somebody can still do something about. `due` is the half-way mark and is
 * deliberately quiet: it is information, not an alarm.
 *
 * Ember is absent on purpose. It is this product's primary-action colour, and
 * a status wearing it makes every row look like a button.
 */
const TONES = {
    calm: {
        wrap: "border-white/10 text-muted-foreground",
        Icon: Clock,
    },
    due: {
        wrap: "border-white/15 text-foreground/80",
        Icon: Clock,
    },
    overdue: {
        wrap: "border-amber-400/30 bg-amber-400/10 text-amber-200",
        Icon: AlertTriangle,
    },
    critical: {
        wrap: "border-rose-400/40 bg-rose-400/10 text-rose-200",
        Icon: AlertTriangle,
    },
};

/**
 * @param {object} props
 * @param {object|null} props.ageing  The server's block. Nothing renders without it.
 * @param {boolean} [props.iconOnly]  Drop the words — for a table cell that has
 *   room for a glyph and not a sentence. The title still carries the full text,
 *   and the words are what a screen reader gets either way.
 */
export default function AgeBadge({ ageing, iconOnly = false, className = "", testid }) {
    if (!ageing || !ageing.label) return null;

    const tone = TONES[ageing.tone] || TONES.calm;
    const { Icon } = tone;

    // What the target actually is, for somebody wondering why this is amber.
    // Only when there is one — most rows have an age and no target.
    const target = ageing.sla_hours
        ? `Target ${ageing.sla_hours < 48 ? `${ageing.sla_hours}h` : `${Math.round(ageing.sla_hours / 24)}d`}`
        : null;

    return (
        <span
            data-testid={testid}
            data-tone={ageing.tone}
            title={[ageing.label, target].filter(Boolean).join(" · ")}
            className={
                "inline-flex max-w-full items-center gap-1.5 rounded border px-1.5 py-0.5 " +
                `text-xs leading-tight ${tone.wrap} ${className}`
            }
        >
            <Icon aria-hidden="true" className="h-3 w-3 shrink-0" />
            {/* The words are always in the DOM, even when they are visually
                dropped for width. An icon-only badge that hid its meaning from
                a screen reader would say nothing at all to somebody using one,
                and "overdue" is not decoration. */}
            <span className={iconOnly ? "sr-only" : "truncate"}>{ageing.label}</span>
        </span>
    );
}
