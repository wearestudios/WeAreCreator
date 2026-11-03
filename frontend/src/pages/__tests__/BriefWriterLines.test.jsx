// The brief writer's lines on the public site render only while its switch
// is on, and the For Brands h1 never changes.
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
const { BRANDS } = jest.requireActual("@/content/marketing");

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

const byId = (id) => container.querySelector(`[data-testid="${id}"]`);
const page = (C) =>
    act(() =>
        root.render(
            <MemoryRouter>
                <C />
            </MemoryRouter>,
        ),
    );

describe.each([
    ["off", {}],
    ["on", { briefWriter: true }],
])("brief writer %s", (state, switches) => {
    beforeEach(() => {
        mockLive = switches;
    });
    const on = state === "on";

    test("For Brands: the hero lead swaps and the h1 stays", () => {
        page(require("@/pages/ForBrands").default);
        expect(Boolean(byId("brands-hero-ai-lead"))).toBe(on);
        expect(container.textContent.includes(BRANDS.hero.aiLead)).toBe(on);
        expect(container.textContent.includes(BRANDS.hero.lead)).toBe(!on);
        expect(container.querySelector("h1").textContent).toBe(BRANDS.hero.title);
    });

    test("For Brands: the FAQ entry", () => {
        page(require("@/pages/ForBrands").default);
        expect(container.textContent.includes("Do I have to write the brief myself?")).toBe(on);
        if (on) {
            expect(container.querySelector('[data-track-section="faq-ai-brief-writer"]')).not.toBeNull();
        }
    });

    test("Home: the feature row's brief writer card", () => {
        page(require("@/pages/Home").default);
        const el = byId("process-feature-aiBrief");
        expect(Boolean(el)).toBe(on);
        if (on) expect(el.getAttribute("data-track-section")).toBe("feature-aiBrief");
    });
});
