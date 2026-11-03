// The app's primitives, rendered.
//
// The AI card is the one that matters most here: it must be absent — not
// empty, not a placeholder — unless the public switch is on *and* the endpoint
// returned a summary. An empty cream card is still the AI being advertised.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";

import { aiLive } from "@/content/marketing";
import { AiSummaryCard, ActionCard, Pill, Sparkline, StatTile } from "../ui";

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
    aiLive.mockReset();
});

const render = (el) => act(() => root.render(el));

describe("AiSummaryCard", () => {
    test("renders the summary when the switch is on and there is one", () => {
        aiLive.mockReturnValue(true);
        render(<AiSummaryCard testid="ai" text="Reels carried the campaign." />);
        const card = container.querySelector('[data-testid="ai"]');
        expect(card).not.toBeNull();
        expect(card.textContent).toContain("Reels carried the campaign.");
        expect(aiLive).toHaveBeenCalledWith("campaignSummary");
    });

    test("is absent when the switch is off, whatever the API said", () => {
        aiLive.mockReturnValue(false);
        render(<AiSummaryCard testid="ai" text="Reels carried the campaign." />);
        expect(container.innerHTML).toBe("");
    });

    test.each([[undefined], [null], [""], ["   "]])("is absent when the API returned %p", (text) => {
        aiLive.mockReturnValue(true);
        render(<AiSummaryCard testid="ai" text={text} />);
        expect(container.innerHTML).toBe("");
    });
});

describe("Sparkline", () => {
    test("draws nothing from fewer than two numbers", () => {
        render(<Sparkline points={[120]} />);
        expect(container.querySelector("svg")).toBeNull();
    });

    test("draws the line once, from the numbers given and nothing else", () => {
        render(<Sparkline points={[10, null, 30, 20]} label="Views" />);
        const paths = container.querySelectorAll("path");
        expect(paths).toHaveLength(2);
        const line = paths[1];
        expect(line.getAttribute("class")).toContain("dash-draw");
        // Three real points → one move and two line segments; the null is
        // dropped rather than drawn as a zero.
        expect(line.getAttribute("d").match(/[ML]/g)).toEqual(["M", "L", "L"]);
    });
});

describe("the rest", () => {
    test("a pill names its state in words on its tint", () => {
        render(<Pill tone="due">Due Thursday</Pill>);
        const pill = container.firstChild;
        expect(pill.textContent).toBe("Due Thursday");
        expect(pill.className).toContain("bg-state-due-wash");
    });

    test("an action card is red only when told and carries the one action given", () => {
        render(<ActionCard tone="red" title="Approve the draft" action={<button>Review</button>} testid="act" />);
        const card = container.querySelector('[data-testid="act"]');
        expect(card.className).toContain("bg-wash-red");
        expect(card.querySelectorAll("button")).toHaveLength(1);
    });

    test("a stat tile prints the value it was handed", () => {
        render(<StatTile value="2,86,900" label="Views" testid="tile" />);
        expect(container.querySelector('[data-testid="tile"]').textContent).toBe("2,86,900Views");
    });
});
