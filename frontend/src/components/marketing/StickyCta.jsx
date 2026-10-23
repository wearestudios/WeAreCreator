// The phone's bottom bar: one ask, always within reach.
//
// **It appears once the hero has scrolled out of view and goes away when the
// closing section is on screen** (or has been passed), because both of those
// already carry the same ask at full size — a bar repeating a button the
// reader is looking at is a bar covering the page for nothing. Phone only:
// below `md`. The ask is a 48px tap target.
//
// **It arrives without animation.** The public site's motion is five
// primitives and this is not one of them; a bar that slides in is a sixth.
//
// Watches two elements by id, set by the page: `heroId` and `closeId`. While
// hidden it is `hidden`, so it is neither seen nor reachable by keyboard.
import React, { useEffect, useState } from "react";

import { Cta } from "@/components/marketing/SiteParts";
import { SITE_PARTS as IDS } from "@/constants/testIds";

export default function StickyCta({ ask, heroId, closeId, label = "Quick action" }) {
    const [pastHero, setPastHero] = useState(false);
    const [atClose, setAtClose] = useState(false);

    useEffect(() => {
        if (typeof IntersectionObserver === "undefined") return undefined;
        const hero = document.getElementById(heroId);
        const close = document.getElementById(closeId);
        const observers = [];
        if (hero) {
            const io = new IntersectionObserver(([e]) => setPastHero(!e.isIntersecting && e.boundingClientRect.top < 0));
            io.observe(hero);
            observers.push(io);
        }
        if (close) {
            // Visible, or already above the viewport (scrolled into the footer).
            const io = new IntersectionObserver(([e]) => setAtClose(e.isIntersecting || e.boundingClientRect.top < 0));
            io.observe(close);
            observers.push(io);
        }
        return () => observers.forEach((io) => io.disconnect());
    }, [heroId, closeId]);

    const shown = pastHero && !atClose;
    return (
        <div
            data-testid={IDS.stickyCta}
            role="region"
            aria-label={label}
            hidden={!shown}
            className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur md:hidden"
        >
            <Cta ask={ask} testid={IDS.stickyCtaButton} className="w-full min-h-[3rem]" />
        </div>
    );
}
