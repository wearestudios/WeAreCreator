// Render a value the content module may not have yet — or nothing.
//
// `content/marketing.js` holds a value nobody knows as `null`, and the rule is
// that `null` hides its element: the line, the card, the FAQ item, the
// section. This is that rule as a component, so a page cannot render a
// maybe-null value any other way by accident.
//
//   <Known value={FACTS.verifiedCreatorCount}>{(n) => <p>{n} verified</p>}</Known>
//
// **In development and on a Vercel preview** a missing value draws a small
// dashed marker naming what is missing, so the people building the page can
// see the hole. **In production it draws nothing**, and the marker's markup
// is not in the production bundle at all: the branch is written inline behind
// `SHOW_BRIEFS`, which the build folds to `false`.
import React from "react";

import { SHOW_BRIEFS } from "@/content/photoSlots";
import { known } from "@/content/marketing";

/**
 * @param {{ value: any, name?: string, children: (value: any) => React.ReactNode }} props
 */
export default function Known({ value, name, children }) {
    if (known(value)) return children(value);
    return SHOW_BRIEFS ? (
        <span
            data-content-missing={name || "unnamed"}
            className="inline-block rounded border border-dashed border-tint/30 px-2 py-1 text-meta text-muted-foreground"
        >
            Not set yet: {name || "a value"} (hidden in production)
        </span>
    ) : null;
}
