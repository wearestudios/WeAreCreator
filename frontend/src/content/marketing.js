// Every word the public pages render, and nothing else.
//
// **Components hold layout; this file holds copy.** A page that needs a
// sentence reads it from here, so the copy can be rewritten — by somebody who
// is not going to open a component — without a layout change riding along,
// and so the word budget and the claim checks in `test_marketing_pages.py`
// have one place to read rather than a JSX tree to walk.
//
// Two rules for whoever edits it:
//
//   - **Every claim has to be one the product keeps.** The tests read this
//     file against the server: a promise about money, verification or
//     contact details is pinned to the code that makes it true, and a claim
//     whose mechanism is not in the tree is refused rather than shipped.
//   - **Invented names only** in anything drawn as product UI. A real
//     company's name inside a mock screen on a public page reads as an
//     endorsement it never gave.

/**
 * The platform fee a brand pays on each agreed collaboration, as a percentage
 * of the creator's fee.
 *
 * **This is a pricing decision, not a layout value.** It is `null` because
 * nobody has decided the published figure, and a made-up percentage on a
 * pricing card is a promise somebody will be held to on an invoice. While it
 * is `null` the card says the fee is shown before the brand accepts — which
 * is true today: the rate applied to a campaign is on the brand's own
 * campaign before anybody is taken on. Set it here, once, when the figure is
 * agreed; every surface that quotes it reads this constant.
 */
export const PLATFORM_FEE_PERCENT = null;

/** What the pricing card says about the fee, decided in one place. */
export const FEE_PENDING_LABEL = "Shown before you accept";

export function platformFeeLabel(percent = PLATFORM_FEE_PERCENT) {
    if (percent === null || percent === undefined || Number.isNaN(Number(percent))) {
        return FEE_PENDING_LABEL;
    }
    return `${Number(percent)}% of the creator's fee`;
}

// ---------------------------------------------------------------------------
// Shared across the three pages
// ---------------------------------------------------------------------------

/** The two asks, each spelled once. A page asks in the same words top and
 * bottom by spreading the same object, so "the same words" is structural. */
export const ASK_BRAND = { label: "Post a brief", to: "/signup?role=brand" };
export const ASK_TALK = { label: "Talk to us instead", to: "/contact" };
export const ASK_CREATOR = { label: "Join as a creator", to: "/signup?role=creator" };

/** The four steps of the job. One list, read by the hero's rail and by the
 * home page's expanded steps, so the two cannot name a step differently. */
export const STEP_LABELS = ["Offer", "Agree", "Deliver", "Get paid"];

// ---------------------------------------------------------------------------
// The hero deck's four screens
//
// Drawn as product UI, so every name and figure here is invented. What each
// screen *claims* is real, and pinned by `test_hero_deck.py`:
//
//   - Agree shows a creator's quote and the fee agreed, then both sides
//     accepting with the terms frozen. It does **not** show offers and
//     counters back and forth: negotiation history is not in this tree
//     (PR #37), so a screen drawing it would be a promise.
//   - Get paid shows the payout window the brief stated, after approval —
//     not money held before the shoot, because nothing is.
// ---------------------------------------------------------------------------

export const HERO_SCREENS = {
    offer: {
        kicker: "Brief · Oddbloom Bakehouse",
        title: "Weekend brunch launch",
        chips: ["2 reels", "3 stories"],
        fee: "₹12,000 per creator",
        monograms: ["PS", "RM", "TK", "AV"],
        applied: "24 applied",
        shortlistLabel: "Shortlist",
        shortlistValue: "6 picked · in review 2d",
    },
    agree: {
        kicker: "The deal · Priya S.",
        title: "The fee, on the record",
        rows: [
            { label: "Budget on the brief", value: "₹11,000" },
            { label: "Priya quoted", value: "₹14,000" },
            { label: "Fee agreed", value: "₹12,500" },
        ],
        finalLabel: "Both accepted · terms frozen",
        finalValue: "₹12,500",
    },
    deliver: {
        kicker: "Drafts · Weekend brunch launch",
        title: "4 creators, one list",
        nextLabel: "Next move",
        rows: [
            { initials: "PS", name: "Priya S.", state: "Draft in", tone: "pending", next: "Us" },
            { initials: "RM", name: "Rahul M.", state: "Approved", tone: "good", next: "—" },
            { initials: "TK", name: "Tanvi K.", state: "Changes asked", tone: "active", next: "Creator" },
            { initials: "AV", name: "Arjun V.", state: "Shoot Friday", tone: "idle", next: "Creator" },
        ],
    },
    paid: {
        kicker: "Payout · Priya S.",
        title: "Approved, then paid",
        rows: [
            { label: "Work approved", value: "Tue 14 Oct" },
            { label: "Paid within 7 days of approval", value: "Mon 20 Oct" },
            { label: "Paid in full", value: "₹12,500" },
        ],
        reference: "Ref UTR 4471 0093 · Invoice INV-0213",
    },
};

