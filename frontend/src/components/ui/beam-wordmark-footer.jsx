// Adapted from Beam Wordmark Footer (21st.dev), original author credited per
// its licence. The source file carried no licence text of its own; the credit
// is kept here, in the source, and never rendered in the UI.
//
// A dark closing section crossed by a slow diagonal shaft of light, with a
// giant, bottom-cropped wordmark the light runs through.
//
// Changes from the original, all deliberate:
//   - JavaScript, no types; generic props, no template text, names or credits.
//   - No social buttons and no credit lines: `contactLines` take their place.
//   - Links go through `renderLink` when given one (a router link), else <a>.
//     An absolute http(s) link opens in a new tab with noopener noreferrer;
//     `external` alone means "not a router link" (a mailto, or a page the
//     backend renders) and stays in the tab.
//   - **The loop moves layers; it never repaints.** The original wrote the
//     beam's position into CSS variables on the root every frame, which moved
//     gradient stops inside a blurred backdrop and inside every letter — a
//     full repaint per frame, measured at ~100ms of main thread each on a
//     laptop. Here the beam, the pointer glow and the rule's highlight are
//     static paintings on their own layers, and the loop writes only their
//     `transform` and `opacity`, which the compositor applies. The letters
//     are a static fill blended with `mix-blend-mode: screen`, so the beam
//     passing beneath lights them without the letters being painted again.
//   - Reduced motion draws the beam once, at rest: no rAF loop, no drift, no
//     pointer glow. The loop also stops while the footer is offscreen or the
//     tab is hidden.
//   - Every easing is the site's one curve, `--weare-ease`; every tint is a
//     `color-mix` over the palette, so a palette can be design tokens.
//   - The wordmark is decorative (aria-hidden); a visually hidden label
//     carries the name once.
import * as React from "react";

// #region beam — pure: colour, fitting and beam maths. Exported for the tests.

export const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);

/**
 * A three- or six-digit hex, hash optional → "r, g, b". Anything unparseable
 * falls back. Kept from the original for callers holding a hex; the component
 * itself mixes colours with `color-mix`, so its palette may be tokens.
 */
export const hexToRgb = (hex, fallback = "61, 107, 255") => {
    const m = /^#?([\da-f]{3}|[\da-f]{6})$/i.exec((hex || "").trim());
    if (!m) return fallback;
    const h = m[1].length === 3 ? m[1].replace(/./g, (c) => c + c) : m[1];
    const n = parseInt(h, 16);
    return ((n >> 16) & 255) + ", " + ((n >> 8) & 255) + ", " + (n & 255);
};

/**
 * Font size (px) that makes a word measured at 100px span `target` px. A short
 * word would grow into a tower, so it is capped at `cap` px. Bad input is 0.
 */
export const fitSize = (measuredAt100, target, cap) => {
    if (!(measuredAt100 > 0) || !(target > 0)) return 0;
    const size = (100 * target) / measuredAt100;
    return cap > 0 ? Math.min(size, cap) : size;
};

/** Where the beam sits (% across the section) for a pointer at `u` (0 → 1 across). */
export const beamTarget = (u, lo = 30, hi = 82) =>
    lo + (hi - lo) * clamp(Number.isFinite(u) ? u : 0.5, 0, 1);

/** The beam's idle sway: two slow, unrelated sines so it never visibly loops. */
export const drift = (t, centre = 58, amp = 9) =>
    centre + amp * (0.7 * Math.sin(t * 0.21) + 0.3 * Math.sin(t * 0.077 + 1.3));

/** Frame-rate independent ease toward a target: `k` is the fraction closed per 1/60s. */
export const approach = (from, to, k, dt) =>
    to + (from - to) * Math.pow(1 - clamp(k, 0, 1), clamp(dt, 0, 0.1) * 60);

/**
 * Where the baseline sits in a `line-height: 1` box, as a fraction of the font
 * size, from the font's ascent and descent at 100px. The line box is 100px; the
 * content area is centred in it. Missing metrics fall back to a typical 0.8.
 */
export const baselineAt = (ascent, descent) => {
    if (!(ascent > 0) || !(descent >= 0)) return 0.8;
    return clamp(((100 - ascent - descent) / 2 + ascent) / 100, 0.5, 1.2);
};

