// Creator step 04: the upload, the revision count, approved.
import React from "react";
import { Check, Upload } from "lucide-react";

import Chip from "./Chip";
import { StepCardFrame } from "./StepCardFrame";

export default function StepCardSubmit({ card, active, testid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <div className="flex items-center gap-3 px-4 py-3">
                <span
                    aria-hidden
                    className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-brand-white/15 text-brand-white/90"
                >
                    <Upload className="h-3.5 w-3.5" />
                </span>
                <p className="min-w-0 flex-1 truncate text-[0.8125rem] text-brand-white/90">{card.file}</p>
                <Chip>
                    <Check aria-hidden className="h-3 w-3" />
                    {card.chip}
                </Chip>
            </div>
            <p className="border-t border-brand-white/[0.06] px-4 py-2.5 text-[0.8125rem] text-brand-white/65">
                {card.revisions}
            </p>
        </StepCardFrame>
    );
}
