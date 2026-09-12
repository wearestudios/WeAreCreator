// What this platform is doing for you.
//
// **Retention, not a threat**, and the framing is the whole design. The rule
// about taking work off-platform has an account-ending consequence attached
// to it, and a panel that led with that on somebody's own home page would
// read as a warning to a creator who has done nothing. This is the same fact
// from the other end: a creator weighing up a direct offer is weighing it
// against exactly this list, whether or not anybody has written it down for
// them — and until now nobody had.
//
// So: no mention of removal, no mention of the rule, no "don't". The clause
// itself is read at signup and again in the terms frozen at acceptance, which
// are the two places somebody is actually agreeing to something.
//
// The content comes from the server (`PLATFORM_PROTECTIONS`), with the
// mirrored copy in `lib/platformTerms.js` as the fallback — one wording, so
// the thing offered here and the thing the terms describe cannot drift.
import React from "react";
import { ShieldCheck } from "lucide-react";

import { CIRCUMVENTION as IDS } from "@/constants/testIds";
import { PLATFORM_PROTECTIONS } from "@/lib/platformTerms";

export default function PlatformProtections({ protections }) {
    const rows = protections?.length ? protections : PLATFORM_PROTECTIONS;
    if (!rows.length) return null;

    return (
        <section data-testid={IDS.protections}>
            <p className="flex items-center gap-1.5 text-xs uppercase tracking-[0.2em] text-ember-500">
                <ShieldCheck aria-hidden="true" className="h-3.5 w-3.5" />
                What you get here
            </p>
            <h2 className="mt-3 font-serif text-fluid-2xl leading-tight">
                Every brief on this platform comes with the same five things
            </h2>

            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {rows.map((p) => (
                    <div
                        key={p.key}
                        data-testid={IDS.protection(p.key)}
                        className="rounded-lg border border-white/10 bg-card p-5"
                    >
                        <p className="text-sm font-medium text-foreground">{p.title}</p>
                        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                            {p.detail}
                        </p>
                    </div>
                ))}
            </div>
        </section>
    );
}
