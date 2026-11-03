// Turns the originals in `public/img/photos/_incoming/` into the files the
// public site's photo slots serve. Run it from `frontend/`:
//
//     npm run photos
//     node scripts/prepare-photos.mjs [incomingDir]
//
// Drop an original into `_incoming/` named after its slot —
// `brands-full-room.jpg`, `auth-login.webp`, any of jpg/jpeg/png/webp — and
// run this. For each slot it finds, it:
//
//   1. **steps around the corner mark.** Generated images carry a small
//      sparkle in the bottom-right corner. The crop never covers a box of
//      `max(150px, 12% of the short side)` in that corner, which clears the
//      mark on every original measured with room to spare (the largest sat
//      133px in from the edges of a 1493px side). It shrinks whichever
//      dimension costs less picture, so the ratio is exact either way. Every
//      corner is also scored for a small grey shape that differs from its
//      surroundings, and a hit anywhere else is printed: a replacement from a
//      different generator puts its mark somewhere this does not expect, and
//      the person running this has to look;
//   2. **crops to the slot's ratio**, placed on the slot's anchor — the part
//      of the frame the layout needs: the subject on the right where a
//      headline sits on the left, the people rather than the ceiling;
//   3. **exports two widths as WebP**, `<slot>-<small>.webp` and
//      `<slot>-<large>.webp` (1200/2400 landscape, 900/1800 portrait),
//      starting at quality 78 and stepping down until each file is inside its
//      budget — 140 KB for the small one, 350 KB for the large one. A file
//      that cannot get there by quality 50 fails the run rather than
//      shipping soft;
//   4. **strips metadata.** sharp writes none unless asked (`withMetadata`
//      is never called here) and converts to sRGB on the way, so no EXIF, no
//      XMP and no ICC profile reaches the site — a generated image's
//      provenance block and a phone's GPS tag alike;
//   5. **deletes `_incoming/`** once every slot it found has exported, so an
//      original is never committed. `.gitignore` covers it too.
//
// A source narrower than the large width is upsampled (lanczos3) and says so:
// the `2400w` descriptor in `srcSet` has to be true of the file. A sharper
// original dropped in later replaces it with no other change.
//
// Wiring a new photograph is then one entry in `src/content/photoSlots.js`:
// `src`, `srcSet`, `alt` and `focal`. This script prints the first two.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(HERE, "../public/img/photos");
const INCOMING = path.resolve(process.argv[2] || path.join(OUT, "_incoming"));

/** Bytes a file may weigh, by which of the two widths it is. */
export const BUDGET = { small: 140 * 1024, large: 350 * 1024 };
const START_QUALITY = 78;
const QUALITY_STEP = 4;
const MIN_QUALITY = 50;

const LANDSCAPE = { small: 1200, large: 2400 };
const PORTRAIT = { small: 900, large: 1800 };

/**
 * Each slot's ratio, widths and anchor. The anchor is where the crop window
 * centres, as fractions of the original (0 left/top, 1 right/bottom), and is
 * clamped so the window stays inside the picture.
 */
export const SLOTS = {
    // The homepage slider's "On location" slide: a rounded 3:2 frame with a
    // chip top right and the booking card bottom left, so the subject wants
    // the right half and those two corners want to be calm.
    "home-on-location": { ratio: [3, 2], widths: LANDSCAPE, anchor: [0.6, 0.5] },
    // The two audience-page bands: 2:1, headline card bottom left.
    "brands-full-room": { ratio: [2, 1], widths: LANDSCAPE, anchor: [0.5, 0.5] },
    "creators-on-shoot": { ratio: [2, 1], widths: LANDSCAPE, anchor: [0.5, 0.5] },
    // The sign-in and sign-up asides: portrait, logo top left, line bottom left.
    "auth-login": { ratio: [3, 4], widths: PORTRAIT, anchor: [0.5, 0.5] },
    "auth-signup": { ratio: [3, 4], widths: PORTRAIT, anchor: [0.6, 0.5] },
    // The 404's picture, a rounded 4:3 card.
    "not-found": { ratio: [4, 3], widths: LANDSCAPE, anchor: [0.5, 0.5] },
};

const EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

