// The homepage's process spine: brand steps by default, the switch swapping
// them and writing the hash, the feature row's six product cards and no AI
// card whatever the switches say (the AI is a hero slide now), no
// before/after strip, no real client anywhere in the section, and reduced
// motion at the end state.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";

let mockLive = {};
jest.mock("@/content/marketing", () => {
    const actual = jest.requireActual("@/content/marketing");
    return { ...actual, aiLive: (key) => mockLive[key] === true };
});
const mockTrack = jest.fn();
jest.mock("@/lib/track", () => {
    const actual = jest.requireActual("@/lib/track");
    return { ...actual, track: (...a) => mockTrack(...a) };
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const { HOME, FACTS } = jest.requireActual("@/content/marketing");
const { PROCESS: IDS } = require("@/constants/testIds");
const ProcessSpine = require("../ProcessSpine").default;
const { spineProgress, tabFromHash } = require("../ProcessSpine");

const copy = HOME.processSpine;
let reduced = false;
let container;
let root;

beforeAll(() => {
    global.IntersectionObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
    };
    Element.prototype.scrollIntoView = () => {};
});
beforeEach(() => {
    reduced = false;
    mockLive = {};
    mockTrack.mockReset();
    window.history.replaceState(null, "", "/");
    window.matchMedia = (q) => ({
        matches: q.includes("reduce") ? reduced : false,
        media: q,
        addEventListener() {},
        removeEventListener() {},
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
const titles = () => [...container.querySelectorAll(`[data-testid="${IDS.steps}"] h3`)].map((h) => h.textContent);

function render() {
    act(() =>
        root.render(
            <MemoryRouter>
                <ProcessSpine n={4} />
            </MemoryRouter>,
        ),
    );
}

test("renders the five brand steps by default", () => {
    render();
    expect(titles()).toEqual(copy.steps.brands.map((s) => s.title));
    expect(titles()).toHaveLength(5);
    for (let n = 1; n <= 5; n += 1) {
        expect(byId(IDS.step(n))).not.toBeNull();
        expect(byId(IDS.card(n))).not.toBeNull();
        expect(byId(IDS.node(n)).textContent).toBe(String(n).padStart(2, "0"));
    }
    expect(byId(IDS.tab("brands")).getAttribute("aria-selected")).toBe("true");
});

test("switching to creators swaps the titles and writes the hash", () => {
    jest.useFakeTimers();
    render();
    act(() => byId(IDS.tab("creators")).click());
    act(() => jest.advanceTimersByTime(250));
    expect(titles()).toEqual(copy.steps.creators.map((s) => s.title));
    expect(window.location.hash).toBe("#creators");
    expect(byId(IDS.tab("creators")).getAttribute("aria-selected")).toBe("true");
    expect(mockTrack).toHaveBeenCalledWith("process_tab_change", expect.objectContaining({ tab: "creators" }));

    act(() => byId(IDS.tab("brands")).click());
    act(() => jest.advanceTimersByTime(250));
    expect(titles()).toEqual(copy.steps.brands.map((s) => s.title));
    expect(window.location.hash).toBe("#brands");
});

test("a #creators link opens on the creators' steps", () => {
    window.history.replaceState(null, "", "/#creators");
    render();
    expect(titles()).toEqual(copy.steps.creators.map((s) => s.title));
});

test("the feature row is the six product features and no AI card, whatever the switches say", () => {
    mockLive = { briefWriter: true, nicheMatching: true, campaignSummary: true };
    render();
    expect(copy.features.items.filter((i) => i.aiKey)).toHaveLength(0);
    expect(copy.features.items).toHaveLength(6);
    for (const item of copy.features.items) expect(byId(IDS.feature(item.key))).not.toBeNull();
    expect(container.querySelector('[data-testid^="process-feature-ai"]')).toBeNull();
    expect(byId(IDS.section).textContent).not.toMatch(/\bAI\b/);
});

test("the before/after strip is gone: the hero's problem slide tells it", () => {
    render();
    expect(container.querySelector('[data-testid="process-before-after"]')).toBeNull();
    expect(copy.strip).toBeUndefined();
});

test("no real client's name appears in the section, on either side", () => {
    jest.useFakeTimers();
    mockLive = { briefWriter: true, nicheMatching: true, campaignSummary: true };
    render();
    const names = FACTS.confirmedClients;
    expect(names.length).toBeGreaterThan(0);
    const check = () => {
        const html = byId(IDS.section).outerHTML;
        for (const name of names) expect(html).not.toContain(name);
    };
    check();
    act(() => byId(IDS.tab("creators")).click());
    act(() => jest.advanceTimersByTime(250));
    check();
});

test("every card says it is an example", () => {
    render();
    for (let n = 1; n <= 5; n += 1) expect(byId(IDS.card(n)).textContent).toContain("Example");
});

test("reduced motion: every step at full strength, the spine full, the figures final", () => {
    reduced = true;
    render();
    for (let n = 1; n <= 5; n += 1) {
        const step = byId(IDS.step(n));
        expect(step.getAttribute("data-state")).toBe("full");
        const parts = step.querySelectorAll("[data-strength]");
        expect(parts).toHaveLength(2);
        parts.forEach((el) => {
            expect(el.className).toContain("opacity-100");
            expect(el.className).not.toContain("opacity-[0.35]");
        });
    }
    expect(byId(IDS.spineFill).getAttribute("data-full")).toBe("true");
    const tiles = copy.steps.brands[4].card.tiles;
    tiles.forEach((tile, i) => {
        expect(byId(IDS.kpi(i)).textContent).toContain(tile.value.toLocaleString("en-IN"));
    });
});

test("without reduced motion the steps away from the centre are dimmed", () => {
    render();
    const states = [1, 2, 3, 4, 5].map((n) => byId(IDS.step(n)).getAttribute("data-state"));
    expect(states).toEqual(["active", "dim", "dim", "dim", "dim"]);
    const dim = byId(IDS.step(2)).querySelector("[data-strength]");
    expect(dim.className).toContain("md:opacity-[0.35]");
    expect(dim.className).toContain("opacity-[0.7]");
});

test("the pure helpers", () => {
    expect(tabFromHash("#creators")).toBe("creators");
    expect(tabFromHash("brands")).toBe("brands");
    expect(tabFromHash("#how-it-works")).toBeNull();
    expect(spineProgress(500, 1000, 1000)).toBe(0);
    expect(spineProgress(-500, 1000, 1000)).toBe(1);
    expect(spineProgress(0, 1000, 1000)).toBe(0.5);
    expect(spineProgress(0, 0, 1000)).toBe(0);
});
