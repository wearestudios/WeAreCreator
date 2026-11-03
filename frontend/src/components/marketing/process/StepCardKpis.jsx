// Brand step 05: three results tiles and the creator's payout row.
//
// **The figures count up once, the first time the step is active**, over
// 900ms, by writing `textContent` on a ref — no React render per frame.
// A screen reader hears the final figure from the start; the counting digits
// are `aria-hidden`. Under reduced motion the first paint is the final value.
import React, { useEffect, useRef } from "react";

import { StepCardFrame } from "./StepCardFrame";

const COUNT_MS = 900;
const format = (n) => Math.round(n).toLocaleString("en-IN");

function Tile({ tile, play, reduced, testid }) {
    const ref = useRef(null);
    const done = useRef(false);
    useEffect(() => {
        const el = ref.current;
        if (!el || done.current) return undefined;
        if (reduced) {
            el.textContent = format(tile.value);
            done.current = true;
            return undefined;
        }
        if (!play) return undefined;
        done.current = true;
        let raf = 0;
        const start = performance.now();
        const tick = (now) => {
            const t = Math.min(1, (now - start) / COUNT_MS);
            const eased = 1 - Math.pow(1 - t, 3);
            el.textContent = format(tile.value * eased);
            if (t < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => {
            cancelAnimationFrame(raf);
            // An interrupted count still ends on the real figure.
            el.textContent = format(tile.value);
        };
    }, [play, reduced, tile.value]);
    return (
        <div data-testid={testid} className="rounded-[10px] border border-brand-white/10 px-3 py-2.5">
            <p className="text-[0.6875rem] text-brand-white/65">{tile.label}</p>
            <p className="mt-1 font-serif text-[1.25rem] tabular-nums text-brand-white/90">
                <span className="sr-only">{format(tile.value)}</span>
                <span ref={ref} aria-hidden data-count-final={format(tile.value)}>
                    {reduced ? format(tile.value) : "0"}
                </span>
            </p>
        </div>
    );
}

export default function StepCardKpis({ card, active, testid, play, reduced, kpiTestid }) {
    return (
        <StepCardFrame card={card} active={active} testid={testid}>
            <div className="grid grid-cols-3 gap-2 px-4 py-3">
                {card.tiles.map((tile, i) => (
                    <Tile key={tile.label} tile={tile} play={play} reduced={reduced} testid={kpiTestid && kpiTestid(i)} />
                ))}
            </div>
            <p className="flex items-center gap-1.5 border-t border-brand-white/[0.06] px-4 py-2.5 text-[0.8125rem] text-brand-white/90">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-brand-red" />
                {card.paid}
            </p>
        </StepCardFrame>
    );
}
