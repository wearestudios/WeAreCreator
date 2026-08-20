// Choosing what a brief asks for.
//
// **A row per format, and the quantity is the whole control.** Zero means "not
// asking for this", so there is no separate checkbox to fall out of step with
// the number beside it — a ticked row with a quantity of nothing is a state
// this cannot reach because it does not exist.
//
// The steppers are the primary way in because this is filled on a phone as
// often as on a laptop, and a number input on a phone opens a keyboard to
// change 1 to 2. The field is still typable: three stories is two taps and
// twelve is not.
import React from "react";
import { Minus, Plus } from "lucide-react";

import {
    DELIVERABLE_KEYS,
    DELIVERABLE_TYPES,
    MAX_DELIVERABLE_QUANTITY,
    deliverableLabel,
} from "@/lib/deliverables";

/** What the picker holds: `{reel: 1, story: 3}` — absent or 0 is "no". */
export const emptyDeliverables = () => ({});

/** The wire shape, from the picker's own. */
export const toDeliverableItems = (counts) =>
    DELIVERABLE_KEYS.filter((k) => Number(counts?.[k]) > 0).map((k) => ({
        type: k,
        quantity: Math.min(MAX_DELIVERABLE_QUANTITY, Math.floor(Number(counts[k]))),
    }));

/** The picker's shape, from what the API returned — for the edit round trip. */
export const fromDeliverableItems = (items) => {
    const out = {};
    for (const row of items || []) {
        if (!DELIVERABLE_KEYS.includes(row?.type)) continue;
        const qty = Math.floor(Number(row?.quantity));
        if (Number.isFinite(qty) && qty > 0) out[row.type] = qty;
    }
    return out;
};

export function DeliverablePicker({ value, onChange, testid = "deliverable-picker" }) {
    const counts = value || {};

    const set = (key, next) => {
        const qty = Math.max(0, Math.min(MAX_DELIVERABLE_QUANTITY, Math.floor(next || 0)));
        const out = { ...counts };
        // Dropped rather than kept at zero, so the object is only ever what
        // the brief actually asks for and `toDeliverableItems` has nothing to
        // filter that a reader would have to know about.
        if (qty === 0) delete out[key];
        else out[key] = qty;
        onChange(out);
    };

    const chosen = toDeliverableItems(counts);

    return (
        <div data-testid={testid}>
            <ul className="divide-y divide-white/10 overflow-hidden rounded-md border border-white/10 bg-background/40">
                {DELIVERABLE_KEYS.map((key) => {
                    const qty = Number(counts[key]) || 0;
                    return (
                        <li
                            key={key}
                            data-testid={`${testid}-row-${key}`}
                            className="flex items-center gap-4 px-4 py-3"
                        >
                            <span
                                className={
                                    "min-w-0 flex-1 text-sm " +
                                    (qty > 0 ? "" : "text-muted-foreground")
                                }
                            >
                                {DELIVERABLE_TYPES[key]}
                            </span>
                            <div className="flex flex-none items-center gap-1">
                                <button
                                    type="button"
                                    aria-label={`One fewer ${DELIVERABLE_TYPES[key]}`}
                                    disabled={qty === 0}
                                    onClick={() => set(key, qty - 1)}
                                    data-testid={`${testid}-minus-${key}`}
                                    className="flex h-11 w-11 items-center justify-center rounded-md border border-white/10 text-muted-foreground transition-colors duration-150 hover:border-white/25 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 disabled:opacity-30 md:h-9 md:w-9"
                                >
                                    <Minus className="h-4 w-4" />
                                </button>
                                <input
                                    type="text"
                                    inputMode="numeric"
                                    aria-label={`How many ${DELIVERABLE_TYPES[key]}`}
                                    value={qty === 0 ? "" : String(qty)}
                                    placeholder="0"
                                    onChange={(e) =>
                                        set(key, Number(e.target.value.replace(/\D/g, "")))
                                    }
                                    data-testid={`${testid}-input-${key}`}
                                    className="h-11 w-14 rounded-md border border-white/10 bg-background/60 text-center text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 md:h-9"
                                />
                                <button
                                    type="button"
                                    aria-label={`One more ${DELIVERABLE_TYPES[key]}`}
                                    disabled={qty >= MAX_DELIVERABLE_QUANTITY}
                                    onClick={() => set(key, qty + 1)}
                                    data-testid={`${testid}-plus-${key}`}
                                    className="flex h-11 w-11 items-center justify-center rounded-md border border-white/10 text-muted-foreground transition-colors duration-150 hover:border-white/25 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 disabled:opacity-30 md:h-9 md:w-9"
                                >
                                    <Plus className="h-4 w-4" />
                                </button>
                            </div>
                        </li>
                    );
                })}
            </ul>

            {/* The sentence the campaign will carry, as it is being built. The
                server derives exactly this string, so what the brand reads
                here is what a creator reads on the brief. */}
            <p
                data-testid={`${testid}-summary`}
                className="mt-2 text-xs text-muted-foreground"
            >
                {chosen.length === 0
                    ? "Pick at least one — a brief has to say what it's asking for."
                    : `This brief asks for ${chosen.map(deliverableLabel).join(" · ")}.`}
            </p>
        </div>
    );
}

export default DeliverablePicker;