// ---------------------------------------------------------------------------
// Home — brands first
// ---------------------------------------------------------------------------

export const HOME = {
    meta: {
        title: "WeAre Creators — influencer marketing, run in one place",
        description:
            "Post one brief, agree the fee in writing, review the work and pay on approval. A creator marketplace for India, with verified creators.",
    },
    hero: {
        // The eyebrow is `HERO_EYEBROW` in `lib/siteNav.js`, shared with the
        // brief feed and the sign-in screen, so it is not a second string here.
        // Two lines, each its own entrance. The heading's accessible name is
        // the two joined, which is what a search engine reads.
        titleLines: ["One place for", "the whole job"],
        steps: [
            { key: "offer", label: STEP_LABELS[0], line: "Send one brief, not sixty DMs." },
            { key: "agree", label: STEP_LABELS[1], line: "Agree the number, and it stays agreed." },
            { key: "deliver", label: STEP_LABELS[2], line: "Get the draft, in one place." },
            { key: "paid", label: STEP_LABELS[3], line: "Approve it, and the money moves." },
        ],
        railLabel: "The four steps",
    },
    swap: {
        title: "A campaign is not a spreadsheet and sixty DMs",
        todayLabel: "How it runs today",
        hereLabel: "How it runs here",
        sheetHead: ["Creator", "Rate", "Status", "Paid?"],
        sheetRows: [
            ["Priya S.", "12k?", "no reply 6d", "—"],
            ["Rahul M.", "15,000", "reel wrong?", "?"],
            ["Tanvi K.", "barter", "shot, no link", "no"],
            ["Arjun V.", "18k / 15k?", "draft???", ""],
            ["", "", "", ""],
        ],
        bubbles: ["Hi! Did the brief come through?", "Sorry, what was the amount again?"],
        hereRows: [
            { name: "Priya S.", amount: "₹12,000", tone: "pending", state: "In review · 2d" },
            { name: "Rahul M.", amount: "₹15,000", tone: "active", state: "Your call" },
            { name: "Tanvi K.", amount: "₹9,500", tone: "good", state: "Paid" },
        ],
    },
    band: {
        title: "The brief, the fee and the work, on one record",
    },
    steps: {
        eyebrow: "How a campaign runs",
        title: "Four steps, and you can see every one",
        items: [
            { title: "Offer", line: "Post one brief. Creators who fit it apply, and we shortlist." },
            { title: "Agree", line: "The fee is agreed in writing and frozen into the terms before anyone shoots." },
            {
                title: "Deliver",
                line: "Creators shoot, submit and resubmit until the work matches the brief.",
                tag: "We handle this part",
            },
            { title: "Get paid", line: "You approve the work, and the creator is paid within the window the brief stated." },
        ],
    },
    // **Called "the guarantees" in the brief and nowhere on the page**:
    // "guarantee" is in `_FORBIDDEN_MARKETING_PHRASES`, because it promises an
    // outcome nobody controls. These are mechanisms, and each names its own.
    promises: {
        eyebrow: "What is always true",
        title: "Three things the product enforces",
        items: [
            {
                title: "A brand never gets a creator's number",
                line: "Every screen a brand sees is built from a list that has no phone, email or address in it.",
            },
            {
                title: "The fee is agreed before anyone shoots",
                line: "A shoot can't be booked until the fee is recorded, and the terms are frozen when both sides accept.",
            },
            {
                title: "Every creator is checked before they apply",
                line: "A person reviews each profile. Pitches from creators we haven't checked are held, not sent.",
            },
        ],
    },
    clients: {
        eyebrow: "Who built it",
        title: "Built by people who run these campaigns",
    },
    creatorDoor: {
        title: "Paid briefs. Your number stays yours.",
        cta: { label: "For creators", to: "/creators" },
    },
    close: {
        title: "Post your first brief",
        line: "Free to post, and no retainer.",
    },
};

/**
 * The three clients in "Who built it".
 *
 * **Real names belong here and nowhere else on the site** — this is the one
 * section that says who we have worked for, so a real name is the claim
 * rather than an endorsement nobody gave. They are not filled in because they
 * are not ours to guess: the section renders nothing until all three have a
 * `name`, the "absent rather than short" rule the brand wall holds. Each
 * card's photograph is the matching slot in `photoSlots.js`. No WeAre Studios
 * team member is named anywhere, here included.
 */