/** Visible wordmark height: down to the baseline, plus `cut` em below it. */
export const wordHeight = (fontSize, baseline, cut) =>
    Math.max(0, fontSize * (baseline + clamp(Number.isFinite(cut) ? cut : 0, -0.4, 0.4)));

/** True for a link that leaves the site and so opens in a new tab. */
export const isOffsite = (href) => /^https?:\/\//i.test(href || "");

/** The beam layer's offset (% of the section's width) for a beam at `b`%. */
export const beamOffset = (b) => (Number.isFinite(b) ? b : 58) - 50;

// #endregion

/** Baseline of the wordmark's actual font, read off a canvas. */
const measureBaseline = (family, weight, text) => {
    try {
        const ctx = document.createElement("canvas").getContext("2d");
        if (!ctx) return 0.8;
        ctx.font = weight + " 100px " + family;
        const m = ctx.measureText(text);
        return baselineAt(m.fontBoundingBoxAscent, m.fontBoundingBoxDescent);
    } catch {
        return 0.8;
    }
};

const EASE = "var(--weare-ease)";

// The accent at `pct`%, scaled by the beam strength unless `k` is false.
const acc = (pct, k = true) =>
    "color-mix(in srgb,var(--bwf-acc) " + (k ? "calc(" + pct + "% * var(--bwf-k))" : pct + "%") + ",transparent)";

