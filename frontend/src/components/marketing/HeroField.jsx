// The hero's background: a field of dots the light moves across.
//
// Four layers, all painted by `index.css` (`.hero-field-*`), every colour a
// `color-mix` of a brand token:
//
//   a) a 24px grid of 1px navy dots at low alpha, fading toward the bottom
//   b) the same grid in red, revealed only inside a circle at `--mx`/`--my`
//      (260px; 180px on a phone)
//   c) a soft red glow, 560px, moved by `transform`
//   d) two blurred drifts — red top right, navy bottom left — on CSS
//      keyframes, 22s and 26s, alternating, transform only
//
// **Where the light goes.** A mouse over the hero pulls it, eased (k 0.12 per
// 1/60s). With no mouse — a touch screen, or the pointer elsewhere — it
// wanders a slow Lissajous path, so a phone gets the same living page without
// a finger having to chase it. Touch never drives it: a finger scrolling the
// page is not pointing at anything.
//
// **What it costs, and why it costs that.** This sits behind the homepage's
// h1, which is the page's LCP, so it may not compete with it:
//   - **One rAF loop, and only while it can be seen**: an IntersectionObserver
//     on the hero and `visibilitychange` start and stop it. Offscreen or in a
//     hidden tab nothing runs.
//   - **No layout read per frame.** The hero's rect is cached, refreshed by a
//     ResizeObserver, and marked stale by a passive scroll listener so the
//     next frame reads it once. A pointer event stores `clientX/Y` and
//     nothing else.
//   - **Each frame writes two custom properties on one layer and one
//     transform on another.** The custom properties sit on the lit layer
//     alone, so the style recalc is that element and no subtree.
//   - **Reduced motion: no loop and no drift.** The script writes nothing at
//     all and the CSS defaults leave the light at rest at 70% / 30%.
//
// Decorative: `aria-hidden`, and `pointer-events: none` so nothing behind or
// in front of it ever loses a click to it. It listens on its parent — the
// hero section — rather than on itself.
import React, { useEffect, useRef } from "react";

/** Where the light rests, as a fraction of the hero: 70% across, 30% down. */
export const REST = { x: 0.7, y: 0.3 };

/** The fraction of the gap closed per 1/60s while following a mouse. */
export const FOLLOW_K = 0.12;

/** The wander, gentler than the follow so a mouse leaving reads as a drift back. */
export const WANDER_K = 0.04;

/**
 * The wander path at `t` seconds: two unrelated sines, so it never visibly
 * loops, inside the hero's box with a margin. Pure.
 */
export function lissajous(t, w, h) {
    return {
        x: w * (0.6 + 0.28 * Math.sin(t * 0.17 + 0.6)),
        y: h * (0.4 + 0.24 * Math.sin(t * 0.23 + 1.9)),
    };
}

/** Frame-rate independent ease: `k` is the fraction closed per 1/60s. Pure. */
export function ease(from, to, k, dt) {
    const step = Math.min(0.1, Math.max(0, dt)) * 60;
    return to + (from - to) * Math.pow(1 - k, step);
}

const REDUCED = "(prefers-reduced-motion: reduce)";

