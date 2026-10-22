// The four product screens the hero deck shows, one per step.
//
// **Drawn, never screenshotted, and pure.** Each is a function of nothing: no
// state, no effects, no data fetching, no context — `test_hero_deck.py` greps
// this file for every hook and fails on one. That is what keeps a DOM screen
// as cheap to mount as the picture it replaced, and the deck mounts at most
// two of them at a time. A screenshot dates the day somebody moves a button;
// these borrow the product's language (cards, hairlines, state chips) and are
// simplified past literal, the rule `filmUI.jsx` already holds.
//
// **Every name is invented.** A real company's name in product UI on a public
// page reads as an endorsement from somebody who is not a customer. The brand
// and the creators here are made up and meant to feel like the market.
//
// **Every claim drawn is one the product makes today.** The deal screen shows
// the creator's quote, the agreed fee and the terms frozen at acceptance —
// not an offer-and-counter history, which is not on main. The payout screen
// shows the window the brief promised and a payment reference, not money held
// before the shoot, because nothing is.
//
// Tokens only. No palette class and no colour literal, so the screens follow
// whichever theme is live.
import React from "react";
import { Check, Clock, FileText, IndianRupee, Users } from "lucide-react";

/** The card every screen sits in. */
const Frame = ({ kicker, title, children }) => (
    <div className="flex h-full flex-col rounded-lg border border-tint/10 bg-card p-5 md:p-6">
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{kicker}</p>
        <p className="mt-2 font-serif text-xl leading-tight text-foreground md:text-2xl">{title}</p>
        <div className="mt-5 flex-1">{children}</div>
    </div>
);

const Monogram = ({ text }) => (
    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-tint/10 bg-muted font-serif text-xs text-foreground">
        {text}
    </span>
);

const TONE = {
    pending: "border-state-pending/30 bg-state-pending/10 text-state-pending",
    good: "border-state-approved/30 bg-state-approved/10 text-state-approved",
    active: "border-state-progress/30 bg-state-progress/10 text-state-progress",
    idle: "border-tint/15 bg-tint/5 text-muted-foreground",
};

export const Chip = ({ tone = "idle", children }) => (
    <span
        className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] ${TONE[tone]}`}
    >
        {children}
    </span>
);

const Row = ({ children }) => (
    <div className="flex items-center justify-between gap-3 border-t border-tint/10 py-2.5 first:border-t-0">
        {children}
    </div>
);

/** 01 — one brief, and the people it reached. */
export function OfferScreen() {
    return (
        <Frame kicker="Brief · Oddbloom Bakehouse" title="Weekend brunch launch">
            <div className="flex flex-wrap gap-2">
                <Chip>2 reels</Chip>
                <Chip>3 stories</Chip>
                <Chip tone="active">₹12,000 per creator</Chip>
            </div>
            <div className="mt-6 flex items-center gap-3">
                <div className="flex -space-x-2">
                    {["AK", "NR", "KS", "TM"].map((m) => (
                        <Monogram key={m} text={m} />
                    ))}
                </div>
                <p className="text-sm text-foreground">
                    <Users className="mr-1.5 inline h-4 w-4 text-muted-foreground" />
                    24 applied
                </p>
            </div>
            <div className="mt-6 rounded-md border border-tint/10 bg-muted p-3 text-sm">
                <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Shortlist</span>
                    <Chip tone="pending">6 picked · 2d</Chip>
                </div>
            </div>
        </Frame>
    );
}

/** 02 — the number, and that it stays the number. */
export function AgreeScreen() {
    return (
        <Frame kicker="Deal · Nisha R." title="₹15,000, agreed">
            <div>
                <Row>
                    <span className="text-sm text-muted-foreground">Creator quoted</span>
                    <span className="text-sm text-foreground">₹18,000</span>
                </Row>
                <Row>
                    <span className="text-sm text-muted-foreground">Fee agreed</span>
                    <span className="text-sm text-foreground">₹15,000</span>
                </Row>
                <Row>
                    <span className="text-sm text-muted-foreground">Terms</span>
                    <Chip tone="idle">Frozen at acceptance</Chip>
                </Row>
                <Row>
                    <span className="text-sm text-muted-foreground">Creator</span>
                    <Chip tone="good">
                        <Check className="mr-1 h-3 w-3" />
                        Accepted
                    </Chip>
                </Row>
            </div>
        </Frame>
    );
}

const DRAFTS = [
    { m: "AK", name: "Aarav K.", tone: "pending", state: "Draft in", owes: "You" },
    { m: "NR", name: "Nisha R.", tone: "good", state: "Approved", owes: "—" },
    { m: "KS", name: "Kabir S.", tone: "active", state: "Changes asked", owes: "Creator" },
    { m: "TM", name: "Tanvi M.", tone: "idle", state: "Shoot Friday", owes: "Creator" },
];

/** 03 — every draft in one list, and whose move it is. */
export function DeliverScreen() {
    return (
        <Frame kicker="Drafts · Weekend brunch launch" title="4 creators, one list">
            <div>
                {DRAFTS.map((d) => (
                    <Row key={d.m}>
                        <span className="flex min-w-0 items-center gap-2.5">
                            <Monogram text={d.m} />
                            <span className="truncate text-sm text-foreground">{d.name}</span>
                        </span>
                        <span className="flex items-center gap-2">
                            <Chip tone={d.tone}>{d.state}</Chip>
                            <span className="hidden w-14 text-right text-[11px] text-muted-foreground sm:inline">
                                {d.owes}
                            </span>
                        </span>
                    </Row>
                ))}
            </div>
        </Frame>
    );
}

/** 04 — approval, the payout date it starts, and the record both sides keep. */
export function GetPaidScreen() {
    return (
        <Frame kicker="Payout · Nisha R." title="₹15,000 on its way">
            <div>
                <Row>
                    <span className="text-sm text-muted-foreground">Delivery</span>
                    <Chip tone="good">
                        <Check className="mr-1 h-3 w-3" />
                        Approved
                    </Chip>
                </Row>
                <Row>
                    <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                        <Clock className="h-3.5 w-3.5" />
                        Paid within
                    </span>
                    <span className="text-sm text-foreground">7 days of approval</span>
                </Row>
                <Row>
                    <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                        <IndianRupee className="h-3.5 w-3.5" />
                        To the creator
                    </span>
                    <span className="text-sm text-foreground">₹15,000, in full</span>
                </Row>
            </div>
            <div className="mt-4 flex items-center gap-2 rounded-md border border-tint/10 bg-muted p-3 text-[11px] text-muted-foreground">
                <FileText className="h-3.5 w-3.5 shrink-0" />
                Ref UTR 4471 0093 · Invoice INV-0213 to the brand
            </div>
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
