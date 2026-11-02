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

/**
 * The AI features the public site may talk about, one switch each.
 *
 * - A switch is flipped to `true` **only in the PR that ships that feature to
 *   brands or creators** — the route, its module and the screen together. A
 *   line on a public page about something a visitor cannot use yet is a claim
 *   the product does not keep.
 * - **Every AI line on the public site renders only while its switch is
 *   `true`**, through `aiLive(key)`. No page reads this object directly.
 * - **If `AI_ENABLED` is ever set to `false` in production, flip these off
 *   too.** The server hides the features when its switch is off; this file is
 *   built into the bundle and cannot read the server's environment, so the
 *   public site would keep advertising a feature that has gone dark.
 *
 * `test_ai_switches.py` fails CI when a switch is `true` and the backend
 * capability it names (the route and its module) does not exist.
 */
export const AI_FEATURES = {
    campaignSummary: true,
    nicheMatching: true,
    briefWriter: true,
};

/** Whether the site may mention this AI feature. Unknown keys are off. */
export function aiLive(key) {
    return AI_FEATURES[key] === true;
}

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
// accident: money held before the shoot (there is no escrow), an exportable
// statement and a receipt (neither exists), offers and counter-offers (a creator quotes and
// a fee is agreed), "ID-verified" (a person reviews the profile; no ID is
// collected), "messaging runs here" (it does not), "ranked by whether they
// finish, not by follower count" (follower fit outweighs delivery in the
// ranking), a self-serve column (every brand brief is run by us), and "you
// only pay when a deal is agreed" (a campaign fee exists). Each replacement is
// listed in the PR that made it.
//
// **Two came back when the product caught up, worded to its rules.** The
// review clock (`draft_review_days`, `_approve_draft_by_window`) applies where
// a brief reviews drafts: 3 days unless the brief sets 1–14, and an admin may
// extend or pause it — so nothing here says "never" or "forever". The cap on
// revisions (`revisions_included`, `_revision_allowance`) is frozen at
// acceptance and shown as "1 of 2 used" on both sides. `test_site_promises.py`
// fails either claim if the field behind it goes.
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
        // Each step shows both sides of the deal at once, as the old
        // /how-it-works page did: `line` is the brand's, `creatorLine` what
        // happens on the creator's side.
        creatorSide: "The creator",
        items: [
            {
                key: "offer",
                title: "Offer",
                line: "Post the brief: what you want made, what it pays and how you may use it.",
                creatorLine: "Creators see what it pays, what it asks for and how it may be used before they apply.",
                // Each rendered only while `aiLive(key)`.
                ai: [
                    { key: "briefWriter", line: "Describe it in two lines — we draft the brief." },
                    { key: "nicheMatching", line: "Matched creators apply — matched on what they post, not by follower count alone." },
                ],
                screen: { kicker: "New brief", rows: ["Weekend brunch launch", "₹11,000 per creator", "1 reel · 3 stories"] },
                yours: true,
            },
            {
                key: "agree",
                title: "Agree",
                line: "We shortlist verified creators and agree each fee in writing. The terms freeze when a creator is taken on.",
                creatorLine: "Their fee is agreed in writing before they travel, and their number stays theirs.",
                screen: { kicker: "Shortlist", rows: ["Kiran M. · 94% match", "Fee agreed ₹12,500", "Terms frozen"] },
                yours: false,
            },
            {
                key: "deliver",
                title: "Deliver",
                line: "We book the slot, run the shoot day and check the post carries its disclosure.",
                creatorLine: "They turn up at the slot, shoot, and post with the disclosure the brief asks for.",
                screen: { kicker: "Shoot day", rows: ["Sat 11:00 · slot confirmed", "Checked in", "Draft received"] },
                yours: false,
                weHandle: true,
            },
            {
                key: "paid",
                title: "Get paid",
                line: "You approve the work, and the creator is paid within 7 days of your approval.",
                creatorLine: "Paid to their UPI or bank within 7 days of your approval — all of it.",
                // Rendered only while `aiLive(key)`.
                ai: [
                    { key: "campaignSummary", line: "An AI summary then reads your results in plain English, using only your real numbers." },
                ],
                screen: { kicker: "Payment", rows: ["Work approved", "₹12,500 to Kiran", "Paid in full"] },
                yours: true,
            },
        ],
    },
    // The scroll film beside the four steps: seven beats, grouped under the
    // four steps' own names. **Captions are argument and count against the
    // budget; everything under `screen` is drawn product UI and does not.**
    // The story is one the product keeps: a person checks creators, the fee
    // is agreed in writing, the brand approves the work (a draft gate is
    // optional per brief, so the film does not claim one), and the creator
    // is paid all of the fee within 7 days of approval.
    film: {
        beats: [
            { key: "brief", step: "offer", caption: "A brief goes up" },
            { key: "applied", step: "offer", caption: "Verified creators apply" },
            { key: "accepted", step: "agree", caption: "One is taken on" },
            { key: "message", step: "agree", caption: "The fee is agreed in writing" },
            { key: "slot", step: "deliver", caption: "A slot is booked" },
            { key: "approved", step: "deliver", caption: "You approve the work" },
            { key: "paid", step: "paid", caption: "Paid within 7 days, all of it" },
        ],
        screen: {
            brief: { tag: "Brief posted", meta: "Food & drink", title: "Weekend brunch launch", chips: ["₹11,000 per creator", "3 needed"] },
            applicants: [
                { name: "Kiran M.", followers: "24K followers", rate: "₹14,000" },
                { name: "Priya R.", followers: "11K followers", rate: "₹12,000" },
                { name: "Tanvi M.", followers: "38K followers", rate: "₹9,500" },
            ],
            accepted: "Taken on",
            message: { channel: "WhatsApp", text: "You're on. Fee agreed:", amount: "₹12,500" },
            slot: { label: "Slot booked · Sat 11:00", days: ["M", "T", "W", "T", "F", "S", "S"], booked: 5 },
            approval: { title: "Work reviewed", line: "Approved by the brand", tag: "Approved" },
            payout: { label: "Paid to the creator", amount: 12500, line: "All of it. Our fee is charged to the brand." },
        },
    },
    // The hero card: one screen per step, cycling. Drawn product UI, so it
    // sits under `screen` and does not count against the budget. The deal is
    // `card` above, unchanged, as the Agree screen.
    deck: {
        label: "The four steps",
        screen: {
            offer: {
                kicker: "New brief",
                title: "Weekend brunch launch",
                chips: ["1 reel", "3 stories", "₹11,000 per creator"],
                monograms: ["KM", "PR", "TM", "AS"],
                applied: "18 applied",
                shortlistLabel: "Shortlist",
                shortlist: "Checked by a person",
            },
            agree: { kicker: "Deal · Kiran M.", termsLabel: "Terms", terms: "Frozen at acceptance" },
            deliver: {
                kicker: "Shoot · Weekend brunch launch",
                title: "3 creators, one list",
                rows: [
                    { m: "KM", name: "Kiran M.", tone: "good", state: "Approved", owes: "Done" },
                    { m: "PR", name: "Priya R.", tone: "warn", state: "Draft sent back", owes: "Creator" },
                    { m: "TM", name: "Tanvi M.", tone: "info", state: "Shoot Saturday", owes: "Creator" },
                ],
            },
            paid: {
                kicker: "Payout · Kiran M.",
                title: "₹12,500 on its way",
                rows: [
                    { label: "Work", value: "Approved", tone: "good" },
                    { label: "Paid within", value: "7 days of approval" },
                    { label: "To the creator", value: "₹12,500, all of it" },
                ],
                foot: "Our fee is invoiced to you on its own line.",
            },
        },
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
                // The review clock (`_approve_draft_by_window`). Scoped to a
                // brief that reviews drafts, because that is the only review
                // with a clock — live content has none.
                title: "A draft review has a deadline",
                line: "Where a brief reviews drafts, a draft nobody answers is approved when its window ends — three days unless the brief sets one to fourteen.",
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
        // In place of `lead` while `aiLive("briefWriter")`. The brief said
        // "you shortlist"; we do — the brand chooses from our shortlist.
        aiLead: "Describe your campaign in two lines and we draft the full brief for you to edit. Matched creators apply, we shortlist, and every term you agree is recorded.",
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
            // Drawn product UI, invented creators. `why` is shown only while
            // `aiLive("nicheMatching")` — it is the line the product prints.
            whyLabel: "Why this creator",
            rows: [
                { initials: "KM", name: "Kiran M.", reasons: ["Food & drink", "Your city", "Posts reels"], why: "Casual dining · Kannada · English · shoots in Indiranagar", quote: "₹14,000", match: "94%" },
                { initials: "PR", name: "Priya R.", reasons: ["Food & drink", "Finished 6 of 6"], why: "Cafés & coffee · English · shoots in Koramangala", quote: "₹12,000", match: "88%" },
                { initials: "TM", name: "Tanvi M.", reasons: ["Lifestyle", "Your city"], why: "Bakery & desserts · Hindi · shoots in HSR Layout", quote: "₹9,500", match: "81%" },
            ],
        },
        // Rendered only while `aiLive("nicheMatching")`.
        aiLine: "Creators are matched on what they actually post — cuisine, language and neighbourhood — and you see why each one fits.",
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
        // `FeeFlow`: where the money goes, drawn. **No escrow** — there is
        // none, and the FAQ says so — and **no fee figure while
        // `FACTS.platformFeePercent` is null**: the middle node then says the
        // fee is shown before you accept, which is true without a number.
        flow: {
            label: "Where the money goes",
            steps: [
                { key: "brand", who: "You", line: "Pay the creator's agreed fee, with our fee on top." },
                { key: "weare", who: "WeAre Creators", line: "Invoices you, and pays the creator once you approve the work." },
                { key: "creator", who: "The creator", line: "Receives the whole agreed fee, within 7 days of your approval." },
            ],
            share: 100,
            shareLabel: "of the agreed fee reaches the creator",
        },
    },
    report: {
        label: "What you get at the end",
        title: "One report, not nine screenshots",
        lead: "Views, accounts reached, likes, shares, saves and comments for every post — read from Instagram's official API where the creator connected it — with every post on one page.",
        // Rendered only while `aiLive("campaignSummary")`.
        aiLine: "An AI summary reads your results in plain English — using only your real numbers, never invented ones.",
        card: {
            kicker: "Example report",
            // **A mirror of the real dashboard and nothing more.** Every
            // figure is one `GET /brand/campaigns/{id}/analytics` returns in
            // its `dashboard` block, under the label the dashboard prints, and
            // a test holds the two lists together. Creator names and figures
            // are invented.
            title: "Weekend brunch launch",
            hero: { label: "Total views", value: "4,27,300", sub: "across 11 posts from 9 creators" },
            totals: [
                { label: "Creators", value: "9", sub: "all posted" },
                { label: "Accounts reached", value: "2,81,900", sub: "added across posts" },
                { label: "Likes", value: "19,600" },
                { label: "Shares", value: "2,450" },
                { label: "Saves", value: "2,790" },
                { label: "Comments", value: "1,035" },
            ],
            postsLabel: "Every post",
            posts: [
                { name: "Ananya", format: "reel", views: "98,000", shares: "880" },
                { name: "Ishaan", format: "reel", views: "76,000", shares: "410" },
                { name: "Meghna", format: "reel", views: "64,000", shares: "300" },
                { name: "Rohan", format: "reel", views: "52,000", shares: "260" },
                { name: "Zoya", format: "carousel", count: 5, views: "21,000", shares: "90" },
                { name: "Dev", format: "carousel", count: 4, views: "18,000", shares: "60" },
            ],
            more: "+5 more",
            note: "Accounts reached are added across posts: one person who saw two posts counts twice.",
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
                // Shown only while `aiLive("briefWriter")`.
                aiKey: "briefWriter",
                track: "faq-ai-brief-writer",
                q: "Do I have to write the brief myself?",
                a: "No. Describe the campaign in a line or two, in English, Kannada or Hinglish, and we draft it. You edit and post; nothing goes out without you.",
            },
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
                // Every brand-posted brief is run by us, so drafts are ours to
                // review; the window is `draft_review_days` on the brief.
                q: "What if I don't review in time?",
                a: "Our team reviews drafts within the window on your brief — three days unless you set one to fourteen. A draft still unanswered when it ends is approved.",
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
        // Rendered only while `aiLive("nicheMatching")`.
        aiLine: "Briefs are matched to what you post, so you see the ones that suit you first.",
        card: {
            kicker: "Brief · Food & drink",
            title: "Weekend brunch launch",
            fee: "₹12,000",
            feeLabel: "per creator",
            // The revisions chip is `revisions_included` on the brief — two
            // unless the brand sets 0–5 — which a creator reads before
            // applying.
            chips: ["Matches your niche", "In your city", "2 rounds of changes", "Usage: organic repost only", "Disclosure: #ad"],
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
            // The second half is the review clock, scoped as it works: only a
            // brief that reviews drafts has one.
            { key: "delivered", title: "Delivered", line: "You post what was asked for and it's approved — where drafts are reviewed, when the review window runs out at the latest." },
            // "…with a receipt" is gone: creators are not sent one.
            { key: "paid", title: "Paid", line: "Within 7 days of approval, to your UPI or bank." },
        ],
        amount: 12500,
        amountSuffix: "paid · all of it",
        // `PayoutClock`: the 7 days, drawn from approval to payment. The
        // number is `CREATOR_PAYOUT_DAYS` (lib/payoutWindow.js), drift-tested
        // against the server; these are the words around it.
        clock: {
            start: "Work approved",
            end: "Paid by",
            unit: "days",
            ours: "From approval to your UPI or bank, at most",
        },
    },
    protections: {
        label: "What protects you",
        title: "Three things on your side",
        items: [
            // `revisions_included`, frozen at acceptance; the card prints
            // exactly "1 of 2 used". Past it, an extra round is a request the
            // creator accepts or declines.
            { title: "A cap on revisions", line: "The brief sets the rounds of changes and your card counts them — 1 of 2 used. Any extra round is yours to agree to." },
            // `_approve_draft_by_window`, on a brief that reviews drafts.
            { title: "A clock on the review", line: "Where a brief reviews drafts, yours is approved if nobody answers within its review window." },
            { title: "The terms, frozen", line: "The fee, usage, deliverables and rounds of changes are frozen the moment you're taken on." },
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
