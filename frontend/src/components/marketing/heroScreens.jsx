// The four product screens the hero deck shows, one per step.
//
// **Drawn, never screenshotted, and pure.** Each is a function of its props:
// no state, no effects, no data fetching, no context — `test_hero_deck.py`
// greps this file for every hook and fails on one. That is what keeps a DOM
// screen as cheap to mount as a picture, and the deck mounts at most two of
// them at a time. A screenshot dates the day somebody moves a button; these
// borrow the product's language (cards, hairlines, state chips) and are
// simplified past literal, the rule the old scroll film held.
//
// **Every word arrives from `content/marketing.js`** (`HOME.deck`, and the
// deal in `HOME.card` for the Agree screen) — the rule every public page
// follows. Every name is invented, and every claim drawn is one the product
// makes today: the deal shows the creator's quote, the agreed fee and the
// terms frozen at acceptance; the payout shows the 7-day window from approval
// and the whole fee reaching the creator, not money held before the shoot,
// because nothing is.
//
// Tokens only, sentence case only — the label face and tracked capitals are
// the section rule's and nothing else's on a public page.
//
// Restored from the four-step hero (#39), which was never merged; what
// changed is where the words come from and the colour and type tokens, which
// moved under it.
import React from "react";
import { Check, Clock, FileText, IndianRupee, Users } from "lucide-react";

import { RowWriter } from "@/components/marketing/primitives";
import { Chip } from "@/components/marketing/siteMocks";

/** The card every screen sits in. */
const Frame = ({ kicker, title, children }) => (
    <div className="flex h-full flex-col rounded-lg border border-border bg-card p-5 md:p-6">
        <p className="text-meta text-muted-foreground">{kicker}</p>
        <p className="mt-1.5 font-serif text-[1.5rem] leading-tight text-heading">{title}</p>
        <div className="mt-4 flex-1">{children}</div>
    </div>
);

const Monogram = ({ text }) => (
    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-border bg-muted text-[0.6875rem] font-medium text-foreground">
        {text}
    </span>
);

const Row = ({ children }) => (
    <div className="flex items-center justify-between gap-3 border-t border-border py-2.5 first:border-t-0">
        {children}
    </div>
);

/** 01 — one brief, and the people it reached. */
export function OfferScreen({ screen }) {
    return (
        <Frame kicker={screen.kicker} title={screen.title}>
            <div className="flex flex-wrap gap-2">
                {screen.chips.map((c, i) => (
                    <Chip key={c} tone={i === screen.chips.length - 1 ? "info" : "idle"}>
                        {c}
                    </Chip>
                ))}
            </div>
            <div className="mt-5 flex items-center gap-3">
                <div className="flex -space-x-2">
                    {screen.monograms.map((m) => (
                        <Monogram key={m} text={m} />
                    ))}
                </div>
                <p className="text-meta text-foreground">
                    <Users aria-hidden className="mr-1.5 inline h-4 w-4 text-muted-foreground" />
                    {screen.applied}
                </p>
            </div>
            <div className="mt-5 flex items-center justify-between rounded-md border border-border bg-muted p-3 text-meta">
                <span className="text-muted-foreground">{screen.shortlistLabel}</span>
                <Chip tone="good">{screen.shortlist}</Chip>
            </div>
        </Frame>
    );
}

/**
 * 02 — the number, and that it stays the number. The deal is the hero's own
 * card from before the deck (`HOME.card`): the budget, the quote, and the
 * agreed fee as **the one large figure**, written in row by row as the screen
 * arrives — the `RowWriter` the card used, so the agreed figure still lands
 * rather than slides.
 */
export function AgreeScreen({ screen, card, rowTestid }) {
    const rows = card.rows.map((row, i) => ({
        key: `${row.who}-${i}`,
        final: Boolean(row.final),
        node: (
            <div
                data-testid={rowTestid ? rowTestid(i) : undefined}
                className="flex items-center justify-between gap-3 border-b border-border py-2.5"
            >
                <span className={`text-meta ${row.final ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
                    {row.who}
                </span>
                {row.final ? (
                    <span className="font-serif text-[1.75rem] leading-none text-heading">{row.amount}</span>
                ) : (
                    <span className="text-meta text-foreground">{row.amount}</span>
                )}
            </div>
        ),
    }));
    return (
        <Frame kicker={screen.kicker} title={card.title}>
            <div>
                <RowWriter rows={rows} />
                <Row>
                    <span className="text-meta text-muted-foreground">{screen.termsLabel}</span>
                    <Chip tone="good">
                        <Check aria-hidden className="mr-1 h-3 w-3" />
                        {screen.terms}
                    </Chip>
                </Row>
            </div>
        </Frame>
    );
}

/** 03 — every creator in one list, and whose move it is. */
export function DeliverScreen({ screen }) {
    return (
        <Frame kicker={screen.kicker} title={screen.title}>
            <div>
                {screen.rows.map((d) => (
                    <Row key={d.m}>
                        <span className="flex min-w-0 items-center gap-2.5">
                            <Monogram text={d.m} />
                            <span className="truncate text-meta text-foreground">{d.name}</span>
                        </span>
                        <span className="flex items-center gap-2">
                            <Chip tone={d.tone}>{d.state}</Chip>
                            <span className="hidden w-14 text-right text-meta text-muted-foreground sm:inline">{d.owes}</span>
                        </span>
                    </Row>
                ))}
            </div>
        </Frame>
    );
}

const PAID_ICONS = [null, Clock, IndianRupee];

/** 04 — approval, the payout window it starts, and the whole fee arriving. */
export function GetPaidScreen({ screen }) {
    return (
        <Frame kicker={screen.kicker} title={screen.title}>
            <div>
                {screen.rows.map((row, i) => {
                    const Icon = PAID_ICONS[i];
                    return (
                        <Row key={row.label}>
                            <span className="flex items-center gap-1.5 text-meta text-muted-foreground">
                                {Icon ? <Icon aria-hidden className="h-3.5 w-3.5" /> : null}
                                {row.label}
                            </span>
                            {row.tone ? (
                                <Chip tone={row.tone}>
                                    <Check aria-hidden className="mr-1 h-3 w-3" />
                                    {row.value}
                                </Chip>
                            ) : (
                                <span className="text-meta text-foreground">{row.value}</span>
                            )}
                        </Row>
                    );
                })}
            </div>
            <p className="mt-4 flex items-center gap-2 rounded-md border border-border bg-muted p-3 text-meta text-muted-foreground">
                <FileText aria-hidden className="h-3.5 w-3.5 shrink-0" />
                {screen.foot}
            </p>
        </Frame>
    );
}

/** Keyed by step, so the deck reads the screen off the step it is showing. */
export const SCREENS = {
    offer: OfferScreen,
    agree: AgreeScreen,
    deliver: DeliverScreen,
    paid: GetPaidScreen,
};
