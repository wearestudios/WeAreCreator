// The film's props: stylised interfaces, never screenshots.
//
// Every piece here is a simplified drawing of a real surface in the product —
// a brief card, an applicant row, a slot strip, a payout. **None of them is a
// screenshot, and none imports a real component.** Two reasons, and the second
// is the load-bearing one:
//
//   - A screenshot dates the moment the product changes. This section is the
//     homepage's explanation of the whole job; it should not need re-shooting
//     because somebody moved a button.
//   - A real component would drag the app's data shapes, its API calls and its
//     auth context onto a page that has none of them. These are dumb divs.
//
// **Every word and figure arrives as a prop from `HOME.film.screen` in
// `content/marketing.js`**, like every word on the public pages. They used to
// be written in here — "Opening night", three names, a city, ₹12,000 — so the
// film told a different campaign from the four steps beside it. It now tells
// the same one: the weekend brunch launch, Kiran M., ₹12,500, paid in full.
//
// Drawn in tokens — `bg-card`, `border-border`, `bg-muted` — so they follow
// the light ground they now sit on, and in sentence case: tracked capitals
// belong to the section rule alone on a public page. The one thing that
// matters in each is navy or a state colour; **the brand red is never a
// status and never a word below 24px**, so the accepted ring is the red as a
// mark and its label is `accent-ink`.
import React from "react";

import { CreatorMonogram } from "@/components/marketing/filmParts";
import { MARKETING as IDS } from "@/constants/testIds";

const PAYOUT_TESTID = IDS.filmPayout;

/** The shared panel treatment. Everything in the film sits on one of these. */
export const PANEL = "rounded-lg border border-border bg-card";

/** A small chip — sentence case, like the rest of the public pages. */
export function Tag({ children, tone = "muted" }) {
    const colour =
        tone === "ember"
            ? "border-accent/40 text-accent-ink"
            : tone === "good"
              ? "border-state-approved/30 bg-state-approved-wash text-state-approved"
              : "border-border text-muted-foreground";
    return (
        <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[0.75rem] ${colour}`}>
            {children}
        </span>
    );
}

/** Beat 1 — the brief, as a brand posts it: what, how much, how many. */
export function BriefCard({ brief }) {
    return (
        <div className={`${PANEL} w-full p-4`}>
            <div className="flex items-center justify-between">
                <Tag tone="ember">{brief.tag}</Tag>
                <span className="text-[0.75rem] text-muted-foreground">{brief.meta}</span>
            </div>
            <p className="mt-3 font-serif text-[1.125rem] leading-tight text-heading">{brief.title}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
                {brief.chips.map((c) => (
                    <span key={c} className="rounded-md bg-muted px-2 py-1 text-[0.75rem] text-muted-foreground">
                        {c}
                    </span>
                ))}
            </div>
        </div>
    );
}

/**
 * Beat 2 — an applicant, with their audience and the rate they quoted.
 *
 * `accepted` is beat 3: the row keeps its place and gains a red ring, which is
 * what being taken on looks like in the product — a state on the row you were
 * already reading, not a new screen.
 */
export function ApplicantRow({ name, followers, rate, accepted, acceptedLabel }) {
    return (
        <div className={`${PANEL} flex items-center gap-3 p-3 ${accepted ? "!border-accent/60" : ""}`}>
            <CreatorMonogram name={name} />
            <div className="min-w-0 flex-1">
                <p className="truncate text-meta text-foreground">{name}</p>
                <p className="text-[0.75rem] text-muted-foreground">{followers}</p>
            </div>
            {accepted ? (
                <Tag tone="ember">{acceptedLabel}</Tag>
            ) : (
                <span className="shrink-0 text-[0.75rem] text-muted-foreground">{rate}</span>
            )}
        </div>
    );
}

/**
 * Beat 4 — the fee, in writing, on the channel the creator reads.
 *
 * Drawn as a bubble rather than a chat window. **No WhatsApp logo, no
 * WhatsApp green** — that would be borrowing somebody else's mark to make a
 * claim about ours.
 */
export function MessageBubble({ message }) {
    return (
        <div className={`${PANEL} w-full max-w-[16rem] rounded-2xl rounded-bl-sm p-3`}>
            <p className="text-[0.75rem] text-muted-foreground">{message.channel}</p>
            <p className="mt-1.5 text-meta leading-snug text-foreground">
                {message.text} <span className="font-semibold text-heading">{message.amount}</span>
            </p>
        </div>
    );
}

/**
 * Beat 5 — the slot, on a week strip. Seven cells, one filled: "a specific
 * day is now taken" is the whole idea, so one cell going navy says it.
 */
export function SlotStrip({ slot }) {
    return (
        <div className={`${PANEL} w-full p-3`}>
            <p className="text-[0.75rem] text-muted-foreground">{slot.label}</p>
            <div className="mt-2.5 grid grid-cols-7 gap-1.5">
                {slot.days.map((d, i) => (
                    <div
                        key={`${d}-${i}`}
                        className={`grid h-8 place-items-center rounded-md text-[0.75rem] ${
                            i === slot.booked ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                        }`}
                    >
                        {d}
                    </div>
                ))}
            </div>
        </div>
    );
}

/**
 * Beat 6 — the work, approved by the brand.
 *
 * It said "Draft reviewed · approved before publishing", which is true only
 * where a brief turns the draft gate on — optional per campaign, and off by
 * default on the briefs a brand posts. Approving the delivered work is the
 * step every brief has.
 */
export function ApprovalCard({ approval }) {
    return (
        <div className={`${PANEL} w-full p-3`}>
            <div className="flex items-center gap-3">
                <div aria-hidden className="h-12 w-16 shrink-0 rounded-md border border-border bg-muted" />
                <div className="min-w-0">
                    <p className="text-meta text-foreground">{approval.title}</p>
                    <p className="text-[0.75rem] text-muted-foreground">{approval.line}</p>
                </div>
                <span className="ml-auto">
                    <Tag tone="good">{approval.tag}</Tag>
                </span>
            </div>
        </div>
    );
}

/**
 * Beat 7 — the payout.
 *
 * The figure is a `<span>` the film writes into directly, so it counts with
 * scroll position rather than on a timer — which is what lets it run
 * backwards when somebody scrolls back up. See `CampaignFilm`.
 */
export function PayoutCard({ payout, amountRef }) {
    return (
        <div className={`${PANEL} w-full p-4`}>
            <p className="text-[0.75rem] text-muted-foreground">{payout.label}</p>
            <p className="mt-1.5 font-serif text-[1.875rem] leading-none text-heading">
                ₹
                <span ref={amountRef} data-testid={PAYOUT_TESTID}>
                    {payout.amount.toLocaleString("en-IN")}
                </span>
            </p>
            <p className="mt-2 text-[0.75rem] text-muted-foreground">{payout.line}</p>
        </div>
    );
}
