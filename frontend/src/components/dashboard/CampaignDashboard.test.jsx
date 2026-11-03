// The results dashboard, rendered: Indian grouping, the fallback tile for an
// expired thumbnail, the end state under reduced motion, and the empty state.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";

import CampaignDashboard from "./CampaignDashboard";
import { DASHBOARD as IDS } from "@/constants/testIds";

const mockGet = jest.fn();
jest.mock("@/lib/api", () => ({ api: { get: (...a) => mockGet(...a), post: jest.fn() } }));
jest.mock("@/lib/feedback", () => ({ notifyError: jest.fn(), notifySuccess: jest.fn() }));
jest.mock("@/lib/download", () => ({ downloadCsv: jest.fn(() => Promise.resolve()) }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const post = (key, over = {}) => ({
    key, creator_name: "Ananya", media_type: "reel", permalink: `https://www.instagram.com/reel/${key}/`,
    thumbnail_url: `https://cdn.example/${key}.jpg`, carousel_count: null,
    views: 98000, reach: 61000, likes: 4100, comments: 210, shares: 880, saves: 640,
    source: "instagram", unsupported_metrics: [], posted_at: "2026-10-20T10:00:00Z", ...over,
});

const DASH = {
    campaign: { id: "c1", title: "Weekend brunch launch", start_date: "2026-10-18T00:00:00Z", end_date: "2026-10-30T00:00:00Z" },
    updated_at: "2026-11-02T10:00:00Z",
    totals: { views: 427300, reach_sum: 281900, likes: 19600, comments: 1035, shares: 2450, saves: 2790, interactions: 25875, engagement_rate: 9.18 },
    creators: { total: 9, posted: 9, list: [] },
    posts: { total: 11, live: 2, items: [post("A1"), post("B2", { media_type: "carousel", carousel_count: 4, creator_name: "Zoya", views: 21000, shares: 90 })] },
    by_format: [{ format: "reel", posts: 1, views: 98000 }, { format: "carousel", posts: 1, views: 21000 }],
    by_creator: [{ name: "Ananya", views: 98000, posts: 1 }, { name: "Zoya", views: 21000, posts: 1 }],
    timeseries: [{ date: "2026-10-20", views: 50000 }, { date: "2026-10-21", views: 119000 }],
    markers: [{ date: "2026-10-20", name: "Ananya" }],
    versus_last_campaign: { title: "Diwali menu", views: 300000, change_percent: 42.4 },
};

let container;
let root;

function setReducedMotion(on) {
    window.matchMedia = (q) => ({ matches: on && q.includes("reduce"), addListener() {}, removeListener() {} });
}

beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    global.requestAnimationFrame = (cb) => setTimeout(() => cb(performance.now()), 16);
    global.cancelAnimationFrame = (id) => clearTimeout(id);
    mockGet.mockImplementation((url) =>
        url.endsWith("/summary")
            ? Promise.resolve({ data: { available: false } })
            : Promise.resolve({ data: { dashboard: DASH } }),
    );
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
    jest.useRealTimers();
});

async function render(dash = DASH) {
    mockGet.mockImplementation((url) =>
        url.endsWith("/summary")
            ? Promise.resolve({ data: { available: false } })
            : Promise.resolve({ data: { dashboard: dash } }),
    );
    await act(async () => {
        root.render(
            <MemoryRouter>
                <CampaignDashboard campaignId="c1" />
            </MemoryRouter>,
        );
    });
}

const $ = (id) => container.querySelector(`[data-testid="${id}"]`);

test("under reduced motion the first paint is the final value, in Indian grouping", async () => {
    setReducedMotion(true);
    await render();
    expect($(IDS.totalViews).textContent).toBe("4,27,300");
    expect($(IDS.tile("reach")).textContent).toContain("2,81,900");
    expect($(IDS.tile("reach")).textContent).toContain("added across posts");
    expect($(IDS.live).textContent).toBe("2 of 11 posts live");
    expect($(IDS.delta).textContent).toContain("+42.4%");
    expect(container.querySelector(".dash-rise")).not.toBeNull();
});

test("without reduced motion the number counts up from zero and lands on the total", async () => {
    setReducedMotion(false);
    jest.useFakeTimers();
    await render();
    expect($(IDS.totalViews).textContent).toBe("0");
    await act(async () => {
        jest.advanceTimersByTime(1200);
    });
    expect($(IDS.totalViews).textContent).toBe("4,27,300");
});

test("an expired thumbnail becomes a plain tile, never a broken image", async () => {
    setReducedMotion(true);
    await render();
    const img = $(IDS.post("A1")).querySelector("img");
    expect(img).not.toBeNull();
    await act(async () => {
        img.dispatchEvent(new Event("error"));
    });
    expect($(IDS.postFallback("A1"))).not.toBeNull();
    expect($(IDS.post("A1")).querySelector("img")).toBeNull();
});

test("a post with no thumbnail at all starts as the plain tile", async () => {
    setReducedMotion(true);
    await render({ ...DASH, posts: { ...DASH.posts, items: [post("C3", { thumbnail_url: null })] } });
    expect($(IDS.postFallback("C3"))).not.toBeNull();
});

test("a carousel shows 1/N and every tile opens the post", async () => {
    setReducedMotion(true);
    await render();
    const carousel = $(IDS.post("B2"));
    expect(carousel.textContent).toContain("1/4");
    expect(carousel.getAttribute("href")).toBe("https://www.instagram.com/reel/B2/");
    expect(carousel.getAttribute("target")).toBe("_blank");
});

test("each chart can be read as a table", async () => {
    setReducedMotion(true);
    await render();
    await act(async () => {
        $(IDS.asTable("bars")).click();
    });
    expect($(IDS.table("bars")).textContent).toContain("98,000");
});

test("before anything is live: the people and where they are, and no zeros", async () => {
    setReducedMotion(true);
    await render({
        ...DASH,
        totals: { views: null, reach_sum: null, likes: null, comments: null, shares: null, saves: null, interactions: null, engagement_rate: null },
        creators: { total: 2, posted: 0, list: [{ name: "Ananya", posted: false, status: "Shoot booked" }, { name: "Zoya", posted: false, status: "Draft in review" }] },
        posts: { total: 2, live: 0, items: [] },
        by_format: [], by_creator: [], timeseries: [], markers: [],
    });
    expect($(IDS.empty).textContent).toContain("Shoot booked");
    expect($(IDS.totalViews)).toBeNull();
    expect(container.textContent).not.toMatch(/\b0 views\b/);
});