// One scoped stylesheet. Every rule sits under .bwf; element resets go through
// :where(.bwf) so they never out-rank the component's own classes or a caller's.
const CSS =
    ".bwf{position:relative;isolation:isolate;overflow:hidden;container-type:inline-size;background:var(--bwf-bg);color:var(--bwf-ink);-webkit-font-smoothing:antialiased;touch-action:pan-y}" +
    ":where(.bwf) a{color:inherit;text-decoration:none}" +
    ":where(.bwf) ul{list-style:none;margin:0;padding:0}" +
    ":where(.bwf) p{margin:0}" +
    ".bwf svg{max-width:none;display:block}" +
    ".bwf .bwf-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}" +
    // The top rule: a hairline of accent, with a brighter stretch that tracks
    // the beam.
    ".bwf-rule{position:absolute;left:0;right:0;top:0;height:1px;z-index:3;overflow:hidden;background:" + acc(15, false) + "}" +
    ".bwf-rule-hi{position:absolute;inset:0;background:linear-gradient(90deg,transparent 32%," + acc(55, false) + " 50%,transparent 68%);will-change:transform}" +
    // Backdrop: wash, faint vertical bands, the beam, the pointer glow and
    // grain. Only the beam and the glow move, and only by transform.
    ".bwf-sky{position:absolute;inset:0;z-index:0;pointer-events:none;overflow:hidden}" +
    ".bwf-wash{position:absolute;inset:0;background:radial-gradient(120% 90% at 8% 0%," + acc(20) + ",transparent 55%),radial-gradient(90% 70% at 92% 8%," + acc(14) + ",transparent 60%),linear-gradient(180deg," + acc(6) + ",transparent 70%)}" +
    ".bwf-bands{position:absolute;inset:0;background:repeating-linear-gradient(90deg," + acc(5) + " 0 1.6cqw,transparent 1.6cqw 4.2cqw);-webkit-mask-image:linear-gradient(100deg,var(--bwf-bg) 0%,transparent 55%);mask-image:linear-gradient(100deg,var(--bwf-bg) 0%,transparent 55%);opacity:.9}" +
    // The beam is painted once, centred, and slid sideways.
    ".bwf-beam{position:absolute;top:-10%;bottom:-10%;left:0;width:100%;will-change:transform;filter:blur(calc(1px + 1.6cqw));background:linear-gradient(118deg,transparent 39%," + acc(10) + " 45%," + acc(34) + " 50%," + acc(8) + " 54%,transparent 59%),linear-gradient(118deg,transparent 16%," + acc(10) + " 23%,transparent 30%)}" +
    // The glow is a painted disc that follows the pointer.
    ".bwf-glow{position:absolute;left:0;top:0;width:52cqw;height:52cqw;margin:-26cqw 0 0 -26cqw;opacity:0;will-change:transform,opacity;background:radial-gradient(circle closest-side," + acc(16) + ",transparent 70%)}" +
    ".bwf-grain{position:absolute;inset:0;opacity:.14;mix-blend-mode:overlay;background-image:url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")}" +
    // Layout: a wide first column, then one per link column.
    ".bwf-inner{position:relative;z-index:2;box-sizing:border-box;max-width:var(--bwf-max);margin:0 auto;padding:clamp(48px,8.5cqw,104px) clamp(20px,6cqw,88px) 0;display:grid;grid-template-columns:minmax(0,1.5fr) repeat(var(--bwf-cols),minmax(0,1fr));column-gap:clamp(24px,4cqw,48px);row-gap:44px}" +
    ".bwf-label{font-size:13px;line-height:1.2;letter-spacing:.01em;color:var(--bwf-acc);padding-bottom:13px;position:relative;display:block}" +
    ".bwf-label::after{content:'';position:absolute;left:0;right:0;bottom:0;height:1px;background:linear-gradient(90deg," + acc(55, false) + "," + acc(28, false) + ");transform-origin:0 50%;transform:scaleX(var(--bwf-line,1));transition:transform 1.1s " + EASE + " var(--bwf-d,0ms)}" +
    ".bwf[data-in='false'] .bwf-label::after{--bwf-line:0}" +
    ".bwf-col{min-width:0}" +
    ".bwf-col:nth-child(1){max-width:420px}" +
    ".bwf-fade{transition:opacity .9s " + EASE + " var(--bwf-d,0ms),translate .9s " + EASE + " var(--bwf-d,0ms)}" +
    ".bwf[data-in='false'] .bwf-fade{opacity:0;translate:0 14px}" +
    // The lead slot and the contact lines.
    ".bwf-lead{margin-bottom:28px;color:var(--bwf-muted);font-size:14px;line-height:1.55}" +
    ".bwf-contact{margin-top:13px;font-size:14.5px;line-height:1.5;color:var(--bwf-ink)}" +
    ".bwf-contact li{padding:6px 0}" +
    ".bwf-contact a,.bwf-company{background:linear-gradient(var(--bwf-acc),var(--bwf-acc)) 0 100%/0 1px no-repeat;transition:background-size .35s " + EASE + "}" +
    ".bwf-contact a{user-select:text;-webkit-user-select:text;overflow-wrap:anywhere}" +
    ".bwf-contact a:hover,.bwf-contact a:focus-visible,.bwf-company:hover,.bwf-company:focus-visible{background-size:100% 1px;outline:none}" +
    // Link columns.
    ".bwf-links{margin-top:13px;display:flex;flex-direction:column;gap:0}" +
    ".bwf-link{position:relative;display:inline-flex;align-items:center;gap:8px;padding:6px 0;font-size:14.5px;line-height:21px;color:var(--bwf-ink)}" +
    ".bwf-link-t{display:inline-block;transition:translate .35s " + EASE + "}" +
    ".bwf-link::before{content:'';position:absolute;left:0;top:50%;width:6px;height:1px;background:var(--bwf-acc);transform:scaleX(0);transform-origin:0 50%;transition:transform .35s " + EASE + "}" +
    ".bwf-link svg{width:12px;height:12px;opacity:0;translate:-6px 0;color:var(--bwf-acc);transition:opacity .25s " + EASE + ",translate .35s " + EASE + "}" +
    ".bwf-link:hover,.bwf-link:focus-visible{outline:none}" +
    ".bwf-link:hover::before,.bwf-link:focus-visible::before{transform:scaleX(1)}" +
    ".bwf-link:hover .bwf-link-t,.bwf-link:focus-visible .bwf-link-t{translate:12px 0}" +
    ".bwf-link:hover svg,.bwf-link:focus-visible svg{opacity:1;translate:10px 0}" +
    ".bwf-link:focus-visible .bwf-link-t,.bwf-contact a:focus-visible,.bwf-company:focus-visible{text-decoration:underline;text-underline-offset:4px;text-decoration-color:var(--bwf-acc)}" +
    // The wordmark. `screen` lets the beam and the glow beneath brighten the
    // letters as they pass, without the letters being repainted.
    ".bwf-word-wrap{position:relative;margin-top:clamp(28px,7cqw,96px)}" +
    ".bwf-word{position:relative;overflow:hidden;mix-blend-mode:screen}" +
    ".bwf-word-box{padding:0 clamp(20px,6cqw,88px);max-width:var(--bwf-max);margin:0 auto;box-sizing:border-box}" +
    // `transition-property:none` because the fit sets the font size to 100px,
    // reads the width, and sets it back in one go. A host stylesheet that puts
    // a duration on everything (a reduced-motion backstop does) would make the
    // size transition, the read would return the old width, and the fit would
    // oscillate for ever.
    ".bwf .bwf-word-in{display:inline-flex;white-space:nowrap;font-optical-sizing:auto;line-height:1;transition-property:none;user-select:none;-webkit-user-select:none}" +
    ".bwf-lw{display:inline-block;translate:0 0;transition:translate 1.25s " + EASE + " var(--bwf-d,0ms)}" +
    ".bwf[data-in='false'] .bwf-lw{translate:0 85%}" +
    ".bwf-l{display:inline-block;cursor:pointer;color:transparent;-webkit-background-clip:text;background-clip:text;background-image:linear-gradient(180deg,var(--bwf-wt) 8%,var(--bwf-wf) 88%);transition:transform .5s " + EASE + ",filter .4s " + EASE + ";transform-origin:50% 100%}" +
    ".bwf-l:hover{transform:translateY(-.045em);filter:brightness(1.35)}" +
    ".bwf-l.is-hop{animation:bwf-hop .75s " + EASE + "}" +
    "@keyframes bwf-hop{0%{transform:translateY(0) scale(1,1)}18%{transform:translateY(.02em) scale(1.06,.9)}45%{transform:translateY(-.14em) scale(.97,1.05)}70%{transform:translateY(.01em) scale(1.02,.97)}100%{transform:translateY(-.045em) scale(1,1)}}" +
    // The foot sinks the word into the ground. A sibling of the blended word,
    // not inside it, so it paints normally.
    ".bwf-foot{position:absolute;left:0;right:0;bottom:0;height:34%;pointer-events:none;background:linear-gradient(180deg,transparent,color-mix(in srgb,var(--bwf-bg) 55%,transparent) 55%,var(--bwf-bg))}" +
    "@container (max-width: 1000px){.bwf-inner{grid-template-columns:repeat(var(--bwf-cols),minmax(0,1fr))}.bwf-col:nth-child(1){grid-column:1 / -1;max-width:none}}" +
    "@container (max-width: 640px){.bwf-inner{grid-template-columns:minmax(0,1fr) minmax(0,1fr);row-gap:40px}}" +
    "@media (prefers-reduced-motion: reduce){.bwf .bwf-lw,.bwf .bwf-fade,.bwf .bwf-label::after,.bwf .bwf-l,.bwf .bwf-link-t,.bwf .bwf-link svg,.bwf .bwf-contact a,.bwf .bwf-company{transition:none!important;animation:none!important}.bwf[data-in='false'] .bwf-lw,.bwf[data-in='false'] .bwf-fade{translate:none;opacity:1}.bwf[data-in='false'] .bwf-label::after{--bwf-line:1}}";

