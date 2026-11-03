// The overview's top half, rendered against endpoint-shaped data.
//
// What it holds: every count is a count of the queue's own rows; the payouts
// tile is amber exactly when the server flagged a payout at risk (day five of
// the seven-day promise) and calm otherwise; the AI card is absent unless the
// switch is on *and* a summary came back; a figure the API did not serve is
// not drawn; and the screen carries one Fraunces title.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";

import { api } from "@/lib/api";
import { aiLive } from "@/content/marketing";
import { loadQueueRows } from "./ActionQueue";
import Today, { oldestFirst, rowState } from "./Today";
import { ADMIN_TODAY as IDS } from "@/constants/testIds";

jest.mock("@/lib/api", () => ({ api: { get: jest.fn() } }));
jest.mock("@/lib/feedback", () => ({ notifyError: jest.fn() }));
jest.mock("@/content/marketing", () => ({ aiLive: jest.fn() }));
jest.mock("./ActionQueue", () => {
    const icon = () => null;
    const meta = (label) => ({ label, Icon: icon, band: 0 });
    return {
        loadQueueRows: jest.fn(),
        KIND_META: {
            payment: meta("Payout"),
            question: meta("Question"),
            collaboration: meta("Collaboration"),
            campaign: meta("Campaign"),
            brand: meta("Brand"),
            creator: meta("Creator"),
        },
    };
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
beforeAll(() => {
    window.matchMedia =
        window.matchMedia ||
        (() => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }));
});
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

const day = (d) => new Date(Date.now() - d * 86400000).toISOString();
const payment = (urgent, days) => ({
    id: `payment-${days}`,
    kind: "payment",
    since: day(days),
    urgent,
    primary: "₹15,000 to Hema",
    raw: { id: `c${days}`, payout_unpaid_days: days },
});
const ROWS = [
    { id: "campaign-1", kind: "campaign", since: day(1), primary: "Natural wine evening", raw: { id: "k1" } },
    { id: "creator-1", kind: "creator", since: day(3), primary: "Cal Mehta", raw: { user_id: "u1" } },
    { id: "question-1", kind: "question", since: day(2), primary: "Can I bring a friend?", link: "/admin/campaigns/k2", raw: {} },
];
const DASHBOARD = {
    totals: { payouts_pending: 69000, platform_revenue: 15450, active_creators: 6 },
    campaign_summary: [{ id: "done1", title: "Barrier serum", status: "closed" }],
};
const INTELLIGENCE = {
    creators: { active: 8, window_days: 60 },
    brands: { repeat: 4, total: 4 },
    fill_rate: [null, 80, 100, null, 60],
    window_weeks: 5,
};

function stubApi({ summary = null } = {}) {
    api.get.mockImplementation((url) => {
        if (url === "/admin/dashboard") return Promise.resolve({ data: DASHBOARD });
        if (url === "/admin/intelligence") return Promise.resolve({ data: INTELLIGENCE });
        if (url.endsWith("/summary")) return Promise.resolve({ data: summary });
        return Promise.reject(new Error(`unexpected ${url}`));
    });
}

async function render(rows, { allAccess = true } = {}) {
    loadQueueRows.mockResolvedValue({ rows, waiting: [], suspensions: {} });
    await act(async () => {
        root.render(
            <MemoryRouter>
                <Today allAccess={allAccess} />
            </MemoryRouter>,
        );
    });
}
const q = (id) => container.querySelector(`[data-testid="${id}"]`);

describe("the payouts tile", () => {
    test("is amber when the server flagged a payout at risk, and names the oldest day", async () => {
        aiLive.mockReturnValue(false);
        stubApi();
        await render([...ROWS, payment(true, 6), payment(false, 2)]);
        const tile = q(IDS.tile("payment"));
        expect(tile.dataset.tone).toBe("due");
        expect(tile.className).toContain("bg-state-due-wash");
        expect(tile.textContent).toContain("2");
        expect(tile.textContent).toContain("Oldest on day 6");
    });

    test("is calm while no payout is past day five", async () => {
        aiLive.mockReturnValue(false);
        stubApi();
        await render([...ROWS, payment(false, 3)]);
        expect(q(IDS.tile("payment")).dataset.tone).toBe("calm");
    });
});

