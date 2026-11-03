// Under the process spine: the same campaign done over DMs, and done here,
// in one wide panel with the ask at its far end.
//
// The labels are the label face — JetBrains Mono, small capitals — the one
// other place on the public site that wears it besides the section rules,
// beside the spine's step numbers. The "before" label is `accent-ink`,
// which on the navy band is the brand red at full strength — 4.9:1 there,
// and any paler red would fall below AA at this size.
//
// The ask reports its own click (`cta_click`, `location: "process_strip"`);
// `data-track-self` keeps the analytics gate from counting it a second time.
import React from "react";
import { ArrowRight } from "lucide-react";

import { Cta } from "@/components/marketing/SiteParts";
import { PROCESS as IDS } from "@/constants/testIds";
import { EVENTS, track } from "@/lib/track";

function BeforeAfterStrip({ strip, ask, className = "" }) {
    const onCta = () => track(EVENTS.ctaClick, { location: "process_strip", cta: ask.cta });
    return (
        <div
            data-testid={IDS.beforeAfter}
            data-track-self=""
            className={`grid items-center gap-6 rounded-[16px] border border-brand-white/10 px-6 py-6 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto] md:gap-8 md:px-8 ${className}`}
        >
            <div>
                <p className="mkt-label text-accent-ink">{strip.before.label}</p>
                <p className="mkt-body mt-2 text-brand-white/65">{strip.before.line}</p>
            </div>
            <span
                aria-hidden
                className="grid h-11 w-11 place-items-center rounded-full border border-brand-white/15 text-brand-white/90"
            >
                <ArrowRight className="h-4 w-4 rotate-90 md:rotate-0" />
            </span>
            <div>
                <p className="mkt-label text-brand-white/90">{strip.after.label}</p>
                <p className="mkt-body mt-2 text-brand-white/90">{strip.after.line}</p>
            </div>
            <Cta ask={ask} testid={IDS.stripCta} onClick={onCta} className="w-full md:w-auto" />
        </div>
    );
}

// Memoised: its props are the content module's, and the spine above it
// re-renders as the active step changes.
export default React.memo(BeforeAfterStrip);
