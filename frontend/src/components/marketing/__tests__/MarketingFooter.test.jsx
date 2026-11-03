// The marketing footer: the site's own links, the studio named in the
// copyright, nothing left over from the template, and a beam that does not
// loop for somebody who asked for less motion.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router-dom";

const mockTrack = jest.fn();
jest.mock("@/lib/track", () => ({
    EVENTS: { ctaClick: "cta_click", sectionView: "section_view", outboundWhatsapp: "outbound_whatsapp" },
    track: (...a) => mockTrack(...a),
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const { FOOTER_COLUMNS, CONTACT_EMAIL, copyrightYear } = require("@/lib/siteNav");
const { WHATSAPP_HREF } = require("@/content/marketing");
const { FOOTER: IDS } = require("@/constants/testIds");
const MarketingFooter = require("../MarketingFooter").default;

let reduced = false;
let frames = [];
let rafCalls = 0;
let ioCallbacks = [];

// jsdom's CSS parser predates container queries and reports the footer's
// stylesheet as unparseable. Browsers parse it; that one message is noise here.
const realError = console.error;
beforeAll(() => {
    jest.spyOn(console, "error").mockImplementation((...args) => {
        const first = args[0];
        if (first && String(first.message || first).includes("Could not parse CSS stylesheet")) return;
        realError(...args);
    });
    HTMLCanvasElement.prototype.getContext = () => null;
    global.ResizeObserver = class {
        observe() {}
        disconnect() {}
    };
    global.IntersectionObserver = class {
        constructor(cb) {
            ioCallbacks.push(cb);
        }
        observe() {}
        disconnect() {}
    };
});

let container;
let root;
beforeEach(() => {
    reduced = false;
    frames = [];
    rafCalls = 0;
    ioCallbacks = [];
    mockTrack.mockReset();
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
    window.cancelAnimationFrame = () => {};
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

function Where() {
    const loc = useLocation();
    return <output data-testid="where">{loc.pathname + loc.search}</output>;
}

function render() {
    act(() =>
        root.render(
            <MemoryRouter initialEntries={["/"]}>
                <MarketingFooter />
                <Where />
            </MemoryRouter>,
        ),
    );
}

const byId = (id) => container.querySelector(`[data-testid="${id}"]`);

/** Run the frames that are queued, `n` times over; returns how many ran. */
function flushFrames(n) {
    let ran = 0;
    for (let i = 0; i < n; i += 1) {
        const queued = frames;
        frames = [];
        act(() => queued.forEach((cb) => cb(performance.now() + 16 * (i + 1))));
        ran += queued.length;
    }
    return ran;
}

function showFooter() {
    act(() => ioCallbacks.forEach((cb) => cb([{ isIntersecting: true }])));
}

test("renders every footer column and link, in order", () => {
    render();
    const navs = [...container.querySelectorAll("nav")];
    expect(navs.map((n) => n.getAttribute("aria-label"))).toEqual(FOOTER_COLUMNS.map((c) => c.heading));
    FOOTER_COLUMNS.forEach((col, i) => {
        expect(navs[i].textContent).toContain(col.heading);
        const anchors = [...navs[i].querySelectorAll("a")];
        expect(anchors.map((a) => a.textContent)).toEqual(col.links.map((l) => l.label));
        col.links.forEach((l, j) => {
            expect(anchors[j].getAttribute("href")).toBe(l.to);
            expect(anchors[j].getAttribute("data-testid")).toBe(IDS.link(l.to));
        });
    });
});

test("internal links are router links: the click is the router's, not a reload", () => {
    render();
    const link = byId(IDS.link("/for-brands"));
    let prevented;
    act(() => {
        const ev = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
        link.dispatchEvent(ev);
        prevented = ev.defaultPrevented;
    });
    expect(prevented).toBe(true);
    expect(byId("where").textContent).toBe("/for-brands");
    expect(mockTrack).toHaveBeenCalledWith("cta_click", {
        location: "footer",
        label: "For brands",
        href: "/for-brands",
    });
});

test("a server-rendered page stays a plain link the router does not catch", () => {
    render();
    const work = byId(IDS.link("/work"));
    expect(work.getAttribute("target")).toBeNull();
    let prevented;
    act(() => {
        const ev = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
        work.dispatchEvent(ev);
        prevented = ev.defaultPrevented;
    });
    expect(prevented).toBe(false);
});

test("WhatsApp opens in a new tab and the email is a mailto", () => {
    render();
    const wa = byId(IDS.whatsapp);
    expect(wa.getAttribute("href")).toBe(WHATSAPP_HREF);
    expect(wa.getAttribute("target")).toBe("_blank");
    expect(wa.getAttribute("rel")).toContain("noopener");
    expect(wa.textContent).toBe("Talk to us on WhatsApp");
    const mail = byId(IDS.contact);
    expect(mail.getAttribute("href")).toBe(`mailto:${CONTACT_EMAIL}`);
    expect(mail.textContent).toBe(CONTACT_EMAIL);
    expect(mail.getAttribute("target")).toBeNull();
});

test("the copyright names the studio and the year", () => {
    render();
    expect(byId(IDS.copyright).textContent).toBe(`© ${copyrightYear()} WeAre Studios`);
    expect(byId(IDS.copyrightLink).textContent).toBe("WeAre Studios");
});

test("there is no wordmark: no word block, no hidden label, nothing measured", () => {
    const observed = [];
    const RealRO = global.ResizeObserver;
    global.ResizeObserver = class {
        observe(el) {
            observed.push(el);
        }
        disconnect() {}
    };
    const fonts = document.fonts;
    let waited = 0;
    Object.defineProperty(document, "fonts", {
        configurable: true,
        value: {
            get ready() {
                waited += 1;
                return Promise.resolve();
            },
        },
    });
    try {
        render();
        expect(container.querySelector(".bwf-word-wrap")).toBeNull();
        expect(container.querySelector(".bwf-word-in")).toBeNull();
        expect(container.querySelector(".bwf-sr")).toBeNull();
        expect(byId(IDS.root).getAttribute("data-word")).toBe("false");
        // The fit effect returns before it touches the DOM.
        expect(observed).toEqual([]);
        expect(waited).toBe(0);
        // The site is still named once, by the logo in the lead.
        expect(byId(IDS.wordmark)).not.toBeNull();
    } finally {
        global.ResizeObserver = RealRO;
        Object.defineProperty(document, "fonts", { configurable: true, value: fonts });
    }
});

test("nothing from the template survives", () => {
    render();
    const html = container.innerHTML;
    expect(html).not.toMatch(/Kedhar|Night Shift|template by/i);
});

test("with reduced motion the beam is drawn once and never loops", () => {
    reduced = true;
    render();
    showFooter();
    flushFrames(5);
    expect(rafCalls).toBeLessThanOrEqual(1);
    // At rest: the beam layer is placed once, eight points right of centre.
    expect(container.querySelector(".bwf-beam").style.transform).toBe("translate3d(8.00%,0,0)");
});

test("without it the beam runs a loop while on screen", () => {
    render();
    showFooter();
    flushFrames(5);
    expect(rafCalls).toBeGreaterThan(3);
});

test("the wordmark is still there for a caller that passes one, measured and labelled", () => {
    const BeamWordmarkFooter = require("@/components/ui/beam-wordmark-footer").default;
    const observed = [];
    const RealRO = global.ResizeObserver;
    global.ResizeObserver = class {
        observe(el) {
            observed.push(el);
        }
        disconnect() {}
    };
    try {
        act(() => root.render(<BeamWordmarkFooter word="Mark" wordLabel="The mark" testIds={{ root: "bwf" }} />));
        const word = container.querySelector(".bwf-word-in");
        expect(word.getAttribute("aria-hidden")).toBe("true");
        expect(word.textContent).toBe("Mark");
        expect(container.querySelector(".bwf-sr").textContent).toBe("The mark");
        expect(byId("bwf").getAttribute("data-word")).toBe("true");
        expect(observed).toHaveLength(1);
    } finally {
        global.ResizeObserver = RealRO;
    }
});
