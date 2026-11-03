// Brand step 04: the content, the revision count, and the two answers. The
// buttons are drawings of buttons — nothing here can be pressed.
import React from "react";

import { StepCardFrame } from "./StepCardFrame";

export default function StepCardApprove({ card, active, testid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <div className="flex gap-4 px-4 py-3">
                <div className="grid aspect-[9/16] w-16 shrink-0 place-items-end rounded-[10px] border border-brand-white/10 bg-brand-white/[0.06] p-1.5">
                    <span className="text-[0.625rem] text-brand-white/65">{card.thumb}</span>
                </div>
                <div className="flex min-w-0 flex-1 flex-col justify-between gap-3">
                    <p className="text-[0.8125rem] text-brand-white/90">{card.revisions}</p>
                    <div aria-hidden className="flex flex-wrap gap-2">
                        <span className="rounded-[10px] bg-brand-red px-3 py-1.5 text-[0.75rem] font-medium text-brand-white">
                            {card.approve}
                        </span>
                        <span className="rounded-[10px] border border-brand-white/20 px-3 py-1.5 text-[0.75rem] text-brand-white/90">
                            {card.changes}
                        </span>
                    </div>
                </div>
            </div>
        </StepCardFrame>
    );
}
