// Brand step 02: applicants, one shortlisted, and the contact details a
// brand never receives.
import React from "react";
import { Lock } from "lucide-react";

import Chip from "./Chip";
import { Monogram, StepCardFrame } from "./StepCardFrame";

export default function StepCardShortlist({ card, active, testid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <ul className="divide-y divide-brand-white/[0.06]">
                {card.rows.map((row) => (
                    <li key={row.handle} className="flex items-center gap-3 px-4 py-2.5">
                        <Monogram handle={row.handle} />
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-[0.8125rem] text-brand-white/90">{row.handle}</p>
                            <p className="text-[0.75rem] text-brand-white/65">
                                {row.niche} · {row.followers}
                            </p>
                        </div>
                        {row.chip ? <Chip>{row.chip}</Chip> : null}
                    </li>
                ))}
            </ul>
            <p className="flex items-center gap-1.5 border-t border-brand-white/[0.06] px-4 py-2.5 text-[0.75rem] text-brand-white/65">
                <Lock aria-hidden className="h-3.5 w-3.5" />
                {card.lock}
            </p>
        </StepCardFrame>
    );
}
