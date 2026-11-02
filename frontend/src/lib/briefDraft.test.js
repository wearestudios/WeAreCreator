// The brief writer never overwrites what a brand typed without asking.
import { isAiValue, planDraft, toFormValue } from "./briefDraft";

const baseline = { title: "", budget_per_creator: "", creators_needed: "1", compensation_type: "fixed", area: "" };

test("an empty form takes the whole draft", () => {
    const { apply, conflicts } = planDraft({
        fields: { title: "Brunch launch", budget_per_creator: 6000, creators_needed: 4 },
        current: { ...baseline },
        baseline,
    });
    expect(apply).toEqual({ title: "Brunch launch", budget_per_creator: "6000", creators_needed: "4" });
    expect(conflicts).toEqual([]);
});

test("a field the brand typed is a conflict, not a silent overwrite", () => {
    const { apply, conflicts } = planDraft({
        fields: { title: "Brunch launch", creators_needed: 4 },
        current: { ...baseline, title: "My own title" },
        baseline,
    });
    expect(conflicts).toEqual(["title"]);
    expect(apply).toEqual({ creators_needed: "4" });
});

test("regenerate replaces what the last draft wrote, but not what was edited since", () => {
    const aiValues = { title: "Brunch launch", budget_per_creator: "6000" };
    const current = { ...baseline, title: "Brunch launch", budget_per_creator: "7000" };
    const { apply, conflicts } = planDraft({
        fields: { title: "Weekend brunch", budget_per_creator: 6000 },
        current,
        baseline,
        aiValues,
    });
    expect(apply).toEqual({ title: "Weekend brunch" });
    expect(conflicts).toEqual(["budget_per_creator"]);
});

test("the marker follows the value: typing removes it", () => {
    const aiValues = { title: "Brunch launch" };
    expect(isAiValue("title", { title: "Brunch launch" }, aiValues)).toBe(true);
    expect(isAiValue("title", { title: "Brunch launch!" }, aiValues)).toBe(false);
    expect(isAiValue("budget_per_creator", { budget_per_creator: "" }, aiValues)).toBe(false);
});

test("barter is left unselected, never chosen", () => {
    expect(toFormValue("compensation_type", null)).toBeNull();
    const { apply } = planDraft({
        fields: { compensation_type: null },
        current: { ...baseline },
        baseline,
    });
    expect(apply.compensation_type).toBeNull();
});

test("an area the select cannot show is skipped", () => {
    const { apply } = planDraft({
        fields: { area: "Whitefield" },
        current: { ...baseline },
        baseline,
        allowed: { area: (v) => ["Indiranagar"].includes(v) },
    });
    expect(apply).toEqual({});
});

test("deliverables compare by what was asked for, not by zeros", () => {
    const aiValues = { deliverable_items: { reel: 2 } };
    expect(isAiValue("deliverable_items", { deliverable_items: { reel: 2, story: 0 } }, aiValues)).toBe(true);
});
