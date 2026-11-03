// The photo slots, rendered: a photograph carries both widths and the
// caller's `sizes`, says what it shows, and sits on its focal point — and a
// slot with no photograph is still its drawing or its brief, as before.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";

import PhotoSlot from "../PhotoSlot";
import PlaceholderImage from "../PlaceholderImage";
import { PHOTO_SLOTS, PLACEHOLDER_PHOTOS } from "@/content/photoSlots";

jest.mock("@/lib/api", () => ({ api: { get: () => new Promise(() => {}), post: jest.fn() }, API_BASE: "" }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
let wide = true;
beforeAll(() => {
    global.IntersectionObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
    };
    global.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
    };
    window.scrollTo = () => {};
});
beforeEach(() => {
    wide = true;
    window.matchMedia = (q) => ({
        matches: q.includes("min-width: 768px") ? wide : false,
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

const render = (el) => act(() => root.render(<MemoryRouter>{el}</MemoryRouter>));
const img = () => container.querySelector("img");

function widths(srcset) {
    return srcset.split(",").map((part) => part.trim().split(/\s+/)[1]);
}

describe("PhotoSlot", () => {
    test("a band's photograph carries both widths and the caller's sizes", () => {
        render(<PhotoSlot id="brands-full-room" fill sizes="100vw" />);
        const el = img();
        const slot = PHOTO_SLOTS["brands-full-room"];
        expect(el.getAttribute("src")).toBe(slot.src);
        expect(widths(el.getAttribute("srcset"))).toEqual(["1200w", "2400w"]);
        expect(el.getAttribute("sizes")).toBe("100vw");
        expect(el.getAttribute("alt")).toBe(slot.alt);
        expect(el.getAttribute("alt").length).toBeGreaterThan(20);
        expect(el.getAttribute("loading")).toBe("lazy");
        expect(el.style.objectPosition).toBe(slot.focal);
    });

    test("the slider's frame says it is never wider than 540px from lg", () => {
        render(<PhotoSlot id="creators-on-shoot" fill sizes="(min-width: 1024px) 540px, 100vw" />);
        expect(img().getAttribute("sizes")).toBe("(min-width: 1024px) 540px, 100vw");
    });

    test("a slot with no photograph is still its brief here, with no srcset", () => {
        // `home-on-location` did not get its photograph; under test the
        // environment is development, so it is the dashed brief.
        expect(PHOTO_SLOTS["home-on-location"].src).toBeNull();
        render(<PhotoSlot id="home-on-location" fill bare sizes="100vw" />);
        const box = container.querySelector('[data-slot="home-on-location"]');
        expect(box.getAttribute("data-empty")).toBe("placeholder");
        expect(container.querySelector("img[srcset]")).toBeNull();
    });
});

// Held in variables: `test_site_foundations` sweeps every file for a literal
// `note="…"`, because on a page that is a brief shipped in the bundle.
const CARD_NOTE = "a card";
const TABLE_NOTE = "An empty table by a window";

describe("PlaceholderImage", () => {
    test("a named slot with a photograph renders it, in every environment", () => {
        render(<PlaceholderImage slot="auth-login" fill sizes="50vw" eager />);
        const el = img();
        const photo = PLACEHOLDER_PHOTOS["auth-login"];
        expect(el.getAttribute("src")).toBe(photo.src);
        expect(widths(el.getAttribute("srcset"))).toEqual(["900w", "1800w"]);
        expect(el.getAttribute("sizes")).toBe("50vw");
        expect(el.getAttribute("alt")).toBe(photo.alt);
        expect(el.getAttribute("loading")).toBe("eager");
        expect(el.style.objectPosition).toBe(photo.focal);
        // A photograph is not a placeholder: no brief on the element.
        expect(container.querySelector("[data-placeholder]")).toBeNull();
    });

    test("the 404's picture keeps its ratio on the container", () => {
        render(<PlaceholderImage slot="not-found" ratio="4/3" sizes="(min-width: 768px) 50vw, 100vw" />);
        const box = container.querySelector('[data-slot="not-found"]');
        expect(box.className).toContain("aspect-[4/3]");
        expect(img().className).not.toMatch(/aspect-/);
        expect(widths(img().getAttribute("srcset"))).toEqual(["1200w", "2400w"]);
    });

    test("a src passed directly stays decorative and single-width", () => {
        render(<PlaceholderImage note={CARD_NOTE} src="/img/marketing/float-fnb.svg" alt="" />);
        expect(img().getAttribute("alt")).toBe("");
        expect(img().hasAttribute("srcset")).toBe(false);
        expect(img().hasAttribute("sizes")).toBe(false);
    });

    test("no photograph and no src is still the tint with its brief", () => {
        render(<PlaceholderImage note={TABLE_NOTE} ratio="4/3" />);
        expect(img()).toBeNull();
        expect(container.querySelector("[data-placeholder]").getAttribute("data-placeholder")).toBe(TABLE_NOTE);
    });
});

describe("the auth asides", () => {
    const pages = {
        login: () => require("@/pages/Login").default,
        signup: () => require("@/pages/Signup").default,
    };
    jest.mock("@/context/AuthContext", () => ({
        useAuth: () => ({ requestOtp: jest.fn(), verifyOtp: jest.fn(), user: null }),
    }));

    test.each(Object.keys(pages))("/%s: half the screen, eager from md, lazy below it", (name) => {
        const Page = pages[name]();
        render(<Page />);
        expect(img().getAttribute("sizes")).toBe("50vw");
        expect(img().getAttribute("loading")).toBe("eager");
        expect(container.querySelector('[data-testid="auth-aside-scrim"]')).not.toBeNull();
        act(() => root.unmount());
        root = createRoot(container);
        wide = false;
        render(<Page />);
        // Below md the aside is display:none; lazy is what keeps a phone
        // from downloading a picture it never draws.
        expect(img().getAttribute("loading")).toBe("lazy");
    });
});
