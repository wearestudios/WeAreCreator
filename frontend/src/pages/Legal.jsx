import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Mail } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import Footer from "@/components/Footer";

/**
 * Terms and privacy.
 *
 * Signup records consent against the account (`terms_accepted_at` +
 * `terms_version`), so these pages have to exist and be reachable — a consent
 * record that points at nothing is worth nothing.
 *
 * THE COPY BELOW IS A PLAIN-ENGLISH DESCRIPTION of what the product actually
 * does with the data. It is not legal text and has not been reviewed by a
 * lawyer. Replace both sections with the real documents, and bump
 * TERMS_VERSION in the backend when you do, so it's clear who accepted which
 * version.
 *
 * It is kept accurate on purpose: a privacy page that describes a data flow
 * the product no longer has is worse than a placeholder, because somebody
 * reads it and believes it. The last review found exactly that — this page
 * still said contact details were handed to a brand on acceptance, months
 * after that was removed everywhere in the product.
 *
 * ---------------------------------------------------------------------------
 * NEEDS A LAWYER — do not invent language for these. Each is a real question
 * this product raises and none of them is answerable by reading the code:
 *
 *   - DPDP Act 2023 duties: the consent notice's required form, the grievance
 *     officer's name and address, and what a "significant data fiduciary"
 *     obligation would mean at scale. We record consent at signup
 *     (`terms_accepted_at` + `terms_version`) but the notice itself is not
 *     drafted.
 *   - Retention periods. `RETENTION_DAYS` in server.py is now a real table
 *     rather than a shrug, and the page below quotes it — but the numbers in
 *     it are a considered guess at the statutory minimums, not advice. Two of
 *     the rows are the actual open questions: how long a *rejected* business's
 *     documents may be held (the accepted case is a year after the decision,
 *     the rejected one has no obvious anchor), and whether an audit line
 *     naming a person is a record we are obliged to keep or personal data we
 *     are obliged to erase. Where the two duties conflict the code keeps the
 *     line and erases the name; somebody has to say whether that is right.
 *   - Erasure, now that it exists. `_erase_personal_data` takes a defensible
 *     position — remove the person, keep the anonymised transaction — but
 *     whether an anonymised collaboration row is still personal data, how long
 *     it may be held, and whether a deletion request may ever be *refused*
 *     rather than deferred are all questions for a lawyer. The product defers
 *     while work is in flight and declines only with a reason.
 *   - Withholding. The platform records the TDS an admin enters and computes
 *     no rate anywhere. Which section applies, thresholds, and what an
 *     inoperative PAN means for the rate are not decided in code, and the
 *     certificate a creator is entitled to is not issued by this product.
 *   - Identity and business documents (GST certificates, FSSAI licences,
 *     registration papers) carry directors' names and registered addresses.
 *     How long we may hold them after a verification decision is a legal
 *     question, not a product one.
 *   - Unpublished draft content. A creator's draft sits on our disk before it
 *     is public; who may see it, and for how long we keep it after a campaign
 *     closes, wants a clause rather than a paragraph.
 *   - Location coordinates are precise enough to identify a home. Whether
 *     that is sensitive personal data under the DPDP Act is a lawyer's call.
 *   - Content licensing: the brief states reuse terms in prose. Whether that
 *     forms a licence, and what happens on cancellation, is unresolved here.
 *   - Instagram data received through the official API is subject to Meta's
 *     platform terms as well as ours. Those obligations are not described.
 * ---------------------------------------------------------------------------
 */

const CONTACT = "creators@wearemonk.in";

const Section = ({ title, children }) => (
    <section className="mt-10">
        <h2 className="font-serif text-fluid-3xl leading-tight tracking-tight">
            {title}
        </h2>
        <div className="mt-4 space-y-4 text-sm leading-relaxed text-muted-foreground">
            {children}
        </div>
    </section>
);

const Shell = ({ kicker, title, standfirst, children }) => (
    <div data-testid="legal-page" className="min-h-screen bg-background grain-page">
        <Navbar />
        <main className="mx-auto max-w-3xl px-6 py-14 md:py-20">
            <Link
                to="/"
                data-testid="legal-back-link"
                className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.2em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
            >
                <ArrowLeft className="h-3.5 w-3.5" />
                Home
            </Link>

            <p className="mt-6 text-xs uppercase tracking-[0.2em] text-ember-500">
                {kicker}
            </p>
            <h1 className="mt-4 font-serif text-fluid-5xl leading-none tracking-tight">
                {title}
            </h1>
            <p className="mt-6 text-base leading-relaxed text-muted-foreground">
                {standfirst}
            </p>

            <div
                data-testid="legal-draft-notice"
                className="mt-8 rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-relaxed text-amber-200"
            >
                This is a plain-English summary of how WeAre Creators works today,
                published so you can see what you're agreeing to. The full legal
                document is being finalised — write to{" "}
                <a
                    href={`mailto:${CONTACT}`}
                    className="underline underline-offset-4 hover:no-underline"
                >
                    {CONTACT}
                </a>{" "}
                for a copy or with any question.
            </div>

            {children}

            <div className="mt-14 flex items-center gap-2 border-t border-white/10 pt-8 text-sm text-muted-foreground">
                <Mail className="h-4 w-4 text-ember-500" />
                Questions about any of this:{" "}
                <a
                    href={`mailto:${CONTACT}`}
                    className="text-ember-500 underline-offset-4 hover:underline"
                >
                    {CONTACT}
                </a>
            </div>
        </main>
        <Footer />
    </div>
);

