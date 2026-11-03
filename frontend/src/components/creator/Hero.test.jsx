// The creator's header: who, where the follower count came from, and the
// three figures — rendered.
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";

import Hero from "./Hero";
import { CREATOR_HERO as IDS } from "@/constants/testIds";

jest.mock("@/lib/api", () => ({ mediaUrl: (u) => u }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
beforeAll(() => {
    // CountUp asks framer-motion about reduced motion; answer "reduce" so the
    // figures paint at their final value.
    window.matchMedia = () => ({ matches: true, addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {} });
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

const PROFILE = {
    name: "Ana Kulkarni",
    verification_status: "verified",
    instagram_handle: "ana.eats",
    niches: ["fnb", "nightlife"],
    city: "Pune",
    follower_count: 42000,
    follower_count_verified: false,
};
const EARNINGS = { lifetime_earned: 49000, pending_earnings: 32300, campaigns_completed: 3 };

const render = (profile) => act(() => root.render(<Hero user={{ name: "Ana" }} profile={profile} earnings={EARNINGS} />));
const q = (id) => container.querySelector(`[data-testid="${id}"]`);

test("the line is handle · niche · their city · followers · where that number came from", () => {
    render(PROFILE);
    const header = q(IDS.section).textContent;
    for (const part of ["@ana.eats", "F&B", "Pune", "42k followers", "self-reported"]) {
        expect(header).toContain(part);
    }
    expect(q(IDS.followersVerified)).toBeNull();
});

test('"from Instagram" only when the count was read from Instagram', () => {
    render({ ...PROFILE, follower_count_verified: true });
    expect(q(IDS.followersVerified).textContent).toBe("from Instagram");
    expect(q(IDS.followersNote)).toBeNull();
});

test("one Fraunces title, the verified pill, and three figures from the payload", () => {
    render(PROFILE);
    expect(container.querySelectorAll(".app-title")).toHaveLength(1);
    expect(q(IDS.badge("verified")).textContent).toBe("Verified");
    expect(q(IDS.lifetime).textContent).toBe("49,000");
    expect(q(IDS.pending).textContent).toBe("32,300");
    expect(q(IDS.completed).textContent).toBe("3");
    // Every figure sits in a tabular cell.
    for (const id of [IDS.lifetime, IDS.pending, IDS.completed]) {
        expect(q(id).closest(".app-figure")).not.toBeNull();
    }
});

test("no city, no niche, no count — nothing left dangling", () => {
    render({ ...PROFILE, city: null, niches: [], follower_count: null });
    const line = q(IDS.handle).closest("p");
    // Only the handle is left on the line.
    expect(line.children).toHaveLength(1);
});
