import { clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * `tailwind-merge`, told about this project's type scale.
 *
 * Out of the box it does not know `text-meta`, `text-body`, `text-label` or
 * any of the other font-size tokens in `tailwind.config.js`, so it read them
 * as text *colours* — and a colour and a "colour" conflict, so the later one
 * won. A `Button` at `size="sm"` (which carries `text-meta`) therefore lost
 * its variant's `text-primary-foreground`, and a navy button drew its label
 * in navy. Naming the sizes puts them in the font-size group, where they
 * conflict with each other and with nothing else.
 */
const SIZE_TOKENS = [
    "eyebrow", "label", "meta", "body", "body-lg", "h1", "h2", "h3",
    "fluid-2xl", "fluid-3xl", "fluid-4xl", "fluid-5xl", "fluid-5xl-wide",
    "fluid-6xl", "fluid-6xl-wide", "fluid-hero",
];

const twMerge = extendTailwindMerge({
    extend: {
        classGroups: {
            "font-size": [{ text: SIZE_TOKENS }],
        },
    },
});

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
