// The marketing pages' shared furniture.
//
// Five pages plus the 404. Bespoke layout on each would be six design systems
// inside a fortnight, which is what the hand-written HTML this replaced was
// already becoming.
//
// **The shape enforces the copy rules.** Every primitive here takes a short
// label and *one* supporting line — there is no prop that accepts a paragraph,
// because the rule "replace prose with structure" survives about a fortnight
// if it lives only in a style guide. A section that wants to make two points
// has to be two sections, which is the constraint doing its job.
//
// Motion comes from `motion.js`: one easing curve, 200–400ms, transforms and
// opacity, and `Reveal` handles `prefers-reduced-motion` once rather than at
// each call site.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import MarketingNavbar from "@/components/marketing/MarketingNavbar";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import PageMeta from "@/components/marketing/PageMeta";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import Reveal from "@/components/marketing/Reveal";
import { CARD_HOVER } from "@/components/marketing/motion";
import { Button } from "@/components/ui/button";
import { MARKETING as IDS } from "@/constants/testIds";

/** Uppercase, tiny, wide — the design guidelines' overline rule. */
export function Eyebrow({ children, className = "" }) {
    return (
        <p className={`text-xs uppercase tracking-[0.2em] text-ember-500 ${className}`}>
            {children}
        </p>
    );
}

/**
 * The page shell: meta, the marketing navbar, the content, the marketing
 * footer.
 *
 * Both bars are marketing variants. The shared `Navbar` and `Footer` are on
 * authenticated surfaces and stay exactly as they are.
 */
export function MarketingPage({ testid, title, description, path, children }) {
    return (
        <div
            data-testid={testid}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <PageMeta title={title} description={description} path={path} />
            <MarketingNavbar />
            <main>{children}</main>
            <MarketingFooter />
        </div>
    );
}

/**
 * One ask, and the same ask each time.
 *
 * Every audience page states its CTA at the top and again at the bottom, in
 * **the same words**: two differently-worded buttons is a choice of doors, one
 * repeated is an ask.
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
 * A short label and one line beneath it.
 *
 * The unit that replaced the paragraph. Four words and a sentence carry the
 * same point as fifty words and are read rather than skipped — and a reader
 * scanning three of these has the whole section in about four seconds.
 */
export function Point({ label, line, i = 0, testid = IDS.point }) {
    // **The hover treatment is on a child, not on the animated element.**
    // Framer Motion writes `transform` as an inline style, and an inline style
    // beats a class — so `hover:-translate-y-0.5` on the same node the
    // entrance animates is silently dead once the entrance settles at
    // `transform: none`. The border warm worked and the lift did not, which is
    // exactly the sort of half-working hover nobody notices.
    return (
        <Reveal i={i} as="li" className="flex">
            <div
                data-testid={testid}
                className={`flex-1 rounded-lg border border-white/10 bg-card grain-surface p-6 ${CARD_HOVER}`}
            >
                <h3 className="font-serif text-fluid-xl leading-tight tracking-tight">
                    {label}
                </h3>
                <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
                    {line}
                </p>
            </div>
        </Reveal>
    );
}

/** Three or four `Point`s in a row. */
export function Points({ items, testid, columns = 3 }) {
    const cols = columns === 4 ? "md:grid-cols-2 lg:grid-cols-4" : "md:grid-cols-3";
    return (
        <ul data-testid={testid} className={`grid gap-4 ${cols}`}>
            {items.map((p, i) => (
                <Point key={p.label} label={p.label} line={p.line} i={i} />
            ))}
        </ul>
    );
}

/**
 * The top of a page: eyebrow, headline, one line, the ask, and the first
 * image slot beside them.
 */
export function MarketingHero({ eyebrow, title, line, cta, image, footnote }) {
    return (
        <section
            data-testid={IDS.hero}
            className="relative overflow-hidden border-b border-white/10"
        >
            <div
                aria-hidden
                className="pointer-events-none absolute -right-40 -top-24 h-[520px] w-[520px] rounded-full bg-ember-500/10 blur-[120px]"
            />
            <div className="relative mx-auto grid max-w-7xl gap-12 px-6 py-16 md:grid-cols-12 md:items-center md:py-20">
                <div className="group md:col-span-6">
                    <Reveal onView={false}>
                        <Eyebrow>{eyebrow}</Eyebrow>
                    </Reveal>
                    <Reveal i={1} onView={false}>
                        <h1 className="mt-5 font-serif text-fluid-5xl leading-none tracking-tight">
                            {title}
                        </h1>
                    </Reveal>
                    <Reveal i={2} onView={false}>
                        <p className="mt-6 max-w-xl text-base leading-relaxed text-muted-foreground md:text-lg">
                            {line}
                        </p>
                    </Reveal>
                    {/* A page with two audiences has no single ask, and
                        inventing one puts half its readers through the wrong
                        door. Those pages route at the close instead. */}
                    {cta ? (
                        <Reveal i={3} onView={false} className="mt-8">
                            <Cta {...cta} />
                        </Reveal>
                    ) : null}
                    {footnote ? (
                        <Reveal i={4} onView={false}>
                            <p className="mt-4 text-sm text-muted-foreground">{footnote}</p>
                        </Reveal>
                    ) : null}
                </div>
                <Reveal i={2} onView={false} noTravel className="group md:col-span-6">
                    <PlaceholderImage {...image} testid={IDS.heroImage} zoom />
                </Reveal>
            </div>
        </section>
    );
}

