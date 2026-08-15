import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Mail } from "lucide-react";
import { Navbar } from "@/components/Navbar";

/**
 * Terms and privacy.
 *
 * Signup records consent against the account (`terms_accepted_at` +
 * `terms_version`), so these pages have to exist and be reachable — a consent
 * record that points at nothing is worth nothing.
 *
 * THE COPY BELOW IS A PLACEHOLDER describing what the product actually does
 * with the data. It is not legal text and has not been reviewed by a lawyer.
 * Replace both sections with the real documents, and bump TERMS_VERSION in the
 * backend when you do, so it's clear who accepted which version.
 */

const CONTACT = "creators@wearemonk.in";

const Section = ({ title, children }) => (
    <section className="mt-10">
        <h2 className="font-serif text-2xl leading-tight tracking-tight md:text-3xl">
            {title}
        </h2>
        <div className="mt-4 space-y-4 text-sm leading-relaxed text-muted-foreground">
            {children}
        </div>
    </section>
);

const Shell = ({ kicker, title, standfirst, children }) => (
    <div data-testid="legal-page" className="min-h-screen bg-background">
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
            <h1 className="mt-4 font-serif text-4xl leading-none tracking-tight md:text-5xl">
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
                    Creators submit a profile and are reviewed by the WeAre team before
                    they can pitch on briefs. Brands are reviewed before their campaigns
                    are promoted. We may decline or remove an account.
                </p>
            </Section>

            <Section title="Applying and being chosen">
                <p>
                    A creator applies with a pitch and a quoted fee. The WeAre team vets
                    the application, and the brand decides whether to accept. Either side
                    may decline before the fee is agreed. Applying is not a guarantee of
                    work.
                </p>
            </Section>

            <Section title="Fees and payment">
                <p>
                    Creators receive 100% of the fee agreed on a collaboration. WeAre's
                    platform fee is charged to the brand on top of that amount, and is
                    shown before the brand confirms.
                </p>
                <p>
                    Payment is released after the brand approves the submitted content.
                    We pay to the UPI ID on the creator's profile, and deduct tax at
                    source where the law requires it — which is why PAN is mandatory
                    before a payout.
                </p>
            </Section>

            <Section title="Cancellations">
                <p>
                    A collaboration can be cancelled before content is approved. Where a
                    creator has already attended a shoot, we will work with both sides on
                    a fair outcome case by case.
                </p>
            </Section>

            <Section title="Content and rights">
                <p>
                    Creators keep ownership of the content they make. The brief sets out
                    what the brand may reuse and for how long. Nothing here overrides the
                    terms of the platform the content is published on.
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
                    <span className="text-foreground">Creators:</span> email, city,
                    neighbourhood, Instagram handle, niches, rates, and public Instagram
                    statistics. For payouts: UPI ID, account name, PAN, and GSTIN if you
                    have one.
                </p>
                <p>
                    <span className="text-foreground">Brands:</span> business name,
                    category and the areas you operate in.
                </p>
            </Section>

            <Section title="Who sees what">
                <p>
                    Brands browsing the creator directory see your name, handle, city,
                    niches, follower count and rate — never your email, phone number,
                    address or payout details.
                </p>
                <p>
                    Your contact details are shared with a brand only once they have
                    accepted you onto a campaign, so you can coordinate the shoot.
                </p>
                <p>
                    Payout details are visible only to the WeAre team, and are used only
                    to pay you and to file the tax that goes with it.
                </p>
            </Section>

            <Section title="Who we share it with">
                <p>
                    WhatsApp messages are delivered through AiSensy. We share what is
                    necessary with tax authorities and our payment providers. Nobody
                    else.
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
                    to get a copy of everything we hold about you, correct it, or have
                    your account deleted. We keep records of completed collaborations and
                    payments for as long as tax law requires, even after an account is
                    closed.
                </p>
            </Section>
        </Shell>
    );
}