export default function HeroField({ testid }) {
    const fieldRef = useRef(null);
    const litRef = useRef(null);
    const glowRef = useRef(null);

    useEffect(() => {
        const field = fieldRef.current;
        const lit = litRef.current;
        const glow = glowRef.current;
        const hero = field && field.parentElement;
        if (!hero || !lit || !glow) return undefined;

        const mq = window.matchMedia ? window.matchMedia(REDUCED) : null;
        let reduced = !!(mq && mq.matches);
        let inView = typeof IntersectionObserver === "undefined";
        let shown = !document.hidden;
        let raf = 0;
        let last = 0;
        let t = 0;

        // The cached rect, and whether a scroll has moved it since.
        const box = { left: 0, top: 0, w: 0, h: 0 };
        let stale = true;
        const read = () => {
            const r = hero.getBoundingClientRect();
            box.left = r.left;
            box.top = r.top;
            box.w = r.width;
            box.h = r.height;
            stale = false;
        };
        const mouse = { x: 0, y: 0, on: false };
        const cur = { x: NaN, y: NaN };

        const tick = (now) => {
            const dt = last ? (now - last) / 1000 : 1 / 60;
            last = now;
            t += dt;
            if (stale) read();
            const target = mouse.on
                ? { x: mouse.x - box.left, y: mouse.y - box.top }
                : lissajous(t, box.w, box.h);
            if (Number.isNaN(cur.x)) {
                cur.x = box.w * REST.x;
                cur.y = box.h * REST.y;
            }
            const k = mouse.on ? FOLLOW_K : WANDER_K;
            cur.x = ease(cur.x, target.x, k, dt);
            cur.y = ease(cur.y, target.y, k, dt);
            lit.style.setProperty("--mx", cur.x.toFixed(1) + "px");
            lit.style.setProperty("--my", cur.y.toFixed(1) + "px");
            // The glow rests at 70% / 30% in CSS; the transform is the
            // distance from there.
            glow.style.transform =
                "translate3d(" + (cur.x - box.w * REST.x).toFixed(1) + "px," + (cur.y - box.h * REST.y).toFixed(1) + "px,0)";
            raf = requestAnimationFrame(tick);
        };

        const stop = () => {
            if (raf) cancelAnimationFrame(raf);
            raf = 0;
            last = 0;
        };
        const rest = () => {
            lit.style.removeProperty("--mx");
            lit.style.removeProperty("--my");
            glow.style.removeProperty("transform");
            cur.x = NaN;
            cur.y = NaN;
        };
        const sync = () => {
            if (reduced) {
                stop();
                rest();
                return;
            }
            if (inView && shown) {
                if (!raf) raf = requestAnimationFrame(tick);
            } else stop();
        };

        const onPointer = (e) => {
            if (e.pointerType !== "mouse") return;
            mouse.x = e.clientX;
            mouse.y = e.clientY;
            mouse.on = e.type !== "pointerleave";
        };
        const onScroll = () => {
            stale = true;
        };
        const onVisible = () => {
            shown = !document.hidden;
            sync();
        };
        const onReduced = () => {
            reduced = !!(mq && mq.matches);
            sync();
        };

        hero.addEventListener("pointermove", onPointer, { passive: true });
        hero.addEventListener("pointerenter", onPointer, { passive: true });
        hero.addEventListener("pointerleave", onPointer, { passive: true });
        window.addEventListener("scroll", onScroll, { passive: true });
        document.addEventListener("visibilitychange", onVisible);
        if (mq) {
            if (mq.addEventListener) mq.addEventListener("change", onReduced);
            else if (mq.addListener) mq.addListener(onReduced);
        }
        const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(onScroll);
        if (ro) ro.observe(hero);
        const io =
            typeof IntersectionObserver === "undefined"
                ? null
                : new IntersectionObserver(([entry]) => {
                      inView = entry.isIntersecting;
                      sync();
                  });
        if (io) io.observe(hero);
        sync();

        return () => {
            stop();
            hero.removeEventListener("pointermove", onPointer);
            hero.removeEventListener("pointerenter", onPointer);
            hero.removeEventListener("pointerleave", onPointer);
            window.removeEventListener("scroll", onScroll);
            document.removeEventListener("visibilitychange", onVisible);
            if (mq) {
                if (mq.removeEventListener) mq.removeEventListener("change", onReduced);
                else if (mq.removeListener) mq.removeListener(onReduced);
            }
            if (ro) ro.disconnect();
            if (io) io.disconnect();
        };
    }, []);

    return (
        <div ref={fieldRef} aria-hidden="true" data-testid={testid} className="hero-field">
            <div className="hero-field-drift hero-field-drift-a" />
            <div className="hero-field-drift hero-field-drift-b" />
            <div ref={glowRef} className="hero-field-glow" />
            <div className="hero-field-dots" />
            <div ref={litRef} className="hero-field-lit" />
        </div>
    );
}
