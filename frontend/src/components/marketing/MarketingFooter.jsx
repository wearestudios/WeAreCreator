// The footer, for the marketing site only — the navy closing band with the
// beam (`components/ui/beam-wordmark-footer.jsx`).
//
// **No wordmark.** The giant cropped "WeAre" under the columns is gone: the
// logo in the lead already names the site, and a second, page-wide name under
// it was the footer saying it twice. The component's wordmark is optional and
// this passes none, so nothing is measured or fitted here at all — the beam,
// the glow and the accent rule are what is left, on the navy ground.
//
// **A variant, not an edit.** `components/Footer.jsx` stays exactly as it is
// for Legal, Campaigns and CampaignDetail; nothing here reaches into it.
//
// The link list is not duplicated: `lib/siteNav.js` is the one definition,
// mirrored by `FOOTER_COLUMNS` in `server.py`, which builds the sitemap from
// it. Two lists is how a footer advertises a page that moved.
//
// No social icons: there are no real profile URLs in the repository. When
// there are, they belong in `lib/siteNav` beside the columns, not typed here.
import React from "react";
import { Link } from "react-router-dom";

import BeamWordmarkFooter from "@/components/ui/beam-wordmark-footer";
import Logo from "@/components/brand/Logo";
import { FOOTER as IDS } from "@/constants/testIds";
import { WHATSAPP_HREF } from "@/content/marketing";
import { CONTACT_EMAIL, FOOTER_COLUMNS, copyrightYear } from "@/lib/siteNav";
import { STUDIO_NAME, STUDIO_URL } from "@/lib/studio";
import { EVENTS, track } from "@/lib/track";

// The brand tokens, never literals: the navy ground (`--brand-navy`), ink and
// muted are white at 90% and 60%, the brand red accent (`--brand-red`). Measured
// on the ground: ink 15.6:1, muted 7.0:1, the accent 4.9:1 — every word
// somebody has to read passes AA.
const PALETTE = {
    ground: "hsl(var(--brand-navy))",
    ink: "hsl(var(--brand-white) / 0.9)",
    muted: "hsl(var(--brand-white) / 0.6)",
    accent: "hsl(var(--brand-red))",
};

const COLUMNS = FOOTER_COLUMNS.map((col) => ({
    title: col.heading,
    // `external` marks a destination the router must not handle: `/work` is
    // server-rendered by the backend, so it stays a plain <a>.
    links: col.links.map((l) => ({ label: l.label, href: l.to, external: !!l.external })),
}));

const CONTACT = [
    { label: CONTACT_EMAIL, href: `mailto:${CONTACT_EMAIL}`, external: true, id: IDS.contact },
    { label: "Talk to us on WhatsApp", href: WHATSAPP_HREF, external: true, id: IDS.whatsapp },
];

const TEST_IDS = {
    root: IDS.root,
    copyright: IDS.copyright,
    company: IDS.copyrightLink,
    link: (l) => IDS.link(l.href),
    contact: (line) => line.id,
};

const renderLink = (link, props) => <Link to={link.href} {...props} />;

// The footer reports its own clicks, with where they came from; the root
// carries `data-track-self` so the analytics gate's delegated listener does
// not count the same press a second time. A WhatsApp link is reported as
// "whatsapp", never as the number inside it.
const onLinkClick = (link) =>
    track(EVENTS.ctaClick, {
        location: "footer",
        label: link.label,
        href: link.href === WHATSAPP_HREF ? "whatsapp" : link.href,
    });

export function MarketingFooter() {
    return (
        <BeamWordmarkFooter
            className="font-sans"
            columns={COLUMNS}
            // The copyright names WeAre Studios, which overrides an older note
            // that argued for the old owner name: the entity in a copyright line is
            // the owner's to name. It also absorbs the studio credit — the
            // `StudioEndorsement` line is gone, because ownership is already
            // stated here.
            companyName={STUDIO_NAME}
            // Absent is a supported state: `STUDIO_URL` comes from the
            // environment, and an `<a href="">` reloads the page, so unset
            // renders the name as text.
            companyHref={STUDIO_URL || undefined}
            year={copyrightYear()}
            contactLines={CONTACT}
            lead={
                <>
                    <Link to="/" data-testid={IDS.wordmark} className="inline-flex" onClick={() => onLinkClick({ label: "Home", href: "/" })}>
                        <Logo variant="horizontal" height={26} tone="white" />
                    </Link>
                    <p className="mt-5 max-w-xs">
                        Influencer marketing across India, run end to end — casting, rates, the shoot and the
                        report.
                    </p>
                </>
            }
            palette={PALETTE}
            beamStrength={0.7}
            renderLink={renderLink}
            onLinkClick={onLinkClick}
            testIds={TEST_IDS}
            rootProps={{ "data-track-self": "" }}
        />
    );
}

export default MarketingFooter;
