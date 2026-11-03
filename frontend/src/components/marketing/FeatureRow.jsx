// The row of what is built in, under the process spine — six product
// features. The three AI cards it used to carry are the hero slider's AI
// slide now, which says the same thing once rather than twice.
//
// **Native overflow scroll with snap points, and two buttons** — no
// drag-to-explore: a phone swipes it the way it swipes anything else, and
// the row scrolls inside its own box, so the page never scrolls sideways.
// The buttons move it by most of a view and disable at either end, read off
// the row's own scroll position once per frame.
import React, { useEffect, useRef, useState } from "react";
import {
    BarChart3,
    CalendarCheck,
    CheckCheck,
    ChevronLeft,
    ChevronRight,
    FileText,
    Users,
    Wallet,
} from "lucide-react";

import { PROCESS as IDS } from "@/constants/testIds";

const ICONS = { BarChart3, CalendarCheck, CheckCheck, FileText, Users, Wallet };

const CARD =
    "w-[16.5rem] shrink-0 snap-start rounded-[16px] border border-brand-white/10 bg-brand-white/[0.04] p-5";
const CHIP = "grid h-10 w-10 place-items-center rounded-[10px] bg-brand-red/15 text-accent-ink";

const BUTTON =
    "grid h-10 w-10 place-items-center rounded-full border border-brand-white/15 text-brand-white/90 transition-colors duration-200 hover:border-brand-white/40 disabled:cursor-default disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red focus-visible:ring-offset-2 focus-visible:ring-offset-brand-navy";

function FeatureRow({ features, reduced = false, className = "" }) {
    const items = features.items;
    const rowRef = useRef(null);
    const [edges, setEdges] = useState({ start: true, end: false });

    useEffect(() => {
        const row = rowRef.current;
        if (!row) return undefined;
        let raf = 0;
        const read = () => {
            raf = 0;
            const max = row.scrollWidth - row.clientWidth;
            const start = row.scrollLeft <= 2;
            const end = row.scrollLeft >= max - 2;
            setEdges((prev) => (prev.start === start && prev.end === end ? prev : { start, end }));
        };
        const onScroll = () => {
            if (!raf) raf = requestAnimationFrame(read);
        };
        read();
        row.addEventListener("scroll", onScroll, { passive: true });
        window.addEventListener("resize", onScroll);
        return () => {
            row.removeEventListener("scroll", onScroll);
            window.removeEventListener("resize", onScroll);
            if (raf) cancelAnimationFrame(raf);
        };
    }, [items.length]);

    const move = (dir) => {
        const row = rowRef.current;
        if (!row) return;
        row.scrollBy({ left: dir * row.clientWidth * 0.8, behavior: reduced ? "auto" : "smooth" });
    };

    return (
        <div data-testid={IDS.featureRow} className={className}>
            <div className="flex items-center justify-between gap-4">
                <h3 className="font-sans text-body-lg font-medium text-brand-white/90">{features.label}</h3>
                <div className="flex gap-2">
                    <button
                        type="button"
                        aria-label={features.prev}
                        data-testid={IDS.featurePrev}
                        disabled={edges.start}
                        onClick={() => move(-1)}
                        className={BUTTON}
                    >
                        <ChevronLeft aria-hidden className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        aria-label={features.next}
                        data-testid={IDS.featureNext}
                        disabled={edges.end}
                        onClick={() => move(1)}
                        className={BUTTON}
                    >
                        <ChevronRight aria-hidden className="h-4 w-4" />
                    </button>
                </div>
            </div>
            <ul
                ref={rowRef}
                className="mt-6 flex snap-x snap-mandatory gap-4 overflow-x-auto overscroll-x-contain pb-3 [scrollbar-width:thin]"
            >
                {items.map((item) => (
                    <FeatureCard key={item.key} item={item} />
                ))}
            </ul>
        </div>
    );
}

function FeatureCard({ item }) {
    const Icon = ICONS[item.icon] || FileText;
    return (
        <li
            data-testid={IDS.feature(item.key)}
            data-track-section={`feature-${item.key}`}
            className={CARD}
        >
            <span aria-hidden className={CHIP}>
                <Icon className="h-5 w-5" />
            </span>
            <p className="mt-4 font-medium text-brand-white/90">{item.title}</p>
            <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-brand-white/65">{item.line}</p>
        </li>
    );
}

// Memoised: its props are the content module's, and the spine above it
// re-renders as the active step changes.
export default React.memo(FeatureRow);
