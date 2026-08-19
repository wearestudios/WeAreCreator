// The 404.
//
// The catch-all used to be `<Navigate to="/" replace />`, which is worse than
// it looks: a mistyped URL, a link from an old post, or a brief that has since
// closed all landed on the front page with no explanation, and the visitor's
// evidence was that they had been *moved* rather than that anything was wrong.
// A shared link that quietly becomes the home page is indistinguishable from a
// shared link that worked.
//
// So: say what happened, and offer the three places somebody who got here
// actually wanted. Deliberately not a bare "404" — the number is for us.
import React from "react";
import { Link, useLocation } from "react-router-dom";

import { MarketingPage, Eyebrow } from "@/components/marketing/Sections";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import { MARKETING as IDS } from "@/constants/testIds";

const WAYS_ON = [
    {
        to: "/campaigns",
        label: "Browse live briefs",
        body: "Everything open right now, from brands we have checked.",
    },
    {
        to: "/how-it-works",
        label: "How it works",
        body: "The whole journey, from both sides.",
    },
    {
        to: "/",
        label: "Back to the start",
        body: "The front page, and the two ways in.",
    },
];

export default function NotFound() {
    const { pathname } = useLocation();

    return (
        <MarketingPage
            testid={IDS.notFound}
            title="Page not found"
            description="That page does not exist, or it has moved."
            path={pathname}
        >
            <section className="mx-auto grid max-w-7xl gap-12 px-6 py-20 md:grid-cols-12 md:items-center md:py-28">
                <div className="md:col-span-6">
                    <Eyebrow>404</Eyebrow>
                    <h1 className="mt-5 font-serif text-fluid-5xl leading-none tracking-tight">
                        That page isn&apos;t here.
                    </h1>
                    <p className="mt-6 max-w-lg text-base leading-relaxed text-muted-foreground">
                        It may have moved, or the brief may have closed — campaigns come
                        down when they fill. Nothing has gone wrong with your account.
                    </p>

                    <ul className="mt-10 space-y-3">
                        {WAYS_ON.map((w) => (
                            <li key={w.to}>
                                <Link
                                    to={w.to}
                                    data-testid={`not-found-link-${w.to.replace(/\W+/g, "-").replace(/^-|-$/g, "") || "home"}`}
                                    className="group block rounded-lg border border-white/10 bg-card grain-surface p-5 transition-colors duration-200 hover:border-ember-500/40"
                                >
                                    <p className="font-serif text-fluid-xl leading-tight tracking-tight transition-colors duration-200 group-hover:text-ember-500">
                                        {w.label}
                                    </p>
                                    <p className="mt-1.5 text-sm text-muted-foreground">
                                        {w.body}
                                    </p>
                                </Link>
                            </li>
                        ))}
                    </ul>
                </div>

                <div className="md:col-span-6">
                    <PlaceholderImage
                        // PLACEHOLDER IMAGE: an empty venue between shoots —
                        // chairs stacked, light through a window. Quiet rather
                        // than apologetic. Portrait-friendly 4:3.
                        note="Empty venue between shoots, chairs stacked, light through a window, 4:3"
                        ratio="4/3"
                    />
                </div>
            </section>
        </MarketingPage>
    );
}
