// Creator step 01: two briefs in the feed, each with its niche and what it
// pays — a fee, or a barter chip.
import React from "react";

import Chip from "./Chip";
import { StepCardFrame } from "./StepCardFrame";

export default function StepCardCampaigns({ card, active, testid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <ul className="space-y-2 px-4 py-3">
                {card.rows.map((row) => (
                    <li key={row.title} className="rounded-[10px] border border-brand-white/10 px-3 py-2.5">
                        <p className="font-serif text-[0.9375rem] text-brand-white/90">{row.title}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2">
                            <span className="rounded-pill border border-brand-white/15 px-2 py-0.5 text-[0.6875rem] text-brand-white/65">
                                {row.niche}
                            </span>
                            <Chip>{row.pay}</Chip>
                        </div>
                    </li>
                ))}
            </ul>
        </StepCardFrame>
    );
}