/** The corner box the crop must not cover, in px. */
export function markBox(width, height) {
    return Math.max(150, Math.round(0.12 * Math.min(width, height)));
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/**
 * The crop window: the slot's exact ratio, the largest that fits without
 * covering the bottom-right mark box, centred on the anchor. Pure.
 */
export function cropWindow(width, height, [rw, rh], [ax, ay]) {
    const b = markBox(width, height);
    // The largest window at this ratio. Whole multiples of the ratio, so the
    // crop is exactly 3:4 rather than 1365×1821 — which resizes to 1800×2401
    // and makes the reserved box and the file disagree by a pixel row.
    const fit = (maxW, maxH) => {
        const k = Math.floor(Math.min(maxW / rw, maxH / rh));
        return { w: rw * k, h: rh * k };
    };
    // Either the window stops short of the mark on the right, or above it.
    const left = { ...fit(width - b, height), xMax: width - b, yMax: height };
    const above = { ...fit(width, height - b), xMax: width, yMax: height - b };
    const pick = left.w * left.h >= above.w * above.h ? left : above;
    const x = Math.round(clamp(ax * width - pick.w / 2, 0, pick.xMax - pick.w));
    const y = Math.round(clamp(ay * height - pick.h / 2, 0, pick.yMax - pick.h));
    return { left: x, top: y, width: pick.w, height: pick.h, mark: b };
}

/**
 * Scores each corner for something mark-shaped: a cluster of low-saturation
 * pixels well away from the corner's median brightness. Returns the corners
 * that look marked. A report, not a decision — the crop always avoids the
 * bottom-right, and anything else needs a person to look.
 */
async function suspectCorners(file, width, height) {
    const size = Math.min(220, Math.floor(Math.min(width, height) / 4));
    const corners = {
        "top-left": [0, 0],
        "top-right": [width - size, 0],
        "bottom-left": [0, height - size],
        "bottom-right": [width - size, height - size],
    };
    const hits = [];
    for (const [name, [left, top]] of Object.entries(corners)) {
        const { data } = await sharp(file)
            .extract({ left, top, width: size, height: size })
            .removeAlpha()
            .raw()
            .toBuffer({ resolveWithObject: true });
        const n = size * size;
        const lum = new Float32Array(n);
        for (let i = 0; i < n; i += 1) lum[i] = (data[i * 3] + data[i * 3 + 1] + data[i * 3 + 2]) / 3;
        const median = Float32Array.from(lum).sort()[n >> 1];
        let count = 0;
        for (let i = 0; i < n; i += 1) {
            const r = data[i * 3];
            const g = data[i * 3 + 1];
            const bl = data[i * 3 + 2];
            const sat = Math.max(r, g, bl) - Math.min(r, g, bl);
            if (sat < 14 && Math.abs(lum[i] - median) > 45 && lum[i] > 110 && lum[i] < 215) count += 1;
        }
        // The sparkle covers 1–5% of its box; scenery that matches the test
        // is either scattered (a few px) or a whole lit wall (most of it).
        const share = count / n;
        if (share > 0.01 && share < 0.12) hits.push(`${name} (${(share * 100).toFixed(1)}%)`);
    }
    return hits;
}

async function exportWidth(pipeline, width, budget) {
    let quality = START_QUALITY;
    for (;;) {
        const buf = await pipeline
            .clone()
            .resize({ width, kernel: "lanczos3" })
            .webp({ quality, effort: 6, smartSubsample: true })
            .toBuffer();
        if (buf.length <= budget) return { buf, quality };
        if (quality - QUALITY_STEP < MIN_QUALITY) {
            throw new Error(`${width}px is ${Math.round(buf.length / 1024)} KB at quality ${quality}, over ${budget / 1024} KB`);
        }
        quality -= QUALITY_STEP;
    }
}

async function main() {
    if (!fs.existsSync(INCOMING)) {
        console.log(`Nothing to do: ${path.relative(process.cwd(), INCOMING)} does not exist.`);
        return;
    }
    fs.mkdirSync(OUT, { recursive: true });
    const rows = [];
    const missing = [];
    for (const [slot, spec] of Object.entries(SLOTS)) {
        const source = EXTENSIONS.map((ext) => path.join(INCOMING, slot + ext)).find((f) => fs.existsSync(f));
        if (!source) {
            missing.push(slot);
            continue;
        }
        // Upright first: a phone's JPEG can be stored sideways with an EXIF
        // orientation, and the crop is worked out on the picture as seen.
        const upright = await sharp(source).rotate().toBuffer();
        const meta = await sharp(upright).metadata();
        const suspects = await suspectCorners(upright, meta.width, meta.height);
        const win = cropWindow(meta.width, meta.height, spec.ratio, spec.anchor);
        const cropped = sharp(upright).extract(win);
        // And afterwards: the corner of the crop should now be scenery.
        const croppedBuf = await cropped.clone().png().toBuffer();
        const after = await suspectCorners(croppedBuf, win.width, win.height);
        const out = {};
        for (const size of ["small", "large"]) {
            const w = spec.widths[size];
            const { buf, quality } = await exportWidth(cropped, w, BUDGET[size]);
            const file = path.join(OUT, `${slot}-${w}.webp`);
            fs.writeFileSync(file, buf);
            out[size] = { w, bytes: buf.length, quality };
        }
        rows.push({ slot, source: path.basename(source), meta, win, suspects, after, out, spec });
    }

    for (const r of rows) {
        const { slot, win, out, spec } = r;
        console.log(`\n${slot}  ←  ${r.source} (${r.meta.width}×${r.meta.height})`);
        console.log(`  crop ${win.width}×${win.height} at ${win.left},${win.top}; bottom-right ${win.mark}px kept out`);
        if (win.width < spec.widths.large) {
            console.log(`  upsampled: the crop is ${win.width}px wide and the large file is ${spec.widths.large}px`);
        }
        const other = r.suspects.filter((s) => !s.startsWith("bottom-right"));
        if (other.length) console.log(`  LOOK AT THIS: something mark-shaped in ${other.join(", ")}`);
        const left = r.after.filter((s) => s.startsWith("bottom-right"));
        if (left.length) console.log(`  LOOK AT THIS: the cropped bottom-right still scores ${left.join(", ")}`);
        for (const size of ["small", "large"]) {
            const o = out[size];
            console.log(`  ${slot}-${o.w}.webp  ${(o.bytes / 1024).toFixed(1)} KB  q${o.quality}`);
        }
        console.log(
            `  src: "/img/photos/${slot}-${out.large.w}.webp",\n` +
                `  srcSet: "/img/photos/${slot}-${out.small.w}.webp ${out.small.w}w, /img/photos/${slot}-${out.large.w}.webp ${out.large.w}w",`,
        );
    }
    if (missing.length) console.log(`\nNo original for: ${missing.join(", ")}`);

    if (rows.length) {
        fs.rmSync(INCOMING, { recursive: true, force: true });
        console.log(`\nRemoved ${path.relative(process.cwd(), INCOMING)}/ — only the exports are committed.`);
    }
}

// Only when run, so the pure helpers above can be imported and tested.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    main().catch((err) => {
        console.error(err);
        process.exit(1);
    });
}
