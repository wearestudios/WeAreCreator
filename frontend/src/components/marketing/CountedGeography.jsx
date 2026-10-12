// Geography, counted rather than typed.
//
// The pages used to carry "The network runs deepest in Bengaluru" as a string
// literal. It was true when somebody wrote it, and a sentence in a `COPY`
// block is a sentence nobody re-checks — so as the operation goes national the
// one failure that matters is the copy getting ahead of the supply. A claim a
// visitor can go and disprove is worse than a smaller claim.
//
// So the city is rendered from `GET /public/proof`, the same endpoint and the
// same floor gate as the figures in `ProofStrip`. `_FORBIDDEN_MARKETING_PHRASES`
// still bans "pan-India", "every city" and "nationwide" **as literals**, which
// is the half of the old rule worth keeping: the mechanism changed from "do not
// say this" to "do not say it unless you counted it", and a hardcoded national
// claim is still a hardcoded claim.
//
// **Below the floor it renders nothing at all.** `_platform_proof` returns `{}`
// as a set, so a page cannot name a city while the counts that would give that
// name a denominator are absent — "we are deepest in Kochi" with no figures
// beside it is a smaller claim than silence, not a bigger one.
//
// A render prop rather than a fixed sentence: the two call sites want different
// shapes (a section title and line on `/for-brands`, one labelled point on
// `/why-weare`), and the thing worth centralising is *when there is a city to
// name*, not how it reads.
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

/**
 * The deepest-supply city, or `null`.
 *
 * Three states, and they are genuinely different: `undefined` is in flight,
 * `null` is resolved-with-nothing (below the floor, or a failed request), and a
 * string is an answer. A caller that collapsed the first two would render its
 * absent branch on every first paint.
 */
export function useDeepestCity() {
    const [city, setCity] = useState(undefined);

    useEffect(() => {
        let cancelled = false;
        api.get("/public/proof")
            .then(({ data }) => {
                if (!cancelled) setCity(data?.deepest_city || null);
            })
            // Silence is the right failure mode, the same as the proof strip's.
            // A geography line reading "—" is worse than no geography line.
            .catch(() => {
                if (!cancelled) setCity(null);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    return city;
}

/**
 * Renders `children(city)` once there is a city to name, and nothing before.
 *
 * Nothing in flight and nothing when absent, which are drawn the same way on
 * purpose: both mean "there is no counted claim to make yet", and holding a
 * section open for one that may never arrive would be a permanent gap standing
 * in for copy that is not coming.
 */
export default function CountedGeography({ children }) {
    const city = useDeepestCity();
    if (!city) return null;
    return children(city);
}