export const CLIENTS = [
    { name: null, line: null, slot: "client-1" },
    { name: null, line: null, slot: "client-2" },
    { name: null, line: null, slot: "client-3" },
];

// ---------------------------------------------------------------------------
// For brands — the reader is afraid of wasting money and looking foolish
// ---------------------------------------------------------------------------

export const BRANDS = {
    meta: {
        title: "For brands — WeAre Creators",
        description:
            "Write one brief and we bring a shortlist of verified creators, scored against it. Free to post, no retainer, and no markup on creator fees.",
    },
    hero: {
        eyebrow: "For brands",
        title: "Ten minutes to a brief",
        line: "Write it once. We shortlist verified creators against it and run the campaign with WeAre Studios behind it.",
    },
    shortlist: {
        eyebrow: "01 · The shortlist",
        title: "Scored against your brief, with the reasons",
        line: "Audience numbers are read from Instagram where a creator has connected it, beside what each creator quoted.",
        card: {
            kicker: "Shortlist · Weekend brunch launch",
            rows: [
                {
                    initials: "PS",
                    name: "Priya S.",
                    match: "94%",
                    quote: "₹14,000",
                    reasons: ["Food and café niche", "Posts reels", "Your city"],
                },
                {
                    initials: "RM",
                    name: "Rahul M.",
                    match: "88%",
                    quote: "₹11,500",
                    reasons: ["Finished 6 briefs here", "Your city"],
                },
                {
                    initials: "TK",
                    name: "Tanvi K.",
                    match: "81%",
                    quote: "₹9,000",
                    reasons: ["Food niche", "Audience in your tier"],
                },
            ],
            matchLabel: "match",
            quoteLabel: "quoted",
        },
        closing: "You never see a phone number or an email. We handle the conversations.",
    },
    pricing: {
        eyebrow: "02 · What it costs",
        title: "Three lines, and none of them small print",
        cards: [
            { title: "Free to post", line: "Writing and posting a brief costs nothing." },
            {
                title: "A fee on each agreed collaboration",
                // The figure comes from `PLATFORM_FEE_PERCENT` at render.
                feeFromConstant: true,
                line: "Charged to you on top of the creator's rate, never taken out of theirs: no markup on creator fees.",
            },
            {
                title: "No retainer",
                line: "The campaign fee is refunded if we cannot fill it, unless you turned down everyone we shortlisted.",
            },
        ],
    },
    band: {
        title: "Your brief, our people, your sign-off",
    },
    promises: {
        eyebrow: "What is always true",
        title: "Three things you can hold us to",
        items: [
            {
                title: "Creators are verified before they apply",
                line: "A person reviews every profile. Nobody unchecked reaches your shortlist.",
            },
            {
                title: "What you agree stays off public pages",
                line: "An agreed fee is shown to you, the creator and us. Never on a public page or to another brand.",
            },
            {
                title: "The campaign fee comes back if we can't fill it",
                line: "Unless you turned down everyone we shortlisted. The rule is written into your terms.",
            },
        ],
    },
    // **Not "run it yourself vs have us run it."** The product is
    // managed-only: a brand cannot invite creators or reach a raw application,
    // so a self-serve column would describe something that does not exist —
    // and the phrase is banned on this page for that reason. The two ways a
    // campaign actually gets run are over DMs and a spreadsheet, or here.
    compare: {
        eyebrow: "05 · Two ways to run it",
        title: "Over DMs, or here",
        columns: ["", "Over DMs and a spreadsheet", "With WeAre Creators"],
        rows: [
            ["Brief", "Retyped into every chat", "Written once, read by everyone"],
            ["Shortlisting", "Whoever replied first", "Scored against your brief, with the reasons"],
            ["Shoot day", "Times agreed in a thread", "Booked slots, checked in at the door"],
            // The cell is the brief's, word for word, in both columns: the
            // sign-off is the brand's either way, and saying so is what makes
            // the rest of the table credible. The row is the *work*, not the
            // draft — on a campaign we run, drafts are reviewed by our
            // manager, and the brand approves what is delivered.
            ["Approving the work", "You — this one stays yours", "You — this one stays yours"],
            ["Cost", "Your time, and nothing in writing", "Free to post; a fee per agreed collaboration"],
        ],
    },
    faq: {
        eyebrow: "06 · Questions",
        title: "What brands ask first",
        // **Exactly these six questions.** The answers are the product's
        // own rules, each checkable.
        items: [
            {
                q: "What if nobody applies?",
                a: "We invite creators who fit the brief. If we still can't fill it, the campaign fee is refunded, unless you turned down everyone we shortlisted.",
            },
            {
                q: "What if the content is bad?",
                a: "Don't approve work that misses the brief. Send it back with a note and the creator resubmits. A brief can also ask to see a draft before anything is posted.",
            },
            {
                q: "Can I use creators I already work with?",
                a: "Yes. Send us their handles and we'll invite them to your brief. They join through the same checks as everyone else.",
            },
            {
                q: "Who owns the content?",
                a: "Your brief says what you may do with it: organic posting only, paid usage for a set period, or a full buyout. It's frozen into the terms when you accept a creator.",
            },
            {
                q: "Is this only for Bengaluru?",
                a: "No. A brief can name any city on our list, and creators are verified wherever they are. If we can't fill it, the campaign fee rule above applies.",
            },
            {
                q: "Do I have to use escrow?",
                a: "No, and there isn't any. Agreed fees are invoiced to you, and we pay the creator after you approve the work.",
            },
        ],
    },
    close: {
        title: "Write the brief. We'll bring the people.",
        line: "At the end of the campaign, you get a report on how the posts performed.",
    },
};

