// The marketing shell: the page wrapper every public page sits in, and the
// eyebrow the older marketing components still use.
//
// **This used to be the whole marketing kit** — hero, text-and-image section,
// value props, steps, two paths and a closing band — for five pages that each
// argued in the same shape. Home, /brands and /creators were rebuilt on their
// own furniture in `SiteParts.jsx`, which reads every word from
// `content/marketing.js`; /how-it-works and /why-weare were folded into
// /brands. Nothing used the old primitives after that, so they went rather
// than staying as a second way to build a page.
import React from "react";

import MarketingNavbar from "@/components/marketing/MarketingNavbar";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import PageMeta from "@/components/marketing/PageMeta";

/** Uppercase, tiny, wide — the design guidelines' overline rule. */
export function Eyebrow({ children, className = "" }) {
    return (
        <p className={`text-xs uppercase tracking-[0.2em] text-primary ${className}`}>
            {children}
        </p>
    );
}

/**
 * The page shell: meta, the marketing navbar, the content, the marketing
 * footer.
 *
 * Both bars are marketing variants. The shared `Navbar` and `Footer` are on
 * authenticated surfaces and stay exactly as they are.
 */
export function MarketingPage({ testid, title, description, path, children }) {
    return (
        <div
            data-testid={testid}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <PageMeta title={title} description={description} path={path} />
            <MarketingNavbar />
            <main>{children}</main>
            <MarketingFooter />
        </div>
    );
}
