// Verified creators, campaigns run, cities — counted, never written down.
//
// A hardcoded "500+ creators" is a claim that was true on the day somebody
// typed it, on the pages whose whole job is to be believed by a stranger. So
// the figures come from `GET /public/proof`, which counts them.
//
// **Each appears only above a floor, and the whole strip disappears when there
// is nothing worth saying.** A strip reading "3 creators" is not proof, it is
// a reason to close the tab, and the honest move at that size is silence
// rather than rounding up. The floors live on the server so every surface
// agrees about what counts as sayable.
//
// It renders nothing while the request is in flight, and nothing if it fails.
// A proof strip that says "—" is worse than no proof strip.
import React, { useEffect, useState } from "react";

import { api } from "@/lib/api";
import CountUp from "@/components/marketing/CountUp";
import Reveal from "@/components/marketing/Reveal";
import { MARKETING as IDS } from "@/constants/testIds";

const LABEL = {
    creators: "verified creators",
    campaigns: "campaigns run",
    cities: "cities",
    brands: "verified brands",
};

// The order they read in, not the order the API happens to return.
const ORDER = ["creators", "campaigns", "cities", "brands"];

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
    if (!keys.length) return null;

    return (
        <section
            data-testid={IDS.proof}
            className={`border-y border-white/10 bg-card/30 ${className}`}
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
