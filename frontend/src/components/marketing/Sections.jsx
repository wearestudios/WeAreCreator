// The marketing pages' shared furniture.
//
// Four pages — /for-brands, /for-creators, /how-it-works, /why-weare — plus
// home and the 404. Bespoke layout on each would be five design systems inside
// a fortnight, which is exactly what happened the first time these existed as
// hand-written HTML on the backend.
//
// Everything here is presentational and takes its copy as props. The pages own
// what they say; this file owns how it looks.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { Navbar } from "@/components/Navbar";
import Footer from "@/components/Footer";
import PageMeta from "@/components/marketing/PageMeta";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import { Button } from "@/components/ui/button";
import { MARKETING as IDS } from "@/constants/testIds";

/** Uppercase, tiny, wide — the design guidelines' overline rule. */
export function Eyebrow({ children, className = "" }) {
    return (
        <p
            className={`text-xs uppercase tracking-[0.2em] text-ember-500 ${className}`}
        >
            {children}
        </p>
    );
}

/**
 * The page shell: meta, navbar, the content, the footer.
 *
 * Every marketing page is on the grained page ground and carries the footer —
 * these are the pages a signed-out person lands on, and the footer is the only
 * route to terms, privacy and a human.
 */
export function MarketingPage({ testid, title, description, path, children }) {
    return (
        <div
            data-testid={testid}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <PageMeta title={title} description={description} path={path} />
            <Navbar />
            <main>{children}</main>
            <Footer />
        </div>
    );
}

/**
 * One ask, and the same ask each time.
 *
 * Every audience page states its CTA at the top and again at the bottom, in
 * **the same words**: two differently-worded buttons is a choice of doors,
 * one repeated is an ask. The nav's own button makes it three, which is the
 * same sentence a third time rather than a third option.
 */
export function Cta({ to, label, testid, className = "" }) {
    return (
        <Link to={to} data-testid={testid} className={className}>
            <Button className="group h-12 rounded-full bg-ember-500 px-7 text-black transition-colors duration-200 hover:bg-ember-400">
                {label}
                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
            </Button>
        </Link>
    );
}

/**
 * The top of an audience page: eyebrow, headline, standfirst, the ask, and the
 * page's first image slot beside them.
 *
 * The image is a slot rather than decoration — it is the first thing a visitor
 * looks at and the last thing we have. See `PlaceholderImage`.
 */
export function MarketingHero({
    eyebrow,
    title,
    standfirst,
    cta,
    image,
    footnote,
}) {
    return (
        <section
            data-testid={IDS.hero}
            className="relative overflow-hidden border-b border-white/10"
        >
            <div
                aria-hidden
                className="pointer-events-none absolute -right-40 -top-24 h-[520px] w-[520px] rounded-full bg-ember-500/10 blur-[120px]"
            />
            <div className="relative mx-auto grid max-w-7xl gap-12 px-6 py-16 md:grid-cols-12 md:items-center md:py-24">
                <div className="md:col-span-6">
                    <Eyebrow>{eyebrow}</Eyebrow>
                    <h1 className="mt-5 font-serif text-fluid-5xl leading-none tracking-tight">
                        {title}
                    </h1>
                    <p className="mt-6 max-w-xl text-base leading-relaxed text-muted-foreground md:text-lg">
                        {standfirst}
                    </p>
                    {/* A page with two audiences has no single ask, and
                        inventing one puts half its readers through the wrong
                        door. Those pages route at the close instead. */}
                    {cta ? (
                        <div className="mt-9">
                            <Cta {...cta} />
                        </div>
                    ) : null}
                    {footnote ? (
                        <p className="mt-4 text-sm text-muted-foreground">{footnote}</p>
                    ) : null}
                </div>
                <div className="md:col-span-6">
                    <PlaceholderImage {...image} testid={IDS.heroImage} />
                </div>
            </div>
        </section>
    );
}

/**
 * A block of prose beside an image, alternating sides down the page.
 *
 * `flip` puts the image on the left. Alternating is the whole reason these are
 * one component: doing it by hand means somebody eventually ships two in a row
 * on the same side and the page reads as a column with pictures next to it.
 */
