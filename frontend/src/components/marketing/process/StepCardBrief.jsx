// Brand step 01: a brief, as the brand's form would read it back.
import React from "react";

import { CardRows, StepCardFrame } from "./StepCardFrame";

export default function StepCardBrief({ card, active, testid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <p className="px-4 pt-3 font-serif text-[1.0625rem] text-brand-white/90">{card.title}</p>
            <div className="pt-1">
                <CardRows rows={card.rows} />
            </div>
        </StepCardFrame>
    );
}
