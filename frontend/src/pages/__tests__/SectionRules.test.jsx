// The four marketing pages, rendered: every section rule is a label and a
// hairline, and none of them carries a section number. Numbering stays only
// where it encodes a real sequence — the process spine's steps, which are not
// section rules.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";

jest.mock("@/lib/api", () => ({ api: { get: () => new Promise(() => {}), post: jest.fn() }, API_BASE: "" }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
beforeAll(() => {
    global.IntersectionObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
    };
    global.ResizeObserver = class {
        observe() {}
        disconnect() {}
    };
    window.scrollTo = () => {};
    Element.prototype.scrollIntoView = () => {};
    HTMLCanvasElement.prototype.getContext = () => null;
});
beforeEach(() => {
    window.matchMedia = (q) => ({
        matches: q.includes("reduce"),
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
});

const PAGES = {
    home: () => require("@/pages/Home").default,
    "for-brands": () => require("@/pages/ForBrands").default,
    "for-creators": () => require("@/pages/ForCreators").default,
    about: () => require("@/pages/About").default,
};

const SECTION_NUMBER = /^\(?\d{2}\)?$/;

describe.each(Object.keys(PAGES))("/%s", (name) => {
    test("no section rule renders a section number", () => {
        const Page = PAGES[name]();
        act(() =>
            root.render(
                <MemoryRouter>
                    <Page />
                </MemoryRouter>,
            ),
        );
        const rules = [...container.querySelectorAll('[data-testid^="section-rule-"]')];
        expect(rules.length).toBeGreaterThan(0);
        for (const rule of rules) {
            const text = rule.textContent.trim();
            expect(text).not.toMatch(SECTION_NUMBER);
            expect(text).not.toMatch(/\(\d{2}\)/);
            // Each piece of the rule on its own, too: the label and the hairline.
            for (const part of rule.children) {
                expect(part.textContent.trim()).not.toMatch(SECTION_NUMBER);
            }
            // Keyed on its label, never a number.
            expect(rule.getAttribute("data-testid")).not.toMatch(/^section-rule-\d+$/);
            // Label first, hairline after it.
            expect(rule.children).toHaveLength(2);
            expect(rule.lastElementChild.getAttribute("aria-hidden")).toBe("true");
        }
    });
});

test("the slider renders no section rule and no 'At a glance'", () => {
    const HeroSlider = require("@/components/marketing/HeroSlider").default;
    act(() =>
        root.render(
            <MemoryRouter>
                <HeroSlider aiCards={[]} aiPowered={false} />
            </MemoryRouter>,
        ),
    );
    expect(container.querySelector('[data-testid^="section-rule-"]')).toBeNull();
    expect(container.textContent).not.toContain("At a glance");
});
