// The creators on the homepage.
//
// **What this is not.** It is not a ranking anybody can read a position off.
// The server sends the cards in order and every one of them looks the same:
// no number, no medal, no "1st". A visible ordinal is a public statement that
// somebody is eighth, and the person it is worst for is whoever is last —
// which on a row of eight is a creator we chose to feature. What each card
// carries instead is a professional signal: how many campaigns they have
// finished here, and the reliability band, which is the same interpreted-once
// verdict a brand gets rather than a count a stranger has no denominator for.
//
// **And it never shows money or audience size.** No fee, no rate, no follower
// count. `_public_creator_card` on the server is the allow-list and simply
// does not send them; this file could not render one if it tried.
//
// **Consent, upstream of all of it.** Everybody here ticked a box that said
// "Show my profile on the WeAre Creators homepage." Nobody is featured by
// default, and switching it off takes effect on the next load — see
// `_leaderboard_eligible`.
//
// **The section is absent below the floor**, not short. Six is the default
// and it is stored, so an operator can move it. A row of three under a
// heading about top creators advertises a platform with three creators on it,
// which is worse for the three than saying nothing.
//
// Performance, because this is the front door on mobile data:
//
//   - **Nothing is fetched until it is nearly on screen.** An
//     IntersectionObserver with a generous margin starts the request while the
//     section is still below the fold, so it is usually there by the time
//     somebody scrolls to it and is never on the critical path if they don't.
//   - **The request is a cache read.** `GET /public/leaderboard` returns what
//     the daily job computed; the ranking is never worked out per visit.
//   - Transform and opacity only, as everywhere on this site. The tilt is a
//     static transform and the hover is a 2px lift.
import React, { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import Reveal from "@/components/marketing/Reveal";
import { CARD_HOVER } from "@/components/marketing/motion";
import { CARD_SHADOW } from "@/components/marketing/FloatingCards";
import { Eyebrow } from "@/components/marketing/Sections";
import { Skeleton } from "@/components/ui/skeleton";
import { MARKETING as IDS } from "@/constants/testIds";

const COPY = {
    eyebrow: "Who is working",
    title: "Creators the work keeps coming back to.",
    line: "Featured with their permission, ranked on how they work rather than what they charge.",
};

// How many card-shaped holes to reserve while the request is in flight.
//
// **A presentation default, not a copy of the server's rule.** The floor and
// the size are the server's and this file never compares against them — it
// renders exactly what it is sent. This number only decides how much space is
// held open in the meantime, and it matches the server's default size so the
// common case reserves precisely.
const SKELETON_CARDS = 8;

// The tilt per position in the row, cycled. Small angles — these sit in a grid
// carrying names somebody has to read, not behind a headline.
const TILT = [-2.5, 1.5, -1, 2];

/** Their initial, where there is no photograph.
 *
 * Same treatment as `CreatorAvatar` and `BrandAvatar` elsewhere: the two show
 * up on the same screens in the app, and two fallback styles would read as two
 * kinds of account. Here it is the only fallback there is — a broken image
 * frame on a page about people is worse than a letter.
 */
function Monogram({ name, id }) {
    const letter = (name || "?").trim().charAt(0).toUpperCase() || "?";
    return (
        <div
            data-testid={IDS.leaderboardMonogram(id)}
            aria-hidden="true"
            className="flex h-full w-full items-center justify-center bg-ember-500/10 font-serif text-3xl text-ember-500/70"
        >
            {letter}
        </div>
    );
}

function CreatorCard({ creator, i }) {
    const tilt = TILT[i % TILT.length];
    return (
        <Reveal i={i} as="li" className="flex">
            {/* **Not a link, and that is a deliberate answer rather than an
                omission.** The rule is to link through to a creator's public
                profile page where one exists and to leave the card inert
                otherwise, never to send somebody to a login wall — and this
                product has no public creator page. `/profile` is the
                creator's own, behind auth and behind the creator role, so
                linking there would put every visitor on a sign-in screen from
                a section whose whole job is to be read by strangers.

                An `<article>`, so it is one item to a screen reader without
                claiming to be interactive. When a public creator page exists,
                this becomes an anchor and the server sends the path — the
                same shape `BrandName` already uses for brands. */}
            <article
                data-testid={IDS.leaderboardCard(creator.id)}
                style={{ transform: `rotate(${tilt}deg)` }}
                className={`flex flex-1 flex-col overflow-hidden rounded-lg border border-white/10 bg-card grain-surface ${CARD_SHADOW} ${CARD_HOVER}`}
            >
                {/* The ratio is on the container, never on the `<img>`, so a
                    photograph that never arrives still occupies the space it
                    claimed — the design foundations' rule, and what keeps the
                    monogram and the photo the same size. */}
                <div className="aspect-[4/5] w-full overflow-hidden bg-white/5">
                    {creator.profile_image_url ? (
                        <img
                            src={creator.profile_image_url}
                            alt={creator.name || "Creator"}
                            loading="lazy"
                            className="h-full w-full object-cover"
                        />
                    ) : (
                        <Monogram name={creator.name} id={creator.id} />
                    )}
                </div>

                <div className="flex flex-1 flex-col gap-1 p-4">
                    <h3
                        data-testid={IDS.leaderboardName(creator.id)}
                        className="font-serif text-fluid-lg leading-tight tracking-tight"
                    >
                        {creator.name}
                    </h3>
                    {creator.instagram_handle && (
                        <p className="text-sm text-muted-foreground">
                            @{creator.instagram_handle}
                        </p>
                    )}
                    <p className="text-xs text-muted-foreground/80">
                        {[creator.city, ...(creator.niches || [])]
                            .filter(Boolean)
                            .join(" · ")}
                    </p>
                    {/* The professional signal, in the place a rank would
                        have gone. Campaigns finished is a fact; the band is
                        the server's one-word verdict. Neither is a position. */}
                    <p
                        data-testid={IDS.leaderboardSignal(creator.id)}
                        className="mt-auto pt-3 text-xs uppercase tracking-[0.15em] text-ember-500"
                    >
                        {creator.campaigns_completed}{" "}
                        {creator.campaigns_completed === 1 ? "campaign" : "campaigns"}
                        {creator.reliability?.enough_history &&
                            ` · ${creator.reliability.label}`}
                    </p>
                </div>
            </article>
        </Reveal>
    );
}

export function CreatorLeaderboard() {
    const [creators, setCreators] = useState(null);
    // Whether the section has come close enough to the viewport to be worth
    // fetching for. Starts false on every load, so a visitor who never scrolls
    // never pays for this at all.
    const [near, setNear] = useState(false);
    const anchor = useRef(null);

    useEffect(() => {
        const node = anchor.current;
        if (!node) return undefined;
        // No observer (an old browser, a test environment) means fetch rather
        // than never render. Degrading to "the section is missing" would hide
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
            // Start the request while it is still a screen and a half away, so
            // it has usually landed by the time anybody reads it.
            { rootMargin: "600px" },
        );
        observer.observe(node);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (!near) return undefined;
        let cancelled = false;
        api.get("/public/leaderboard")
            .then(({ data }) => {
                if (!cancelled) setCreators(data?.creators || []);
            })
            // A marketing section that says "couldn't load" is worse than a
            // marketing section that isn't there. Same rule as the proof
            // strip.
            .catch(() => {
                if (!cancelled) setCreators([]);
            });
        return () => {
            cancelled = true;
        };
    }, [near]);

    // **Nothing at all when there is nothing worth showing**: the request
    // failed, or the server withheld the row because too few creators are
    // eligible. The server decides the second one — the floor is its number,
    // and a client holding a second copy is a client that disagrees the day it
    // moves.
    // **And nothing before the request is even in flight.** The reserved shape
    // below is for the gap between asking and being answered; drawing it
    // earlier would put a section-shaped hole on the page of a visitor who
    // never scrolls that far and never triggers the fetch at all — a
    // permanent block of grey boxes standing in for content nobody asked for.
    // Caught in a browser: the skeleton rendered from first paint and the
    // section never arrived, because the observer had not fired.
    if (!near || (creators && creators.length === 0)) {
        return <div ref={anchor} aria-hidden="true" />;
    }

    // Not fetched yet is a different case, and it gets a shape rather than a
    // hole. **Measured**: rendering nothing and then a section is a 1,870px
    // growth at 390px, which cost 0.0837 CLS on a page whose whole budget is
    // 0.0002. Reserving a pixel height would have been wrong at every width
    // between the breakpoints — the cards are 4:5, so the section's height
    // tracks the column width continuously from 1,149px at 768 to 1,409px at
    // 1280. A skeleton in the same grid is right at every width by
    // construction, which is the reason the rule is "shaped like the content"
    // rather than "the same height as it".
    //
    // The one case that still shifts is a deployment below the floor, where
    // the reserved shape collapses once. That is the right way round, and the
    // same trade `ProofStrip` documents: the site with a row is the site
    // people visit, and holding a permanent gap open on the other one would be
    // a hole standing in for a section that is never coming.
    const loading = !creators;

    return (
        <section
            ref={anchor}
            data-testid={loading ? IDS.leaderboardSkeleton : IDS.leaderboard}
            aria-hidden={loading || undefined}
            className="border-t border-white/10 py-16 md:py-24"
        >
            <div className="mx-auto max-w-7xl px-6">
                {/* **The heading is not skeletoned.** It is static copy that
                    is known at build time, so drawing grey bars in its place
                    would reserve a *different* height from the real thing —
                    measured at 136px of error on a phone, where the headline
                    wraps to three lines and three bars do not. The only part
                    that has to wait is the part that comes from the server. */}
                <Reveal>
                    <Eyebrow>{COPY.eyebrow}</Eyebrow>
                    <h2 className="mt-3 max-w-2xl font-serif text-fluid-3xl leading-[1.05] tracking-tight">
                        {COPY.title}
                    </h2>
                    <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
                        {COPY.line}
                    </p>
                </Reveal>

                <ul className="mt-10 grid grid-cols-2 gap-4 md:mt-14 md:grid-cols-4">
                    {loading
                        ? Array.from({ length: SKELETON_CARDS }).map((_, i) => (
                              <li key={i} className="flex">
                                  {/* The same box the card occupies: the 4:5
                                      frame and four lines under it. */}
                                  <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-white/10 bg-card">
                                      {/* The frame reserves itself: 4:5 on
                                          the container is exact at every
                                          width, which is why the ratio lives
                                          there rather than on the image. */}
                                      <Skeleton className="aspect-[4/5] w-full rounded-none" />
                                      {/* The text block cannot: how many
                                          lines "Bengaluru · fnb · lifestyle"
                                          takes depends on the real names. So
                                          it is pinned to the height the real
                                          block was measured at — 183px where
                                          that line wraps, 157px above `lg`
                                          where it does not. */}
                                      <div className="flex min-h-[183px] flex-1 flex-col gap-1 p-4 lg:min-h-[157px]">
                                          <Skeleton className="h-5 w-3/4" />
                                          <Skeleton className="h-4 w-1/2" />
                                          <Skeleton className="h-3 w-2/3" />
                                          <Skeleton className="mt-auto h-3 w-1/2" />
                                      </div>
                                  </div>
                              </li>
                          ))
                        : creators.map((creator, i) => (
                              <CreatorCard key={creator.id} creator={creator} i={i} />
                          ))}
                </ul>
            </div>
        </section>
    );
}

export default CreatorLeaderboard;