// ---------------------------------------------------------------------------
// For creators — the reader is afraid of being used
// ---------------------------------------------------------------------------

export const CREATORS = {
    meta: {
        title: "For creators — WeAre Creators",
        description:
            "Real paid briefs from checked brands. The fee is agreed before you shoot, you keep all of it, and a brand never gets your number.",
    },
    hero: {
        eyebrow: "For creators",
        title: "Your number stays yours",
        line: "Real paid briefs from brands we have checked. Brands reach you through the brief, never through your phone. Free to join.",
    },
    brief: {
        eyebrow: "01 · Briefs that fit",
        title: "The fee is on the brief before you apply",
        line: "So is what the brand may do with the work, and when you'll be paid.",
        card: {
            kicker: "Brief · Oddbloom Bakehouse",
            title: "Weekend brunch launch",
            fee: "₹12,000",
            feeLabel: "per creator",
            chips: ["2 reels · 3 stories", "Organic posting only", "Paid within 7 days of approval"],
            actions: ["Apply", "Quote your rate"],
        },
    },
    // **Not "the brand funds it, the money is held".** There is no escrow in
    // this product: the fee is agreed and frozen, the brand approves, and we
    // pay inside the window the brief stated. The three states drawn are the
    // ones the record actually moves through.
    money: {
        eyebrow: "02 · The money",
        title: "Where your fee is, at every step",
        amount: 12500,
        states: [
            { title: "Agreed", line: "The fee is recorded and frozen into the terms before you shoot." },
            { title: "Delivered", line: "You submit the work and the brand approves it. Payment follows approval." },
            { title: "Paid", line: "Paid in full inside the window the brief stated, and dated on your dashboard." },
        ],
        closing: "Our fee is charged to the brand on top, never taken out of yours. You keep all of it.",
    },
    protections: {
        eyebrow: "03 · What protects you",
        title: "The record is on your side",
        cards: [
            {
                title: "A note with every send-back",
                line: "Work can't be sent back without a reason you can act on.",
                detail: "Revision 1 · note attached",
            },
            {
                title: "A date on your payment",
                line: "Once your work is approved, the day you'll be paid by is on your card.",
                detail: "Due Mon 20 Oct",
            },
            {
                title: "The terms, frozen",
                line: "The fee, the deliverables and the usage are fixed the moment you're accepted.",
                detail: "Frozen at acceptance",
            },
        ],
    },
    band: {
        title: "Real paid briefs, from brands we have checked",
    },
    payout: {
        eyebrow: "05 · Getting paid properly",
        title: "UPI or a bank account, your choice",
        items: [
            { title: "UPI or bank", line: "Paid to whichever you set up. Changing it is checked again first." },
            { title: "PAN on file", line: "Asked for before your first payout, never to sign up." },
            { title: "Every payment, listed", line: "Paid and pending in one list on your dashboard." },
        ],
    },
    // **Not "this, not follower count, moves you up".** Audience size against
    // the brief is part of how a shortlist is scored, so claiming it isn't
    // would be false. What is true: finishing is scored too, and it is the
    // part entirely in a creator's hands.
    record: {
        eyebrow: "06 · Finishing counts",
        title: "Finishing what you take on is scored",
        line: "A brief's shortlist weighs whether you finished past briefs here, not only your follower count. It is the part you control.",
        card: {
            kicker: "Your record",
            rows: [
                { label: "Briefs finished", value: "19 / 20" },
                { label: "Slots kept", value: "20 / 20" },
                { label: "Drafts on time", value: "18 / 19" },
            ],
            band: "Consistently delivers",
        },
    },
    close: {
        title: "Paid briefs, in your city",
        line: "Free to join. The fee is agreed before you shoot.",
    },
};