/**
 * A headline, one line, optional points, and an image — alternating sides
 * down the page.
 *
 * `flip` puts the image on the left. Alternating is the whole reason these are
 * one component: doing it by hand means somebody eventually ships two in a row
 * on the same side and the page reads as a column with pictures next to it.
 */
export function TextImageSection({
    eyebrow,
    title,
    line,
    points,
    image,
    flip = false,
    testid,
}) {
    return (
        <section
            data-testid={testid}
            className="border-b border-white/10 py-16 md:py-20"
        >
            <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 md:grid-cols-12">
                <div className={`md:col-span-6 ${flip ? "md:order-2" : ""}`}>
                    {eyebrow ? (
                        <Reveal>
                            <Eyebrow>{eyebrow}</Eyebrow>
                        </Reveal>
                    ) : null}
                    <Reveal i={1}>
                        <h2 className="mt-4 font-serif text-fluid-4xl leading-tight tracking-tight">
                            {title}
                        </h2>
                    </Reveal>
                    {line ? (
                        <Reveal i={2}>
                            <p className="mt-5 max-w-lg text-base leading-relaxed text-muted-foreground">
                                {line}
                            </p>
                        </Reveal>
                    ) : null}
                    {points?.length ? (
                        <ul className="mt-8 space-y-4">
                            {points.map((p, i) => (
                                <Reveal
                                    key={p.label}
                                    i={i + 3}
                                    as="li"
                                    className="flex gap-3"
                                >
                                    <span
                                        aria-hidden
                                        className="mt-2.5 h-1 w-4 shrink-0 rounded-full bg-ember-500/70"
                                    />
                                    <span>
                                        <span className="font-serif text-fluid-lg leading-tight">
                                            {p.label}
                                        </span>
                                        <span className="block text-sm leading-relaxed text-muted-foreground">
                                            {p.line}
                                        </span>
                                    </span>
                                </Reveal>
                            ))}
                        </ul>
                    ) : null}
                </div>
                <Reveal
                    i={1}
                    noTravel
                    className={`group md:col-span-6 ${flip ? "md:order-1" : ""}`}
                >
                    <PlaceholderImage {...image} zoom />
                </Reveal>
            </div>
        </section>
    );
}

/** A numbered sequence — how it works, from one side. Label plus one line. */
export function Steps({ eyebrow, title, items, testid }) {
    return (
        <section data-testid={testid} className="border-b border-white/10 py-16 md:py-20">
            <div className="mx-auto max-w-7xl px-6">
                <Reveal>
                    <Eyebrow>{eyebrow}</Eyebrow>
                </Reveal>
                <Reveal i={1}>
                    <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                        {title}
                    </h2>
                </Reveal>
                <ol className="mt-10 grid gap-8 md:grid-cols-2 lg:grid-cols-4">
                    {items.map((step, i) => (
                        <Reveal
                            key={step.label}
                            i={i}
                            as="li"
                            className="border-t border-white/10 pt-6"
                        >
                            <span className="font-serif text-sm text-ember-500">
                                {String(i + 1).padStart(2, "0")}
                            </span>
                            <h3 className="mt-3 font-serif text-fluid-xl leading-tight tracking-tight">
                                {step.label}
                            </h3>
                            <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
                                {step.line}
                            </p>
                        </Reveal>
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
        "group flex-1 rounded-lg border border-white/10 bg-card grain-surface p-7 " +
        CARD_HOVER;
    return (
        <div data-testid={testid} className="flex flex-col gap-4 sm:flex-row">
            <Reveal as="div" className="flex flex-1">
                <Link to="/for-creators" data-testid={IDS.pathCreator} className={card}>
                    <p className="flex items-center gap-2 font-serif text-fluid-2xl leading-tight tracking-tight">
                        I&apos;m a creator
                        <ArrowRight className="h-4 w-4 text-ember-500 transition-transform duration-200 group-hover:translate-x-1" />
                    </p>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                        Paid briefs, your rate in writing, paid on approved delivery.
                    </p>
                </Link>
            </Reveal>
            <Reveal i={1} as="div" className="flex flex-1">
                <Link to="/for-brands" data-testid={IDS.pathBrand} className={card}>
                    <p className="flex items-center gap-2 font-serif text-fluid-2xl leading-tight tracking-tight">
                        I&apos;m a brand
                        <ArrowRight className="h-4 w-4 text-ember-500 transition-transform duration-200 group-hover:translate-x-1" />
                    </p>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                        Checked creators, approval before publication, a report at the
                        end.
                    </p>
                </Link>
            </Reveal>
        </div>
    );
}

/**
 * The closing ask. Same words as the hero's, one image slot behind it.
 *
 * `cta` for a page with one audience; `children` for a page with two, which
 * passes <TwoPaths /> instead.
 */
export function ClosingSection({ title, line, cta, image, children }) {
    return (
        <section
            data-testid={IDS.closing}
            className="group relative overflow-hidden py-20 md:py-24"
        >
            <div aria-hidden className="absolute inset-0 opacity-40">
                <PlaceholderImage {...image} fill zoom />
            </div>
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background via-background/85 to-background"
            />
            <div className="relative mx-auto max-w-3xl px-6 text-center">
                <Reveal>
                    <h2 className="font-serif text-fluid-4xl leading-tight tracking-tight">
                        {title}
                    </h2>
                </Reveal>
                <Reveal i={1}>
                    <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
                        {line}
                    </p>
                </Reveal>
                {cta ? (
                    <Reveal i={2} className="mt-8 flex justify-center">
                        <Cta {...cta} />
                    </Reveal>
                ) : null}
                {children ? <div className="mt-10 text-left">{children}</div> : null}
            </div>
        </section>
    );
}
