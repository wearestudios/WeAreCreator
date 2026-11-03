// The Applications list draws barter as barter.
//
// A barter collaboration has no agreed amount on purpose, so the row used to
// fall back to `quoted_rate` and print the creator's own quote with a rupee
// sign, as if a fee had been agreed on a brief that pays a dinner.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import Applications from "./Applications";
import { CREATOR_APPLICATIONS as IDS } from "@/constants/testIds";

// The list never calls the API on render; mocking it keeps axios (an ES
// module) out of Jest's transform.
jest.mock("@/lib/api", () => ({ api: { post: jest.fn(), get: jest.fn() } }));
jest.mock("@/lib/feedback", () => ({ notifyError: jest.fn(), notifySuccess: jest.fn() }));

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
});

const base = {
    campaign_id: "c1",
    campaign_title: "Weekend tasting",
    brand_name: "Toit",
    state: "accepted",
    created_at: "2026-10-01T10:00:00Z",
    quoted_rate: 9000,
    agreed_amount: null,
};

function render(applied) {
    act(() => {
        root.render(
            <MemoryRouter>
                <Applications applied={applied} declined={[]} invitations={[]} />
            </MemoryRouter>,
        );
    });
}

const amount = (id) => container.querySelector(`[data-testid="${IDS.amount(id)}"]`);

test("a barter row shows the barter terms, muted, and never the quote", () => {
    render([
        {
            ...base,
            id: "b1",
            compensation_type: "barter",
            barter_terms: "Dinner for two",
        },
    ]);
    const cell = amount("b1");
    expect(cell).not.toBeNull();
    expect(cell.textContent).toBe("Barter · Dinner for two");
    expect(cell.getAttribute("data-barter")).toBe("true");
    expect(cell.className).toContain("text-muted-foreground");
    expect(cell.className).toContain("text-meta");
    // The creator's own quote must appear nowhere on the row.
    const row = container.querySelector(`[data-testid="${IDS.row("b1")}"]`);
    expect(row.textContent).not.toMatch(/9,000|₹/);
});

test("a barter row with no stated terms still says barter", () => {
    render([{ ...base, id: "b2", compensation_type: "barter", barter_terms: null }]);
    expect(amount("b2").textContent).toBe("Barter");
});

test("a paid row is unchanged: the agreed fee, or the quote before one", () => {
    render([
        { ...base, id: "p1", compensation_type: "fixed", agreed_amount: 12000 },
        { ...base, id: "p2", compensation_type: "negotiated" },
    ]);
    expect(amount("p1").textContent).toBe("12,000");
    expect(amount("p1").getAttribute("data-barter")).toBeNull();
    expect(amount("p2").textContent).toBe("9,000");
});