export function Terms() {
    return (
        <Shell
            kicker="Terms"
            title="How working with WeAre works."
            standfirst="WeAre Creators connects verified creators with brands running paid campaigns. These are the terms you accept when you create an account."
        >
            <Section title="Getting on the platform">
                <p>
                    Creators build a profile and are reviewed by the WeAre team before
                    they can apply to a brief. Joining and applying are free, and stay
                    free — there is no subscription and nothing is deducted from a
                    creator's fee.
                </p>
                <p>
                    Brands register in the name of one person at the business, who is the
                    account. A brand is checked against the documents it uploads before
                    it can reach a creator at all. We may decline or remove an account.
                </p>
                <p>
                    Making a material change to a verified profile — your name, your
                    handles, your city or your payout details — puts it back in front of
                    the team before you apply to anything new. Work already accepted
                    carries on.
                </p>
            </Section>

            <Section title="Applying and being chosen">
                <p>
                    A creator applies with a pitch and a quoted fee. The WeAre team checks
                    the application, and the brand decides whether to accept. Either side
                    may decline before the fee is agreed. Applying is not a guarantee of
                    work.
                </p>
                <p>
                    Some campaigns are run by the brand and some by the WeAre Studios
                    team, and each brief says which. That decides who you deal with day to
                    day — who answers your questions, and who reviews what you send.
                </p>
                <p>
                    A brief may be public or invite-only. An invite-only brief is visible
                    only to creators who were invited to it.
                </p>
            </Section>

            <Section title="Fees and payment">
                <p>
                    Creators receive 100% of the fee agreed on a collaboration. WeAre's
                    platform fee is charged to the brand on top of that amount, and is
                    shown before the brand confirms.
                </p>
                <p>
                    The fee is agreed in writing before anyone shoots. On a fixed-fee
                    brief it is the figure on the brief; on a negotiated one it is
                    whatever the two sides settle on, recorded against the collaboration.
                    Some briefs are barter — a meal, a stay, a product rather than money —
                    and say so on their face.
                </p>
                <p>
                    Payment is released after the brand approves the published content. We
                    pay to the UPI ID or bank account on the creator's profile, and
                    deduct tax at source where the law requires it — the amount
                    withheld is recorded against the payment — which is why PAN is
                    mandatory before a
                    payout.
                </p>
            </Section>

            <Section title="Approval before it goes live">
                <p>
                    On campaigns that ask for it, a creator sends the content for review
                    as a draft — a file or an unlisted link — before publishing anything.
                    Whoever runs the campaign either approves it or asks for changes with
                    a note saying what to change. A draft is held privately and is not
                    shown to anyone outside the campaign.
                </p>
                <p>
                    The creator publishes once the draft is approved, then submits the
                    live links. The brand approves the delivery, and that is what releases
                    payment. Where a campaign does not ask for a draft, the creator
                    publishes and submits the links directly.
                </p>
            </Section>

            <Section title="Cancellations">
                <p>
                    A creator can release a booked slot up to 24 hours before it starts. A
                    collaboration can be cancelled by either side before content is
                    approved. Where a creator has already attended a shoot, we will work
                    with both sides on a fair outcome case by case.
                </p>
            </Section>

            <Section title="Content and rights">
                <p>
                    Creators keep ownership of the content they make. Sending a draft for
                    review does not change that. The brief sets out what the brand may
                    reuse and for how long. Nothing here overrides the terms of the
                    platform the content is published on.
                </p>
                <p>
                    We record how published content performed — reach, engagement and the
                    like — and report it to the brand that paid for it.
                </p>
            </Section>
        </Shell>
    );
}

