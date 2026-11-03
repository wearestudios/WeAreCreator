// Creator step 03: the slot booked, and the address — kept with the WeAre
// team, never handed to the brand.
import React from "react";

import { CardRows, StepCardFrame } from "./StepCardFrame";

export default function StepCardBooked({ card, active, testid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <CardRows rows={card.rows} />
        </StepCardFrame>
    );
}