// Only when the caller passes `wordFont`; otherwise `wordClassName` (or the
// inherited face) decides, and a rule here would out-rank it.
const WORD_FONT_CSS =
    ".bwf .bwf-word-in{font-family:var(--bwf-wfam);font-weight:var(--bwf-ww);font-variation-settings:var(--bwf-wvar);letter-spacing:var(--bwf-wls)}";

const Arrow = () => (
    <svg viewBox="0 0 12 12" aria-hidden="true">
        <path
            d="M2.5 9.5l7-7M4 2.5h5.5V8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
        />
    </svg>
);

// Any CSS colour works. The defaults are this app's brand tokens, because a
// literal here is a colour no theme can reach.
const DEFAULT_PALETTE = {
    ground: "hsl(var(--brand-navy))",
    ink: "hsl(var(--brand-white) / 0.9)",
    muted: "hsl(var(--brand-white) / 0.6)",
    accent: "hsl(var(--brand-red))",
    wordFrom: "color-mix(in srgb, hsl(var(--brand-navy)) 84%, hsl(var(--brand-white)))",
    wordTo: "color-mix(in srgb, hsl(var(--brand-navy)) 96%, hsl(var(--brand-white)))",
};

const DEFAULT_WORD_FONT = {
    family: "inherit",
    weight: 500,
    variationSettings: "normal",
    letterSpacing: "-.045em",
};

/** A link as the footer draws it: the caller's router link, or an <a>. */
function FooterAnchor({ link, renderLink, children, ...props }) {
    if (!link.external && !isOffsite(link.href) && renderLink) {
        return renderLink(link, { ...props, children });
    }
    const newTab = isOffsite(link.href) ? { target: "_blank", rel: "noopener noreferrer" } : {};
    return (
        <a href={link.href || "#"} {...newTab} {...props}>
            {children}
        </a>
    );
}

