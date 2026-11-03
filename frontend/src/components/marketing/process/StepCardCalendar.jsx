// Brand step 03: four days of slots, two booked, and a delivery that landed.
import React from "react";

import { StepCardFrame } from "./StepCardFrame";

export default function StepCardCalendar({ card, active, testid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <ol className="grid grid-cols-4 gap-2 px-4 py-3">
                {card.days.map((day) => (
                    <li
                        key={day.n}
                        className={`rounded-[10px] border px-2 py-2 text-center ${
                            day.booked ? "border-brand-red/40 bg-brand-red/10" : "border-brand-white/10"
                        }`}
                    >
                        <p className="text-[0.6875rem] text-brand-white/65">{day.d}</p>
                        <p className="font-serif text-[1.125rem] tabular-nums text-brand-white/90">{day.n}</p>
                        <p className="mt-0.5 h-4 text-[0.6875rem] tabular-nums text-brand-white">
                            {day.booked ? day.booked : ""}
                        </p>
                    </li>
                ))}
            </ol>
            <p className="border-t border-brand-white/[0.06] px-4 py-2.5 text-[0.8125rem] text-brand-white/90">
                {card.delivered}
            </p>
        </StepCardFrame>
    );
}
