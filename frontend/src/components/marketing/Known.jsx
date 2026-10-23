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
// is not in the production bundle at all.
//
// **The test is written out here rather than imported** from
// `content/photoSlots.js`, where the same expression lives as `SHOW_BRIEFS`.
// The build substitutes `process.env.*` with literals in each module, so an
// expression in *this* module folds to `false` and the minifier drops the
// branch; an imported constant is a reference to another module, which it
// does not fold — measured: imported, the marker's text was in the bundle.
import React from "react";

import { known } from "@/content/marketing";

const SHOW_MISSING =
    process.env.NODE_ENV !== "production" || process.env.REACT_APP_VERCEL_ENV === "preview";

/**
 * @param {{ value: any, name?: string, children: (value: any) => React.ReactNode }} props
 */
export default function Known({ value, name, children }) {
    if (known(value)) return children(value);
    return SHOW_MISSING ? (
        <span
            data-content-missing={name || "unnamed"}
            className="inline-block rounded border border-dashed border-tint/30 px-2 py-1 text-meta text-muted-foreground"
        >
            Not set yet: {name || "a value"} (hidden in production)
        </span>
    ) : null;
}
