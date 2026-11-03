// A small chip on a mockup: "Shortlisted", "Approved", what a brief pays.
// Neutral on purpose — the brand red is a mark and a large figure, never a
// status, and a chip is a status (`test_site_foundations.py`).
import React from "react";

export default function Chip({ children }) {
    return (
        <span className="inline-flex items-center gap-1 rounded-pill border border-brand-white/20 bg-brand-white/10 px-2 py-0.5 text-[0.6875rem] font-medium text-brand-white">
            {children}
        </span>
    );
}
