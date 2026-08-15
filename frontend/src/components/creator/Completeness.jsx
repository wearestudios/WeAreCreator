// Profile completeness.
//
// Only rendered while something is missing, and gone entirely at 100% — a
// permanent "you're done!" panel is a strip of the page that stops carrying
// information the day it's earned. Named fields rather than a bare
// percentage, because "72% complete" tells a creator nothing they can act on.
import React from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { CREATOR_COMPLETENESS as IDS } from "@/constants/testIds";

const RADIUS = 30;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const Ring = ({ percent }) => {
    const still = useReducedMotion();
    const offset = CIRCUMFERENCE * (1 - Math.max(0, Math.min(100, percent)) / 100);
    return (
        <div
            data-testid={IDS.ring}
            role="img"
            aria-label={`Profile ${percent}% complete`}
            className="relative h-[72px] w-[72px] flex-none"
        >
            <svg viewBox="0 0 72 72" className="h-full w-full -rotate-90">
                <circle
                    cx="36"
                    cy="36"
                    r={RADIUS}
                    fill="none"
                    strokeWidth="3"
                    className="stroke-white/10"
                />
                <motion.circle
                    cx="36"
                    cy="36"
                    r={RADIUS}
                    fill="none"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeDasharray={CIRCUMFERENCE}
                    className="stroke-ember-500"
                    initial={still ? false : { strokeDashoffset: CIRCUMFERENCE }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: still ? 0 : 0.9, ease: [0.22, 1, 0.36, 1] }}
                />
            </svg>
            <span
                data-testid={IDS.percent}
                className="absolute inset-0 grid place-items-center font-serif text-lg"
            >
                {percent}%
            </span>
        </div>
    );
};

export default function Completeness({ completeness }) {
    const missing = completeness?.missing || [];
    // Hidden entirely once there's nothing left to ask for.
    if (!completeness || completeness.complete || missing.length === 0) return null;

    return (
        <div className="rounded-md border border-white/10 bg-card p-6 md:p-7">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
                <Ring percent={completeness.percent ?? 0} />

                <div className="min-w-0 flex-1">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Your profile
                    </p>
                    <p className="mt-3 font-serif text-xl leading-tight">
                        {/* Framed as what it unlocks, not as a chore. */}
                        A few more details and brands can find you properly.
                    </p>

                    <ul
                        data-testid={IDS.list}
                        className="mt-5 flex flex-wrap gap-2"
                    >
                        {missing.map((row) => (
                            <li
                                key={row.field}
                                data-testid={IDS.item(row.field)}
                                className="rounded-full border border-white/10 bg-background/60 px-3 py-1 text-xs text-muted-foreground"
                            >
                                {row.label}
                            </li>
                        ))}
                    </ul>

                    <Link
                        to="/onboarding/creator"
                        data-testid={IDS.cta}
                        className="group mt-6 inline-flex items-center gap-2 text-sm text-ember-500 transition-colors duration-200 hover:text-ember-400"
                    >
                        Finish your profile
                        <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                    </Link>
                </div>
            </div>
        </div>
    );
}
