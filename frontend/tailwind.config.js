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
            borderRadius: {
                lg: "var(--radius)",
                md: "calc(var(--radius) - 2px)",
                sm: "calc(var(--radius) - 4px)",
            },
            colors: {
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
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
                },
                secondary: {
                    DEFAULT: "hsl(var(--secondary))",
                    foreground: "hsl(var(--secondary-foreground))",
                },
                muted: {
                    DEFAULT: "hsl(var(--muted))",
                    foreground: "hsl(var(--muted-foreground))",
                },
                accent: {
                    DEFAULT: "hsl(var(--accent))",
                    foreground: "hsl(var(--accent-foreground))",
                },
                destructive: {
                    DEFAULT: "hsl(var(--destructive))",
                    foreground: "hsl(var(--destructive-foreground))",
                },
                border: "hsl(var(--border))",
                input: "hsl(var(--input))",
                ring: "hsl(var(--ring))",
                ember: {
                    50: "#FFF3EC",
                    100: "#FFDDC5",
                    200: "#FFB988",
                    300: "#FF9450",
                    400: "#F5751F",
                    500: "#F05D14",
                    600: "#C6480A",
                    700: "#8E3306",
                    800: "#5A2004",
                    900: "#2E1002",
                },
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