test("every count is the queue's own rows, and the heading is their total", async () => {
    aiLive.mockReturnValue(false);
    stubApi();
    await render([...ROWS, payment(false, 3)]);
    expect(q(IDS.heading).textContent).toBe("4 things need a person today");
    expect(q(IDS.tile("campaign")).textContent).toContain("1");
    expect(q(IDS.tile("creator")).textContent).toContain("1");
    expect(q(IDS.tile("brand")).textContent).toContain("0");
    expect(q(IDS.tile("question")).textContent).toContain("1");
    // One Fraunces title on the screen, and every tile figure is tabular.
    expect(container.querySelectorAll(".app-title")).toHaveLength(1);
    for (const kind of ["campaign", "payment"]) {
        expect(q(IDS.tile(kind)).querySelector(".app-figure")).not.toBeNull();
    }
});

test("a team member's overview has no creator tile and no admin-only figures", async () => {
    aiLive.mockReturnValue(true);
    stubApi();
    await render(ROWS.filter((r) => r.kind !== "creator"), { allAccess: false });
    expect(q(IDS.tile("creator"))).toBeNull();
    const urls = api.get.mock.calls.map((c) => c[0]);
    expect(urls).not.toContain("/admin/intelligence");
    expect(urls.some((u) => u.endsWith("/summary"))).toBe(false);
    expect(q(IDS.figure("revenue"))).toBeNull();
    expect(q(IDS.fill)).toBeNull();
});

test("the card is oldest first, with one action per row", async () => {
    aiLive.mockReturnValue(false);
    stubApi();
    await render(ROWS);
    const rows = [...container.querySelectorAll(`[data-testid^="admin-today-row-"]`)].filter((el) =>
        /^admin-today-row-[a-z]+-\d+$/.test(el.dataset.testid),
    );
    expect(rows.map((r) => r.dataset.testid)).toEqual([
        IDS.row("creator-1"),
        IDS.row("question-1"),
        IDS.row("campaign-1"),
    ]);
    for (const row of ROWS) {
        expect(q(IDS.rowAction(row.id)).querySelectorAll("button")).toHaveLength(1);
    }
    expect(oldestFirst(ROWS).map((r) => r.id)).toEqual(["creator-1", "question-1", "campaign-1"]);
});

test("the row states are read off the row", () => {
    expect(rowState(payment(true, 6))).toEqual({ tone: "due", label: "Day 6 unpaid" });
    expect(rowState(payment(false, 2))).toEqual({ tone: "info", label: "To pay" });
    expect(rowState({ kind: "campaign", raw: { auto_published_at: "x" } }).label).toBe("Live, unread");
});

describe("the AI card", () => {
    const summary = { available: true, summary: { headline: "Reels carried it." } };

    test("is there with the switch on and a summary from the API", async () => {
        aiLive.mockReturnValue(true);
        stubApi({ summary });
        await render(ROWS);
        expect(q(IDS.ai).textContent).toContain("Reels carried it.");
        expect(q(IDS.ai).textContent).toContain("Barrier serum");
    });

    test("is not even asked for with the switch off", async () => {
        aiLive.mockReturnValue(false);
        stubApi({ summary });
        await render(ROWS);
        expect(q(IDS.ai)).toBeNull();
        expect(api.get.mock.calls.some((c) => c[0].endsWith("/summary"))).toBe(false);
    });

    test.each([
        ["the API says unavailable", { available: false }],
        ["no summary has been written", { available: true, summary: null }],
    ])("is absent when %s", async (_, response) => {
        aiLive.mockReturnValue(true);
        stubApi({ summary: response });
        await render(ROWS);
        expect(q(IDS.ai)).toBeNull();
    });
});

test("a figure the API did not serve is not drawn", async () => {
    aiLive.mockReturnValue(false);
    api.get.mockImplementation((url) => {
        if (url === "/admin/dashboard") return Promise.resolve({ data: { totals: {} } });
        if (url === "/admin/intelligence") return Promise.resolve({ data: { creators: {}, brands: {}, fill_rate: [] } });
        return Promise.reject(new Error(url));
    });
    await render(ROWS);
    expect(q(IDS.lately)).toBeNull();
});
