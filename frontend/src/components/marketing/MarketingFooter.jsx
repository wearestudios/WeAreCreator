// The footer, for the marketing site only.
//
// **A variant, not an edit.** `components/Footer.jsx` stays exactly as it is
// for Legal, Campaigns and CampaignDetail. This one differs in one way that
// matters: every link is a `<Link>`, because every destination it names is a
// route the SPA owns, and it carries the hover warm the rest of the marketing
// site uses.
//
// The link list itself is not duplicated — `lib/siteNav.js` is still the one
// definition, mirrored by `FOOTER_COLUMNS` in `server.py`, which builds the
// sitemap from it. Two footers with two lists is how one of them ends up
// advertising a page that moved.
import React from "react";
import { Link } from "react-router-dom";

import { StudioEndorsement } from "@/components/StudioEndorsement";
import { CONTACT_EMAIL, FOOTER_COLUMNS, copyrightYear } from "@/lib/siteNav";
import { FOOTER as IDS, LANDING_STUDIO as STUDIO_IDS } from "@/constants/testIds";

const LINK =
    "text-sm text-muted-foreground transition-colors duration-200 hover:text-ember-500";

function FooterLink({ link }) {
    const testid = IDS.link(link.to);
    // `external` marks a destination the router must not handle — today only
    // the mailto.
    if (link.external) {
        return (
            <a href={link.to} data-testid={testid} className={LINK}>
                {link.label}
            </a>
        );
    }
    return (
        <Link to={link.to} data-testid={testid} className={LINK}>
            {link.label}
        </Link>
    );
}

export function MarketingFooter() {
    return (
        <footer
            data-testid={IDS.root}
            className="border-t border-white/10 bg-card/40"
        >
            <div className="mx-auto max-w-7xl px-6 py-14 md:py-16">
                <div className="grid gap-10 md:grid-cols-12">
                    <div className="md:col-span-5">
                        <Link
                            to="/"
                            data-testid={IDS.wordmark}
                            className="inline-flex items-center gap-2.5"
                        >
                            <span className="grid h-7 w-7 place-items-center rounded-md bg-ember-500 font-serif text-sm text-black">
                                W
                            </span>
                            <span className="font-serif text-lg leading-none">
                                WeAre <span className="text-ember-500">Creators</span>
                            </span>
                        </Link>
                        <div className="mt-3">
                            <StudioEndorsement testid={STUDIO_IDS.footer} />
                        </div>
                        <p className="mt-5 max-w-xs text-sm leading-relaxed text-muted-foreground">
                            Creator campaigns, handled properly.
                        </p>
                    </div>

                    <nav
                        aria-label="Footer"
                        className="grid grid-cols-2 gap-8 sm:grid-cols-4 md:col-span-7"
                    >
                        {FOOTER_COLUMNS.map((col) => (
                            <div key={col.heading}>
                                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/70">
                                    {col.heading}
                                </p>
                                <ul className="mt-4 space-y-3">
                                    {col.links.map((link) => (
                                        <li key={link.to}>
                                            <FooterLink link={link} />
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </nav>
                </div>

                <div className="mt-12 flex flex-col gap-3 border-t border-white/10 pt-7 sm:flex-row sm:items-center sm:justify-between">
                    {/* "WeAre Monk" is the entity that was already in the
                        copyright line. Who owns the thing is a fact rather
                        than a copy decision, so it is carried over verbatim
                        rather than re-branded to match the product name. */}
                    <p data-testid={IDS.copyright} className="text-xs text-muted-foreground">
                        © {copyrightYear()} WeAre Monk · Bengaluru, India
                    </p>
                    <a
                        href={`mailto:${CONTACT_EMAIL}`}
                        data-testid={IDS.contact}
                        className="text-xs text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                    >
                        {CONTACT_EMAIL}
                    </a>
                </div>
            </div>
        </footer>
    );
}

export default MarketingFooter;
