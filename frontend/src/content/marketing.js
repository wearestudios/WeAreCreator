// Every word the public pages render, and nothing else.
//
// **Components hold layout; this file holds copy.** A page reads every
// sentence from here, so copy can be rewritten by somebody who is not going to
// open a component, and the word budgets and the claim checks have one place
// to read rather than a JSX tree to walk.
//
// Three rules for whoever edits it:
//
//   - **A value nobody knows yet is `null`, and `null` hides its element in
//     production** — the line, the card, the FAQ item or the section. Never a
//     placeholder, never "TBC": a visitor who reads "TBC" on a pricing card
//     has learned that we have not decided what to charge them. `<Known>`
//     (components/marketing/Known.jsx) is the one way a page renders a
//     maybe-null value, so the rule is a component rather than a habit.
//   - **Every claim has to be one the product keeps.** The tests read this
//     file against the server: a promise about money, verification or contact
//     details is pinned to the code that makes it true, and a claim whose
//     mechanism is not in the tree is refused rather than shipped.
//   - **Invented names only** in anything drawn as product UI. Real client
//     names appear in exactly one place — `confirmedClients`, rendered only by
//     the home page's "who built it" section.

/**
 * Facts the pages depend on that are not copy. Each is either known or
 * `null`, and a `null` hides whatever would have shown it.
 */
export const FACTS = {
    /**
     * The platform fee a brand pays on each agreed collaboration, as a
     * percentage of the creator's fee.
     *
     * **A pricing decision, not a layout value.** `null` because nobody has
     * decided the published figure, and a made-up percentage on a pricing
     * card is a promise somebody will be held to on an invoice. While it is
     * `null` the percentage is simply not printed; the card's own sentence
     * ("shown before you accept") is true without it, because the rate applied
     * to a campaign is on the brand's own campaign before anybody is taken on.
     * Never invent a figure here.
     */
    platformFeePercent: null,

    /** "What should I budget?" — ranges per creator size. A pricing decision
     * too; the whole block is hidden until it is set. */
    budgetRangesByCreatorSize: null,

    /** A count of verified creators. A number on a public page is a claim a
     * stranger can check, so it is shown only once somebody sets it. */
    verifiedCreatorCount: null,

    /** `true` once it is confirmed brands receive a GST invoice; the FAQ item
     * that says so renders only then. Never `false` — unconfirmed is `null`. */
    gstInvoiceConfirmed: null,

    /**
     * Real clients we may name, in the order they appear. These three are
     * confirmed; anybody else is unconfirmed and therefore absent. Rendered
     * only in the home page's "who built it" section and its marquee.
     */
    confirmedClients: ["The Brew Factory", "9889", "The Rameshwaram Cafe"],
};

/** True for a value a page may show. `0` and `false` are values; `null` and
 * `undefined` are not. */
export function known(value) {
    return value !== null && value !== undefined;
}

/** The percentage, formatted, or `null` while undecided. */
export function platformFeeText(percent = FACTS.platformFeePercent) {
    if (!known(percent) || Number.isNaN(Number(percent))) return null;
    return `${Number(percent)}% of the creator's fee`;
}

// ===========================================================================
// The pages
//
// What follows is every word the home page, `/for-brands` and `/for-creators`
// render. **Where the rewrite brief asked for a sentence the product does not
// keep, the sentence here is the nearest true one**, and
// `test_site_claims.py` names the untrue one so it cannot come back by
// accident: money held before the shoot (there is no escrow), a review that
// clears itself (not on this tree), a revision cap, an exportable statement
// and a receipt (none exist), offers and counter-offers (a creator quotes and
// a fee is agreed), "ID-verified" (a person reviews the profile; no ID is
// collected), "messaging runs here" (it does not), "ranked by whether they
// finish, not by follower count" (follower fit outweighs delivery in the
// ranking), a self-serve column (every brand brief is run by us), and "you
// only pay when a deal is agreed" (a campaign fee exists). Each replacement is
// listed in the PR that made it.
// ===========================================================================

/** The section rule's numbers, written once: "(01)". */
export const sectionNumber = (n) => `(${String(n).padStart(2, "0")})`;

/** The one WhatsApp door on the public pages. A link, not a name. */
const WHATSAPP_NUMBER = "+919916154048";
const WHATSAPP_TEXT = "Hi, I'd like to talk about a creator campaign.";
export const WHATSAPP_HREF = `https://wa.me/${WHATSAPP_NUMBER.replace(/\D/g, "")}?text=${encodeURIComponent(
    WHATSAPP_TEXT,
)}`;

