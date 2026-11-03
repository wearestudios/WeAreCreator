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
    joinFree: { label: "Join free", to: "/signup?role=creator", cta: "join-free" },
    howItWorks: { label: "See how it works", to: "#briefs", cta: "see-how-it-works" },
};

// ---------------------------------------------------------------------------
// Home — two sections: the hero slider, then how it works
// ---------------------------------------------------------------------------

export const HOME = {
    meta: {
        title: "WeAre Creators — influencer marketing, minus the chasing",
        description:
            "Verified creators, every fee and term agreed in writing, and the content approved before anyone is paid. Free to post a brief, and no retainer.",
        // In place of the two above while at least two AI switches are on —
        // "AI-powered" is a claim about the product, and one feature is not
        // a product that is powered by it.
        aiTitle: "WeAre Creators — AI-powered influencer marketing, minus the chasing",
        aiDescription:
            "AI-powered matching with verified creators, every fee and term agreed in writing, and the content approved before anyone is paid. Free to post a brief, and no retainer.",
    },
    hero: {
        title: "Creator campaigns, minus the chasing.",
        // Set in Fraunces true italic, revealed by WipeWord once at load.
        accent: "chasing",
        // Who it is for, said in plain words — it replaced a dotted list of
        // sectors under the buttons.
        lead: "Find verified creators for your restaurant, café or hotel. Agree the fee, approve the content, pay on approval — with every term written down.",
        // In place of `lead` while at least two AI switches are on. The AI is
        // the matching; the fee, the approval and the payment stay people's.
        aiLead: "AI-powered matching with verified creators for your restaurant, café or hotel. Agree the fee, approve the content, pay on approval — with every term written down.",
        // The brief asked for "you pay only when a deal is agreed". A campaign
        // fee can be charged for running a brief, so that is not true of every
        // brief; this is.
        note: "Free to post. No retainer.",
    },
    // Slide A's card, the deal. **The history this product keeps**: the
    // brief's budget, the creator's quote, and the fee agreed — the one large
    // figure. Offers and counter-offers are an unmerged feature; when it lands
    // these rows are the only thing that changes.
    card: {
        tag: "Example",
        title: "Weekend brunch launch",
        subline: "Kiran M. · 1 reel, 3 stories",
        termsLabel: "Terms",
        terms: "Frozen at acceptance",
        rows: [
            { day: "Mon", who: "Your budget", amount: "₹11,000" },
            { day: "Tue", who: "Kiran quoted", amount: "₹14,000" },
            { day: "Wed", who: "Agreed", amount: "₹12,500", final: true },
        ],
        note: "Written on the deal. Both sides see the same numbers.",
    },
    // Slide B of the hero, "The problem": the campaign as it runs today (a
    // spreadsheet and two DMs) against the same campaign here. Everything
    // under the sheet, the bubbles, the rows and `card` is drawn product UI.
    swap: {
        title: "Not a spreadsheet and sixty DMs.",
        // Set in Fraunces italic.
        accent: "DMs",
        line: "Every creator, fee and draft in one place, with both sides looking at the same numbers.",
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
        card: { tag: "Example", here: "On WeAre Creators", sheet: "campaign-final-v3.xlsx" },
    },
    // The hero slider: one slide per entry, in order, each with its tab.
    // **The AI slide is not listed here**: it is `ai` below, appended while
    // any AI switch is on and absent — not hidden — otherwise. The badge is
    // the two-switch claim, the rule `meta.aiTitle` follows.
    slides: {
        label: "At a glance",
        carousel: "WeAre Creators, slide by slide",
        tabsLabel: "Choose a slide",
        aiBadge: "AI-powered creator marketplace",
        items: [
            { key: "deal", tab: "The deal" },
            { key: "problem", tab: "The problem" },
            { key: "onLocation", tab: "On location" },
        ],
        // Slide C. Its headline and line are the photo slot's own
        // (`home-on-location` in `photoSlots.js`), which is where they lived
        // when this was a full-bleed band; the overlays are drawn UI.
        onLocation: {
            slot: "home-on-location",
            card: {
                tag: "Example",
                name: "Kiran M.",
                badge: "Verified",
                line: "Shoot booked · Saturday, 7pm",
                chip: "Fee agreed before the shoot",
            },
        },
    },
    // "How it works": the process spine. Five steps per side of the deal,
    // switched between brands and creators. Each step's `title` and `line`
    // are argument and count against the budget; everything under `card` is
    // drawn product UI — the example mockup beside the step — and does not.
    //
    // **Checked against the product, and reworded where the brief's sentence
    // was not true of it** (each is listed in the PR that added this):
    // - "Live in minutes": a brief is reviewed before it goes live, unless
    //   the brand has earned trust — so the line says it is checked.
    // - "You see reach, niche and past work": every brand brief is run by us,
    //   so we shortlist, and what a brand sees is reach, niche and the
    //   reliability band — there is no portfolio of past work.
    // - "We ship the product": on a delivery brief the parcel's dispatch is
    //   recorded here; who packs it is not ours to promise.
    // - "Approve the draft": a draft gate is optional per brief, so the step
    //   approves the work; the revision cap covers drafts and live content.
    // - "Apply in one tap": an application carries a quoted rate and a pitch.
    // - "Payout receipt": no receipt exists; the card shows the payout row.
    processSpine: {
        label: "How it works",
        title: "From the brief to the results,",
        // Set in Fraunces italic.
        accent: "in one place",
        lead: "Every step of a campaign happens here, for both sides of it.",
        tabsLabel: "Show the steps for",
        tabs: [
            { key: "brands", label: "For brands" },
            { key: "creators", label: "For creators" },
        ],
        steps: {
            brands: [
                {
                    key: "brief",
                    title: "Post a brief",
                    line: "Tell us the venue or product, the deliverables and the budget. We check it, then it goes live.",
                    card: {
                        kind: "brief",
                        tag: "Example",
                        head: "Brief",
                        title: "Weekend brunch tasting",
                        rows: [
                            { k: "Where", v: "Indiranagar café · venue visit" },
                            { k: "Deliverables", v: "Reel + 3 stories" },
                            { k: "Budget", v: "₹8,000–12,000 per creator" },
                            { k: "Status", v: "Applications open", tone: "good" },
                        ],
                    },
                },
                {
                    key: "shortlist",
                    title: "Get a shortlist",
                    line: "Creators apply and we shortlist. You see reach, niche and track record, never a phone or email.",
                    card: {
                        kind: "shortlist",
                        tag: "Example",
                        head: "Applicants",
                        rows: [
                            { handle: "@foodie.daily", niche: "Food", followers: "24K followers", chip: "Shortlisted" },
                            { handle: "@brunchdiaries", niche: "Cafés", followers: "11K followers" },
                            { handle: "@plates.and.places", niche: "Dining", followers: "38K followers" },
                        ],
                        lock: "Contact details hidden",
                    },
                },
                {
                    key: "shoot",
                    title: "The shoot",
                    line: "They visit, or the product is sent to them. Slots and addresses are handled for you.",
                    card: {
                        kind: "calendar",
                        tag: "Example",
                        head: "Shoot slots",
                        days: [
                            { d: "Thu", n: "12" },
                            { d: "Fri", n: "13", booked: "11:00" },
                            { d: "Sat", n: "14", booked: "16:30" },
                            { d: "Sun", n: "15" },
                        ],
                        bookedLabel: "Booked",
                        delivered: "Product delivered ✓",
                    },
                },
                {
                    key: "approve",
                    title: "Approve the work",
                    line: "Review the content, ask for changes within the revisions included, then approve it.",
                    card: {
                        kind: "approve",
                        tag: "Example",
                        head: "Content review",
                        thumb: "Reel · 0:32",
                        revisions: "Revisions · 1 of 2 used",
                        approve: "Approve",
                        changes: "Request changes",
                    },
                },
                {
                    key: "results",
                    title: "Go live, see the numbers",
                    line: "Content goes live. Track creators, views and shares in one dashboard.",
                    card: {
                        kind: "kpis",
                        tag: "Example",
                        head: "Campaign results",
                        tiles: [
                            { label: "Creators", value: 6 },
                            { label: "Total views", value: 184200 },
                            { label: "Shares", value: 2350 },
                        ],
                        paid: "Creator paid · within 7 days",
                    },
                },
            ],
            creators: [
                {
                    key: "find",
                    title: "Find a campaign",
                    line: "Browse paid briefs that match your niche. Barter briefs show only if you turn them on.",
                    card: {
                        kind: "campaigns",
                        tag: "Example",
                        head: "Briefs for you",
                        rows: [
                            { title: "Weekend brunch tasting", niche: "Food", pay: "₹10,000" },
                            { title: "New menu launch", niche: "Dining", pay: "Barter · dinner for two" },
                        ],
                    },
                },
                {
                    key: "apply",
                    title: "Apply",
                    line: "Quote your rate and say why you fit. Your profile does the rest of the talking.",
                    card: {
                        kind: "applied",
                        tag: "Example",
                        head: "Your application",
                        title: "Weekend brunch tasting",
                        rows: [
                            { k: "Your rate", v: "₹10,000" },
                            { k: "Status", v: "Applied", tone: "good" },
                        ],
                    },
                },
                {
                    key: "shoot",
                    title: "Shoot",
                    line: "Book a slot at the venue, or receive the product at home.",
                    card: {
                        kind: "booked",
                        tag: "Example",
                        head: "Your shoot",
                        rows: [
                            { k: "Slot", v: "Sat 14 · 16:30", tone: "good" },
                            { k: "Address", v: "Shared with the WeAre team only" },
                        ],
                    },
                },
                {
                    key: "submit",
                    title: "Submit your content",
                    line: "Get feedback and revise within the agreed number of revisions.",
                    card: {
                        kind: "submit",
                        tag: "Example",
                        head: "Your content",
                        file: "reel-final.mp4",
                        revisions: "Revisions · 1 of 2 used",
                        chip: "Approved",
                    },
                },
                {
                    key: "paid",
                    title: "Get paid",
                    line: "The fee is agreed in writing before you travel. Paid within 7 days of approval, and you keep all of it.",
                    card: {
                        kind: "payout",
                        tag: "Example",
                        head: "Payout",
                        rows: [
                            { k: "Fee agreed", v: "₹10,000" },
                            { k: "Paid to your UPI", v: "₹10,000" },
                            { k: "Status", v: "Paid", tone: "good" },
                        ],
                    },
                },
            ],
        },
        // The feature row: what is built into the product, six cards.
        features: {
            label: "What is built in",
            prev: "Previous features",
            next: "More features",
            items: [
                { key: "briefs", icon: "FileText", title: "Briefs", line: "Venue, deliverables, budget and usage, in one brief." },
                { key: "shortlist", icon: "Users", title: "Creator shortlist", line: "Checked creators, with contact details kept private." },
                { key: "booking", icon: "CalendarCheck", title: "Slot booking & delivery", line: "Shoot slots and product deliveries, tracked." },
                { key: "approvals", icon: "CheckCheck", title: "Draft approvals", line: "Review before it counts, within the revisions agreed." },
                { key: "analytics", icon: "BarChart3", title: "Campaign analytics", line: "Creators, views and shares on one dashboard." },
                { key: "payouts", icon: "Wallet", title: "Payouts in 7 days", line: "Creators paid within 7 days of approval." },
            ],
        },
    },
    // Slide D of the hero, "What the AI does": rendered while any AI switch
    // is on, and absent otherwise. One row per feature that is on, read
    // through `aiLive`; every example under `card` is drawn product UI with
    // invented names and numbers. **No match percentage**: the scorer's
    // number ranks a shortlist, and it is not a figure a brand is shown.
    // The lead says what none of them does — the fee, the approval and the
    // payment are people's.
    ai: {
        // The tab: "AI-powered" only while two switches back it, the rule
        // the badge and `meta.aiTitle` follow; plainer with one.
        tab: "What the AI does",
        aiTab: "AI-powered",
        title: "AI where it helps. People where it counts.",
        // Set in Fraunces italic.
        accent: "counts",
        lead: "It drafts, matches and reads results. People agree every fee, approve every post and pay every creator.",
        cards: [
            {
                key: "briefWriter",
                title: "Drafts your brief",
                card: { quote: "“Weekend brunch, 3 food creators, Indiranagar”", result: "a full brief to edit" },
            },
            {
                key: "nicheMatching",
                title: "Matches creators on what they actually post",
                card: { chips: ["Food · brunch", "Kannada + English", "Indiranagar"], fit: "Strong fit" },
            },
            {
                key: "campaignSummary",
                title: "Reads your results, in plain English",
                card: {
                    summary: "6 creators posted. 1,24,000 views and 2,486 shares — the reel from Priya R. did a third of it.",
                },
            },
        ],
        card: { tag: "Example", head: "What the AI does", foot: "Fees, approvals and payments stay with people." },
    },
};

