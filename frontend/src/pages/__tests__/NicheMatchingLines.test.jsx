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

    test("Home: step 01's line", () => {
        const Home = require("@/pages/Home").default;
        page(Home);
        expect(Boolean(byId("landing-step-offer-ai-nicheMatching"))).toBe(on);
    });
});
