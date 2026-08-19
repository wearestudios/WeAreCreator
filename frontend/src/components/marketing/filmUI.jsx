// The film's props: stylised interfaces, never screenshots.
//
// Every piece here is a simplified drawing of a real surface in the product —
// a brief card, an applicant row, a slot strip, a payout. **None of them is a
// screenshot, and none imports a real component.** Two reasons, and the second
// is the load-bearing one:
//
//   - A screenshot dates the moment the product changes. This section is the
//     centrepiece of the front page; it should not need re-shooting because
//     somebody moved a button.
//   - A real component would drag the app's data shapes, its API calls and its
//     auth context onto a page that has none of them. These are dumb divs.
//
// They are drawn in our own language — `bg-card`, `border-white/10`,
// `grain-surface`, ember for the one thing that matters in each — so they read
// as this product without pretending to be a capture of it. Simplified past
// the point of literal: a real applicant row carries eight fields, this one
// carries three, because at a glance three is what a person can read.
import React from "react";

import { CreatorMonogram } from "@/components/marketing/filmParts";
import { MARKETING as IDS } from "@/constants/testIds";

const PAYOUT_TESTID = IDS.filmPayout;

/** The shared panel treatment. Everything in the film sits on one of these. */
export const PANEL =
    "rounded-lg border border-white/10 bg-card grain-surface";

/** A tiny uppercase label — the same overline rule as the rest of the site. */
export function Tag({ children, tone = "muted" }) {
    const colour =
        tone === "ember"
            ? "border-ember-500/40 text-ember-500"
            : tone === "good"
              ? "border-emerald-400/40 text-emerald-300"
              : "border-white/15 text-muted-foreground";
    return (
        <span
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[9px] uppercase tracking-[0.18em] ${colour}`}
        >
            {children}
        </span>
    );
}

/**
 * Beat 1 — the brief, as a brand posts it.
 *
 * Three facts and a status: what, how much, when. A real campaign card has a
 * cover, a category, a visibility pill, a fill counter and an execution badge;
 * all of that is true and none of it is legible at this size.
 */
export function BriefCard() {
    return (
        <div className={`${PANEL} w-full p-4`}>
            <div className="flex items-center justify-between">
                <Tag tone="ember">Brief posted</Tag>
                <span className="text-[10px] text-muted-foreground">Bengaluru</span>
            </div>
            <p className="mt-3 font-serif text-lg leading-tight">Opening night</p>
            <div className="mt-3 flex items-center gap-2">
                <span className="rounded-md bg-white/5 px-2 py-1 text-[11px] text-muted-foreground">
                    ₹12,000 per creator
                </span>
                <span className="rounded-md bg-white/5 px-2 py-1 text-[11px] text-muted-foreground">
                    3 needed
                </span>
            </div>
        </div>
    );
}

/**
 * Beat 2 — an applicant, with the one number a brand actually shortlists on
 * and the rate they quoted.
 *
 * `accepted` is beat 3: the row keeps its place and gains an ember ring, which
 * is what acceptance looks like in the product — a state on the row you were
 * already reading, not a new screen.
 */
export function ApplicantRow({ name, followers, rate, accepted }) {
    return (
        <div
            className={`${PANEL} flex items-center gap-3 p-3 ${
                accepted ? "!border-ember-500/60" : ""
            }`}
        >
            <CreatorMonogram name={name} />
            <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{name}</p>
                <p className="text-[11px] text-muted-foreground">{followers} followers</p>
            </div>
            {accepted ? (
                <Tag tone="ember">Accepted</Tag>
            ) : (
                <span className="shrink-0 text-[11px] text-muted-foreground">{rate}</span>
            )}
        </div>
    );
}

/**
 * Beat 4 — the WhatsApp confirmation.
 *
 * Drawn as a bubble rather than a chat window: the point is that the creator
 * hears about it on the channel they actually read, not that we can draw
 * WhatsApp. **No WhatsApp logo, no WhatsApp green** — that would be borrowing
 * somebody else's mark to make a claim about ours.
 */
export function MessageBubble() {
    return (
        <div className={`${PANEL} w-full max-w-[15rem] rounded-2xl rounded-bl-sm p-3`}>
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                WhatsApp
            </p>
            <p className="mt-1.5 text-sm leading-snug">
                You&apos;re on. Rate agreed: <span className="text-ember-500">₹12,000</span>
            </p>
        </div>
    );
}

/**
 * Beat 5 — the slot, on a week strip.
 *
 * Seven cells, one filled. A real slot picker shows capacity, shoot windows
 * and restricted days; here the whole idea is "a specific day is now taken",
 * so one cell going ember says it and nothing else needs to.
 */
export function SlotStrip({ booked }) {
    const days = ["M", "T", "W", "T", "F", "S", "S"];
    return (
        <div className={`${PANEL} w-full p-3`}>
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Slot booked
            </p>
            <div className="mt-2.5 grid grid-cols-7 gap-1.5">
                {days.map((d, i) => (
                    <div
                        key={`${d}-${i}`}
                        className={`grid h-8 place-items-center rounded-md text-[11px] ${
                            i === booked
                                ? "bg-ember-500 text-black"
                                : "bg-white/5 text-muted-foreground"
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
 * Beat 6 — the draft, approved.
 *
 * A frame and a verdict. The draft gate is the step most people have never
 * seen on a platform like this, so it gets its own beat rather than being
 * folded into delivery.
 */
export function ApprovalCard() {
    return (
        <div className={`${PANEL} w-full p-3`}>
            <div className="flex items-center gap-3">
                <div className="h-12 w-16 shrink-0 rounded-md bg-gradient-to-br from-ember-700/50 to-black/60" />
                <div className="min-w-0">
                    <p className="text-sm">Draft reviewed</p>
                    <p className="text-[11px] text-muted-foreground">
                        Approved before publishing
                    </p>
                </div>
                <span className="ml-auto"><Tag tone="good">Approved</Tag></span>
            </div>
        </div>
    );
}

/**
 * Beat 7 — the payout.
 *
 * The figure is a `<span>` the film writes into directly, so it counts with
 * scroll position rather than on a timer — which is what lets it run backwards
 * when somebody scrolls back up. See `CampaignFilm`.
 */
export function PayoutCard({ amountRef }) {
    return (
        <div className={`${PANEL} w-full p-4`}>
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Paid to creator
            </p>
            <p className="mt-1.5 font-serif text-3xl leading-none tracking-tight text-ember-500">
                ₹<span ref={amountRef} data-testid={PAYOUT_TESTID}>12,000</span>
            </p>
            <p className="mt-2 text-[11px] text-muted-foreground">
                Full rate. Our fee sits on the brand.
            </p>
        </div>
    );
}