// ---------------------------------------------------------------------------
// About — reached from the footer only
//
// "Who built it" used to be a homepage section. It is the studio's story
// rather than the product's argument, so it lives on its own page, linked
// from the footer and not the navbar: somebody evaluating the product is not
// sent away from it to read about us, and somebody who wants to is one click
// away. Every claim here is one the site already makes: the studio runs
// campaigns end to end (the footer's own line), and every brand brief posted
// here is run by our team (the managed offer). **No person is named and no
// client is named.**
// ---------------------------------------------------------------------------

export const ABOUT = {
    meta: {
        title: "About WeAre Studios, who built it",
        description:
            "WeAre Creators is the tool WeAre Studios built for its own influencer campaigns, and the team that runs every brief posted on it.",
    },
    clients: {
        label: "Who built it",
        title: "Built by people who run these campaigns",
        // The one FillText sentence on the site. It names the city as a
        // record of where the work was done, not as the platform's reach.
        fill: "WeAre Studios has run influencer campaigns for Bengaluru restaurants, cafés and bars for years. This is the tool we wanted and couldn't buy.",
    },
    studio: {
        label: "The studio",
        title: "What the studio does for brands",
        // Rendered after the studio's name, which links out when
        // `STUDIO_URL` is set.
        line: "runs influencer campaigns end to end — casting, rates, the shoot and the report.",
    },
    tool: {
        label: "The tool",
        title: "Built for our own campaigns first",
        line: "Every brief a brand posts here is run by our team, with the tool we built to run our own.",
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
        // Under the lead while `aiLive("nicheMatching")`.
        aiLine: "Briefs are matched to what you post — cuisine, language and neighbourhood.",
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
