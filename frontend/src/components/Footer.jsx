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

import { CONTACT_EMAIL, FOOTER_COLUMNS, copyrightYear } from "@/lib/siteNav";
import { STUDIO_NAME, STUDIO_URL } from "@/lib/studio";
import { FOOTER as IDS } from "@/constants/testIds";
import Logo from "@/components/brand/Logo";

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
        "text-sm text-muted-foreground transition-colors duration-200 hover:text-primary";
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
            className="border-t border-border bg-card/40"
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
                            <Logo variant="horizontal" height={26} />
                        </Link>
                        <div className="mt-3">
                        </div>
                        <p className="mt-5 max-w-xs text-sm leading-relaxed text-muted-foreground">
                            Influencer marketing across India, run end to end — every
                            rate agreed in writing, the content approved before it goes
                            live, and a report at the end.
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

                <div className="mt-12 flex flex-col gap-3 border-t border-border pt-7 sm:flex-row sm:items-center sm:justify-between">
                    {/* **WeAre Studios, linked, and this overrides a note
                        that argued the other way.** The line named "WeAre
                        Monk" on the reasoning that who owns the thing is a
                        fact rather than a copy decision. The owner asked for
                        WeAre Studios directly, which settles it: the entity
                        in a copyright line is theirs to name, and the comment
                        that argued for the old string has no business
                        outliving it.

                        It also absorbs the studio credit. `StudioEndorsement`
                        used to say "A WeAre Studios offering" in six places;
                        the relationship belongs in the copyright, where
                        ownership is already being stated, rather than as a
                        standalone line repeated down the page. */}
                    <p data-testid={IDS.copyright} className="text-xs text-muted-foreground">
                        © {copyrightYear()}{" "}
                        {/* **Absent is a supported state**, as it was for the
                            endorsement this replaced: `STUDIO_URL` comes from
                            the environment because the studio's address is
                            not ours to hardcode, and an `<a href="">` is a
                            link that reloads the page. Unset, the entity is
                            still named — as text. */}
                        {STUDIO_URL ? (
                            <a
                                href={STUDIO_URL}
                                target="_blank"
                                rel="noreferrer"
                                data-testid={IDS.copyrightLink}
                                className="underline-offset-4 transition-colors duration-200 hover:text-foreground hover:underline"
                            >
                                {STUDIO_NAME}
                            </a>
                        ) : (
                            <span data-testid={IDS.copyrightLink}>{STUDIO_NAME}</span>
                        )}{" "}
                        · Bengaluru, India
                    </p>
                    <a
                        href={`mailto:${CONTACT_EMAIL}`}
                        data-testid={IDS.contact}
                        className="text-xs text-muted-foreground transition-colors duration-200 hover:text-primary"
                    >
                        {CONTACT_EMAIL}
                    </a>
                </div>
            </div>
        </footer>
    );
}

export default Footer;
