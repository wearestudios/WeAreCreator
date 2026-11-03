// /about — who built this, reached from the footer only.
//
// "Who built it" was a homepage section. It is the studio's story rather than
// the product's argument, so it moved here when the homepage was cut to the
// hero slider and how it works: somebody weighing up the product is not sent
// away from it to read about us, and somebody who wants to is one link away.
// That is also why it is in `FOOTER_COLUMNS` and not in `MARKETING_LINKS`.
//
// Three sections and one ask:
//
//   - who built it — the heading, the scroll-inked sentence and the drawing
//     it had on home (`why-production`)
//   - the studio — what WeAre Studios does for brands, its name linking out
//     when `STUDIO_URL` is set and plain text otherwise
//   - the tool — that this platform is the one the studio built to run its
//     own campaigns, and the one WhatsApp ask
//
// **Every word is in `ABOUT` in `content/marketing.js`**, held to its own
// word budget, and every claim is one the site already makes. **No person is
// named and no client is named.**
import React from "react";

import Illustration from "@/components/marketing/Illustration";
import { MarketingPage } from "@/components/marketing/Sections";
import { FillText, Rise } from "@/components/marketing/primitives";
import { Band, Cta, SectionHead, SectionRule, Wrap } from "@/components/marketing/SiteParts";
import { MARKETING as IDS } from "@/constants/testIds";
import { ABOUT, ASK } from "@/content/marketing";
import { STUDIO_NAME, STUDIO_URL } from "@/lib/studio";

/** The studio's name, linking out when there is somewhere to link to. An
 * unset `STUDIO_URL` renders text: an `<a href="">` reloads the page. */
function StudioName() {
    if (!STUDIO_URL) return STUDIO_NAME;
    return (
        <a
            href={STUDIO_URL}
            target="_blank"
            rel="noopener noreferrer"
            data-testid={IDS.aboutStudioLink}
            className="text-foreground underline decoration-border underline-offset-4 transition-colors duration-200 hover:decoration-foreground"
        >
            {STUDIO_NAME}
        </a>
    );
}

export default function About() {
    const { meta, clients, studio, tool } = ABOUT;
    return (
        <MarketingPage testid={IDS.about} title={meta.title} description={meta.description} path="/about">
            <Band ground="page" track="about-who-built-it" testid={IDS.aboutClients}>
                <Wrap className="pb-20 pt-10 md:pb-28 md:pt-14">
                    <SectionRule label={clients.label} />
                    <Rise>
                        <h1 className="mkt-h1 mt-8 max-w-4xl text-heading md:mt-10">{clients.title}</h1>
                    </Rise>
                    <div className="mt-12 grid gap-10 md:mt-16 lg:grid-cols-12 lg:items-center lg:gap-16">
                        <div data-testid={IDS.aboutFill} className="lg:col-span-7">
                            <FillText text={clients.fill} className="mkt-h2 text-heading" />
                        </div>
                        <Illustration name="why-production" eager className="order-first lg:order-none lg:col-span-5" />
                    </div>
                </Wrap>
            </Band>

            <Band ground="tint" track="about-studio" testid={IDS.aboutStudio}>
                <Wrap className="py-20 md:py-28">
                    <SectionHead label={studio.label} title={studio.title} />
                    <p className="mkt-lead mt-6 max-w-2xl text-muted-foreground">
                        <StudioName /> {studio.line}
                    </p>
                </Wrap>
            </Band>

            <Band ground="page" track="about-tool" testid={IDS.aboutTool}>
                <Wrap className="py-20 md:py-28">
                    <SectionHead label={tool.label} title={tool.title} />
                    <p className="mkt-lead mt-6 max-w-2xl text-muted-foreground">{tool.line}</p>
                    <Cta ask={ASK.talkWhatsapp} testid={IDS.aboutAsk} className="mt-10" />
                </Wrap>
            </Band>
        </MarketingPage>
    );
}