/** The asks, spelled once each. `cta` is the id `cta_click` reports. */
export const ASK = {
    postBrief: { label: "Post a brief", to: "/signup?role=brand", cta: "post-brief" },
    talkWhatsapp: { label: "Talk to us on WhatsApp", href: WHATSAPP_HREF, cta: "talk-whatsapp" },
    haveUsRunIt: { label: "Have us run it", href: WHATSAPP_HREF, cta: "have-us-run-it" },
    joinFree: { label: "Join free", to: "/signup?role=creator", cta: "join-free" },
    howItWorks: { label: "See how it works", to: "#briefs", cta: "see-how-it-works" },
    forCreators: { label: "For creators", to: "/for-creators", cta: "creator-door" },
};

// ---------------------------------------------------------------------------
// Home — brands first, eight sections
// ---------------------------------------------------------------------------

export const HOME = {
    meta: {
        title: "WeAre Creators — influencer marketing, minus the chasing",
        description:
            "Verified creators, every fee and term agreed in writing, and the content approved before anyone is paid. Free to post a brief, and no retainer.",
    },
    hero: {
        title: "Creator campaigns, minus the chasing.",
        // Set in Fraunces true italic, revealed by WipeWord once at load.
        accent: "chasing",
        // Who it is for, said in plain words — it replaced a dotted list of
        // sectors under the buttons.
        lead: "Find verified creators for your restaurant, café or hotel. Agree the fee, approve the content, pay on approval — with every term written down.",
        // The brief asked for "you pay only when a deal is agreed". A campaign
        // fee can be charged for running a brief, so that is not true of every
        // brief; this is.
        note: "Free to post. No retainer.",
    },
    // The product card in the hero. **The history this product keeps**: the
    // brief's budget, the creator's quote, and the fee agreed — the one large
    // figure. Offers and counter-offers are an unmerged feature; when it lands
    // these rows are the only thing that changes.
    card: {
        title: "Weekend brunch launch",
        subline: "Kiran M. · 1 reel, 3 stories",
        rows: [
            { day: "Mon", who: "Your budget", amount: "₹11,000" },
            { day: "Tue", who: "Kiran quoted", amount: "₹14,000" },
            { day: "Wed", who: "Agreed", amount: "₹12,500", final: true },
        ],
        note: "Written on the deal. Both sides see the same numbers.",
    },
    swap: {
        label: "The problem",
        title: "A campaign is not a spreadsheet and sixty DMs",
        sheetHead: ["Creator", "Rate", "Status", "Paid?"],
        sheetRows: [
            ["Priya R.", "12k?", "no reply 6d", ""],
            ["Rahul S.", "8,000", "reel wrong?", "no"],
            ["Tanvi M.", "barter", "posted", "?"],
            ["", "", "", ""],
        ],
        bubbles: ["did the reel go up yet?", "what did we agree with Rahul?"],
        hereRows: [
            { name: "Priya R.", amount: "₹12,000", state: "Fee agreed", tone: "good" },
            { name: "Rahul S.", amount: "₹8,000", state: "Draft sent back", tone: "warn" },
            { name: "Tanvi M.", amount: "Barter", state: "Posted", tone: "info" },
        ],
    },
    how: {
        label: "How it works",
        title: "Four steps, and you only touch two",
        weHandle: "We handle this part",
        youTouch: "You",
        items: [
            {
                key: "offer",
                title: "Offer",
                line: "Post the brief: what you want made, what it pays and how you may use it.",
                screen: { kicker: "New brief", rows: ["Weekend brunch launch", "₹11,000 per creator", "1 reel · 3 stories"] },
                yours: true,
            },
            {
                key: "agree",
                title: "Agree",
                line: "We shortlist verified creators and agree each fee in writing. The terms freeze when a creator is taken on.",
                screen: { kicker: "Shortlist", rows: ["Kiran M. · 94% match", "Fee agreed ₹12,500", "Terms frozen"] },
                yours: false,
            },
            {
                key: "deliver",
                title: "Deliver",
                line: "We book the slot, run the shoot day and check the post carries its disclosure.",
                screen: { kicker: "Shoot day", rows: ["Sat 11:00 · slot confirmed", "Checked in", "Draft received"] },
                yours: false,
                weHandle: true,
            },
            {
                key: "paid",
                title: "Get paid",
                line: "You approve the work, and the creator is paid within 7 days of your approval.",
                screen: { kicker: "Payment", rows: ["Work approved", "₹12,500 to Kiran", "Paid in full"] },
                yours: true,
            },
        ],
    },
    // The navy band. "Guarantee" is a banned word on these pages, so the
    // label is not the brief's "The guarantees".
    promises: {
        label: "What holds",
        title: "Three things that are true in the code",
        items: [
            {
                title: "A brand never gets a creator's number",
                line: "No phone, email or address at any stage — enforced by field allow-lists, not by policy.",
            },
            {
                // The brief: "Money is held before the shoot". There is no
                // escrow; the fee being agreed and frozen first is what is true.
                title: "The fee is agreed before anyone shoots",
                line: "Every fee and term is written down and frozen when a creator is taken on, before a slot is booked.",
            },
            {
                // The brief: "Reviews cannot stall forever". The review clock
                // is not on this tree; this is what replaces it.
                title: "Every creator is checked before they apply",
                line: "A person reviews each profile. A pitch from somebody not yet checked is held, never shown to a brand.",
            },
        ],
    },
    // No client names on the homepage: the marquee and the three cards were
    // removed. `FACTS.confirmedClients` stays for use elsewhere later.
    clients: {
        label: "Who built it",
        title: "Built by people who run these campaigns",
        // The one FillText sentence on the site. It names the city as a
        // record of where the work was done, not as the platform's reach.
        fill: "WeAre Studios has run influencer campaigns for Bengaluru restaurants, cafés and bars for years. This is the tool we wanted and couldn't buy.",
    },
    creatorDoor: {
        label: "For creators",
        title: "Paid briefs. Your number stays yours.",
        // The brief: "The money is held before you travel". No escrow; the
        // fee being in writing first is what is true.
        line: "Any follower count, as long as you're verified. The fee is agreed in writing before you travel, you keep all of it, and a brand never sees your contact details.",
    },
    close: {
        label: "Get started",
        title: "Post your first brief",
        // The brief: "You only pay when a collaboration is agreed". A campaign
        // fee can apply, so that is not true of every brief.
        line: "Free to post, and no retainer.",
    },
};

