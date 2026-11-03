// The phone's bottom bar: one ask, always within reach.
//
// **It appears once the hero has scrolled out of view and goes away when the
// closing section or the footer is on screen** (or has been passed). The
// closing band carries the same ask at full size, and the footer is the end
// of the page, where a bar covers the links somebody scrolled down to reach.
// Home has no closing band any more — it ends on the spine, then the footer —
// so the footer is the one that hides it there; on the audience pages the
// closing band comes first and the behaviour is what it was. Phone only:
// below `md`. The ask is a 48px tap target.
//
// **It arrives without animation.** The public site's motion is five
// primitives and this is not one of them; a bar that slides in is a sixth.
//
// Watches the hero and, when the page has one, the closing band by id
// (`heroId`, `closeId`), and always the marketing footer by its test id. While
// hidden it is `hidden`, so it is neither seen nor reachable by keyboard.
import React, { useEffect, useState } from "react";

import { Cta } from "@/components/marketing/SiteParts";
import { FOOTER, SITE_PARTS as IDS } from "@/constants/testIds";

export default function StickyCta({ ask, heroId, closeId, label = "Quick action" }) {
    const [pastHero, setPastHero] = useState(false);
    const [atClose, setAtClose] = useState(false);
    const [atFooter, setAtFooter] = useState(false);

    useEffect(() => {
        if (typeof IntersectionObserver === "undefined") return undefined;
        const hero = document.getElementById(heroId);
        const close = closeId ? document.getElementById(closeId) : null;
        const footer = document.querySelector(`[data-testid="${FOOTER.root}"]`);
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
        if (footer) {
            // Once any of it is on screen — the end of the page, and its links.
            const io = new IntersectionObserver(([e]) => setAtFooter(e.isIntersecting || e.boundingClientRect.top < 0));
            io.observe(footer);
            observers.push(io);
        }
        return () => observers.forEach((io) => io.disconnect());
    }, [heroId, closeId]);

    const shown = pastHero && !atClose && !atFooter;
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
