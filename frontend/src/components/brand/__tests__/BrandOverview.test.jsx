// The brand dashboard's top half, rendered against endpoint-shaped data.
//
// What matters here is what is *absent*: the AI card without the switch or a
// summary, a stat tile the analytics did not measure, the budget card on a
// brief with no cap, a contact detail planted on a creator, and any second
// Fraunces title or second red card.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";

import { api } from "@/lib/api";
import { aiLive } from "@/content/marketing";
import BrandOverview, { loadBrandOverview, needsYouItems, pickLiveCampaign } from "../BrandOverview";
import { BRAND_OVERVIEW as IDS } from "@/constants/testIds";

jest.mock("@/lib/api", () => ({ api: { get: jest.fn() } }));
jest.mock("@/content/marketing", () => ({ aiLive: jest.fn() }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(() => {
    act(() => root.unmount());
    container.remove();
    jest.resetAllMocks();
});

const ago = (d) => new Date(Date.now() - d * 86400000).toISOString();

const LIVE = {
    id: "c1",
    title: "Barrier serum, everyday routine",
    status: "in_progress",
    start_date: ago(21),
    filled_slots: 3,
    creators_needed: 3,
    compensation_type: "fixed",
    budget: { total: 90000, committed: 75000, remaining: 15000, ratio: 0.833, warning: true, exhausted: false },
};
const OTHER = { id: "c2", title: "SPF 50", status: "open", start_date: ago(-5) };

const ANALYTICS = {
    dashboard: {
        totals: { views: 286900, shares: 1640, engagement_rate: 8.83 },
        timeseries: [{ views: 30000 }, { views: 51000 }, { views: 286900 }],
        creators: {
            list: [
                { name: "Diya F", posted: true, status: "Posted" },
                { name: "Kabir S", posted: false, status: "Shoot booked" },
            ],
        },
        by_creator: [{ name: "Diya F", views: 76300 }],
    },
};

// The applicant board's rows, with contact values planted on the creator as
// though the projection had leaked them — they must never reach the screen.
const BOARD = {
    campaign: { compensation_type: "fixed" },
    applicants: [
        {
            id: "a1",
            can_review_content: true,
            agreed_amount: 25000,
            creator: {
                name: "Diya F",
                profile_image_url: null,
                phone: "+919812345678",
                whatsapp: "+919812345678",
                email: "diya@example.com",
                full_address: "12 Leak Street",
            },
        },
    ],
};

const DATA = {
    campaigns: [LIVE, OTHER],
    totals: { content_to_review: 1, awaiting_decision: 0 },
    publish_block: null,
};

const render = (el) => act(() => root.render(<MemoryRouter>{el}</MemoryRouter>));
const q = (id) => container.querySelector(`[data-testid="${id}"]`);

describe("the live campaign", () => {
    test("is the one under way, not the one that opens next week", () => {
        expect(pickLiveCampaign([OTHER, LIVE]).id).toBe("c1");
        expect(pickLiveCampaign([{ ...LIVE, status: "draft" }])).toBeNull();
    });

    test("draws the three tiles the analytics measured, and one Fraunces title", () => {
        aiLive.mockReturnValue(false);
        render(<BrandOverview data={DATA} overview={{ live: LIVE, analytics: ANALYTICS, board: BOARD }} />);
        expect(q(IDS.panel)).not.toBeNull();
        expect(q(IDS.tile("views")).textContent).toContain("2.87L");
        expect(q(IDS.tile("shares")).textContent).toContain("1,640");
        expect(q(IDS.tile("engagement")).textContent).toContain("8.83%");
        expect(container.querySelectorAll(".app-title")).toHaveLength(1);
        expect(q(IDS.booked).textContent).toBe("3 of 3 creators booked · ₹75,000 of ₹90,000 committed");
    });

    test("leaves out a tile the analytics returned as unknown", () => {
        const partial = { dashboard: { ...ANALYTICS.dashboard, totals: { views: 1200, shares: null, engagement_rate: null } } };
        render(<BrandOverview data={DATA} overview={{ live: LIVE, analytics: partial }} />);
        expect(q(IDS.tile("views"))).not.toBeNull();
        expect(q(IDS.tile("shares"))).toBeNull();
        expect(q(IDS.tile("engagement"))).toBeNull();
    });

    test("says the numbers are coming when none are measured yet", () => {
        render(<BrandOverview data={DATA} overview={{ live: LIVE, analytics: { dashboard: { totals: {} } } }} />);
        expect(q(IDS.tiles)).toBeNull();
        expect(q(IDS.noNumbers)).not.toBeNull();
    });
});

test("with nothing live, a navy panel takes the same place and the only red is at the top", () => {
    render(<BrandOverview data={{ campaigns: [], totals: {} }} overview={{ live: null }} />);
    expect(q(IDS.panel)).toBeNull();
    expect(q(IDS.emptyPanel).textContent).toContain("Post your first brief");
    expect(container.querySelectorAll(".app-title")).toHaveLength(1);
    expect(container.querySelectorAll(".bg-urgent")).toHaveLength(0);
});

describe("needs you", () => {
    test("the delivery waiting on the brand is the one red card", () => {
        const items = needsYouItems(
            {
                ...DATA,
                totals: { content_to_review: 2 },
                campaigns: [{ id: "x", title: "A", awaiting_decision: 3 }, { id: "y", title: "B", status: "draft" }],
            },
            LIVE,
            BOARD,
        );
        expect(items.filter((i) => i.tone === "red")).toHaveLength(1);
        expect(items[0]).toMatchObject({ key: "content", to: "/brand/applications/a1" });
        expect(items.map((i) => i.key)).toEqual(["content", "decide-x", "draft-y"]);
    });

    test("an overdue invoice is not a card — the app has nothing to press for it", () => {
        const items = needsYouItems({ campaigns: [], totals: {}, publish_block: { code: "invoice_overdue", message: "Settle it" } });
        expect(items).toHaveLength(0);
        const unverified = needsYouItems({ campaigns: [], totals: {}, publish_block: { code: "unverified", message: "Check" } });
        expect(unverified.map((i) => i.key)).toEqual(["verify"]);
    });
});

test("a creator row shows a name, a fee and views — and no contact detail ever", () => {
    render(<BrandOverview data={DATA} overview={{ live: LIVE, analytics: ANALYTICS, board: BOARD }} />);
    const rows = container.querySelectorAll(`[data-testid="${IDS.creatorRow}"]`);
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("₹25,000");
    expect(rows[0].textContent).toContain("76,300 views");
    for (const planted of ["9812345678", "diya@example.com", "Leak Street"]) {
        expect(container.innerHTML).not.toContain(planted);
    }
});

describe("the budget", () => {
    test("is agreed against left, from the block — and no paid segment", () => {
        render(<BrandOverview data={DATA} overview={{ live: LIVE, analytics: ANALYTICS }} />);
        const card = q(IDS.budget);
        expect(card.textContent).toContain("₹15,000");
        expect(card.textContent).toContain("Agreed ₹75,000");
        expect(card.textContent).not.toMatch(/paid/i);
    });

    test.each([
        ["no cap", { ...LIVE, budget: { total: null, committed: 1000 } }],
        ["barter", { ...LIVE, compensation_type: "barter" }],
    ])("is absent on a brief with %s", (_, live) => {
        render(<BrandOverview data={DATA} overview={{ live, analytics: ANALYTICS }} />);
        expect(q(IDS.budget)).toBeNull();
    });
});

describe("the AI card", () => {
    const summary = { available: true, summary: { headline: "Reels carried it." } };

    test("is there with the switch on and a summary", () => {
        aiLive.mockReturnValue(true);
        render(<BrandOverview data={DATA} overview={{ live: LIVE, analytics: ANALYTICS, summary }} />);
        expect(q(IDS.ai).textContent).toContain("Reels carried it.");
    });

    test.each([
        ["the switch is off", false, summary],
        ["the API says unavailable", true, { available: false }],
        ["no summary has been written", true, { available: true, summary: null }],
    ])("is absent when %s", (_, on, s) => {
        aiLive.mockReturnValue(on);
        render(<BrandOverview data={DATA} overview={{ live: LIVE, analytics: ANALYTICS, summary: s }} />);
        expect(q(IDS.ai)).toBeNull();
    });

    test("is not even asked for with the switch off", async () => {
        aiLive.mockReturnValue(false);
        api.get.mockResolvedValue({ data: {} });
        await loadBrandOverview([LIVE]);
        const urls = api.get.mock.calls.map((c) => c[0]);
        expect(urls).toEqual(["/brand/campaigns/c1/analytics", "/brand/campaigns/c1/applicants"]);
    });
});