export function TextImageSection({
    eyebrow,
    title,
    body,
    points,
    image,
    flip = false,
    testid,
}) {
    return (
        <section
            data-testid={testid}
            className="border-b border-white/10 py-16 md:py-24"
        >
            <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 md:grid-cols-12">
                <div className={`md:col-span-6 ${flip ? "md:order-2" : ""}`}>
                    {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
                    <h2 className="mt-4 font-serif text-fluid-4xl leading-tight tracking-tight">
                        {title}
                    </h2>
                    {body ? (
                        <p className="mt-5 text-base leading-relaxed text-muted-foreground">
                            {body}
                        </p>
                    ) : null}
                    {points?.length ? (
                        <ul className="mt-7 space-y-4">
                            {points.map((p) => (
                                <li key={p} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
                                    <span
                                        aria-hidden
                                        className="mt-2 h-1 w-4 shrink-0 rounded-full bg-ember-500/70"
                                    />
                                    <span>{p}</span>
                                </li>
                            ))}
                        </ul>
                    ) : null}
                </div>
                <div className={`md:col-span-6 ${flip ? "md:order-1" : ""}`}>
                    <PlaceholderImage {...image} />
                </div>
            </div>
        </section>
    );
}

/** Three value propositions in a row, each a card on the grained ground. */
export function ValueProps({ items, testid }) {
    return (
        <section data-testid={testid} className="border-b border-white/10 py-16 md:py-24">
            <div className="mx-auto max-w-7xl px-6">
                <div className="grid gap-6 md:grid-cols-3">
                    {items.map((item) => (
                        <div
                            key={item.title}
                            className="rounded-lg border border-white/10 bg-card grain-surface p-7"
                        >
                            <h3 className="font-serif text-fluid-2xl leading-tight tracking-tight">
                                {item.title}
                            </h3>
                            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                                {item.body}
                            </p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}

/** A numbered sequence — how it works, from one side. */
export function Steps({ eyebrow, title, items, testid }) {
    return (
        <section data-testid={testid} className="border-b border-white/10 py-16 md:py-24">
            <div className="mx-auto max-w-7xl px-6">
                {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
                <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                    {title}
                </h2>
                <ol className="mt-12 grid gap-8 md:grid-cols-2 lg:grid-cols-4">
                    {items.map((step, i) => (
                        <li key={step.title} className="border-t border-white/10 pt-6">
                            <span className="font-serif text-sm text-ember-500">
                                {String(i + 1).padStart(2, "0")}
                            </span>
                            <h3 className="mt-3 font-serif text-fluid-2xl leading-tight tracking-tight">
                                {step.title}
                            </h3>
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                {step.body}
                            </p>
                        </li>
                    ))}
                </ol>
            </div>
        </section>
    );
}

/**
 * Two doors, for the pages that cannot know who arrived.
 *
 * Home and /how-it-works speak to both sides, so a single CTA would send half
 * the room through the wrong door. This is the one place competing buttons are
 * right — and they are deliberately equal in weight, because picking one for
 * the visitor is the mistake, not offering two.
 *
 * The audience pages never use this. There, one ask stated twice is the rule.
 */
export function TwoPaths({ testid }) {
    const card =
        "group flex-1 rounded-lg border border-white/10 bg-card grain-surface p-7 transition-colors duration-200 hover:border-ember-500/40";
    return (
        <div data-testid={testid} className="flex flex-col gap-4 sm:flex-row">
            <Link to="/for-creators" data-testid={IDS.pathCreator} className={card}>
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    I make content
                </p>
                <p className="mt-3 flex items-center gap-2 font-serif text-fluid-2xl leading-tight tracking-tight">
                    I&apos;m a creator
                    <ArrowRight className="h-4 w-4 text-ember-500 transition-transform duration-200 group-hover:translate-x-1" />
                </p>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    Paid briefs, your rate in writing, and payment on approved
                    delivery.
                </p>
            </Link>
            <Link to="/for-brands" data-testid={IDS.pathBrand} className={card}>
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    I have something to launch
                </p>
                <p className="mt-3 flex items-center gap-2 font-serif text-fluid-2xl leading-tight tracking-tight">
                    I&apos;m a brand
                    <ArrowRight className="h-4 w-4 text-ember-500 transition-transform duration-200 group-hover:translate-x-1" />
                </p>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    Creators we have checked, approval before publication, and a
                    report at the end.
                </p>
            </Link>
        </div>
    );
}

/**
 * The closing ask. Same words as the hero's, one image slot behind it.
 *
 * `cta` for a page with one audience; `children` for a page with two, which
 * passes <TwoPaths /> instead.
 */
export function ClosingSection({ title, body, cta, image, children }) {
    return (
        <section
            data-testid={IDS.closing}
            className="relative overflow-hidden py-20 md:py-28"
        >
            <div aria-hidden className="absolute inset-0 opacity-40">
                <PlaceholderImage {...image} fill />
            </div>
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background via-background/85 to-background"
            />
            <div className="relative mx-auto max-w-3xl px-6 text-center">
                <h2 className="font-serif text-fluid-4xl leading-tight tracking-tight">
                    {title}
                </h2>
                <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
                    {body}
                </p>
                {cta ? (
                    <div className="mt-9 flex justify-center">
                        <Cta {...cta} />
                    </div>
                ) : null}
                {children ? <div className="mt-10 text-left">{children}</div> : null}
            </div>
        </section>
    );
}