export function Privacy() {
    return (
        <Shell
            kicker="Privacy"
            title="What we hold, and why."
            standfirst="We collect the minimum needed to run collaborations and pay people, and we don't sell any of it."
        >
            <Section title="What we collect">
                <p>
                    <span className="text-foreground">Everyone:</span> name, WhatsApp
                    number, and the time you accepted these terms.
                </p>
                <p>
                    <span className="text-foreground">Creators:</span> email, profile
                    photo, city, neighbourhood, a short bio, your niches and the
                    platforms you post on, your rate, and links to your work. Your
                    delivery address, and — if you drop a pin — the map coordinates of
                    it. For payouts, whichever you choose: a UPI ID, or the name on
                    your bank account with its account number and IFSC. PAN either
                    way, because it is required before tax can be deducted, and GSTIN
                    if you have one.
                </p>
                <p>
                    <span className="text-foreground">
                        Creators who connect Instagram:
                    </span>{" "}
                    we use Instagram's official API to read your account's follower
                    count, engagement, and the reach and interactions on posts you
                    submitted as deliverables. We hold an access token for your account,
                    encrypted, and never post or change anything. Disconnect at any time
                    and we stop reading, keeping only the figures already recorded
                    against past work.
                </p>
                <p>
                    <span className="text-foreground">Brands:</span> business name,
                    legal entity name, business type, category, registered address, GST
                    number and website where you have them, your logo, the outlets you
                    operate — including map coordinates where you set them — and the
                    name, role, work email and WhatsApp number of the person registering
                    on the business's behalf.
                </p>
                <p>
                    <span className="text-foreground">Business documents:</span> the
                    files you upload to prove the business exists — GST certificate,
                    registration, FSSAI or shop &amp; establishment licence. These carry
                    directors' names and registered addresses, so they are stored apart
                    from everything else and are never served publicly.
                </p>
                <p>
                    <span className="text-foreground">While a campaign runs:</span> your
                    application and quoted rate, the agreed fee, the slot you booked,
                    whether you checked in at the venue, the draft you sent for review
                    and the links you published, the questions you asked on a campaign,
                    and the payment record. Drafts are held privately until they are
                    published by you.
                </p>
            </Section>

            <Section title="Who sees what">
                <p>
                    Brands see your name, photo, handles and public stats, follower
                    count, engagement rate, city, niches, what you make and your rate.
                </p>
                <p>
                    <span className="text-foreground">
                        A brand never receives your phone number, WhatsApp number, email
                        or full address
                    </span>{" "}
                    — not at any stage of a collaboration, not in the invite flow, and
                    not in anything they can export. This used to be different: contact
                    details were handed over once a brand accepted you. They are not any
                    more, and a brand reaches you through the platform instead.
                </p>
                <p>
                    The map pin on your address is never shown to a brand at all. The
                    WeAre team running a shoot does see your number, because somebody
                    has to be able to call you on the day.
                </p>
                <p>
                    Payout details are visible only to the WeAre team, and are used only
                    to pay you and to file the tax that goes with it. Business documents
                    are visible only to the WeAre team reviewing them, and every time one
                    is opened it is logged.
                </p>
            </Section>

            <Section title="Who we share it with">
                <p>
                    WhatsApp messages are delivered through AiSensy. Instagram data comes
                    to us from Meta through the official API when you connect your
                    account — we read, and send nothing back. We share what is necessary
                    with tax authorities and our payment providers. Nobody else, and we
                    do not sell any of it.
                </p>
            </Section>

            <Section title="Your data, your call">
                <p>
                    Write to{" "}
                    <a
                        href={`mailto:${CONTACT}`}
                        className="text-ember-500 underline-offset-4 hover:underline"
                    >
                        {CONTACT}
                    </a>{" "}
                    to get a copy of everything we hold about you or correct it.
                </p>
                <p>
                    {/* The right, and what exercising it actually does — said
                        here because somebody agreeing to it without being told
                        has not agreed to what happens. */}
                    <span className="text-foreground">Deleting your account.</span> You
                    can ask for it from your profile page. Somebody reads every request
                    — it is not automatic — and we will tell you when it is done. On
                    erasure your name, number, email, address, map pin, photo, payout
                    details and PAN are removed, your Instagram token is deleted, and
                    the words of anything you wrote in a work note or a question thread
                    are removed. Records of completed collaborations and payments stay,
                    without you in them: they are a brand's proof of what it paid for
                    and our own accounting record, and tax law requires us to keep them.
                </p>
                <p>
                    We cannot erase you while a collaboration is still under way — a
                    shoot booked, a draft waiting, a payment owed. We will tell you
                    which ones, and you can ask again once they have finished.
                </p>
                <p>
                    {/* **The retention section, and it names periods rather
                        than saying "as long as necessary".** The phrase means
                        nothing to the person reading it and everything to the
                        person who wrote it, which is the wrong way round. The
                        numbers here are the ones in RETENTION_DAYS in
                        server.py; if the two ever disagree, the code is what
                        actually happens and this page is the lie. */}
                    <span className="text-foreground">How long we keep things.</span>{" "}
                    Business verification documents are deleted a year after we verify
                    a brand — they proved the business exists and the decision itself
                    is recorded separately. Unpublished drafts are deleted ninety days
                    after a collaboration closes. Payment records and the log of who did
                    what are kept for eight years, because tax and accounting rules
                    require it. Everything personal — your name, number, email, address,
                    map pin, photo, payout details, PAN and Instagram token — goes on
                    erasure, immediately and permanently.
                </p>
                <p>
                    {/* Said plainly rather than buried: a page that implies
                        certainty it does not have is worse than one that
                        admits the gap, and somebody reading this is entitled
                        to know which parts are settled. */}
                    We are still taking advice on some of this — in particular how long
                    we may hold a rejected business's documents, and whether an audit
                    line naming you is a record we must keep or personal data we must
                    erase. Where the answer is not settled we keep less rather than
                    more, and this page will say so when it changes.
                </p>
            </Section>
        </Shell>
    );
}