// ---------------------------------------------------------------------------
// For brands
// ---------------------------------------------------------------------------

export const BRANDS = {
    meta: {
        title: "For brands — WeAre Creators",
        description:
            "Post a brief in ten minutes. We shortlist verified creators against it, agree every fee in writing and run the shoot. Free to post, no retainer.",
    },
    hero: {
        label: "For brands",
        title: "Ten minutes to a brief",
        lead: "Say what you want made and what it pays. We shortlist verified creators, agree each fee in writing and run the shoot day.",
    },
    shortlist: {
        label: "The shortlist",
        title: "A shortlist, scored against your brief",
        // The brief: "every one ID-verified, ranked by whether they finish —
        // not by follower count". Creators are checked by a person (no ID is
        // collected), and follower fit is weighted above delivery.
        lead: "Creators of any size, every one checked by a person, ranked against your brief with the reasons shown — not by follower count alone.",
        countLine: (n) => `${n.toLocaleString("en-IN")} verified creators to shortlist from.`,
        card: {
            kicker: "Shortlist · Weekend brunch launch",
            matchLabel: "match",
            quoteLabel: "quote",
            rows: [
                { initials: "KM", name: "Kiran M.", reasons: ["Food & drink", "Your city", "Posts reels"], quote: "₹14,000", match: "94%" },
                { initials: "PR", name: "Priya R.", reasons: ["Food & drink", "Finished 6 of 6"], quote: "₹12,000", match: "88%" },
                { initials: "TM", name: "Tanvi M.", reasons: ["Lifestyle", "Your city"], quote: "₹9,500", match: "81%" },
            ],
        },
        // The brief: "Messaging runs here". There is no brand–creator
        // messaging; on a brief we run, we are the ones talking to creators.
        closing: "You never see a phone number or an email. We handle the conversations.",
    },
    pricing: {
        label: "What it costs",
        title: "Three lines, and none of them a retainer",
        cards: [
            { key: "free", title: "Free", line: "to post a brief." },
            {
                key: "fee",
                title: "Our fee",
                line: "Paid by you, on each collaboration you agree. Creators keep 100% of their fee — ours is separate and shown before you accept.",
            },
            { key: "retainer", title: "No retainer", line: "No monthly fee, and nothing to sign up to before a brief." },
        ],
        budgetTitle: "What should I budget?",
    },
    report: {
        label: "What you get at the end",
        title: "One report, not nine screenshots",
        lead: "Reach, views and engagement for every post — read from Instagram's official API where the creator connected it — with the cost per thousand reached.",
        card: {
            kicker: "Example report",
            title: "Weekend brunch launch · 6 creators",
            // Only measures the backend records: reach, impressions, views,
            // likes, comments, saves, engagement rate over reach, and cost
            // per thousand reach on paid work.
            totals: [
                { label: "Reach", value: "48,200" },
                { label: "Views", value: "61,900" },
                { label: "Engagements", value: "3,140" },
                { label: "Engagement rate", value: "6.5%" },
                { label: "Cost per 1,000 reached", value: "₹1,556" },
            ],
            note: "Engagements are likes, comments and saves; the rate is over reach, not followers.",
        },
    },
    promises: {
        label: "What holds",
        title: "What is true for you",
        items: [
            {
                title: "Creators are checked before they apply",
                line: "A person reviews each profile. You only ever see creators we have checked.",
            },
            {
                // The brief: "no other brand sees your rates". A public brief
                // shows its budget; the fee agreed with a creator is the part
                // that is never published.
                title: "The fee you agree is never published",
                line: "What a creator is paid on your campaign appears on no public page.",
            },
            {
                // The brief: "money leaves only when you approve". A kill fee
                // on a cancellation is owed without an approval; the refund
                // rule is what is true and checkable.
                title: "The campaign fee comes back if we can't fill it",
                line: "Unless you turned down everyone we shortlisted.",
            },
        ],
    },
    compare: {
        label: "Two ways to run it",
        title: "Two ways to run it",
        columns: ["", "Over DMs and a spreadsheet", "With WeAre Creators"],
        rows: [
            ["Writing the brief", "A message, rewritten for every creator", "One brief, ten minutes, terms included"],
            ["Shortlisting", "Scrolling profiles and guessing at the numbers", "Verified creators, scored against the brief"],
            ["Shoot day", "Confirming times by message the night before", "Booked slots, and we run the day"],
            ["Launch night or influencer event", "More than a chat thread can hold", "We run it, guest list to the night itself"],
            // Kept as written. On a brief we run, the final approval is the
            // brand's step; drafts on the way there may be reviewed by us.
            ["Approving the work", "You, chasing a link to check", "You — this one stays yours"],
            ["Cost", "Whatever was agreed in a chat", "Creators' fees as agreed, and our fee shown before you accept"],
        ],
    },
    faq: {
        label: "Questions",
        title: "What brands ask first",
        items: [
            {
                q: "What if nobody applies?",
                a: "We invite creators who fit the brief. If we still can't fill it, the campaign fee is refunded, unless you turned down everyone we shortlisted.",
            },
            {
                q: "What if the content is bad?",
                a: "Don't approve work that misses the brief. Send it back with a note and the creator resubmits. A campaign can also be set to show you a draft first.",
            },
            {
                q: "Can I use creators I already work with?",
                a: "Yes. Send us their handles and we'll invite them to your brief. They join through the same checks as everyone else.",
            },
            {
                q: "Who owns the content?",
                a: "Your brief says what you may do with it: organic posting, paid usage for a set period, or a full buyout — frozen into the terms when a creator is taken on.",
            },
            {
                q: "Is this only for Bengaluru?",
                a: "No. A brief can name any city on our list, and creators are verified wherever they are. If we can't fill it, the campaign fee rule above applies.",
            },
            {
                q: "Do I have to use escrow?",
                a: "No, and there isn't any. Agreed fees are invoiced to you, and we pay the creator after you approve the work.",
            },
            {
                // Rendered only when FACTS.gstInvoiceConfirmed is true.
                q: "Do I get a GST invoice?",
                a: "Yes. Every invoice we raise for a campaign is a GST invoice.",
                showIf: "gstInvoiceConfirmed",
            },
            {
                q: "Can you run a launch night?",
                a: "Yes. That's the managed side — the venue plan, the creator list, the run of show and the night itself.",
            },
        ],
    },
    close: {
        label: "Get started",
        title: "Write the brief. We'll bring the people.",
        line: "Free to post, and no retainer.",
    },
};