/** Whether the tab is showing. The beam stops while it is not. */
function usePageShown() {
    const [shown, setShown] = React.useState(() => typeof document === "undefined" || !document.hidden);
    React.useEffect(() => {
        const onChange = () => setShown(!document.hidden);
        document.addEventListener("visibilitychange", onChange);
        return () => document.removeEventListener("visibilitychange", onChange);
    }, []);
    return shown;
}

const REDUCED = "(prefers-reduced-motion: reduce)";

/** `prefers-reduced-motion: reduce`, read on the first render and followed. */
function useReducedMotion() {
    const [reduced, setReduced] = React.useState(
        () => typeof window !== "undefined" && !!window.matchMedia && window.matchMedia(REDUCED).matches,
    );
    React.useEffect(() => {
        if (!window.matchMedia) return undefined;
        const mq = window.matchMedia(REDUCED);
        const onMq = () => setReduced(mq.matches);
        onMq();
        if (mq.addEventListener) mq.addEventListener("change", onMq);
        else if (mq.addListener) mq.addListener(onMq);
        return () => {
            if (mq.removeEventListener) mq.removeEventListener("change", onMq);
            else if (mq.removeListener) mq.removeListener(onMq);
        };
    }, []);
    return reduced;
}

/**
 * @param word          what the giant wordmark spells
 * @param wordLabel     the name a screen reader hears once (defaults to `word`)
 * @param wordFont      { family, weight, variationSettings, letterSpacing }
 * @param wordClassName a class that sets the wordmark's face instead
 * @param columns       [{ title, links: [{ label, href, external? }] }]
 * @param companyName   the copyright holder
 * @param companyHref   links the name when set; plain text otherwise
 * @param year          the copyright year
 * @param contactLines  [{ label, href, external? }] under the copyright
 * @param lead          a node above the copyright (a logo, a sentence)
 * @param palette       { ground, ink, muted, accent, wordFrom, wordTo }
 * @param beamStrength  0–1, how strongly the accent lights the section
 * @param renderLink    (link, props) => node, for every non-external link
 * @param onLinkClick   (link) => void, after a footer link is pressed
 * @param testIds       { root, word, copyright, company, column(col),
 *                        link(link), contact(line) }
 * @param rootProps     extra attributes for the <footer>
 */
