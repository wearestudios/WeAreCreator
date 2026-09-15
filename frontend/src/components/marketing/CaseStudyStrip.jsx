// Three campaigns we ran, on the pages that sell.
//
// **The strongest thing this operation has to say, and it was on no page.**
// We run campaigns end to end — casting, fees, the shoot, delivery — and the
// only evidence of that anywhere was a counted figure in the proof strip. A
// brand weighing us up is asking "have you done this, for somebody like me",
// and three write-ups with a brand name and a real number on them answer it
// in a way no amount of copy can.
//
// **The cards link out of the SPA, deliberately.** `/work` and `/work/:slug`
// are server-rendered by the backend, so these are plain `<a>` rather than
// `<Link>` — a router link would be caught by the SPA and answered with the
// catch-all. That is the same trade `/c/{id}` makes and it is the right one
// here twice over: a case study is the link we paste into a chat with a
// brand, so the preview *is* the pitch, and it is the one part of this site
// written to be found by search rather than sent. See PREVIEW.md.
//
// Everything else follows `CreatorLeaderboard`, which solved the same problem
// on the same page:
//
//   - **Nothing is fetched until it is nearly on screen**, so a visitor who
//     never scrolls never pays for it.
//   - **Absent rather than short.** Fewer than three published means no
//     section: a shelf of one advertises an operation that has run one
//     campaign, which is worse for us than saying nothing. The floor lives
//     here rather than on the server because it is a *presentation* rule —
//     the endpoint's job is to answer what is published, and a page that
//     wants three is a page that can count to three.
//   - **The ratio is on the container, never on the `<img>`**, so an image
//     that never arrives still occupies the space it claimed.
//   - Transform and opacity only.
import React, { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import Reveal from "@/components/marketing/Reveal";
import { CARD_HOVER } from "@/components/marketing/motion";
import { Eyebrow } from "@/components/marketing/Sections";
import { Skeleton } from "@/components/ui/skeleton";
import { WORK_PATH } from "@/lib/siteNav";
import { MARKETING as IDS } from "@/constants/testIds";

const COPY = {
    eyebrow: "Our work",
    title: "Campaigns we ran, end to end.",
    line: "What the brand needed, who shot it, and what it reached.",
    all: "See all of our work",
};

// Three. Enough to read as a pattern rather than as the one that went well,
// few enough to fit a row on a laptop and a scroll on a phone.
const FEATURED = 3;

/**
 * The floor, and it is the whole reason this can be trusted.
 *
 * The same argument `PROOF_FLOORS` makes on the proof strip: two case studies
 * under a heading about our work is a number a reader is entitled to draw a
 * conclusion from, and the conclusion is right. All three or none.
 */
const FLOOR = 3;

function CaseStudyCard({ study, i }) {
    return (
        <Reveal i={i} as="li" className="flex">
            <a
                href={`${WORK_PATH}/${study.slug}`}
                data-testid={IDS.caseStudyCard(study.slug)}
                className={`flex flex-1 flex-col overflow-hidden rounded-lg border border-white/10 bg-card grain-surface ${CARD_HOVER}`}
            >
                {/* 16:9 on the container. A hero that never arrives is a
                    surface that has not filled rather than a hole, and the
                    card does not change height when it does. */}
                <div className="aspect-[16/9] w-full overflow-hidden bg-white/5">
                    {study.hero_image_url ? (
                        <img
                            src={study.hero_image_url}
                            alt=""
                            loading="lazy"
                            className="h-full w-full object-cover"
                        />
                    ) : (
                        <div aria-hidden="true" className="h-full w-full bg-ember-500/10" />
                    )}
                </div>

                <div className="flex flex-1 flex-col gap-2 p-5">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        {[study.brand_name, study.category_label, study.city]
                            .filter(Boolean)
                            .join(" · ")}
                    </p>
                    <h3 className="font-serif text-fluid-lg leading-tight tracking-tight">
                        {study.title}
                    </h3>
                    {/* The headline result in ember, because it is the one
                        thing on the card a brand is actually reading for. */}
                    {study.headline_result && (
                        <p
                            data-testid={IDS.caseStudyResult(study.slug)}
                            className="mt-auto pt-2 font-serif text-fluid-xl leading-tight text-ember-500"
                        >
                            {study.headline_result}
                        </p>
                    )}
                </div>
            </a>
        </Reveal>
    );
}

export default function CaseStudyStrip() {
    const [studies, setStudies] = useState(null);
    const [near, setNear] = useState(false);
    const anchor = useRef(null);

    useEffect(() => {
        const node = anchor.current;
        if (!node) return undefined;
        // No observer (an old browser, a test environment) means fetch rather
        // than never render: degrading to "the section is missing" would hide
        // real content over a progressive enhancement.
        if (typeof IntersectionObserver === "undefined") {
            setNear(true);
            return undefined;
        }
        const observer = new IntersectionObserver(
            (entries) => {
                if (entries.some((e) => e.isIntersecting)) {
                    setNear(true);
                    observer.disconnect();
                }
            },
            { rootMargin: "600px" },
        );
        observer.observe(node);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (!near) return undefined;
        let cancelled = false;
        api.get("/public/case-studies", { params: { limit: FEATURED } })
            .then(({ data }) => {
                if (!cancelled) setStudies(data?.case_studies || []);
            })
            // A marketing section that says "couldn't load" is worse than one
            // that isn't there. The rule the proof strip already holds.
            .catch(() => {
                if (!cancelled) setStudies([]);
            });
        return () => {
            cancelled = true;
        };
    }, [near]);

    // Nothing before the request is in flight, and nothing below the floor.
    // The first half is the lesson `CreatorLeaderboard` records: drawing the
    // reserved shape earlier puts a permanent section-shaped hole on the page
    // of a visitor who never scrolls far enough to trigger the fetch.
    if (!near || (studies && studies.length < FLOOR)) {
        return <div ref={anchor} aria-hidden="true" />;
    }

    const rows = (studies || []).slice(0, FEATURED);

    return (
        <section
            ref={anchor}
            data-testid={IDS.caseStudyStrip}
            className="border-b border-white/10 py-16 md:py-20"
        >
            <div className="mx-auto max-w-7xl px-6">
                <Reveal>
                    <Eyebrow>{COPY.eyebrow}</Eyebrow>
                </Reveal>
                <Reveal i={1}>
                    <h2 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                        {COPY.title}
                    </h2>
                </Reveal>
                <Reveal i={2}>
                    <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
                        {COPY.line}
                    </p>
                </Reveal>

                {/* Shaped like the content rather than a pixel height: the
                    cards are 16:9, so the section's height tracks the column
                    width continuously and any single number would be wrong at
                    every width between the breakpoints. The heading above is
                    *not* skeletoned — it is static copy that renders
                    immediately, and grey bars in its place reserve a
                    different height from the words. */}
                <ul className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    {studies
                        ? rows.map((s, i) => (
                              <CaseStudyCard key={s.slug} study={s} i={i} />
                          ))
                        : Array.from({ length: FEATURED }).map((_, i) => (
                              <li
                                  key={i}
                                  aria-hidden="true"
                                  className="flex flex-col overflow-hidden rounded-lg border border-white/10 bg-card"
                              >
                                  <Skeleton className="aspect-[16/9] w-full rounded-none" />
                                  <div className="flex flex-col gap-3 p-5">
                                      <Skeleton className="h-3 w-2/3" />
                                      <Skeleton className="h-5 w-full" />
                                      <Skeleton className="h-6 w-1/2" />
                                  </div>
                              </li>
                          ))}
                </ul>

                <Reveal i={3}>
                    <a
                        href={WORK_PATH}
                        data-testid={IDS.caseStudyAll}
                        className="mt-8 inline-flex items-center gap-2 border-b border-ember-500/40 pb-1 text-sm text-ember-500 transition-colors duration-150 hover:border-ember-500"
                    >
                        {COPY.all}
                        <span aria-hidden="true">→</span>
                    </a>
                </Reveal>
            </div>
        </section>
    );
}
