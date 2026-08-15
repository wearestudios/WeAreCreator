// "A WeAre Studios offering".
//
// WeAre Creators is an offering of WeAre Studios and shares the studio's site,
// so the studio is credited — an endorsement, not a co-brand. Creators keeps
// the wordmark, the ember accent and the type; the studio gets one small line
// beside the nav logo and one in the footer, and nothing else.
//
// It lives here rather than in Landing.jsx because the navbar needs it too,
// and a shared component importing a page would be the wrong way round.
import React from "react";
import { STUDIO_NAME, STUDIO_URL } from "@/lib/studio";

export function StudioEndorsement({ testid, className = "" }) {
    const label = `A ${STUDIO_NAME} offering`;
    const base =
        "text-[10px] uppercase tracking-[0.18em] text-muted-foreground/80 " + className;

    // A link only when the studio URL is configured. A line of text that does
    // nothing when clicked beats one that navigates nowhere, and inventing a
    // domain to fill the gap would be worse than both.
    if (!STUDIO_URL) {
        return (
            <span data-testid={testid} className={base}>
                {label}
            </span>
        );
    }
    return (
        <a
            href={STUDIO_URL}
            target="_blank"
            rel="noreferrer"
            data-testid={testid}
            className={base + " transition-colors duration-200 hover:text-ember-500"}
        >
            {label}
        </a>
    );
}

export default StudioEndorsement;
