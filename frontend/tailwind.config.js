/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
    theme: {
        extend: {
            fontFamily: {
                serif: [
                    "Fraunces",
                    "Cormorant Garamond",
                    "ui-serif",
                    "Georgia",
                    "serif",
                ],
                sans: [
                    "Inter Tight",
                    "ui-sans-serif",
                    "system-ui",
                    "-apple-system",
                    "sans-serif",
                ],
            },
            letterSpacing: {
                tightest: "-0.03em",
                eyebrow: "var(--tracking-eyebrow)",
            },
            // The low-density scale. Every value is a custom property in
            // index.css, so the compact density redefines `body` and `meta`
            // on its wrapper and these classes follow without a second
            // component. h1 and h2 clamp; nothing here is an arbitrary size.
            //
            //   text-eyebrow  11px, uppercase, 0.18em — pair with `uppercase
            //                 tracking-eyebrow text-muted-foreground`
            //   text-meta     14px (13 compact)
            //   text-body     16px (14 compact) — also the document base
            //   text-body-lg  17px
            //   text-h3/h2/h1 Fraunces 600 at 24 / 24→30 / 32→46px
            //
            // `max-w-measure` caps a paragraph at ~64ch.
            maxWidth: {
                measure: "var(--measure)",
            },
            height: {
                "list-row": "var(--row-h)",
            },
            spacing: {
                "card-sm": "var(--space-card-sm)",
                card: "var(--space-card)",
                "card-lg": "var(--space-card-lg)",
                inner: "var(--space-inner)",
                section: "var(--space-section)",
                row: "var(--space-row-y)",
            },
            // Fluid display type.
            //
            // Each step replaces one `text-X md:text-Y` pair that was already
            // in use, and its clamp minimum and maximum ARE that pair's two
            // sizes — nothing is larger or smaller than before at either end.
            // What goes away is the jump at 768px, where a headline used to
            // change size mid-scroll on a tablet.
            //
            // Named for where they top out, because that is how the pair read
            // when written out: `text-fluid-5xl` is the heading that reaches
            // 5xl. The `-wide` steps climb two Tailwind sizes rather than one,
            // and exist only because two headings in the app do.
            //
            // The preferred term interpolates between a 375px and a 1280px
            // viewport, so the whole phone range is fluid rather than pinned
            // at the minimum. Line heights match what the pair emitted at its
            // larger size, which is the one most of the reading happens at.
            fontSize: {
                eyebrow: ["var(--text-eyebrow)", { lineHeight: "1.4" }],
                meta: ["var(--text-meta)", { lineHeight: "1.45" }],
                body: ["var(--text-body)", { lineHeight: "1.55" }],
                "body-lg": ["var(--text-body-lg)", { lineHeight: "1.55" }],
                h3: ["var(--text-h3)", { lineHeight: "1.2", letterSpacing: "-0.01em", fontWeight: "600" }],
                h2: ["var(--text-h2)", { lineHeight: "1.12", letterSpacing: "-0.015em", fontWeight: "600" }],
                h1: ["var(--text-h1)", { lineHeight: "1.05", letterSpacing: "-0.025em", fontWeight: "600" }],
                // xl (20px) → 2xl (24px)
                "fluid-2xl": ["clamp(1.25rem, 1.146rem + 0.442vw, 1.5rem)", { lineHeight: "1.333" }],
                // 2xl (24px) → 3xl (30px)
                "fluid-3xl": ["clamp(1.5rem, 1.345rem + 0.663vw, 1.875rem)", { lineHeight: "1.2" }],
                // 3xl (30px) → 4xl (36px)
                "fluid-4xl": ["clamp(1.875rem, 1.72rem + 0.663vw, 2.25rem)", { lineHeight: "1.11" }],
                // 4xl (36px) → 5xl (48px)
                "fluid-5xl": ["clamp(2.25rem, 1.939rem + 1.326vw, 3rem)", { lineHeight: "1.05" }],
                // 3xl (30px) → 5xl (48px)
                "fluid-5xl-wide": ["clamp(1.875rem, 1.409rem + 1.989vw, 3rem)", { lineHeight: "1.05" }],
                // 5xl (48px) → 6xl (60px)
                "fluid-6xl": ["clamp(3rem, 2.689rem + 1.326vw, 3.75rem)", { lineHeight: "1" }],
                // 4xl (36px) → 6xl (60px)
                "fluid-6xl-wide": ["clamp(2.25rem, 1.628rem + 2.652vw, 3.75rem)", { lineHeight: "1" }],
                // The hero. Endpoints unchanged from the `.h-fluid` this
                // replaces; only the band it travels over is widened, so a
                // phone gets a fluid headline instead of a flat 40px.
                "fluid-hero": ["clamp(2.5rem, 1.775rem + 3.094vw, 4.25rem)", { lineHeight: "1" }],
            },
            // The radius scale: sm 10 · md 14 · lg 20 · xl 22 · pill. Read
            // from index.css, where the dark set keeps the old 4/6/8 for the
            // marketing pages drawn to it. `rounded` (4px) stays Tailwind's,
            // for the controls too small to carry 10px — a 16px checkbox at
            // `rounded-sm` would be a circle.
            borderRadius: {
                sm: "var(--radius-sm)",
                md: "var(--radius-md)",
                lg: "var(--radius-lg)",
                xl: "var(--radius-xl)",
                pill: "9999px",
            },
            colors: {
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
                heading: "hsl(var(--heading))",
                wash: "hsl(var(--wash))",
                divider: "hsl(var(--divider))",
                faint: "hsl(var(--faint-foreground))",
                card: {
                    DEFAULT: "hsl(var(--card))",
                    foreground: "hsl(var(--card-foreground))",
                    // `hover:bg-card-elevated` is how a card lifts here.
                    elevated: "hsl(var(--card-elevated))",
                },
                popover: {
                    DEFAULT: "hsl(var(--popover))",
                    foreground: "hsl(var(--popover-foreground))",
                },
                primary: {
                    DEFAULT: "hsl(var(--primary))",
                    foreground: "hsl(var(--primary-foreground))",
                    // The accent doing its other job — text or an icon on a
                    // surface rather than a button fill. Identical to
                    // DEFAULT on dark; darker on light, because #F05D14 on
                    // an off-white page is 3.0:1 and fails AA as body text
                    // while the same orange as a fill is fine.
                    ink: "hsl(var(--primary-ink) / <alpha-value>)",
                    hover: "hsl(var(--primary-hover) / <alpha-value>)",
                },
                secondary: {
                    DEFAULT: "hsl(var(--secondary))",
                    foreground: "hsl(var(--secondary-foreground))",
                },
                muted: {
                    DEFAULT: "hsl(var(--muted))",
                    foreground: "hsl(var(--muted-foreground))",
                },
                // **The red, with two jobs and two tokens.** `accent` fills —
                // a bar, a dot, a badge ground, a border — at 3.76:1 on white,
                // which is AA for large text and UI boundaries and a failure
                // for copy. `accent-ink` (#C41E27, 5.90:1) is the only red a
                // word below 24px may wear. The shadcn primitives used
                // `accent` for a neutral hover highlight; they read `muted`
                // now, or every menu item would light up red.
                accent: {
                    DEFAULT: "hsl(var(--accent) / <alpha-value>)",
                    foreground: "hsl(var(--accent-foreground))",
                    ink: "hsl(var(--accent-ink) / <alpha-value>)",
                    // Translucent by design: the alpha is in the token.
                    wash: "hsl(var(--accent-wash))",
                    border: "hsl(var(--accent-border))",
                },
                // Navy chrome inside the light app. The same under every
                // theme — it is the inverse of the page, not of the theme.
                inverse: {
                    DEFAULT: "hsl(var(--inverse) / <alpha-value>)",
                    alt: "hsl(var(--inverse-alt) / <alpha-value>)",
                    foreground: "hsl(var(--inverse-foreground) / <alpha-value>)",
                    muted: "hsl(var(--inverse-muted) / <alpha-value>)",
                },
                // For a surface that must stay one colour whichever theme is
                // mounted: the mark, and the studio's closing band. Constants.
                brand: {
                    navy: "hsl(var(--brand-navy) / <alpha-value>)",
                    red: "hsl(var(--brand-red) / <alpha-value>)",
                    white: "hsl(var(--brand-white) / <alpha-value>)",
                },
                destructive: {
                    DEFAULT: "hsl(var(--destructive))",
                    foreground: "hsl(var(--destructive-foreground))",
                },
                border: "hsl(var(--border))",
                input: "hsl(var(--input))",
                ring: "hsl(var(--ring))",
                // **The base the console's alpha hairlines are applied to.**
                // `border-tint/10` is what `border-white/10` used to be, and
                // reads identically in dark — `--tint` is white there. The
                // `<alpha-value>` form is the whole point: the alpha stays at
                // the call site, so a 10% hairline and a 15% one remain two
                // different decisions rather than collapsing into one token.
                tint: "hsl(var(--tint) / <alpha-value>)",
                scrim: "hsl(var(--scrim) / <alpha-value>)",
                // The four states the console shows, named for meaning. The
                // chip fill is the same hue at low alpha, so these carry
                // `<alpha-value>` too and `bg-state-pending/10` works.
                // Each state has an ink and a wash; a chip is the ink on the
                // wash. The light washes are the brief's solid values, the
                // dark ones carry their alpha in the token.
                state: {
                    pending: "hsl(var(--state-pending) / <alpha-value>)",
                    "pending-wash": "hsl(var(--state-pending-wash))",
                    approved: "hsl(var(--state-approved) / <alpha-value>)",
                    "approved-wash": "hsl(var(--state-approved-wash))",
                    rejected: "hsl(var(--state-rejected) / <alpha-value>)",
                    "rejected-wash": "hsl(var(--state-rejected-wash))",
                    progress: "hsl(var(--state-progress) / <alpha-value>)",
                    "progress-wash": "hsl(var(--state-progress-wash))",
                    done: "hsl(var(--state-done) / <alpha-value>)",
                    "done-wash": "hsl(var(--state-done-wash))",
                },
                // The literal `navy` and `red` scales are gone: every use is
                // a semantic token or one of the `brand` constants above, and
                // a scale nobody may use is a scale somebody eventually does.
                // Standout data, and the logo. Red on both surfaces — the one
                // value that does not flip. See the note in `index.css`:
                // AA-large only on the light surface, which is what it is for.
                data: "hsl(var(--data) / <alpha-value>)",
            },
            keyframes: {
                "accordion-down": {
                    from: { height: "0" },
                    to: { height: "var(--radix-accordion-content-height)" },
                },
                "accordion-up": {
                    from: { height: "var(--radix-accordion-content-height)" },
                    to: { height: "0" },
                },
                "fade-up": {
                    "0%": { opacity: "0", transform: "translateY(12px)" },
                    "100%": { opacity: "1", transform: "translateY(0)" },
                },
            },
            animation: {
                "accordion-down": "accordion-down 0.2s ease-out",
                "accordion-up": "accordion-up 0.2s ease-out",
                "fade-up": "fade-up 0.7s cubic-bezier(0.22, 1, 0.36, 1) both",
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
};