export default function BeamWordmarkFooter({
    word = "",
    wordLabel,
    wordFont,
    wordClassName = "",
    columns = [],
    companyName = "",
    companyHref,
    year = new Date().getFullYear(),
    contactLines = [],
    lead = null,
    palette,
    beamStrength = 1,
    cut = 0.14,
    maxWidth = 1120,
    animate = true,
    renderLink,
    onLinkClick,
    className = "",
    testIds = {},
    rootProps = {},
}) {
    const p = { ...DEFAULT_PALETTE, ...(palette || {}) };
    const font = wordFont ? { ...DEFAULT_WORD_FONT, ...wordFont } : null;
    const fontKey = font
        ? [font.family, font.weight, font.variationSettings, font.letterSpacing].join("|")
        : wordClassName;
    const text = (word || "").trim();
    const letters = React.useMemo(() => Array.from(text), [text]);

    const rootRef = React.useRef(null);
    const innerRef = React.useRef(null);
    const beamRef = React.useRef(null);
    const glowRef = React.useRef(null);
    const ruleRef = React.useRef(null);
    const [size, setSize] = React.useState(0);
    const [base, setBase] = React.useState(0.8);
    const [seen, setSeen] = React.useState(false);
    const [visible, setVisible] = React.useState(false);
    const reduced = useReducedMotion();
    const pageShown = usePageShown();
    const still = reduced || !animate;

    // Pointer state lives in a ref; the loop reads it, React never re-renders.
    const ptr = React.useRef({ u: 0.5, x: 0, y: 0, inside: false });

    // Fit the wordmark to the column width.
    React.useLayoutEffect(() => {
        const root = rootRef.current;
        const inner = innerRef.current;
        if (!root || !inner) return undefined;
        let frame = 0;
        const fit = () => {
            const wb = inner.parentElement;
            const pad = parseFloat(getComputedStyle(wb).paddingLeft) || 0;
            const target = wb.clientWidth - pad * 2;
            inner.style.fontSize = "100px";
            const measured = inner.offsetWidth;
            const cs = getComputedStyle(inner);
            setBase(measureBaseline(cs.fontFamily, cs.fontWeight, text));
            const next = fitSize(measured, target, target * 0.42);
            inner.style.fontSize = next + "px";
            setSize(next);
        };
        const schedule = () => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(fit);
        };
        fit();
        const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
        if (ro) ro.observe(root);
        let alive = true;
        if (typeof document !== "undefined" && document.fonts && document.fonts.ready) {
            document.fonts.ready.then(() => alive && schedule());
        }
        return () => {
            alive = false;
            cancelAnimationFrame(frame);
            if (ro) ro.disconnect();
        };
    }, [text, fontKey]);

    // Reveal once, the first time the footer is on screen; the beam runs only
    // while it is.
    React.useEffect(() => {
        const root = rootRef.current;
        if (!root) return undefined;
        if (typeof IntersectionObserver === "undefined") {
            setVisible(true);
            setSeen(true);
            return undefined;
        }
        const io = new IntersectionObserver(
            ([e]) => {
                setVisible(e.isIntersecting);
                if (e.isIntersecting) setSeen(true);
            },
            { threshold: 0.12 },
        );
        io.observe(root);
        return () => io.disconnect();
    }, []);

    React.useEffect(() => {
        const beam = beamRef.current;
        const glow = glowRef.current;
        const rule = ruleRef.current;
        if (!beam || !glow || !rule) return undefined;
        // Transforms and opacity only: the compositor moves these layers, and
        // nothing is painted again.
        const set = (b, px, py, g) => {
            const off = beamOffset(b).toFixed(2) + "%";
            beam.style.transform = "translate3d(" + off + ",0,0)";
            rule.style.transform = "translate3d(" + off + ",0,0)";
            glow.style.transform = "translate3d(" + px.toFixed(1) + "px," + py.toFixed(1) + "px,0)";
            glow.style.opacity = g.toFixed(3);
        };
        // Reduced motion, or `animate` off: drawn once, at rest. No loop.
        if (still) {
            set(58, 0, 0, 0);
            return undefined;
        }
        // Offscreen or a hidden tab: hold where it is, no loop.
        if (!visible || !pageShown) return undefined;
        let raf = 0;
        let last = performance.now();
        let t = last / 1000;
        let b = 58;
        let px = ptr.current.x;
        let py = ptr.current.y;
        let g = 0;
        const tick = (now) => {
            const dt = Math.min(0.1, Math.max(0, (now - last) / 1000));
            last = now;
            t += dt;
            const q = ptr.current;
            const idle = drift(t);
            const target = q.inside ? beamTarget(q.u) * 0.75 + idle * 0.25 : idle;
            b = approach(b, target, 0.035, dt);
            px = approach(px, q.x, 0.16, dt);
            py = approach(py, q.y, 0.16, dt);
            g = approach(g, q.inside ? 1 : 0, 0.06, dt);
            set(b, px, py, g);
            raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [still, visible, pageShown]);

    const onPointer = (e) => {
        if (still) return;
        const r = e.currentTarget.getBoundingClientRect();
        const q = ptr.current;
        q.x = e.clientX - r.left;
        q.y = e.clientY - r.top;
        q.u = r.width ? q.x / r.width : 0.5;
        q.inside = e.type !== "pointerleave";
    };

    const hop = (e) => {
        if (reduced) return;
        const el = e.currentTarget;
        el.classList.remove("is-hop");
        // Restarting a CSS animation needs a reflow between the class coming
        // off and going back on; reading a layout property forces one.
        // eslint-disable-next-line no-unused-vars
        const _reflow = el.offsetWidth;
        el.classList.add("is-hop");
    };

    const follow = (e, link) => {
        // "#" and missing hrefs never touch the host page's URL hash.
        if (!link.href || link.href === "#") e.preventDefault();
        if (onLinkClick) onLinkClick(link);
    };

    const vars = {
        "--bwf-bg": p.ground,
        "--bwf-ink": p.ink,
        "--bwf-muted": p.muted,
        "--bwf-acc": p.accent,
        "--bwf-k": String(clamp(Number.isFinite(beamStrength) ? beamStrength : 1, 0, 1)),
        "--bwf-wt": p.wordFrom,
        "--bwf-wf": p.wordTo,
        "--bwf-max": maxWidth + "px",
        "--bwf-cols": String(Math.max(1, columns.length)),
        ...(font
            ? {
                  "--bwf-wfam": font.family,
                  "--bwf-ww": String(font.weight),
                  "--bwf-wvar": font.variationSettings,
                  "--bwf-wls": font.letterSpacing,
              }
            : {}),
    };

    let d = 0;
    const delay = () => ({ "--bwf-d": (d += 70) + "ms" });
    const id = (key, arg) => (typeof testIds[key] === "function" ? testIds[key](arg) : testIds[key]);

    return (
        <footer
            ref={rootRef}
            className={("bwf " + className).trim()}
            style={vars}
            data-in={seen || reduced ? "true" : "false"}
            data-testid={id("root")}
            onPointerMove={onPointer}
            onPointerEnter={onPointer}
            onPointerLeave={onPointer}
            {...rootProps}
        >
            <style>{font ? CSS + WORD_FONT_CSS : CSS}</style>
            <div className="bwf-rule" aria-hidden="true">
                <div ref={ruleRef} className="bwf-rule-hi" />
            </div>
            <div className="bwf-sky" aria-hidden="true">
                <div className="bwf-wash" />
                <div className="bwf-bands" />
                <div ref={beamRef} className="bwf-beam" />
                <div ref={glowRef} className="bwf-glow" />
                <div className="bwf-grain" />
            </div>

            <div className="bwf-inner">
                <div className="bwf-col">
                    {lead ? (
                        <div className="bwf-lead bwf-fade" style={delay()}>
                            {lead}
                        </div>
                    ) : null}
                    <p className="bwf-label" style={delay()} data-testid={id("copyright")}>
                        © {year}{" "}
                        {companyHref ? (
                            <a
                                className="bwf-company"
                                href={companyHref}
                                target="_blank"
                                rel="noopener noreferrer"
                                data-testid={id("company")}
                            >
                                {companyName}
                            </a>
                        ) : (
                            <span data-testid={id("company")}>{companyName}</span>
                        )}
                    </p>
                    {contactLines.length > 0 && (
                        <ul className="bwf-contact">
                            {contactLines.map((line, i) => (
                                <li key={line.href + i} className="bwf-fade" style={delay()}>
                                    <FooterAnchor
                                        link={line}
                                        renderLink={renderLink}
                                        data-testid={id("contact", line)}
                                        onClick={(e) => follow(e, line)}
                                    >
                                        {line.label}
                                    </FooterAnchor>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>

                {columns.map((col, ci) => (
                    <nav
                        key={col.title + ci}
                        className="bwf-col"
                        aria-label={col.title}
                        data-testid={id("column", col)}
                    >
                        <p className="bwf-label" style={delay()}>
                            {col.title}
                        </p>
                        <ul className="bwf-links">
                            {col.links.map((l, li) => (
                                <li key={l.label + li} className="bwf-fade" style={delay()}>
                                    <FooterAnchor
                                        link={l}
                                        renderLink={renderLink}
                                        className="bwf-link"
                                        data-testid={id("link", l)}
                                        onClick={(e) => follow(e, l)}
                                    >
                                        <span className="bwf-link-t">{l.label}</span>
                                        <Arrow />
                                    </FooterAnchor>
                                </li>
                            ))}
                        </ul>
                    </nav>
                ))}
            </div>

            <div className="bwf-word-wrap">
                <p className="bwf-sr">{wordLabel || text}</p>
                <div
                    className="bwf-word"
                    style={{ height: size ? wordHeight(size, base, cut) : "calc(" + (0.8 + cut) * 26 + "cqw)" }}
                >
                    <div className="bwf-word-box">
                        <div
                            ref={innerRef}
                            className={("bwf-word-in " + wordClassName).trim()}
                            aria-hidden="true"
                            data-testid={id("word")}
                        >
                            {letters.map((ch, i) => (
                                <span key={i} className="bwf-lw" style={{ "--bwf-d": 260 + i * 75 + "ms" }}>
                                    <span
                                        className="bwf-l"
                                        onClick={hop}
                                        onAnimationEnd={(e) => e.currentTarget.classList.remove("is-hop")}
                                    >
                                        {ch === " " ? " " : ch}
                                    </span>
                                </span>
                            ))}
                        </div>
                    </div>
                </div>
                <div className="bwf-foot" aria-hidden="true" />
            </div>
        </footer>
    );
}
