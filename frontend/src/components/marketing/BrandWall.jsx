// A row of logos, for brands actually running campaigns here.
//
// **Mirrored on `CreatorLeaderboard`**, which already answered every hard part
// of putting a server-decided row on the front door: fetched only when it is
// nearly on screen, a skeleton in the same grid rather than a pixel height,
// nothing at all before the request is in flight, and the floor owned by the
// server. The two differ in what they are claiming, not in how they behave.
//
// **Where it sits is an argument.** Below the proof strip and above the case
// studies, because that is the order a sceptical brand reads in: the figures
// say there is an operation, the logos say businesses like theirs use it, and
// the case studies say it works. Logos before proof would be decoration;
// logos after the write-ups would be a footnote.
//
// **What this must not become.** A wall of everybody who ever signed up. The
// server gates on having actually finished a campaign (`_brand_wall_eligible`)
// and on the brand having given written permission for its mark — a logo is a
// trademark, and consent is re-read on every request so withdrawal is
// immediate. None of that is decided here; a client holding a second copy of
// the rule is a client that disagrees with the server the day it moves.
import React, { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import Reveal from "@/components/marketing/Reveal";
import { Eyebrow } from "@/components/marketing/Sections";
import { Skeleton } from "@/components/ui/skeleton";
import { CARD_SHADOW } from "@/components/marketing/FloatingCards";
import { MARKETING as IDS } from "@/constants/testIds";

const COPY = {
    eyebrow: "The brands",
    title: "Businesses that run campaigns with us.",
    line: "Each of these has finished at least one campaign here, and has given written permission to be named.",
};

// How many boxes the skeleton draws. The server's default size is 12; the
// skeleton stands in for the common case rather than the ceiling, because a
// row of twelve grey boxes standing in for a row of six is a worse guess than
// a row of six standing in for twelve — the grid reflows either way, and the
// shorter guess errs toward the page not jumping *down*.
const SKELETON_CARDS = 6;

/**
 * One logo.
 *
 * **Greyscale at rest, warming on hover.** Twelve logos in twelve brand
 * palettes is a grid that fights itself and pulls the eye away from the page's
 * own accent; desaturating them makes the row read as one object. Hover
 * restores the real mark, which is the courtesy owed to somebody who gave us
 * their trademark.
 *
 * **`object-contain`, never `object-cover`** — the rule `BrandAvatar` already
 * holds. Cropping a logo to fill a box cuts it in half.
 */
function BrandLogo({ brand, i }) {
    const inner = (
        <>
            {/* The ratio is on the container, so a logo that never arrives
                still occupies the space it claimed. 3:2 rather than square:
                most marks are wordmarks, which are wider than they are tall,
                and a square box makes every one of them small. */}
            <div className="flex aspect-[3/2] w-full items-center justify-center p-5">
                {brand.logo_url ? (
                    <img
                        src={brand.logo_url}
                        alt={brand.name || ""}
                        loading="lazy"
                        data-testid={IDS.brandWallLogo(brand.id)}
                        className="max-h-full max-w-full object-contain opacity-80 grayscale transition duration-200 group-hover:opacity-100 group-hover:grayscale-0"
                    />
                ) : (
                    // The server will not send a card without a logo — the
                    // logo *is* the card — so this is the shape of a mark that
                    // failed to load rather than one that was never set.
                    <span className="font-serif text-lg text-muted-foreground">
                        {(brand.name || "").slice(0, 1).toUpperCase()}
                    </span>
                )}
            </div>
            {/* The name in text as well as in the mark. A wall of logos a
                screen reader reads as twelve images is a wall of nothing, and
                `alt` alone does not survive a logo that fails to load. */}
            <span className="sr-only">{brand.name}</span>
        </>
    );

    return (
        <Reveal
            as="li"
            i={i}
            data-testid={IDS.brandWallCard(brand.id)}
            className="flex"
        >
            {/* **A link only where there is a page to link to**, decided
                server-side. `/brands/{id}` serves verified brands only, so a
                card linking there for anybody else would be a card linking to
                a 404 — the leaderboard's rule, which leaves its cards inert
                because this product has no public creator page at all. */}
            {brand.public_page ? (
                <a
                    href={brand.public_page}
                    className={`group flex flex-1 items-center justify-center rounded-lg border border-white/10 bg-card transition duration-200 hover:border-primary/40 ${CARD_SHADOW}`}
                >
                    {inner}
                </a>
            ) : (
                <div
                    className={`group flex flex-1 items-center justify-center rounded-lg border border-white/10 bg-card ${CARD_SHADOW}`}
                >
                    {inner}
                </div>
            )}
        </Reveal>
    );
}

export default function BrandWall() {
    const [brands, setBrands] = useState(null);
    // Whether the section has come close enough to be worth fetching for.
    // Starts false on every load, so a visitor who never scrolls never pays.
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
            // The same screen-and-a-half the leaderboard uses, so the two
            // sections on this page behave identically.
            { rootMargin: "600px" },
        );
        observer.observe(node);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (!near) return undefined;
        let cancelled = false;
        api.get("/public/brand-wall")
            .then(({ data }) => {
                if (!cancelled) setBrands(data?.brands || []);
            })
            // A marketing section that says "couldn't load" is worse than one
            // that isn't there. The rule the proof strip set.
            .catch(() => {
                if (!cancelled) setBrands([]);
            });
        return () => {
            cancelled = true;
        };
    }, [near]);

    // Nothing when the server withheld the row — which it does below its own
    // floor, because one withdrawal taking the section down is correct.
    if (brands && brands.length === 0) {
        return <div ref={anchor} aria-hidden="true" />;
    }

    // **The shape is held from first paint, which is the opposite of what the
    // leaderboard does, and the difference is where the two sections sit.**
    //
    // The leaderboard is at the bottom of the page and draws nothing until its
    // own observer has fired, because reserving earlier would leave a
    // permanent block of grey boxes for a visitor who never scrolls that far —
    // a real bug, caught in a browser. This section sits directly under the
    // proof strip, which at 390px is right at the fold: the observer fires on
    // load whatever it is told, so "when near" and "from first paint" are the
    // same moment, and gating the shape on `near` bought nothing while costing
    // a 0→full growth that pushed the whole page down.
    //
    // **Measured**: gated on `near` this was 0.0823 CLS at 390px against a
    // control of 0.0000, and 0.1644 when the server withheld the row — the
    // section appearing and then collapsing, counted twice. Held from first
    // paint it is 0.0000 in the case that matters.
    //
    // The remaining cost is one collapse on a deployment below the floor, and
    // that is the right way round — the same trade `ProofStrip` documents: the
    // site with a wall is the site people visit, and holding a permanent gap
    // open on the other one would be a hole standing in for a section that is
    // never coming.
    const loading = !brands;

    return (
        <section
            ref={anchor}
            data-testid={loading ? IDS.brandWallSkeleton : IDS.brandWall}
            aria-hidden={loading || undefined}
            className="border-t border-white/10 py-16 md:py-24"
        >
            <div className="mx-auto max-w-7xl px-6">
                {/* **The heading is not skeletoned**, for the reason the
                    leaderboard documents: it is static copy known at build
                    time, so grey bars in its place reserve a different height
                    from the real thing. Only the part that comes from the
                    server has to wait. */}
                <Reveal>
                    <Eyebrow>{COPY.eyebrow}</Eyebrow>
                    <h2 className="mt-3 max-w-2xl font-serif text-fluid-3xl leading-[1.05] tracking-tight">
                        {COPY.title}
                    </h2>
                    <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
                        {COPY.line}
                    </p>
                </Reveal>

                <ul className="mt-10 grid grid-cols-2 gap-4 md:mt-14 md:grid-cols-3 lg:grid-cols-6">
                    {loading
                        ? Array.from({ length: SKELETON_CARDS }).map((_, i) => (
                              <li key={i} className="flex">
                                  {/* The same box a card occupies. The 3:2
                                      frame reserves itself at every width,
                                      which is why the ratio is on the
                                      container — a pixel height would be
                                      wrong between every pair of
                                      breakpoints. */}
                                  <div className="flex flex-1 items-center justify-center rounded-lg border border-white/10 bg-card">
                                      <Skeleton className="m-5 aspect-[3/2] w-full" />
                                  </div>
                              </li>
                          ))
                        : brands.map((brand, i) => (
                              <BrandLogo key={brand.id} brand={brand} i={i} />
                          ))}
                </ul>
            </div>
        </section>
    );
}
