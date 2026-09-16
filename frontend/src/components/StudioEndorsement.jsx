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
    // **The alpha is dropped in the light console and kept everywhere else.**
    // At 10px, `text-muted-foreground/80` measures 3.53:1 on an off-white page
    // — below AA — and 7.2:1 on the dark one, where it is doing the job it was
    // chosen for. Taking it off globally would have been the tidier rule
    // ("alpha belongs on a fill, never on ink") and it changes 681 pixels of
    // the marketing navbar, which is a surface this work is not allowed to
    // touch. So it is conditional on the theme rather than on the surface:
    // `data-theme` is only ever present inside the console.
    const base =
        "text-[10px] uppercase tracking-[0.18em] text-muted-foreground/80 " +
        "[:root[data-theme=light]_&]:text-muted-foreground " +
        className;

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
            className={base + " transition-colors duration-200 hover:text-primary-ink"}
        >
            {label}
        </a>
    );
}

export default StudioEndorsement;
