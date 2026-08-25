// What is on screen while a surface's chunk is on the wire.
//
// **Deliberately not a guess at the page underneath.** Every page here brings
// its own chrome — the marketing pages use `MarketingNavbar`, the app uses the
// shared `Navbar`, the console has a sidebar — so a fallback that drew one of
// them would draw the wrong one about half the time, and a header that appears
// and is then replaced by a different header is worse than one that arrives
// once.
//
// What it does match is the ground: the same `min-h-screen bg-background
// grain-page` every page sits on, so the swap is a fill rather than a flash,
// and the page that lands is at least a screen tall in every case — which is
// what keeps the shift off the measurement.
//
// Skeletons rather than a spinner, the rule the whole product already holds:
// shape, not motion. Three bars at the width of an eyebrow, a headline and a
// line of body text — the arrangement almost every page opens with.
import React from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { LoadingAnnouncement } from "@/components/data/PageSkeleton";
import { ROUTE_FALLBACK as IDS } from "@/constants/testIds";

export default function RouteFallback() {
    return (
        <div
            data-testid={IDS.root}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            {/* The bar every surface has, at the height the shared navbar and
                the marketing one both use (`h-16`), so the content below it
                starts where it is going to start. */}
            <div className="h-16 border-b border-white/10" aria-hidden="true" />
            <main className="mx-auto max-w-5xl px-6 py-12 md:py-16">
                {/* `aria-hidden` on the shapes and one polite announcement
                    that is not, so a screen reader hears "loading" rather than
                    a list of empty boxes. */}
                <div aria-hidden="true" className="space-y-6">
                    <Skeleton className="h-3 w-28" />
                    <Skeleton className="h-10 w-3/4 max-w-md" />
                    <Skeleton className="h-4 w-full max-w-lg" />
                </div>
                <LoadingAnnouncement testid={IDS.announce}>
                    Loading this section…
                </LoadingAnnouncement>
            </main>
        </div>
    );
}
