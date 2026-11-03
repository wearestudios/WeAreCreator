// The panel every process mockup sits in: white at 4% on the navy band, a
// white-at-10% border, white-at-6% hairlines between rows, 16px corners, and
// the "Example" tag — every card says it is one.
//
// **The active edge glow is a blurred layer behind the panel, not a
// `box-shadow`.** Shadows on the public pages are reserved for things that
// float; this is a tint that fades in, on its own layer, so turning it on
// and off is an opacity change the compositor does.
import React from "react";

export function StepCardFrame({ card, active = false, testid, children }) {
    return (
        <div data-testid={testid} data-active={active ? "true" : "false"} className="relative isolate">
            <div
                aria-hidden
                className={`pointer-events-none absolute -inset-2 -z-10 rounded-[22px] bg-brand-red/20 blur-xl transition-opacity duration-500 ${
                    active ? "opacity-100" : "opacity-0"
                }`}
            />
            <div
                className={`overflow-hidden rounded-[16px] border bg-brand-navy transition-colors duration-500 ${
                    active ? "border-brand-red/40" : "border-brand-white/10"
                }`}
            >
                <div className="bg-brand-white/[0.04]">
                    <div className="flex items-center justify-between gap-3 border-b border-brand-white/[0.06] px-4 py-3">
                        <p className="text-[0.8125rem] font-medium text-brand-white/90">{card.head}</p>
                        <span className="rounded-pill border border-brand-white/15 px-2 py-0.5 text-[0.6875rem] text-brand-white/65">
                            {card.tag}
                        </span>
                    </div>
                    {children}
                </div>
            </div>
        </div>
    );
}

/** Label-and-value rows, the shape four of the cards share. */
export function CardRows({ rows }) {
    return (
        <dl className="divide-y divide-brand-white/[0.06]">
            {rows.map((row) => (
                <div key={row.k} className="flex items-center justify-between gap-4 px-4 py-2.5 text-[0.8125rem]">
                    <dt className="text-brand-white/65">{row.k}</dt>
                    <dd className={row.tone === "good" ? "font-medium text-brand-white" : "text-brand-white/90"}>
                        {row.tone === "good" ? (
                            <span className="inline-flex items-center gap-1.5">
                                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-brand-red" />
                                {row.v}
                            </span>
                        ) : (
                            row.v
                        )}
                    </dd>
                </div>
            ))}
        </dl>
    );
}

/** A round monogram for a generic handle: its first letter after the @. */
export function Monogram({ handle }) {
    const letter = (handle || "").replace(/^@/, "").charAt(0).toUpperCase();
    return (
        <span
            aria-hidden
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-brand-white/15 bg-brand-white/[0.06] text-[0.75rem] font-medium text-brand-white/90"
        >
            {letter}
        </span>
    );
}
