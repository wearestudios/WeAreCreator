// Verified creators, campaigns run, cities — counted, never written down.
//
// A hardcoded "500+ creators" is a claim that was true on the day somebody
// typed it, on the pages whose whole job is to be believed by a stranger. So
// the figures come from `GET /public/proof`, which counts them.
//
// **Three figures, and it is all of them or none.** The floors live on the
// server (`PROOF_FLOORS`) so every surface agrees about what counts as
// sayable, and the gate is on the set rather than on each figure: the old
// per-figure rule rendered "7 cities" alone on real data, which reads as the
// one statistic we could find. A visitor makes the obvious inference about the
// missing ones, and they are right to. "12 creators · 2 campaigns" is worse
// than silence.
//
// It renders nothing if the request fails. A proof strip that says "—" is
// worse than no proof strip.
//
// **While the request is in flight it reserves its own height.** It used to
// render nothing at all until the figures landed, and then appear — which
// pushed every section below it down and was measured at 0.0798 CLS on home,
// the entire layout-shift budget of the page in one event. Reserving is the
// fix that costs nothing: the box is the height the strip will be, so the
// figures drop into a space that is already there.
//
// The one case that still shifts is a deployment with nothing above the
// floors, where the reserved box collapses once on resolution. That is the
// right way round — the site with real figures is the site people visit, and
// holding an empty band open on the other one would be a permanent gap
// standing in for a strip that is never coming.
import React, { useEffect, useState } from "react";

import { api } from "@/lib/api";
import CountUp from "@/components/marketing/CountUp";
import Reveal from "@/components/marketing/Reveal";
import { MARKETING as IDS } from "@/constants/testIds";

const LABEL = {
    creators: "verified creators",
    // "Open briefs", not "campaigns run": the server counts what is live right
    // now, and a label saying otherwise would describe a different number.
    campaigns: "open briefs",
    cities: "cities",
};

// The order they read in, not the order the API happens to return. Three, and
// the server sends all three or none — see `PROOF_FLOORS`.
const ORDER = ["creators", "campaigns", "cities"];

// Measured against the rendered strip, at both widths, because the figures
// wrap: one row above `md` (148px) and two below it (200px). A single value
// was wrong by 52px on a phone, which is a 0.0099 shift — small, and still the
// only shift left on the page. Estimating from the type scale would have got
// the desktop number right and the mobile one wrong in exactly this way.
const RESERVED = "min-h-[200px] md:min-h-[148px]";

export function ProofStrip({ only, className = "" }) {
    const [stats, setStats] = useState(null);

    useEffect(() => {
        let cancelled = false;
        api.get("/public/proof")
            .then(({ data }) => !cancelled && setStats(data || {}))
            // Silence is the correct failure mode here. See above.
            .catch(() => {});
        return () => {
            cancelled = true;
        };
    }, []);

    const keys = ORDER.filter(
        (k) => stats?.[k] != null && (!only || only.includes(k)),
    );

    // In flight: hold the space. Resolved with nothing: say nothing.
    if (stats === null) {
        return (
            <section
                aria-hidden
                data-testid={IDS.proofReserve}
                className={`border-y border-white/10 bg-card/30 ${RESERVED} ${className}`}
            />
        );
    }
    if (!keys.length) return null;

    return (
        <section
            data-testid={IDS.proof}
            className={`border-y border-white/10 bg-card/30 ${RESERVED} ${className}`}
        >
            <div className="mx-auto flex max-w-7xl flex-wrap items-baseline justify-center gap-x-14 gap-y-6 px-6 py-10">
                {keys.map((k, i) => (
                    <Reveal
                        key={k}
                        i={i}
                        data-testid={IDS.proofFigure(k)}
                        className="text-center"
                    >
                        {/* The one place a number counts. These figures are
                            what a stranger is being asked to believe, so the
                            count draws the eye for about a third of a second
                            and then stops. */}
                        <p className="font-serif text-fluid-3xl leading-none tracking-tight">
                            <CountUp value={stats[k]} />
                        </p>
                        <p className="mt-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            {LABEL[k]}
                        </p>
                    </Reveal>
                ))}
            </div>
        </section>
    );
}

export default ProofStrip;
