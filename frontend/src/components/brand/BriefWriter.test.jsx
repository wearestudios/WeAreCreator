// The writer is absent when the server says it is off, and says the agreed
// sentence when a draft fails.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";

const mockPost = jest.fn();
jest.mock("@/lib/api", () => ({
    api: { post: (...a) => mockPost(...a) },
    apiErrorCode: (e) => e?.response?.data?.detail?.code ?? null,
    formatApiError: (e) => e?.response?.data?.detail?.message ?? "error",
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const BriefWriter = require("./BriefWriter").default;

let container;
let root;
beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockPost.mockReset();
});
afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

const byId = (id) => container.querySelector(`[data-testid="${id}"]`);

function type(value) {
    const el = byId("brief-writer-input");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    act(() => {
        setter.call(el, value);
        el.dispatchEvent(new Event("input", { bubbles: true }));
    });
}

test("renders nothing with AI off", () => {
    act(() => root.render(<BriefWriter status={{ available: false }} onDraft={() => {}} />));
    expect(container.innerHTML).toBe("");
});

test("drafts, hands the fields to the form, and counts down", async () => {
    const onDraft = jest.fn();
    mockPost.mockResolvedValue({ data: { fields: { title: "Brunch" }, notices: ["Sounds like barter."], remaining: 9 } });
    act(() => root.render(<BriefWriter status={{ available: true, remaining: 10, limit: 10 }} onDraft={onDraft} />));
    type("Brunch launch this Saturday, 4 creators");
    await act(async () => byId("brief-writer-submit").click());
    expect(mockPost.mock.calls[0][0]).toBe("/brand/campaigns/brief-writer");
    expect(onDraft).toHaveBeenCalledWith({ title: "Brunch" });
    expect(byId("brief-writer-remaining").textContent).toBe("9 of 10 drafts left today");
    expect(byId("brief-writer-notices").textContent).toContain("barter");
});

test("a failure says to fill it in below", async () => {
    mockPost.mockRejectedValue({ code: "ECONNABORTED" });
    act(() => root.render(<BriefWriter status={{ available: true, remaining: 10, limit: 10 }} onDraft={() => {}} />));
    type("Brunch launch this Saturday");
    await act(async () => byId("brief-writer-submit").click());
    expect(byId("brief-writer-error").textContent).toBe("Couldn't draft this — fill it in below.");
});

test("the skeleton shows while drafting", async () => {
    let resolve;
    mockPost.mockReturnValue(new Promise((r) => (resolve = r)));
    act(() => root.render(<BriefWriter status={{ available: true, remaining: 10, limit: 10 }} onDraft={() => {}} />));
    type("Brunch launch this Saturday");
    act(() => byId("brief-writer-submit").click());
    expect(byId("brief-writer-skeleton")).not.toBeNull();
    await act(async () => resolve({ data: { fields: {}, notices: [], remaining: 9 } }));
    expect(byId("brief-writer-skeleton")).toBeNull();
});
