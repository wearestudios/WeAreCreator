// The site footer. There wasn't one.
//
// Every marketing page ended at its closing CTA, so the only way to reach
// terms, privacy or a human was to already know the URL — and a consent
// checkbox pointing at pages nothing links to is a consent record that is
// hard to defend.
//
// Deliberately quiet: this is the bottom of the page, not a second navigation.
// Hairline rule, one column of identity and three of links, and the studio
// endorsement where it belongs — under the wordmark rather than competing
// with it.
//
// The link list comes from `lib/siteNav.js`, which the server-rendered pages
// mirror. A footer that advertises a page that moved is the specific failure
// two copies of this would produce.
import React from "react";
import { Link } from "react-router-dom";

import { StudioEndorsement } from "@/components/StudioEndorsement";
import { CONTACT_EMAIL, FOOTER_COLUMNS, copyrightYear } from "@/lib/siteNav";
import { FOOTER as IDS } from "@/constants/testIds";

/**
 * One link, routed or not.
 *
 * `/for-creators` and `/for-brands` are rendered by the backend, so they need
 * a real anchor — a <Link> is intercepted by the router and lands on the
 * SPA's catch-all, which is the trap the navbar's brand entry already
 * documents. Everything else stays a client-side navigation.
 */
function FooterLink({ link }) {
    const className =
        "text-sm text-muted-foreground transition-colors duration-200 hover:text-ember-500";
    const testid = IDS.link(link.to);

    if (link.external) {
        return (
            <a href={link.to} data-testid={testid} className={className}>
                {link.label}
            </a>
        );
    }
    return (
        <Link to={link.to} data-testid={testid} className={className}>
            {link.label}
        </Link>
    );
}

export function Footer() {
    return (
        <footer
            data-testid={IDS.root}
            className="border-t border-white/10 bg-card/40"
        >
            <div className="mx-auto max-w-7xl px-6 py-14 md:py-16">
                <div className="grid gap-10 md:grid-cols-12">
                    {/* Identity. The wordmark matches the navbar's exactly —
                        a footer that spells the brand differently from the
                        header reads as a different site. */}
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
                            <StudioEndorsement testid={IDS.studio} />
                        </div>
                        <p className="mt-5 max-w-xs text-sm leading-relaxed text-muted-foreground">
                            Creator campaigns with the rate agreed in writing, the
                            content approved before it goes live, and a report at the
                            end.
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

export default Footer;
