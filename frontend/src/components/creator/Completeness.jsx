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

const RADIUS = 22;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const Ring = ({ percent }) => {
    const still = useReducedMotion();
    const offset = CIRCUMFERENCE * (1 - Math.max(0, Math.min(100, percent)) / 100);
    return (
        <div
            data-testid={IDS.ring}
            role="img"
            aria-label={`Profile ${percent}% complete`}
            className="relative h-[52px] w-[52px] flex-none"
        >
            <svg viewBox="0 0 52 52" className="h-full w-full -rotate-90">
                <circle
                    cx="26"
                    cy="26"
                    r={RADIUS}
                    fill="none"
                    strokeWidth="3"
                    className="stroke-border"
                />
                <motion.circle
                    cx="26"
                    cy="26"
                    r={RADIUS}
                    fill="none"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeDasharray={CIRCUMFERENCE}
                    className="stroke-primary"
                    initial={still ? false : { strokeDashoffset: CIRCUMFERENCE }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: still ? 0 : 0.9, ease: [0.22, 1, 0.36, 1] }}
                />
            </svg>
            <span
                data-testid={IDS.percent}
                className="absolute inset-0 grid place-items-center text-label font-extrabold tabular-nums"
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

    // **One row, not a panel.** It sits between the header and the live
    // work, and as a 290px card it pushed the work's first button below the
    // fold on a laptop — a nudge about the profile costing the creator the
    // thing they opened the page to do.
    return (
        <div className="flex items-center gap-3 rounded-lg bg-card px-4 py-3.5 shadow-card sm:gap-4 md:px-[22px]">
            <Ring percent={completeness.percent ?? 0} />

            <div className="min-w-0 flex-1 sm:flex sm:items-center sm:gap-4">
                <div className="min-w-0 flex-1">
                    <p className="text-body font-bold leading-snug text-heading">
                        {/* Framed as what it unlocks, not as a chore. */}
                        A few more details and brands can find you properly.
                    </p>
                    <ul data-testid={IDS.list} className="mt-1.5 flex flex-wrap gap-1.5">
                        {missing.map((row) => (
                            <li
                                key={row.field}
                                data-testid={IDS.item(row.field)}
                                className="rounded-pill bg-wash-warm px-2.5 py-1 text-label text-muted-foreground"
                            >
                                {row.label}
                            </li>
                        ))}
                    </ul>
                </div>

                <Link
                    to="/onboarding/creator"
                    data-testid={IDS.cta}
                    className="group inline-flex min-h-[2.75rem] flex-none items-center gap-2 text-meta font-bold text-foreground transition-colors duration-200 hover:text-primary"
                >
                    Finish your profile
                    <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                </Link>
            </div>
        </div>
    );
}