// ---------------------------------------------------------------------------
// For creators
// ---------------------------------------------------------------------------

export const CREATORS = {
    meta: {
        title: "For creators — WeAre Creators",
        description:
            "Paid briefs from checked brands. A brand never gets your number, the fee is agreed in writing before you travel, and you keep 100% of it.",
    },
    hero: {
        label: "For creators",
        title: "Your number stays yours",
        // The brief: "The money is held before you travel". There is no
        // escrow; the fee being agreed in writing first is what is true.
        lead: "A brand never gets your phone, your email or your address — not when they shortlist you, not after the shoot, not ever. The fee is agreed in writing before you travel, and you keep 100% of it. Brands pay our fee, not you.",
        // The brief's second chip was "ID-verified creators only". A person
        // reviews every profile; no ID document is collected.
        chips: ["Any follower count", "Verified creators only", "Paid within 7 days of approval", "Sign in with WhatsApp"],
    },
    briefs: {
        label: "Briefs that fit",
        title: "See the fee before you apply",
        lead: "Every brief comes from a brand we have checked, and shows what it pays, what it asks for and how the work may be used.",
        card: {
            kicker: "Brief · Food & drink",
            title: "Weekend brunch launch",
            fee: "₹12,000",
            feeLabel: "per creator",
            // The brief's revision-cap chip: there is no cap. Every send-back
            // carries a note instead, and the disclosure is stated up front.
            chips: ["Matches your niche", "In your city", "Usage: organic repost only", "Disclosure: #ad"],
            // "Counter the fee": a creator quotes a rate with the pitch; there
            // is no counter-offer on this tree.
            actions: ["Apply", "Quote your rate"],
        },
    },
    money: {
        label: "The money",
        // The brief: "You never travel on a promise", over three escrow
        // states. There is no escrow; these are the states the record moves
        // through.
        title: "The fee is in writing before you travel",
        states: [
            { key: "agreed", title: "Agreed", line: "The fee and the terms are written down and frozen before you book a slot." },
            { key: "delivered", title: "Delivered", line: "You post what the brief asked for, and the work is approved." },
            // "…with a receipt" is gone: creators are not sent one.
            { key: "paid", title: "Paid", line: "Within 7 days of approval, to your UPI or bank." },
        ],
        amount: 12500,
        amountSuffix: "paid · all of it",
    },
    protections: {
        label: "What protects you",
        title: "Three things on your side",
        items: [
            // The brief: "a cap on revisions (1 of 2 used)". There is no cap.
            { title: "A note with every send-back", line: "A brand can't send work back without saying what to change." },
            // The brief: "a clock on the review". Not on this tree.
            { title: "A date on your payment", line: "Once the work is approved, your card shows the date you'll be paid by." },
            { title: "The terms, frozen", line: "The fee, the usage and the deliverables are frozen the moment you're taken on." },
        ],
    },
    payouts: {
        label: "Getting paid properly",
        title: "Paid the way you'd want to be",
        items: [
            // "…automatically" is gone: a payout is made by a person.
            { title: "UPI or bank", line: "Payouts arrive within 7 days of approval." },
            { title: "PAN on file", line: "Needed before your first payout, and seen only by our team." },
            // The brief: "an exportable statement". None exists.
            { title: "Every payment, listed", line: "Paid and pending, side by side on your dashboard." },
            { title: "No password", line: "Sign in with a code sent to your WhatsApp." },
        ],
    },
    record: {
        label: "Finishing counts",
        title: "Finishing counts",
        // The brief: "reliability is what moves you up a brief's list, not
        // your follower count". Follower fit is weighted above delivery, so
        // this says what is true: it counts, alongside the rest.
        lead: "Whether you finish is part of what moves you up a brief's list — not only your follower count.",
        card: {
            kicker: "Your record",
            rows: [
                { label: "Campaigns finished", value: "19 of 20" },
                { label: "Slots kept", value: "20 of 20" },
                { label: "Drafts on time", value: "18 of 19" },
            ],
            band: "Consistently delivers",
        },
    },
    close: {
        label: "Join",
        title: "Paid briefs, in your city",
        line: "Free to join. Brands pay our fee — you keep 100% of yours.",
    },
};
