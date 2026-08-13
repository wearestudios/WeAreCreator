import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import {
    ArrowRight,
    ShieldCheck,
    Compass,
    Send,
    Wallet,
    Sparkles,
    IndianRupee,
    Lock,
    Rocket,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const IMG_HERO =
    "https://images.unsplash.com/photo-1728910156510-77488f19b152?auto=format&fit=crop&w=1800&q=80";

const fadeUp = {
    hidden: { opacity: 0, y: 16 },
    show: (i = 0) => ({
        opacity: 1,
        y: 0,
        transition: { delay: 0.08 * i, duration: 0.7, ease: [0.22, 1, 0.36, 1] },
    }),
};

// The verticals we cycle through in the hero headline.
const ROTATING_VERTICALS = [
    "cafés",
    "restaurants",
    "retail",
    "real estate",
    "fashion",
    "travel",
    "hotels",
];

// Cities for the marquee strip. Order matters visually.
const CITIES = [
    "Bengaluru",
    "Mumbai",
    "Delhi NCR",
    "Hyderabad",
    "Pune",
    "Chennai",
    "Kolkata",
    "Goa",
    "Ahmedabad",
    "Jaipur",
    "Chandigarh",
    "Kochi",
];

const STEPS = [
    {
        n: "01",
        Icon: ShieldCheck,
        title: "Get vetted",
        body: "Apply once. Our team reviews your profile, niche and audience — from every city in India.",
    },
    {
        n: "02",
        Icon: Compass,
        title: "Discover briefs",
        body: "Live paid campaigns from cafés, restaurants, retail, real estate, fashion, travel and hotels.",
    },
    {
        n: "03",
        Icon: Send,
        title: "Pitch in a tap",
        body: "Send a short note and your rate. Brands review your work and shortlist you from the app.",
    },
    {
        n: "04",
        Icon: Wallet,
        title: "Deliver & get paid",
        body: "Shoot, publish, submit. Once the brand approves, your payout is released — you'll see every step, and we chase the brand, not you.",
    },
];

const TRUST_POINTS = [
    {
        Icon: IndianRupee,
        title: "Fixed, upfront budgets",
        body: "See the fee before you pitch. No opaque negotiations, no bartered meals.",
    },
    {
        Icon: ShieldCheck,
        title: "Vetted on both sides",
        body: "Every creator is reviewed before they can pitch, and every brand we promote is verified by our team.",
    },
    {
        Icon: Lock,
        title: "The fee is agreed in writing",
        body: "Your rate is locked and recorded before the shoot, and we handle collecting from the brand.",
    },
];

const CAT_LABEL = {
    fnb: "F&B",
    hospitality: "Hospitality",
    retail: "Retail",
    real_estate: "Real Estate",
    fashion: "Fashion",
    travel: "Travel",
    wellness: "Wellness",
    lifestyle: "Lifestyle",
};

/**
 * Real open briefs, before anyone signs up.
 *
 * The page promises "discover briefs", but the campaign feed needs an account
 * and a WhatsApp round trip. This shows enough to judge whether it's worth
 * joining — title, brand, area, fee — and nothing you could work the brief from.
 */
function LiveBriefs() {
    const [briefs, setBriefs] = useState(null);
    const [totalOpen, setTotalOpen] = useState(0);

    useEffect(() => {
        let cancelled = false;
        api.get("/public/campaigns", { params: { limit: 6 } })
            .then(({ data }) => {
                if (cancelled) return;
                setBriefs(data.campaigns || []);
                setTotalOpen(data.total_open || 0);
            })
            .catch(() => {
                if (!cancelled) setBriefs([]);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    // Nothing live: don't show an empty shelf on the front page.
    if (briefs !== null && briefs.length === 0) return null;

    return (
        <section
            id="live-briefs"
            data-testid="live-briefs-section"
            className="border-y border-white/10 bg-card/30"
        >
            <div className="mx-auto max-w-7xl px-6 py-24 md:py-32">
                <div className="grid gap-10 md:grid-cols-12 md:items-end">
                    <div className="md:col-span-7">
                        <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                            <span className="h-px w-8 bg-ember-500" />
                            Open right now
                        </p>
                        <h2 className="mt-5 max-w-2xl font-serif text-4xl leading-[0.98] tracking-tight md:text-5xl">
                            Briefs live on the platform{" "}
                            <span className="italic">today</span>.
                        </h2>
                    </div>
                    <p className="text-sm leading-relaxed text-muted-foreground md:col-span-5">
                        {totalOpen > 0
                            ? `${totalOpen} paid ${
                                  totalOpen === 1 ? "brief is" : "briefs are"
                              } open as you read this. Sign up as a creator to see the full brief and pitch.`
                            : "Paid briefs from brands across India. Sign up as a creator to see the full brief and pitch."}
                    </p>
                </div>

                <div className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
                    {briefs === null
                        ? Array.from({ length: 3 }).map((_, i) => (
                              <div
                                  key={i}
                                  className="h-56 animate-pulse rounded-lg border border-white/10 bg-card"
                              />
                          ))
                        : briefs.map((b, idx) => (
                              <motion.article
                                  key={b.id}
                                  data-testid={`live-brief-${b.id}`}
                                  initial={{ opacity: 0, y: 18 }}
                                  whileInView={{ opacity: 1, y: 0 }}
                                  viewport={{ once: true, margin: "-60px" }}
                                  transition={{
                                      duration: 0.55,
                                      delay: idx * 0.06,
                                      ease: [0.22, 1, 0.36, 1],
                                  }}
                                  className="group flex flex-col rounded-lg border border-white/10 bg-card p-7 transition-colors duration-300 hover:border-ember-500/50"
                              >
                                  <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                      <span>{CAT_LABEL[b.category] || b.category}</span>
                                      {b.area && <span>{b.area}</span>}
                                  </div>
                                  <h3 className="mt-5 font-serif text-2xl leading-tight tracking-tight">
                                      {b.title}
                                  </h3>
                                  <p className="mt-2 text-xs uppercase tracking-[0.15em] text-ember-500">
                                      {b.brand_name || "Brand"}
                                  </p>
                                  <p className="mt-4 flex-1 text-sm leading-relaxed text-muted-foreground">
                                      {b.teaser}
                                  </p>
                                  <div className="mt-6 flex items-end justify-between border-t border-white/10 pt-5">
                                      <div>
                                          <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                              Per creator
                                          </div>
                                          <div className="mt-1 flex items-baseline font-serif text-3xl">
                                              <IndianRupee className="h-5 w-5 text-ember-500" />
                                              {typeof b.budget_per_creator === "number"
                                                  ? b.budget_per_creator.toLocaleString("en-IN")
                                                  : "—"}
                                          </div>
                                      </div>
                                      {b.spots_left > 0 && (
                                          <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                                              {b.spots_left}{" "}
                                              {b.spots_left === 1 ? "spot" : "spots"} left
                                          </span>
                                      )}
                                  </div>
                              </motion.article>
                          ))}
                </div>

                <div className="mt-12">
                    <Link to="/signup?role=creator" data-testid="live-briefs-cta">
                        <Button
                            size="lg"
                            className="group h-12 rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400"
                        >
                            Sign up to pitch on these
                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                        </Button>
                    </Link>
                </div>
            </div>
        </section>
    );
}

// ---- Small building blocks ------------------------------------------------

function RotatingWord({ words, className = "" }) {
    const [idx, setIdx] = useState(0);
    useEffect(() => {
        const t = setInterval(
            () => setIdx((i) => (i + 1) % words.length),
            2200,
        );
        return () => clearInterval(t);
    }, [words.length]);
    return (
        <span className={"relative inline-block align-baseline " + className}>
            {/* invisible sizer so layout doesn't jump */}
            <span aria-hidden className="invisible whitespace-nowrap">
                {words.reduce((a, b) => (a.length >= b.length ? a : b), "")}
            </span>
            <AnimatePresence mode="wait">
                <motion.span
                    key={words[idx]}
                    initial={{ y: "0.7em", opacity: 0, filter: "blur(6px)" }}
                    animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
                    exit={{ y: "-0.7em", opacity: 0, filter: "blur(6px)" }}
                    transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
                    className="absolute inset-0 whitespace-nowrap italic text-ember-500"
                >
                    {words[idx]}
                </motion.span>
            </AnimatePresence>
        </span>
    );
}

function CitiesMarquee() {
    // Duplicate so the CSS translate creates a seamless loop.
    const list = [...CITIES, ...CITIES];
    return (
        <div
            data-testid="cities-marquee"
            className="relative overflow-hidden border-y border-white/10 bg-card/30 py-6"
            style={{
                maskImage:
                    "linear-gradient(to right, transparent, black 8%, black 92%, transparent)",
                WebkitMaskImage:
                    "linear-gradient(to right, transparent, black 8%, black 92%, transparent)",
            }}
        >
            <div className="marquee-track flex w-max items-center gap-14 whitespace-nowrap will-change-transform">
                {list.map((c, i) => (
                    <span
                        key={`${c}-${i}`}
                        className="flex items-center gap-14 font-serif text-2xl italic text-muted-foreground/70 md:text-3xl"
                    >
                        {c}
                        <span className="inline-block h-1 w-1 rounded-full bg-ember-500/70" />
                    </span>
                ))}
            </div>
        </div>
    );
}

function AnimatedNumber({ value, suffix = "", duration = 1400 }) {
    const [n, setN] = useState(0);
    useEffect(() => {
        const start = performance.now();
        let frame;
        const tick = (now) => {
            const t = Math.min(1, (now - start) / duration);
            // ease-out cubic
            const eased = 1 - Math.pow(1 - t, 3);
            setN(Math.round(value * eased));
            if (t < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(frame);
    }, [value, duration]);
    return (
        <span>
            {n.toLocaleString("en-IN")}
            {suffix}
        </span>
    );
}

// ---- Page ----------------------------------------------------------------

export default function Landing() {
    // Subtle parallax on the hero image.
    const { scrollY } = useScroll();
    const heroImgY = useTransform(scrollY, [0, 400], [0, 60]);
    const heroImgOpacity = useTransform(scrollY, [0, 400], [0.35, 0.12]);

    return (
        <div
            data-testid="landing-page"
            className="min-h-screen bg-background text-foreground"
        >
            <Navbar />

            {/* ------------------------ HERO ------------------------ */}
            <section className="relative overflow-hidden">
                <motion.div
                    style={{ y: heroImgY, opacity: heroImgOpacity }}
                    className="absolute inset-0"
                >
                    <img
                        src={IMG_HERO}
                        alt=""
                        className="h-full w-full object-cover"
                    />
                </motion.div>
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background/50 via-background/75 to-background" />
                <div className="pointer-events-none grain absolute inset-0" />

                {/* Ember accent orb */}
                <motion.div
                    aria-hidden
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.55 }}
                    transition={{ duration: 2 }}
                    className="pointer-events-none absolute -right-40 top-24 h-[520px] w-[520px] rounded-full bg-ember-500/15 blur-[120px]"
                />

                <div className="relative mx-auto max-w-7xl px-6 pb-28 pt-20 md:pt-32">
                    <motion.p
                        initial="hidden"
                        animate="show"
                        variants={fadeUp}
                        className="mb-6 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs uppercase tracking-[0.22em] text-muted-foreground backdrop-blur"
                    >
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-ember-500 animate-pulse" />
                        <span className="text-ember-500/90">Vol. 01</span>
                        <span className="h-3 w-px bg-white/15" />
                        India · Influencer studio
                    </motion.p>

                    <motion.h1
                        data-testid="hero-heading"
                        initial="hidden"
                        animate="show"
                        custom={1}
                        variants={fadeUp}
                        className="h-fluid max-w-5xl font-serif tracking-tightest"
                    >
                        Influencer campaigns for
                        <span className="block h-[1.05em]">
                            <RotatingWord
                                words={ROTATING_VERTICALS}
                                className="align-baseline"
                            />
                        </span>
                    </motion.h1>

                    <motion.p
                        initial="hidden"
                        animate="show"
                        custom={1.5}
                        variants={fadeUp}
                        className="mt-4 max-w-2xl font-serif text-2xl italic text-muted-foreground md:text-3xl"
                    >
                        Done right, in every city that matters.
                    </motion.p>

                    <motion.p
                        data-testid="hero-subheading"
                        initial="hidden"
                        animate="show"
                        custom={2}
                        variants={fadeUp}
                        className="mt-8 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg"
                    >
                        Post your brief yourself — or hand it to our team. Either way,
                        you're working with the same vetted creator network across
                        every city in India.
                    </motion.p>

                    <motion.div
                        initial="hidden"
                        animate="show"
                        custom={3}
                        variants={fadeUp}
                        className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center"
                    >
                        <Link to="/signup?role=brand" data-testid="hero-cta-brand">
                            <Button
                                size="lg"
                                className="group h-12 w-full rounded-full bg-ember-500 px-7 text-black transition-colors duration-200 hover:bg-ember-400 sm:w-auto"
                            >
                                Post a campaign
                                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                            </Button>
                        </Link>
                        <Link to="/signup?role=creator" data-testid="hero-cta-creator">
                            <Button
                                size="lg"
                                variant="outline"
                                className="h-12 w-full rounded-full border-white/15 bg-transparent px-7 text-foreground hover:bg-white/5 sm:w-auto"
                            >
                                Join as a creator
                            </Button>
                        </Link>
                        <a
                            href="mailto:creators@wearemonk.in?subject=Managed%20campaign%20request"
                            data-testid="hero-managed-link"
                            className="group inline-flex items-center gap-1 pt-2 text-sm text-muted-foreground underline-offset-4 transition-colors duration-200 hover:text-ember-500 hover:underline sm:pt-0 sm:pl-3"
                        >
                            Prefer we run it? Talk to our team
                            <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-1" />
                        </a>
                    </motion.div>

                    {/* Stats strip */}
                    <motion.div
                        initial="hidden"
                        animate="show"
                        custom={4}
                        variants={fadeUp}
                        className="mt-20 grid max-w-3xl grid-cols-3 gap-8 border-t border-white/10 pt-8"
                    >
                        {[
                            { k: 500, s: "+", v: "vetted creators" },
                            { k: 12, s: "+ cities", v: "live coverage" },
                            { k: 0, s: "", v: "hidden fees", prefix: "₹" },
                        ].map((s) => (
                            <div key={s.v}>
                                <div className="font-serif text-3xl text-foreground md:text-4xl">
                                    {s.prefix}
                                    <AnimatedNumber value={s.k} suffix={s.s} />
                                </div>
                                <div className="mt-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                    {s.v}
                                </div>
                            </div>
                        ))}
                    </motion.div>
                </div>
            </section>

            {/* ------------------------ CITIES MARQUEE ------------------------ */}
            <CitiesMarquee />

            {/* ------------------------ HOW IT WORKS ------------------------ */}
            <section
                id="how-it-works"
                data-testid="how-it-works-section"
                className="bg-card/30"
            >
                <div className="mx-auto max-w-7xl px-6 py-24 md:py-32">
                    <div className="grid gap-12 md:grid-cols-12 md:items-end">
                        <div className="md:col-span-7">
                            <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                                <span className="h-px w-8 bg-ember-500" />
                                For creators
                            </p>
                            <h2 className="mt-5 max-w-2xl font-serif text-4xl leading-[0.98] tracking-tight md:text-5xl">
                                Four steps from{" "}
                                <span className="italic">application</span> to
                                bank account.
                            </h2>
                        </div>
                        <p className="text-sm leading-relaxed text-muted-foreground md:col-span-5">
                            We built WeAre so the boring parts — pitching in DMs,
                            chasing invoices, negotiating rates — disappear. You focus
                            on the shoot; we handle the rest.
                        </p>
                    </div>

                    <ol className="mt-16 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
                        {STEPS.map(({ n, Icon, title, body }, idx) => (
                            <motion.li
                                key={n}
                                data-testid={`step-${idx + 1}`}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-80px" }}
                                transition={{
                                    duration: 0.6,
                                    delay: idx * 0.08,
                                    ease: [0.22, 1, 0.36, 1],
                                }}
                                whileHover={{ y: -4 }}
                                className="group relative flex flex-col overflow-hidden rounded-lg border border-white/10 bg-card p-7 transition-colors duration-300 hover:border-ember-500/50 hover:shadow-[0_24px_80px_-32px_rgba(240,93,20,0.45)]"
                            >
                                <span className="absolute inset-x-0 top-0 h-px origin-left scale-x-0 bg-gradient-to-r from-ember-500 via-ember-400 to-transparent transition-transform duration-500 group-hover:scale-x-100" />
                                <div className="flex items-center justify-between">
                                    <span className="font-serif text-[54px] leading-none text-ember-500/90">
                                        {n}
                                    </span>
                                    <Icon className="h-5 w-5 text-muted-foreground transition-colors duration-200 group-hover:text-ember-500" />
                                </div>
                                <div className="mt-8 font-serif text-[26px] leading-tight tracking-tight">
                                    {title}
                                </div>
                                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                    {body}
                                </p>
                            </motion.li>
                        ))}
                    </ol>

                    <div className="mt-14">
                        <Link
                            to="/signup?role=creator"
                            data-testid="how-cta-creator"
                        >
                            <Button
                                size="lg"
                                className="group h-12 rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400"
                            >
                                Start your creator application
                                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                            </Button>
                        </Link>
                    </div>
                </div>
            </section>

            {/* --------------------- LIVE BRIEFS (public) --------------------- */}
            <LiveBriefs />

            {/* ------------------------ TRUST / WHY ------------------------ */}
            <section
                id="why"
                data-testid="why-section"
                className="mx-auto max-w-7xl px-6 py-24 md:py-32"
            >
                <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                    <span className="h-px w-8 bg-ember-500" />
                    Why WeAre
                </p>
                <h2 className="mt-5 max-w-3xl font-serif text-4xl leading-[0.98] tracking-tight md:text-5xl">
                    Built for people who take content{" "}
                    <span className="italic">and</span> payment seriously.
                </h2>

                <div className="mt-14 grid gap-6 md:grid-cols-3">
                    {TRUST_POINTS.map(({ Icon, title, body }, idx) => (
                        <motion.div
                            key={title}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: "-80px" }}
                            transition={{
                                duration: 0.6,
                                delay: idx * 0.09,
                                ease: [0.22, 1, 0.36, 1],
                            }}
                            whileHover={{ y: -4 }}
                            className="group relative overflow-hidden rounded-lg border border-white/10 bg-card p-8 transition-colors duration-300 hover:border-ember-500/50 hover:shadow-[0_24px_80px_-32px_rgba(240,93,20,0.4)]"
                        >
                            <span className="absolute inset-x-0 top-0 h-px origin-left scale-x-0 bg-gradient-to-r from-ember-500 via-ember-400 to-transparent transition-transform duration-500 group-hover:scale-x-100" />
                            <Icon className="h-6 w-6 text-ember-500" />
                            <div className="mt-6 font-serif text-[26px] leading-tight tracking-tight">
                                {title}
                            </div>
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                {body}
                            </p>
                        </motion.div>
                    ))}
                </div>
            </section>

            {/* ------------------------ FOR BRANDS / MANAGED ------------------------ */}
            <section className="border-t border-white/10 bg-card/40">
                <div className="mx-auto max-w-7xl px-6 py-20 md:py-24">
                    <div className="grid gap-10 md:grid-cols-12 md:items-end">
                        <div className="md:col-span-8">
                            <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                                <span className="h-px w-8 bg-ember-500" />
                                For brands
                            </p>
                            <h2 className="mt-5 max-w-3xl font-serif text-4xl leading-[0.98] tracking-tight md:text-5xl">
                                Self-serve platform.{" "}
                                <span className="italic">Or a team</span> that runs
                                the whole thing.
                            </h2>
                            <p className="mt-6 max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">
                                Whether you're a café in Bengaluru, a hotel in Goa,
                                a fashion label in Mumbai or a real estate launch in
                                Gurgaon — post a brief and shortlist creators
                                yourself, or hand it to us and we'll take it from
                                brief to reporting.
                            </p>
                        </div>
                        <div className="md:col-span-4">
                            <div className="flex flex-col gap-3 md:items-end">
                                <Link
                                    to="/signup?role=brand"
                                    data-testid="brand-cta"
                                    className="w-full md:w-auto"
                                >
                                    <Button
                                        size="lg"
                                        className="group h-12 w-full rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400 md:w-auto"
                                    >
                                        Post a campaign
                                        <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                    </Button>
                                </Link>
                                <a
                                    href="mailto:creators@wearemonk.in?subject=Managed%20campaign%20request"
                                    data-testid="managed-cta"
                                    className="group inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                                >
                                    <Rocket className="h-3.5 w-3.5" />
                                    Have us run it
                                    <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-1" />
                                </a>
                            </div>
                        </div>
                    </div>

                    {/* small "verticals" grid */}
                    <div className="mt-14 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
                        {[
                            "F&B",
                            "Hotels",
                            "Retail",
                            "Real Estate",
                            "Fashion",
                            "Travel",
                            "Wellness",
                        ].map((v, i) => (
                            <motion.div
                                key={v}
                                initial={{ opacity: 0, y: 12 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-60px" }}
                                transition={{
                                    duration: 0.45,
                                    delay: i * 0.04,
                                    ease: [0.22, 1, 0.36, 1],
                                }}
                                className="rounded-full border border-white/10 bg-white/[0.02] px-4 py-3 text-center text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500"
                            >
                                {v}
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ------------------------ CTA + FOOTER ------------------------ */}
            <section
                data-testid="closing-cta"
                className="border-t border-white/10"
            >
                <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-6 py-16 md:flex-row md:items-center">
                    <div className="flex items-start gap-4">
                        <span className="mt-1 hidden h-10 w-10 flex-none place-items-center rounded-md bg-ember-500/10 md:grid">
                            <Sparkles className="h-5 w-5 text-ember-500" />
                        </span>
                        <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                Ready when you are
                            </p>
                            <p className="mt-2 max-w-xl font-serif text-2xl leading-tight md:text-3xl">
                                One studio for creators, brands and the team that
                                brings them together.
                            </p>
                        </div>
                    </div>
                    <Link
                        to="/signup"
                        data-testid="closing-cta-btn"
                        className="w-full md:w-auto"
                    >
                        <Button
                            size="lg"
                            className="group h-12 w-full rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400 md:w-auto"
                        >
                            Get started
                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                        </Button>
                    </Link>
                </div>
            </section>

            <footer className="border-t border-white/10">
                <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-4 px-6 py-10 text-sm text-muted-foreground md:flex-row md:items-center">
                    <span className="font-serif text-lg text-foreground">
                        WeAre <span className="text-ember-500">Creators</span>
                    </span>
                    <span>© {new Date().getFullYear()} WeAre Monk · India</span>
                </div>
            </footer>
        </div>
    );
}
