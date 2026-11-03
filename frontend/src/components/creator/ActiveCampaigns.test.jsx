// The creator's live work card, rendered against dashboard-shaped rows.
//
// What it holds: the next step and its button come before the reference half
// of the card (which folds away), the box is red only when the move is the
// creator's, there is at most one red button, whose move it is comes from the
// server's process owner, and the tracker is the shared component's bars.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";

import ActiveCampaigns from "./ActiveCampaigns";
import { APPLICATION, CREATOR_ACTIVE as IDS } from "@/constants/testIds";

jest.mock("@/lib/api", () => ({ api: { post: jest.fn(), get: jest.fn() }, mediaUrl: (u) => u }));
jest.mock("@/lib/feedback", () => ({ notifyError: jest.fn(), notifySuccess: jest.fn() }));

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
});

const STAGES = ["Submitted", "Verified", "Negotiated", "Scheduled", "Attended", "Content review", "Content delivery", "Payment"];
const process = (at, owner, label) => ({
    stages: STAGES.map((l, i) => ({ key: `s${i}`, label: l, done: i < at, current: i === at })),
    stage_number: at + 1,
    stage_count: 8,
    next_action: owner ? { owner, label } : null,
    banner: null,
});

const BOOK = {
    id: "k1",
    campaign_id: "c1",
    campaign_title: "Weekend brunch, Indiranagar",
    brand_name: "Thirdwave Coffee",
    state: "commercial_agreed",
    compensation_type: "fixed",
    agreed_amount: 8000,
    deliverable_items: [{ type: "reel", quantity: 1 }, { type: "story", quantity: 3 }],
    next_action: { action: "book_slot", label: "Pick a time inside the window.", waiting_on: "you" },
    process: process(2, "creator", "Pick your slot"),
    can_raise_dispute: true,
    brief_details: { brief_dos: ["Tag the venue"] },
    negotiation: { entries: [{ kind: "offer", amount: 8000, by_role: "creator", at: "2026-10-01T10:00:00Z" }] },
};

const WAITING = {
    ...BOOK,
    id: "k2",
    state: "content_submitted",
    agreed_amount: 25000,
    next_action: { action: "resubmit_content", label: "The brand is reviewing your content.", waiting_on: "brand" },
    process: process(5, "admin", "The content is being reviewed"),
};

const render = (rows) =>
    act(() =>
        root.render(
            <MemoryRouter>
                <ActiveCampaigns collaborations={rows} />
            </MemoryRouter>,
        ),
    );
const q = (id) => container.querySelector(`[data-testid="${id}"]`);
const card = (id) => q(IDS.card(id));

test("the next step and its button come before the folded reference half", () => {
    render([BOOK]);
    const html = card("k1").innerHTML;
    const button = html.indexOf(IDS.primary("k1"));
    expect(button).toBeGreaterThan(-1);
    const more = q(IDS.more("k1"));
    expect(more.tagName).toBe("DETAILS");
    expect(more.open).toBe(false);
    // The checklist and the fee's history live inside the fold, after it.
    expect(more.textContent).toContain("How the fee was agreed");
    expect(html.indexOf(IDS.more("k1"))).toBeGreaterThan(button);
});

test("their move: a red box, one red button, and the card's own sentence", () => {
    render([BOOK]);
    expect(q(IDS.move("k1")).textContent).toBe("Your move");
    expect(card("k1").querySelectorAll(".bg-wash-red")).toHaveLength(1);
    expect(card("k1").querySelectorAll(".bg-urgent")).toHaveLength(1);
    expect(q(IDS.nextAction("k1")).textContent).toBe("Pick a time inside the window.");
});

test("somebody else's move: navy, no red, and the wait named by the server's owner", () => {
    render([WAITING]);
    // The owner is WeAre on this row — mapped through execution_owner — so the
    // card does not tell the creator the brand is reviewing it.
    expect(q(IDS.move("k2")).textContent).toBe("WeAre's move");
    expect(q(IDS.nextAction("k2")).textContent).toBe("The content is being reviewed");
    expect(card("k2").querySelectorAll(".bg-wash-red")).toHaveLength(0);
    expect(card("k2").querySelectorAll(".bg-urgent")).toHaveLength(0);
});

test("the tracker is the shared flow's bars: done, current, still to come", () => {
    render([BOOK]);
    const flow = card("k1").querySelector(`[data-testid="${APPLICATION.process}"]`);
    expect(flow.dataset.variant).toBe("bars");
    const states = [...flow.querySelectorAll("li")].map((li) => li.dataset.state);
    expect(states).toEqual(["done", "done", "current", "todo", "todo", "todo", "todo", "todo"]);
    expect(flow.textContent).toContain("Negotiated");
    expect(flow.textContent).toContain("Stage 3 of 8");
});

test("raising a dispute is folded away until one exists, and an open one leads", () => {
    render([BOOK]);
    expect(q(IDS.more("k1")).textContent).toContain("Raise a dispute");

    act(() => root.unmount());
    root = createRoot(container);
    render([{ ...BOOK, dispute: { state: "open", raised_by_role: "creator", reason: "Unpaid" } }]);
    const html = card("k1").innerHTML;
    // Above the next step, not inside the fold.
    expect(q(IDS.more("k1"))?.textContent || "").not.toContain("Under dispute");
    expect(html.indexOf("dispute")).toBeLessThan(html.indexOf(IDS.primary("k1")));
});

test("brand, what was asked and the fee share one line, and barter reads as barter", () => {
    render([{ ...BOOK, compensation_type: "barter", agreed_amount: null, barter_terms: "Brunch for two" }]);
    const amount = q(IDS.amount("k1"));
    expect(amount.dataset.barter).toBe("true");
    expect(amount.textContent).toContain("Brunch for two");
    expect(amount.textContent).not.toContain("₹");
    expect(card("k1").textContent).toContain("1 reel · 3 stories");
});

test("two cards sit two up; one card takes the row", () => {
    render([BOOK, WAITING]);
    expect(q(IDS.list).className).toContain("lg:grid-cols-[1.25fr_1fr]");
    act(() => root.unmount());
    root = createRoot(container);
    render([BOOK]);
    expect(q(IDS.list).className).not.toContain("lg:grid-cols");
});
