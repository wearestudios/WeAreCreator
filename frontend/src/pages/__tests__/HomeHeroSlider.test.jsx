// Home, rendered: two sections (the hero slider, then the spine), the AI slide
// with 0, 1, 2 and 3 switches on, the badge and "AI-powered" only from two,
// one h1 and it is slide A's, one unnumbered rule, the carousel's ARIA, what a tab
// click, an arrow key and the timer do, reduced motion, and the phone's sticky
// ask hiding once the footer is on screen.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";

let mockLive = {};
jest.mock("@/content/marketing", () => {
    const actual = jest.requireActual("@/content/marketing");
    return { ...actual, aiLive: (key) => mockLive[key] === true };
});
jest.mock("@/lib/api", () => ({ api: { get: () => new Promise(() => {}), post: jest.fn() }, API_BASE: "" }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { HOME } = jest.requireActual("@/content/marketing");
const { HOLD_MS } = require("@/lib/heroDeck");

// Every observer, so a test can say what has scrolled into view.
let observers = [];
let reduced = false;
let container;
let root;
beforeAll(() => {
    global.IntersectionObserver = class {
        constructor(cb) {
            this.cb = cb;
            this.targets = [];
            observers.push(this);
        }
        observe(el) {
            this.targets.push(el);
        }
        unobserve() {}
        disconnect() {}
    };
    window.scrollTo = () => {};
    Element.prototype.scrollIntoView = () => {};
});
beforeEach(() => {
    observers = [];
    reduced = false;
    window.matchMedia = (q) => ({
        matches: q.includes("reduce") ? reduced : false,
        media: q,
        addEventListener() {},
        removeEventListener() {},
        addListener() {},
        removeListener() {},
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(() => {
    act(() => root.unmount());
    container.remove();
    jest.useRealTimers();
});

const byId = (id) => container.querySelector(`[data-testid="${id}"]`);
const all = (sel) => [...container.querySelectorAll(sel)];
const Home = require("@/pages/Home").default;

function render() {
    act(() =>
        root.render(
            <MemoryRouter>
                <Home />
            </MemoryRouter>,
        ),
    );
}

/** Let the "hero-slides" chunk resolve and Suspense swap it in. */
async function settle() {
    for (let i = 0; i < 3; i += 1) {
        // eslint-disable-next-line no-await-in-loop
        await act(async () => {
            await new Promise((r) => setTimeout(r, 0));
        });
    }
}

const activeSlide = () => byId("hero-slides").querySelector('[data-state="active"]').getAttribute("data-slide");

const CASES = [
    [[], 0],
    [["campaignSummary"], 1],
    [["briefWriter"], 1],
    [["nicheMatching", "campaignSummary"], 2],
    [["briefWriter", "nicheMatching", "campaignSummary"], 3],
];

describe.each(CASES)("switches on: %j", (on, count) => {
    beforeEach(() => {
        mockLive = Object.fromEntries(on.map((k) => [k, true]));
        render();
    });

    test("home is exactly two sections: the hero slider, then the spine", () => {
        const sections = all("main > section");
        expect(sections.map((s) => s.getAttribute("data-testid"))).toEqual(["hero-section", "process-section"]);
        expect(sections.map((s) => s.getAttribute("data-ground"))).toEqual(["page", "navy"]);
        // What used to be below the spine, and the strip inside it, are gone.
        for (const gone of [
            "compare-section", "landing-band", "landing-ai", "landing-promises", "landing-clients",
            "landing-creator-door", "closing-cta", "process-before-after",
        ]) {
            expect(byId(gone)).toBeNull();
        }
    });

    test("one h1, slide A's, never changed and never saying AI", () => {
        const h1s = all("h1");
        expect(h1s).toHaveLength(1);
        expect(h1s[0].textContent).toBe(HOME.hero.title);
        expect(/\bAI\b/.test(h1s[0].textContent)).toBe(false);
        expect(byId("hero-slide-0").contains(h1s[0])).toBe(true);
        expect(byId("hero-slide-0").getAttribute("data-slide")).toBe("deal");
    });

    test("one section rule, How it works', unnumbered; the slider has none", () => {
        const rules = all('[data-testid^="section-rule-"]');
        expect(rules.map((el) => el.getAttribute("data-testid"))).toEqual(["section-rule-how-it-works"]);
        expect(rules[0].textContent).toBe(HOME.processSpine.label);
        expect(byId("hero-section").querySelector('[data-testid^="section-rule-"]')).toBeNull();
        expect(byId("hero-section").textContent).not.toContain("At a glance");
        expect(HOME.slides.label).toBeUndefined();
    });

    test("the AI slide is absent with every switch off, and lists only live features", async () => {
        const slides = all('[data-testid="hero-slides"] > [data-slide]').map((el) => el.getAttribute("data-slide"));
        expect(slides).toEqual(count ? ["deal", "problem", "onLocation", "ai"] : ["deal", "problem", "onLocation"]);
        expect(all('[data-testid^="hero-tab-"]')).toHaveLength(slides.length);
        if (!count) {
            expect(container.querySelector('[data-slide="ai"]')).toBeNull();
            expect(container.textContent.includes(HOME.ai.title)).toBe(false);
            return;
        }
        act(() => byId("hero-tab-3").click());
        await settle();
        const rows = all('li[data-track-section^="hero-ai-"]').map((el) =>
            el.getAttribute("data-track-section").replace("hero-ai-", ""),
        );
        expect(rows.sort()).toEqual([...on].sort());
        const slide = byId("hero-slide-3");
        expect(slide.textContent).toContain(HOME.ai.card.foot);
        // No percentage anywhere on the slide.
        expect(slide.textContent).not.toMatch(/%/);
        // The tab says "AI-powered" only while two switches back it.
        expect(byId("hero-tab-3").textContent).toBe(count >= 2 ? HOME.ai.aiTab : HOME.ai.tab);
    });

    test("no AI anywhere on home outside the hero", () => {
        expect(byId("process-section").textContent).not.toMatch(/\bAI\b/);
        expect(container.querySelector('[data-testid^="process-feature-ai"]')).toBeNull();
    });

    test("the badge, the lead, the title and the description say 'AI-powered' only from two", () => {
        const powered = count >= 2;
        expect(Boolean(byId("hero-ai-badge"))).toBe(powered);
        if (powered) expect(byId("hero-ai-badge").textContent).toBe(HOME.slides.aiBadge);
        expect(byId("hero-lead").textContent).toBe(powered ? HOME.hero.aiLead : HOME.hero.lead);
        expect(document.title.includes("AI-powered")).toBe(powered);
        const description = document.querySelector('meta[name="description"]')?.getAttribute("content") || "";
        expect(description.includes("AI-powered")).toBe(powered);
    });
});

describe("the carousel", () => {
    beforeEach(() => {
        mockLive = { briefWriter: true, nicheMatching: true, campaignSummary: true };
    });

    test("is announced as a carousel of slides, n of N", () => {
        render();
        const region = byId("hero-carousel");
        expect(region.getAttribute("role")).toBe("region");
        expect(region.getAttribute("aria-roledescription")).toBe("carousel");
        const slides = all('[data-testid="hero-slides"] > [data-slide]');
        slides.forEach((slide, i) => {
            expect(slide.getAttribute("aria-roledescription")).toBe("slide");
            expect(slide.getAttribute("aria-label")).toBe(`${i + 1} of ${slides.length}`);
        });
        const tabs = all('[data-testid="hero-tabs"] [role="tab"]');
        expect(tabs.map((t) => t.getAttribute("aria-selected"))).toEqual(["true", "false", "false", "false"]);
        expect(tabs[0].getAttribute("aria-controls")).toBe("hero-slide-0");
    });

    test("the timer advances every 7 seconds, painting at most two slides", () => {
        jest.useFakeTimers();
        render();
        expect(activeSlide()).toBe("deal");
        expect(byId("hero-slides").getAttribute("data-mounted")).toBe("1");
        act(() => jest.advanceTimersByTime(HOLD_MS));
        expect(activeSlide()).toBe("problem");
        expect(byId("hero-slides").getAttribute("data-mounted")).toBe("2");
        act(() => jest.advanceTimersByTime(400));
        expect(byId("hero-slides").getAttribute("data-mounted")).toBe("1");
        expect(byId("hero-progress").getAttribute("data-running")).toBe("true");
    });

    test("a tab click switches the slide and stops the auto-advance for good", () => {
        jest.useFakeTimers();
        render();
        act(() => byId("hero-tab-2").click());
        expect(activeSlide()).toBe("onLocation");
        act(() => jest.advanceTimersByTime(HOLD_MS * 4));
        expect(activeSlide()).toBe("onLocation");
        expect(byId("hero-progress").getAttribute("data-running")).toBe("false");
    });

    test("the arrow keys switch slides, wrap, and stop the auto-advance", () => {
        jest.useFakeTimers();
        render();
        const tabs = byId("hero-tabs");
        const key = (k) =>
            act(() => tabs.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true })));
        key("ArrowLeft");
        expect(activeSlide()).toBe("ai");
        key("ArrowRight");
        expect(activeSlide()).toBe("deal");
        key("ArrowRight");
        expect(activeSlide()).toBe("problem");
        // Focus pauses the clock; leave the slider so only `stopped` holds it.
        act(() => byId("hero-carousel").dispatchEvent(new FocusEvent("focusout", { bubbles: true })));
        act(() => jest.advanceTimersByTime(HOLD_MS * 3));
        expect(activeSlide()).toBe("problem");
    });

    test("the asks and the note are the same on every slide", () => {
        jest.useFakeTimers();
        render();
        const asks = () => [byId("hero-cta-brand"), byId("hero-cta-talk"), byId("hero-note")];
        const first = asks();
        for (let i = 1; i < 4; i += 1) {
            act(() => byId(`hero-tab-${i}`).click());
            expect(asks()).toEqual(first);
            expect(all('[data-testid="hero-cta-brand"]')).toHaveLength(1);
        }
    });

    test("reduced motion: no auto-advance, no progress animation, an instant swap", () => {
        reduced = true;
        jest.useFakeTimers();
        render();
        act(() => jest.advanceTimersByTime(HOLD_MS * 5));
        expect(activeSlide()).toBe("deal");
        expect(byId("hero-progress").getAttribute("data-running")).toBe("false");
        expect(byId("hero-progress").getAttribute("style")).toBeNull();
        act(() => byId("hero-tab-1").click());
        expect(activeSlide()).toBe("problem");
        // No crossfade: the outgoing slide is gone at once, and nothing animates.
        expect(byId("hero-slides").getAttribute("data-mounted")).toBe("1");
        expect(byId("hero-slide-1").getAttribute("style")).toBeNull();
    });
});

describe("the hero's field", () => {
    test("sits behind the slider, decorative, inside the hero section", () => {
        mockLive = {};
        reduced = true;
        render();
        const hero = byId("hero-section");
        const field = byId("hero-field");
        expect(field.parentElement).toBe(hero);
        expect(hero.firstElementChild).toBe(field);
        expect(field.getAttribute("aria-hidden")).toBe("true");
        expect(field.contains(container.querySelector("h1"))).toBe(false);
        expect(hero.className).toMatch(/\brelative\b/);
        expect(hero.className).toMatch(/\boverflow-hidden\b/);
    });
});

describe("the phone's sticky ask", () => {
    const fire = (el, entry) => {
        // Every observer on it: the hero has two, the sticky ask's and the
        // field's, which runs its light only while the hero is on screen.
        const ios = observers.filter((o) => o.targets.includes(el));
        expect(ios.length).toBeGreaterThan(0);
        act(() => ios.forEach((io) => io.cb([{ isIntersecting: false, boundingClientRect: { top: 100 }, ...entry, target: el }])));
    };

    test("shows once the hero has scrolled away, and hides once the footer is on screen", () => {
        mockLive = {};
        render();
        const bar = byId("sticky-cta");
        expect(bar.hidden).toBe(true);
        fire(document.getElementById("hero"), { isIntersecting: false, boundingClientRect: { top: -900 } });
        expect(bar.hidden).toBe(false);
        fire(byId("site-footer"), { isIntersecting: true });
        expect(bar.hidden).toBe(true);
        fire(byId("site-footer"), { isIntersecting: false, boundingClientRect: { top: 400 } });
        expect(bar.hidden).toBe(false);
    });
});
