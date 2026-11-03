// The hero's field: decorative and out of the way, one loop that runs only
// while the hero is on screen and the tab is showing, a mouse that pulls the
// light and a finger that does not, and nothing at all under reduced motion.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";

import HeroField, { FOLLOW_K, REST, ease, lissajous } from "../HeroField";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let reduced = false;
let frames = [];
let rafCalls = 0;
let observers = [];
let rectReads = 0;
let container;
let root;

beforeAll(() => {
    global.IntersectionObserver = class {
        constructor(cb) {
            this.cb = cb;
            observers.push(this);
        }
        observe() {}
        disconnect() {}
    };
    global.ResizeObserver = class {
        observe() {}
        disconnect() {}
    };
});

beforeEach(() => {
    reduced = false;
    frames = [];
    rafCalls = 0;
    observers = [];
    rectReads = 0;
    window.matchMedia = (q) => ({
        matches: q.includes("reduce") ? reduced : false,
        media: q,
        addEventListener() {},
        removeEventListener() {},
    });
    window.requestAnimationFrame = (cb) => {
        rafCalls += 1;
        frames.push(cb);
        return rafCalls;
    };
    window.cancelAnimationFrame = () => {
        frames = [];
    };
    container = document.createElement("section");
    container.getBoundingClientRect = () => {
        rectReads += 1;
        return { left: 0, top: 0, width: 1000, height: 600, right: 1000, bottom: 600 };
    };
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

function render() {
    act(() => root.render(<HeroField testid="field" />));
}
const field = () => container.querySelector('[data-testid="field"]');
const lit = () => container.querySelector(".hero-field-lit");
const glow = () => container.querySelector(".hero-field-glow");

function intersect(isIntersecting) {
    act(() => observers.forEach((o) => o.cb([{ isIntersecting }])));
}

/** Run whatever frames are queued, `n` times over; returns how many ran. */
function flush(n) {
    let ran = 0;
    for (let i = 0; i < n; i += 1) {
        const queued = frames;
        frames = [];
        queued.forEach((cb) => cb(1000 + 16 * (i + 1)));
        ran += queued.length;
    }
    return ran;
}

function pointer(type, pointerType, x, y) {
    const ev = new MouseEvent(type, { bubbles: true, clientX: x, clientY: y });
    Object.defineProperty(ev, "pointerType", { value: pointerType });
    container.dispatchEvent(ev);
}

test("is decorative and never takes a click", () => {
    render();
    expect(field().getAttribute("aria-hidden")).toBe("true");
    expect(field().className).toContain("hero-field");
    // The four layers: two drifts, the glow, the dots and the lit dots.
    expect(field().children).toHaveLength(5);
    // `pointer-events: none` lives in index.css on `.hero-field`; jsdom does
    // not load it, so the rule is read from the stylesheet itself.
    const css = require("fs").readFileSync(require("path").join(__dirname, "../../../index.css"), "utf8");
    const rule = css.slice(css.indexOf(".hero-field {"), css.indexOf("}", css.indexOf(".hero-field {")));
    expect(rule).toContain("pointer-events: none");
    expect(rule).toContain("position: absolute");
});

test("runs one loop while on screen, and stops when the hero scrolls away", () => {
    render();
    intersect(true);
    expect(flush(5)).toBe(5);
    expect(lit().style.getPropertyValue("--mx")).toMatch(/px$/);
    expect(glow().style.transform).toMatch(/^translate3d\(/);
    intersect(false);
    const before = rafCalls;
    expect(flush(5)).toBe(0);
    expect(rafCalls).toBe(before);
    // Back on screen, one loop again — not two.
    intersect(true);
    intersect(true);
    expect(frames).toHaveLength(1);
});

test("stops in a hidden tab", () => {
    render();
    intersect(true);
    flush(2);
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(flush(5)).toBe(0);
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(flush(1)).toBe(1);
});

test("reduced motion: no loop at all, and the light rests where the CSS puts it", () => {
    reduced = true;
    render();
    intersect(true);
    expect(rafCalls).toBe(0);
    expect(flush(5)).toBe(0);
    expect(lit().style.getPropertyValue("--mx")).toBe("");
    expect(glow().style.transform).toBe("");
    pointer("pointermove", "mouse", 100, 100);
    expect(rafCalls).toBe(0);
});

test("the rect is read once, not once per frame", () => {
    render();
    intersect(true);
    flush(30);
    expect(rectReads).toBe(1);
    act(() => window.dispatchEvent(new Event("scroll")));
    flush(10);
    expect(rectReads).toBe(2);
});

test("a mouse pulls the light; a finger does not", () => {
    render();
    intersect(true);
    flush(1);
    const mx = () => parseFloat(lit().style.getPropertyValue("--mx"));
    // A touch at the far left changes nothing about where it is heading.
    pointer("pointermove", "touch", 0, 0);
    flush(120);
    const wandering = mx();
    expect(wandering).toBeGreaterThan(100);
    pointer("pointermove", "mouse", 20, 20);
    flush(120);
    expect(mx()).toBeLessThan(30);
    // Leaving the hero hands it back to the wander.
    pointer("pointerleave", "mouse", 20, 20);
    flush(240);
    expect(mx()).toBeGreaterThan(100);
});

test("the light starts at rest, 70% across and 30% down", () => {
    render();
    intersect(true);
    flush(1);
    // One eased frame from rest toward the wander: still within a few px.
    expect(Math.abs(parseFloat(lit().style.getPropertyValue("--mx")) - 1000 * REST.x)).toBeLessThan(15);
    expect(Math.abs(parseFloat(lit().style.getPropertyValue("--my")) - 600 * REST.y)).toBeLessThan(15);
});

describe("the maths", () => {
    test("ease closes k of the gap per 1/60s and never overshoots", () => {
        expect(ease(0, 100, FOLLOW_K, 1 / 60)).toBeCloseTo(12, 5);
        expect(ease(0, 100, FOLLOW_K, 0)).toBe(0);
        expect(ease(0, 100, FOLLOW_K, 5)).toBeLessThan(100);
    });
    test("the wander stays inside the hero", () => {
        for (let t = 0; t < 600; t += 0.37) {
            const p = lissajous(t, 1000, 600);
            expect(p.x).toBeGreaterThan(0);
            expect(p.x).toBeLessThan(1000);
            expect(p.y).toBeGreaterThan(0);
            expect(p.y).toBeLessThan(600);
        }
    });
});
