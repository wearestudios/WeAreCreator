// Creator step 05: the payout — the fee agreed, the same figure paid.
import React from "react";

import { CardRows, StepCardFrame } from "./StepCardFrame";

export default function StepCardPayout({ card, active, testid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <CardRows rows={card.rows} />
        </StepCardFrame>
    );
}
