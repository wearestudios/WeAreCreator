// The family handshake: the closing band on every marketing page.
//
// Full-bleed studio coral, white type, a black CTA block. **It is the only
// place the studio palette appears on the whole site** — everything above it
// is our dark ground with the ember accent. A colour used twice is a co-brand;
// used once, at the moment the page stops selling and starts asking, it reads
// as a signature.
//
// What is inherited is the confidence and the motion — a field of flat colour,
// poster type, one block to press. Not the studio's copy, not its photographs,
// not its logo treatment. Borrowing those would be putting somebody else's
// page at the bottom of ours.
//
// The colour lives in `lib/studioPalette.js`, once, with a note that the exact
// hex still needs the brand value. It is applied as an inline style rather
// than a Tailwind token because adding one to `tailwind.config.js` would put
// the studio's palette in reach of every authenticated screen in the app,
// which is precisely what "the only place" is supposed to prevent.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import Reveal from "@/components/marketing/Reveal";
import { StudioEndorsement } from "@/components/StudioEndorsement";
import { CORAL, CORAL_DEEP, CORAL_INK } from "@/lib/studioPalette";
import { MARKETING as IDS } from "@/constants/testIds";

/**
 * The CTA block. Sharp-cornered and black on the coral — the one control on
 * the site that is not a pill, because on this field a pill reads as a button
 * borrowed from the page above rather than part of the band.
 */
function HandshakeCta({ to, label, testid }) {
    return (
        <Link
            to={to}
            data-testid={testid}
            style={{ backgroundColor: CORAL_INK }}
            className="group inline-flex min-h-[3.5rem] items-center gap-3 rounded-md px-8 text-base text-white transition-transform duration-200 hover:-translate-y-0.5 motion-reduce:transform-none motion-reduce:transition-none"
        >
            {label}
            <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1 motion-reduce:transform-none" />
        </Link>
    );
}

/**
 * @param {string} title  poster-scale, white
 * @param {string} line   one supporting line, still inside the copy budget
 * @param {object} cta    `{ to, label, testid }` — one ask, or none
 * @param {node}   children  for the pages that route instead of asking
 */
export function HandshakeBand({ title, line, cta, children }) {
    return (
        <section
            data-testid={IDS.handshake}
            style={{ backgroundColor: CORAL }}
            className="relative overflow-hidden"
        >
            {/* A single deeper wash off one corner, so the field has a
                direction without becoming a gradient background. */}
            <div
                aria-hidden
                className="pointer-events-none absolute -left-40 -top-40 h-[560px] w-[560px] rounded-full opacity-40 blur-[140px]"
                style={{ backgroundColor: CORAL_DEEP }}
            />

            <div className="relative mx-auto max-w-7xl px-6 py-20 md:py-28">
                <Reveal>
                    <h2
                        className="max-w-3xl font-serif text-white"
                        // Poster scale, a step below the hero — the band is the
                        // second-loudest thing on the page and must not argue
                        // with the first.
                        style={{ fontSize: "clamp(2.25rem, 6.5vw, 4.5rem)", lineHeight: 0.98 }}
                    >
                        {title}
                    </h2>
                </Reveal>
                <Reveal i={1}>
                    <p className="mt-6 max-w-xl text-base leading-relaxed text-white/85 md:text-lg">
                        {line}
                    </p>
                </Reveal>

                {cta ? (
                    <Reveal i={2} className="mt-10">
                        <HandshakeCta {...cta} />
                    </Reveal>
                ) : null}
                {children ? <div className="mt-10">{children}</div> : null}

                <Reveal i={3} className="mt-14 border-t pt-6" style={{ borderColor: "rgba(255,255,255,0.25)" }}>
                    {/* The endorsement, in the one place it is not a footnote.
                        Inverted for the field rather than restyled — same
                        component, same words. */}
                    <StudioEndorsement
                        testid={IDS.handshakeStudio}
                        className="!text-white/75 hover:!text-white"
                    />
                </Reveal>
            </div>
        </section>
    );
}

export default HandshakeBand;
