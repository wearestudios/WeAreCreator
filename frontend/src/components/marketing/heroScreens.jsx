// The four product screens the hero deck shows, one per step.
//
// **Drawn, never screenshotted, and pure.** Each is a function of its props
// and nothing else: no state, no effects, no data fetching, no context —
// `test_hero_deck.py` greps this file for every hook and fails on one. That is
// what keeps a DOM screen as cheap to mount as a picture, and the deck mounts
// at most two at a time. The words and figures come from `HERO_SCREENS` in
// `content/marketing.js`; this file holds layout only.
//
// **Every name is invented, and every claim drawn is one the product makes
// today.** See the note above `HERO_SCREENS` for the two that were not.
//
// The Agree screen is the hero's counter history, and the one place on the
// page where rows write themselves in. The deck decides *whether* it writes —
// the first time it is shown, never again — and passes that in, so the screen
// stays a function of its props. The writing itself is `RowWriter`, the
// marketing primitive, driven rather than watching.
//
// Tokens only. No palette class and no colour literal, so the screens follow
// whichever surface they sit on.
import React from "react";
import { Check, Clock, FileText, IndianRupee, Users } from "lucide-react";

import { RowWriter } from "@/components/marketing/primitives";
import { HERO_SCREENS } from "@/content/marketing";

/** The card every screen sits in. */
const Frame = ({ kicker, title, children }) => (
    <div className="flex h-full flex-col rounded-lg border border-border bg-card p-5 md:p-7">
        <p className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground">{kicker}</p>
        <p className="mt-2 font-serif text-xl leading-tight text-foreground md:text-2xl">{title}</p>
        <div className="mt-5 flex-1">{children}</div>
    </div>
);

const Monogram = ({ text }) => (
    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-border bg-muted text-eyebrow font-medium text-foreground">
        {text}
    </span>
);

const TONE = {
    pending: "border-state-pending/30 bg-state-pending-wash text-state-pending",
    good: "border-state-approved/30 bg-state-approved-wash text-state-approved",
    active: "border-state-progress/30 bg-state-progress-wash text-state-progress",
    idle: "border-border bg-muted text-muted-foreground",
};

/** A state chip. State tokens only — the brand red is never a status. */
export const Chip = ({ tone = "idle", children }) => (
    <span
        className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-meta ${TONE[tone]}`}
    >
        {children}
    </span>
);

const Row = ({ children }) => (
    <div className="flex items-center justify-between gap-3 border-t border-border py-2.5 first:border-t-0">
        {children}
    </div>
);

/** 01 — one brief, and the people it reached. */
export function OfferScreen({ data = HERO_SCREENS.offer }) {
    return (
        <Frame kicker={data.kicker} title={data.title}>
            {/* Two lines reserved on a phone: the chips wrap differently in the
                fallback face and in Inter Tight, and without the floor the
                row below jumped when the font landed — measured at 0.0124
                CLS at 390px, the whole of the page's shift. */}
            <div className="flex min-h-[3.5rem] flex-wrap content-start gap-2 sm:min-h-0">
                {data.chips.map((c) => (
                    <Chip key={c}>{c}</Chip>
                ))}
                <Chip tone="active">{data.fee}</Chip>
            </div>
            <div className="mt-6 flex items-center gap-3">
                <div className="flex -space-x-2">
                    {data.monograms.map((m) => (
                        <Monogram key={m} text={m} />
                    ))}
                </div>
                <p className="text-meta text-foreground">
                    <Users className="mr-1.5 inline h-4 w-4 text-muted-foreground" aria-hidden />
                    {data.applied}
                </p>
            </div>
            <div className="mt-5 flex items-center justify-between gap-3 rounded-md border border-border bg-muted px-4 py-3">
                <span className="text-meta text-muted-foreground">{data.shortlistLabel}</span>
                <span className="text-meta text-foreground">{data.shortlistValue}</span>
            </div>
        </Frame>
    );
}

/**
 * 02 — the fee, on the record. The hero's counter history.
 *
 * @param {{ write?: boolean }} props  true the first time the screen is shown,
 *   when the rows write themselves; false every time after.
 */
export function AgreeScreen({ data = HERO_SCREENS.agree, write = false }) {
    const rows = [
        ...data.rows.map((r) => ({
            key: r.label,
            node: (
                <Row>
                    <span className="text-meta text-muted-foreground">{r.label}</span>
                    <span className="text-body text-foreground">{r.value}</span>
                </Row>
            ),
        })),
        {
            key: "final",
            final: true,
            node: (
                <div className="mt-3 flex items-end justify-between gap-3 border-t border-border pt-4">
                    <span className="inline-flex items-center gap-1.5 text-meta text-foreground">
                        <Check className="h-4 w-4 text-state-approved" aria-hidden />
                        {data.finalLabel}
                    </span>
                    <span className="mkt-h3 text-foreground">{data.finalValue}</span>
                </div>
            ),
        },
    ];
    return (
        <Frame kicker={data.kicker} title={data.title}>
            <RowWriter rows={rows} written={write} animate={write} />
        </Frame>
    );
}

/** 03 — every draft in one list, and whose move it is. */
export function DeliverScreen({ data = HERO_SCREENS.deliver }) {
    return (
        <Frame kicker={data.kicker} title={data.title}>
            <div className="flex justify-end pb-1 text-eyebrow uppercase tracking-eyebrow text-muted-foreground">
                {data.nextLabel}
            </div>
            {data.rows.map((r) => (
                <Row key={r.name}>
                    <span className="flex min-w-0 items-center gap-3">
                        <Monogram text={r.initials} />
                        <span className="truncate text-meta text-foreground">{r.name}</span>
                    </span>
                    <span className="flex items-center gap-3">
                        <Chip tone={r.tone}>{r.state}</Chip>
                        <span className="w-14 text-right text-meta text-muted-foreground">{r.next}</span>
                    </span>
                </Row>
            ))}
        </Frame>
    );
}

/** 04 — approved, then paid inside the window the brief stated. */
export function GetPaidScreen({ data = HERO_SCREENS.paid }) {
    const icons = [FileText, Clock, IndianRupee];
    return (
        <Frame kicker={data.kicker} title={data.title}>
            {data.rows.map((r, i) => {
                const Icon = icons[i] || FileText;
                return (
                    <Row key={r.label}>
                        <span className="inline-flex items-center gap-2 text-meta text-muted-foreground">
                            <Icon className="h-4 w-4" aria-hidden />
                            {r.label}
                        </span>
                        <span className="text-meta text-foreground">{r.value}</span>
                    </Row>
                );
            })}
            <p className="mt-4 font-mono text-meta text-muted-foreground">{data.reference}</p>
        </Frame>
    );
}

export const SCREENS = {
    offer: OfferScreen,
    agree: AgreeScreen,
    deliver: DeliverScreen,
    paid: GetPaidScreen,
};
