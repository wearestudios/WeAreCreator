// The home page. Two sections, then the footer:
//
//   01 the hero slider — the deal (the page's only h1), the problem, the
//      shoot and, while any AI switch is on, what the AI does; the two asks
//      and the quiet line under them stay put whichever slide is showing
//      (`components/marketing/HeroSlider.jsx`)
//   02 how it works — the process spine: five steps a side, brands or
//      creators, on a navy band, then the feature row
//      (`components/marketing/ProcessSpine.jsx`)
//
// **Two, because the page used to tell its story three times.** The problem,
// the promises and the creator door each restated what the spine already
// walks through, and at 390px the page ran to eleven and a half thousand
// pixels. The story the old sections told now lives in the slider, one slide
// each; "Who built it" is `/about`, linked from the footer.
//
// **The spine sits directly on the footer, and both are navy.** That is the
// one place two neighbours share a ground on this site, and it is deliberate:
// the beam footer's 1px accent rule is the divider between them.
//
// **Every word is in `HOME` in `content/marketing.js`**; this file is layout.
// **No real business is named on this page**: the only names here are the
// invented ones inside the drawn product UI.
//
// **The homepage ships no animation library.** Its LCP is the h1, and 36KB of
// framer-motion in front of it would be the one regression this must not
// cause: the slider reads reduced motion off the media query and crossfades
// in CSS, and the process spine's motion is CSS transitions driven by two
// observers.
import React, { useEffect } from "react";

import HeroSlider from "@/components/marketing/HeroSlider";
import ProcessSpine from "@/components/marketing/ProcessSpine";
import { MarketingPage } from "@/components/marketing/Sections";
import StickyCta from "@/components/marketing/StickyCta";
import { LANDING_PAGE as IDS } from "@/constants/testIds";
import { ASK, HOME, aiLive } from "@/content/marketing";

/**
 * `/how-it-works` lands on `/#how-it-works`. The browser scrolls to a hash on
 * a page it loaded itself, but not on one a client-side redirect rendered
 * after it had already looked, so the page does it once on arrival.
 */
function useScrollToHash() {
    useEffect(() => {
        const id = window.location.hash.slice(1);
        if (!id) return;
        const el = document.getElementById(id);
        if (el) el.scrollIntoView();
    }, []);
}

export default function Home() {
    const { meta: plainMeta } = HOME;
    useScrollToHash();
    // The AI features that are on, read through `aiLive` per feature, never
    // from the switch object. Any one puts the AI slide in the slider.
    const aiCards = HOME.ai.cards.filter((card) => aiLive(card.key));
    // "AI-powered" — the badge, the deal's lead, the AI tab and the page's
    // title — is claimed only when two features are live.
    const aiPowered = aiCards.length >= 2;
    const meta = aiPowered
        ? { title: plainMeta.aiTitle, description: plainMeta.aiDescription }
        : plainMeta;
    return (
        <MarketingPage testid={IDS.page} title={meta.title} description={meta.description} path="/">
            <HeroSlider n={1} aiCards={aiCards} aiPowered={aiPowered} />
            <ProcessSpine n={2} id="how-it-works" />
            <StickyCta ask={ASK.postBrief} heroId="hero" />
        </MarketingPage>
    );
}
