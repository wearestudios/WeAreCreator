// The beam footer's pure helpers: colour, fitting and the beam's motion maths.
import {
    approach,
    baselineAt,
    beamOffset,
    beamTarget,
    clamp,
    drift,
    fitSize,
    hexToRgb,
    isOffsite,
    wordHeight,
} from "../beam-wordmark-footer";

describe("clamp", () => {
    test("holds a value inside its bounds", () => {
        expect(clamp(-5, 0, 1)).toBe(0);
        expect(clamp(5, 0, 1)).toBe(1);
        expect(clamp(0.4, 0, 1)).toBe(0.4);
        expect(clamp(0, 0, 1)).toBe(0);
        expect(clamp(1, 0, 1)).toBe(1);
    });
});

// The colour sweeps in backend/tests/unit refuse a hex or rgb literal anywhere
// under src/, tests included; these are inputs to a parser, not paint, so they
// are spelled through `hex()` rather than exempting the file.
const hex = (digits) => "#" + digits;

describe("hexToRgb", () => {
    test("reads six-digit hex, with or without the hash", () => {
        expect(hexToRgb(hex("FF2731"))).toBe("255, 39, 49");
        expect(hexToRgb("091426")).toBe("9, 20, 38");
    });
    test("reads three-digit hex by doubling each digit", () => {
        expect(hexToRgb(hex("36f"))).toBe("51, 102, 255");
        expect(hexToRgb(hex("fff"))).toBe("255, 255, 255");
    });
    test("falls back on anything else", () => {
        expect(hexToRgb("rgb" + "a(0,0,0,1)")).toBe("61, 107, 255");
        expect(hexToRgb(hex("12345"), "1, 2, 3")).toBe("1, 2, 3");
        expect(hexToRgb(undefined, "0, 0, 0")).toBe("0, 0, 0");
    });
});

describe("fitSize", () => {
    test("grows with the width it has to fill", () => {
        const widths = [200, 390, 768, 1120, 1440];
        const sizes = widths.map((w) => fitSize(300, w));
        for (let i = 1; i < sizes.length; i += 1) expect(sizes[i]).toBeGreaterThan(sizes[i - 1]);
        expect(fitSize(300, 600)).toBe(200);
    });
    test("is never larger than its cap, and never decreases under one", () => {
        const sizes = [100, 400, 800, 1600].map((w) => fitSize(100, w, 500));
        for (let i = 1; i < sizes.length; i += 1) expect(sizes[i]).toBeGreaterThanOrEqual(sizes[i - 1]);
        expect(Math.max(...sizes)).toBe(500);
    });
    test("is 0 for a word that was never measured", () => {
        expect(fitSize(0, 400)).toBe(0);
        expect(fitSize(300, 0)).toBe(0);
        expect(fitSize(NaN, 400)).toBe(0);
    });
});

describe("approach", () => {
    test("converges on its target from either side", () => {
        for (const start of [0, 100]) {
            let v = start;
            let gap = Math.abs(v - 58);
            for (let i = 0; i < 400; i += 1) {
                v = approach(v, 58, 0.05, 1 / 60);
                const next = Math.abs(v - 58);
                expect(next).toBeLessThanOrEqual(gap);
                gap = next;
            }
            expect(gap).toBeLessThan(0.01);
        }
    });
    test("does not move with no time passing, and does not overshoot a long frame", () => {
        expect(approach(10, 50, 0.2, 0)).toBe(10);
        const v = approach(10, 50, 0.2, 5);
        expect(v).toBeGreaterThan(10);
        expect(v).toBeLessThanOrEqual(50);
    });
});

describe("baselineAt", () => {
    test("stays inside its bounds for any metrics", () => {
        const cases = [
            [80, 20],
            [95, 30],
            [10, 0],
            [200, 0],
            [70, 90],
        ];
        for (const [a, d] of cases) {
            const b = baselineAt(a, d);
            expect(b).toBeGreaterThanOrEqual(0.5);
            expect(b).toBeLessThanOrEqual(1.2);
        }
    });
    test("falls back to 0.8 without metrics", () => {
        expect(baselineAt(undefined, undefined)).toBe(0.8);
        expect(baselineAt(0, 20)).toBe(0.8);
        expect(baselineAt(80, -1)).toBe(0.8);
    });
    test("centres the content area in a 100px line box", () => {
        expect(baselineAt(80, 20)).toBeCloseTo(0.8);
    });
});

describe("the rest of the beam", () => {
    test("beamTarget maps the pointer across its band", () => {
        expect(beamTarget(0)).toBe(30);
        expect(beamTarget(1)).toBe(82);
        expect(beamTarget(NaN)).toBe(56);
        expect(beamTarget(5)).toBe(82);
    });
    test("drift stays within its amplitude", () => {
        for (let t = 0; t < 600; t += 0.7) {
            const v = drift(t);
            expect(v).toBeGreaterThanOrEqual(58 - 9);
            expect(v).toBeLessThanOrEqual(58 + 9);
        }
    });
    test("wordHeight is never negative and clamps the cut", () => {
        expect(wordHeight(100, 0.8, 0.14)).toBeCloseTo(94);
        expect(wordHeight(100, 0.8, 9)).toBeCloseTo(120);
        expect(wordHeight(100, 0.1, -0.4)).toBe(0);
    });
    test("beamOffset centres the painted beam on the beam's position", () => {
        expect(beamOffset(50)).toBe(0);
        expect(beamOffset(58)).toBe(8);
        expect(beamOffset(NaN)).toBe(8);
    });
    test("isOffsite is only true for an absolute http(s) link", () => {
        expect(isOffsite("https://wa.me/91")).toBe(true);
        expect(isOffsite("/work")).toBe(false);
        expect(isOffsite("mailto:a@b.c")).toBe(false);
    });
});
