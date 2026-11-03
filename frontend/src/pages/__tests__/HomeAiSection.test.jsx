// Home with 0, 1, 2 and 3 AI switches on: the "What the AI does" section,
// one card per live switch, "AI-powered" in the lead, title and description
// only from two, the h1 never touched, and the section numbers in sequence.
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
const Home = require("@/pages/Home").default;

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
        act(() =>
            root.render(
                <MemoryRouter>
                    <Home />
                </MemoryRouter>,
            ),
        );
    });

    test("the section is there exactly when a switch is, with one card per switch", () => {
        expect(Boolean(byId("landing-ai"))).toBe(count > 0);
        const cards = [...container.querySelectorAll('[data-testid^="landing-ai-card-"]')].map((el) =>
            el.getAttribute("data-testid").replace("landing-ai-card-", ""),
        );
        expect(cards.sort()).toEqual([...on].sort());
        for (const key of on) {
            const card = HOME.ai.cards.find((c) => c.key === key);
            expect(byId(`landing-ai-card-${key}`).textContent).toContain(card.line);
            expect(byId(`landing-ai-card-${key}`).querySelector("img")).not.toBeNull();
            expect(container.querySelector(`[data-track-section="ai-card-${key}"]`)).not.toBeNull();
        }
    });

    test("'AI-powered' in the lead, title and description only from two", () => {
        const powered = count >= 2;
        const lead = byId("landing-hero-lead") || container.querySelector('[data-track-section="hero"] p');
        expect(container.textContent.includes(HOME.hero.aiLead)).toBe(powered);
        expect(container.textContent.includes(HOME.hero.lead)).toBe(!powered);
        expect(lead).not.toBeNull();
        expect(document.title.includes("AI-powered")).toBe(powered);
        const description = document.querySelector('meta[name="description"]')?.getAttribute("content") || "";
        expect(description.includes("AI-powered")).toBe(powered);
    });

    test("the h1 never changes and never says AI", () => {
        const h1 = container.querySelector("h1");
        expect(h1.textContent).toBe(HOME.hero.title);
        expect(/\bAI\b/.test(h1.textContent)).toBe(false);
    });

    test("the section numbers run in sequence", () => {
        const numbers = [...container.querySelectorAll('[data-testid^="section-rule-"]')].map((el) =>
            Number(el.getAttribute("data-testid").replace("section-rule-", "")),
        );
        const expected = count ? [2, 4, 5, 6, 7, 8, 9] : [2, 4, 5, 6, 7, 8];
        expect(numbers).toEqual(expected);
    });
});
