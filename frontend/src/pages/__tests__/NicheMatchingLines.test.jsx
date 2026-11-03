// The niche-matching lines on the public site render only while
// the `nicheMatching` switch is on. A line about a feature brands or
// creators cannot use is a claim the product does not keep.
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

const { BRANDS, CREATORS } = jest.requireActual("@/content/marketing");

let container;
let root;

beforeAll(() => {
    global.IntersectionObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
    };
    if (!window.matchMedia) {
        window.matchMedia = () => ({
            matches: false,
            addEventListener() {},
            removeEventListener() {},
            addListener() {},
            removeListener() {},
        });
    }
    window.scrollTo = () => {};
});

beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

function page(Component) {
    act(() => {
        root.render(
            <MemoryRouter>
                <Component />
            </MemoryRouter>,
        );
    });
}

const byId = (id) => container.querySelector(`[data-testid="${id}"]`);
const text = () => container.textContent;

describe.each([
    ["off", {}],
    ["on", { nicheMatching: true }],
])("niche matching %s", (state, switches) => {
    beforeEach(() => {
        mockLive = switches;
    });
    const on = state === "on";

    test("For Brands: the shortlist line and the why lines", () => {
        const ForBrands = require("@/pages/ForBrands").default;
        page(ForBrands);
        expect(Boolean(byId("brands-shortlist-ai"))).toBe(on);
        expect(text().includes(BRANDS.shortlist.aiLine)).toBe(on);
        for (const row of BRANDS.shortlist.card.rows) {
            expect(text().includes(row.why)).toBe(on);
        }
        // The example rows themselves are always there.
        expect(byId("brands-shortlist-row-0")).not.toBeNull();
        if (on) {
            expect(byId("brands-shortlist-ai").getAttribute("data-track-section")).toBe("shortlist-ai-matching");
        }
    });

    test("For Creators: the briefs line", () => {
        const ForCreators = require("@/pages/ForCreators").default;
        page(ForCreators);
        expect(Boolean(byId("creators-briefs-ai"))).toBe(on);
        expect(text().includes(CREATORS.briefs.aiLine)).toBe(on);
        if (on) {
            expect(byId("creators-briefs-ai").getAttribute("data-track-section")).toBe("briefs-ai-matching");
        }
    });

    test("Home: the AI slide's matching row, and no feature card", async () => {
        page(require("@/pages/Home").default);
        // The feature row is the six product features: no AI card in it.
        expect(container.querySelector('[data-testid^="process-feature-ai"]')).toBeNull();
        const tab = [...container.querySelectorAll('[data-testid^="hero-tab-"]')].pop();
        // With this switch alone on, the AI slide is the fourth; with it off
        // (and every other off), there is no AI slide at all.
        expect(container.querySelectorAll('[data-testid^="hero-tab-"]').length).toBe(on ? 4 : 3);
        if (!on) return;
        await act(async () => {
            tab.click();
            await new Promise((r) => setTimeout(r, 0));
        });
        await act(async () => {
            await new Promise((r) => setTimeout(r, 0));
        });
        const row = container.querySelector('[data-track-section="hero-ai-nicheMatching"]');
        expect(row).not.toBeNull();
        // One row: only the switch that is on.
        expect(container.querySelectorAll('li[data-track-section^="hero-ai-"]').length).toBe(1);
    });
});
