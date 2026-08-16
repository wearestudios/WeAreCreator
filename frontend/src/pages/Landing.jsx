// The public home page.
//
// Three things shape it. It is an endorsed sub-brand — WeAre Creators is an
// offering of WeAre Studios, so the studio is credited in the nav and the
// footer and nowhere else; the ember identity stays Creators'. The hero is a
// slider because creators sign up from every category and one still
// photograph can only argue for one of them. And the geography is
// stated plainly: the network is deepest in Bengaluru, that is where the work
// is today, and signing up is open to anyone in India.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
    motion,
    AnimatePresence,
    useReducedMotion,
    useScroll,
    useTransform,
} from "framer-motion";
import {
    ArrowRight,
    ShieldCheck,
    Compass,
    Send,
    Wallet,
    IndianRupee,
    Lock,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatCompensation, isBarter } from "@/lib/compensation";
import {
    LANDING as PAGE_IDS,
    LANDING_CLOSING as CLOSING_IDS,
    LANDING_FOOTER as FOOTER_IDS,
    LANDING_HERO as HERO_IDS,
    LANDING_REACH as REACH_IDS,
    LANDING_SECTIONS as SECTION_IDS,
    LANDING_STUDIO as STUDIO_IDS,
} from "@/constants/testIds";
import { StudioEndorsement } from "@/components/StudioEndorsement";

// ---------------------------------------------------------------------------
// Hero deck
// ---------------------------------------------------------------------------
//
// Five slides, spanning the categories creators actually sign up from. The
// deck used to be four food shots, which quietly told a beauty or tech creator
// this wasn't for them — the range is the argument, so the deck has to carry
// it. Only the photograph and the headline change between slides; the eyebrow,
// the subheading, both CTAs and the stats are fixed, so the page never appears
// to be selling five different products.
//
// Each headline names the outcome the brand is buying in that category, not
// the shoot. That keeps them specific without any of them being generic.
const SLIDES = [
    {
        key: "launch",
        kicker: "Restaurant launch",
        headline: ["A full room", "on opening night."],
        image:
            "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=2000&q=80",
        alt: "A busy restaurant on its launch night",
    },
    {
        key: "fashion",
        kicker: "Fashion & beauty",
        headline: ["The lookbook that moves", "the whole collection."],
        image:
            "https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=2000&q=80",
        alt: "A fashion shoot on a studio rail",
    },
    {
        key: "travel",
        kicker: "Hotels & travel",
        headline: ["Two nights away.", "A season of bookings."],
        image:
            "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=2000&q=80",
        alt: "A hotel room opening onto a balcony",
    },
    {
        key: "tech",
        kicker: "Tech & gadgets",
        headline: ["The review people", "actually watch to the end."],
        image:
            "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=2000&q=80",
        alt: "A desk of gadgets set up for a review",
    },
    {
        key: "fitness",
        kicker: "Fitness & wellness",
        headline: ["One class filmed.", "Six weeks booked out."],
        image:
            "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?auto=format&fit=crop&w=2000&q=80",
        alt: "A fitness class mid-session",
    },
];

const SLIDE_INTERVAL_MS = 7000;

// Cities we serve. Bengaluru leads because that is where the network is; the
// rest are listed flat, with no "live" or "coming soon" badge, because a badge
// is a promise about a date and we aren't making one.
const CITIES = [
    "Bengaluru",
    "Mumbai",
    "Delhi NCR",
    "Hyderabad",
    "Pune",
    "Chennai",
    "Kolkata",
    "Goa",
];

const STEPS = [
    {
        n: "01",
        Icon: ShieldCheck,
        title: "Get verified",
        body: "Apply once. Our team reviews your profile, niche and audience — every creator on here has been through it.",
    },
    {
        n: "02",
        Icon: Compass,
        title: "Discover briefs",
        body: "Paid campaigns from brands across fashion, beauty, food, travel, tech, fitness and retail. You see the deliverable and the fee before you pitch.",
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
        body: "See the fee before you pitch. No opaque negotiations, and no free product or \"exposure\" standing in for money.",
    },
    {
        Icon: ShieldCheck,
        title: "Verified on both sides",
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

const MANAGED_MAILTO =
    "mailto:creators@wearemonk.in?subject=Managed%20campaign%20request";

const fadeUp = {
    hidden: { opacity: 0, y: 16 },
    show: (i = 0) => ({
        opacity: 1,
        y: 0,
        transition: { delay: 0.08 * i, duration: 0.7, ease: [0.22, 1, 0.36, 1] },
    }),
};

// ---------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------

function AnimatedNumber({ value, suffix = "", duration = 1400 }) {
    const still = useReducedMotion();
    const [n, setN] = useState(still ? value : 0);
    useEffect(() => {
        if (still) {
            setN(value);
            return undefined;
        }
        const start = performance.now();
        let frame;
        const tick = (now) => {
            const t = Math.min(1, (now - start) / duration);
            setN(Math.round(value * (1 - Math.pow(1 - t, 3)))); // ease-out cubic
            if (t < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(frame);
    }, [value, duration, still]);
    return (
        <span>
            {n.toLocaleString("en-IN")}
            {suffix}
        </span>
    );
}

/**
 * One slide's photograph.
 *
 * The gradient and grain sit over it either way, so a photo that fails to load
 * leaves a composed dark panel rather than a broken page — the headline is
 * readable on the background alone. Worth having: these are remote images on
 * the one page most people see first.
 */
function SlideImage({ slide, index, active }) {
    const [failed, setFailed] = useState(false);
    if (failed) return null;
    return (
        <img
            src={slide.image}
            alt={slide.alt}
            data-testid={HERO_IDS.slideImage(index)}
            onError={() => setFailed(true)}
            // The first slide is the one everybody sees; the rest can wait.
            loading={index === 0 ? "eager" : "lazy"}
            fetchpriority={index === 0 ? "high" : "low"}
            decoding="async"
            aria-hidden={active ? undefined : "true"}
            className="h-full w-full object-cover"
        />
    );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

function Hero() {
    const still = useReducedMotion();
    const [index, setIndex] = useState(0);
    const [paused, setPaused] = useState(false);

    // Parallax on the deck, not on any one slide, so crossfades don't fight it.
    const { scrollY } = useScroll();
    const imgY = useTransform(scrollY, [0, 400], [0, 60]);
    // The photograph has to be legible or the slider means nothing —
    // design_guidelines is explicit that an invisible image means the overlay
    // is too heavy. It dims as you scroll into the page, not before.
    const imgOpacity = useTransform(scrollY, [0, 400], [0.85, 0.3]);

    // Reduced motion gets the first slide and nothing else: no timer, no
    // crossfade, no dots to imply something is moving.
    const animated = !still;

    useEffect(() => {
        if (!animated || paused) return undefined;
        const t = setInterval(
            () => setIndex((i) => (i + 1) % SLIDES.length),
            SLIDE_INTERVAL_MS,
        );
        return () => clearInterval(t);
    }, [animated, paused]);

    const slides = animated ? SLIDES : SLIDES.slice(0, 1);
    const current = slides[Math.min(index, slides.length - 1)];

    // Pausing covers focus as well as hover: somebody tabbing through the CTAs
    // shouldn't have the thing they're reading swapped out from under them.
    const hold = useCallback(() => setPaused(true), []);
    const release = useCallback(() => setPaused(false), []);

    return (
        <section
            data-testid={HERO_IDS.section}
            aria-roledescription={animated ? "carousel" : undefined}
            aria-label={animated ? "Campaign types" : undefined}
            onMouseEnter={hold}
            onMouseLeave={release}
            onFocusCapture={hold}
            onBlurCapture={release}
            className="relative overflow-hidden"
        >
            <motion.div
                style={{ y: imgY, opacity: imgOpacity }}
                data-testid={HERO_IDS.slides}
                className="media-frame absolute inset-0"
            >
                <AnimatePresence initial={false}>
                    <motion.div
                        key={current.key}
                        data-testid={HERO_IDS.slide(SLIDES.indexOf(current))}
                        initial={animated ? { opacity: 0 } : false}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        // Slow enough to read as a dissolve rather than a cut.
                        transition={{ duration: animated ? 1.6 : 0, ease: "linear" }}
                        className="absolute inset-0"
                    >
                        <SlideImage
                            slide={current}
                            index={SLIDES.indexOf(current)}
                            active
                        />
                    </motion.div>
                </AnimatePresence>
            </motion.div>

            {/* Preload the rest quietly once the first slide is up, so the
                first crossfade isn't a fade to nothing. */}
            {animated && (
                <div aria-hidden className="pointer-events-none absolute h-0 w-0 overflow-hidden">
                    {SLIDES.slice(1).map((s) => (
                        <img key={s.key} src={s.image} alt="" loading="lazy" decoding="async" />
                    ))}
                </div>
            )}

            {/* Two overlays doing two jobs: the vertical one lands the image
                into the page, the horizontal one is a scrim behind the text so
                the headline stays readable whatever the photograph is doing on
                the left. A single flat wash would have to be heavy enough to
                kill the image to do both. */}
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background/40 via-background/55 to-background" />
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-background/85 via-background/45 to-transparent" />
            <div className="pointer-events-none grain absolute inset-0" />

            <motion.div
                aria-hidden
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.55 }}
                transition={{ duration: still ? 0 : 2 }}
                className="pointer-events-none absolute -right-40 top-24 h-[520px] w-[520px] rounded-full bg-ember-500/15 blur-[120px]"
            />

            <div className="relative mx-auto max-w-7xl px-6 pb-28 pt-20 md:pt-32">
                <motion.p
                    data-testid={HERO_IDS.eyebrow}
                    initial="hidden"
                    animate="show"
                    variants={fadeUp}
                    className="mb-6 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs uppercase tracking-[0.22em] text-muted-foreground backdrop-blur"
                >
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-ember-500 animate-pulse" />
                    <span className="text-ember-500/90">Vol. 01</span>
                    <span className="h-3 w-px bg-white/15" />
                    Bengaluru · Influencer studio
                </motion.p>

                {/* Only this line and the photograph change per slide. */}
                <div className="min-h-[10.5rem] md:min-h-[13rem]">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={current.key}
                            initial={animated ? { opacity: 0, y: 10 } : false}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            transition={{ duration: animated ? 0.7 : 0, ease: [0.22, 1, 0.36, 1] }}
                        >
                            <p
                                data-testid={HERO_IDS.kicker}
                                className="mb-4 text-xs uppercase tracking-[0.2em] text-ember-500"
                            >
                                {current.kicker}
                            </p>
                            <h1
                                data-testid={HERO_IDS.heading}
                                className="max-w-5xl font-serif text-fluid-hero tracking-tightest"
                            >
                                {current.headline[0]}
                                <span className="block italic text-muted-foreground">
                                    {current.headline[1]}
                                </span>
                            </h1>
                        </motion.div>
                    </AnimatePresence>
                </div>

                <motion.p
                    data-testid={HERO_IDS.subheading}
                    initial="hidden"
                    animate="show"
                    custom={2}
                    variants={fadeUp}
                    className="mt-8 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg"
                >
                    Post your brief yourself — or hand it to our team. Either way,
                    you're working with the same verified creator network, and the
                    fee is agreed before anybody shoots.
                </motion.p>

                <motion.div
                    initial="hidden"
                    animate="show"
                    custom={3}
                    variants={fadeUp}
                    className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center"
                >
                    <Link to="/signup?role=brand" data-testid={HERO_IDS.ctaBrand}>
                        <Button
                            size="lg"
                            className="group h-12 w-full rounded-full bg-ember-500 px-7 text-black transition-colors duration-200 hover:bg-ember-400 sm:w-auto"
                        >
                            Post a campaign
                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                        </Button>
                    </Link>
                    <Link to="/signup?role=creator" data-testid={HERO_IDS.ctaCreator}>
                        <Button
                            size="lg"
                            variant="outline"
                            className="h-12 w-full rounded-full border-white/15 bg-transparent px-7 text-foreground hover:bg-white/5 sm:w-auto"
                        >
                            Join as a creator
                        </Button>
                    </Link>
                    <a
                        href={MANAGED_MAILTO}
                        data-testid={HERO_IDS.managedLink}
                        className="group -mb-2 mt-2 inline-flex min-h-[2.75rem] items-center gap-1 py-2 text-sm text-muted-foreground underline-offset-4 transition-colors duration-200 hover:text-ember-500 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:mt-0 sm:pl-3"
                    >
                        Prefer we run it? Talk to our team
                        <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-1" />
                    </a>
                </motion.div>

                {animated && (
                    <div
                        data-testid={HERO_IDS.dots}
                        role="tablist"
                        aria-label="Choose a campaign type"
                        className="mt-12 flex items-center gap-3"
                    >
                        {SLIDES.map((s, i) => {
                            const on = i === index;
                            return (
                                <button
                                    key={s.key}
                                    type="button"
                                    role="tab"
                                    aria-selected={on}
                                    aria-label={s.kicker}
                                    data-testid={HERO_IDS.dot(i)}
                                    onClick={() => setIndex(i)}
                                    className="group -m-2 grid h-11 w-11 place-items-center rounded-full p-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:h-auto md:w-auto"
                                >
                                    <span
                                        className={
                                            "block h-1 rounded-full transition-all duration-500 " +
                                            (on
                                                ? "w-10 bg-ember-500"
                                                : "w-4 bg-white/20 group-hover:bg-white/40")
                                        }
                                    />
                                </button>
                            );
                        })}
                    </div>
                )}

                <motion.div
                    data-testid={HERO_IDS.stats}
                    initial="hidden"
                    animate="show"
                    custom={4}
                    variants={fadeUp}
                    className="mt-16 grid max-w-3xl grid-cols-3 gap-8 border-t border-white/10 pt-8"
                >
                    {[
                        { id: "creators", k: 500, s: "+", v: "verified creators" },
                        // 48 hours is the review turnaround the product commits
                        // to everywhere else, so it is a claim we already keep.
                        { id: "review", k: 48, s: "h", v: "profile review" },
                        { id: "fees", k: 0, s: "", v: "hidden fees", prefix: "₹" },
                    ].map((s) => (
                        <div key={s.id} data-testid={HERO_IDS.stat(s.id)}>
                            <div className="font-serif text-fluid-4xl text-foreground">
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
    );
}

// ---------------------------------------------------------------------------
// Where we are
// ---------------------------------------------------------------------------

/**
 * Replaces the scrolling marquee.
 *
 * A marquee of city names implied a presence in each of them. This says the
 * true thing instead: the network is deepest in Bengaluru, that is where the
 * campaigns are, and anyone in India can sign up today. No "live" or "coming
 * soon" pills — a badge is a promise about a date.
 */
function Reach() {
    return (
        <section
            data-testid={REACH_IDS.section}
            className="border-y border-white/10 bg-card/30"
        >
            <div className="mx-auto max-w-7xl px-6 py-14">
                <div className="grid gap-8 md:grid-cols-12 md:items-center">
                    <p
                        data-testid={REACH_IDS.note}
                        className="text-sm leading-relaxed text-muted-foreground md:col-span-5"
                    >
                        Our creator network runs deepest in{" "}
                        <span className="text-foreground">Bengaluru</span>, and that's
                        where most campaigns are today. Signing up is open to creators
                        anywhere in India.
                    </p>
                    <ul
                        data-testid={REACH_IDS.cities}
                        className="flex flex-wrap gap-x-8 gap-y-3 md:col-span-7 md:justify-end"
                    >
                        {CITIES.map((c) => (
                            <li
                                key={c}
                                data-testid={REACH_IDS.city(c)}
                                className={
                                    "font-serif text-xl italic md:text-2xl " +
                                    (c === "Bengaluru"
                                        ? "text-foreground"
                                        : "text-muted-foreground/60")
                                }
                            >
                                {c}
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </section>
    );
}

// ---------------------------------------------------------------------------
// Live briefs
// ---------------------------------------------------------------------------

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
            data-testid={SECTION_IDS.liveBriefs}
            className="border-b border-white/10 bg-card/30"
        >
            <div className="mx-auto max-w-7xl px-6 py-24 md:py-32">
                <div className="grid gap-10 md:grid-cols-12 md:items-end">
                    <div className="md:col-span-7">
                        <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                            <span className="h-px w-8 bg-ember-500" />
                            Open right now
                        </p>
                        <h2 className="mt-5 max-w-2xl font-serif text-fluid-5xl leading-[0.98] tracking-tight">
                            Briefs live on the platform{" "}
                            <span className="italic">today</span>.
                        </h2>
                    </div>
                    <p className="text-sm leading-relaxed text-muted-foreground md:col-span-5">
                        {totalOpen > 0
                            ? `${totalOpen} paid ${
                                  totalOpen === 1 ? "brief is" : "briefs are"
                              } open as you read this. Sign up as a creator to see the full brief and pitch.`
                            : "Paid briefs from Bengaluru brands. Sign up as a creator to see the full brief and pitch."}
                    </p>
                </div>

                <div className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
                    {briefs === null
                        ? Array.from({ length: 3 }).map((_, i) => (
                              <div
                                  key={i}
                                  className="h-56 animate-pulse rounded-lg border border-white/10 bg-card grain-surface"
                              />
                          ))
                        : briefs.map((b, idx) => (
                              <motion.article
                                  key={b.id}
                                  data-testid={SECTION_IDS.liveBrief(b.id)}
                                  initial={{ opacity: 0, y: 18 }}
                                  whileInView={{ opacity: 1, y: 0 }}
                                  viewport={{ once: true, margin: "-60px" }}
                                  transition={{
                                      duration: 0.55,
                                      delay: idx * 0.06,
                                      ease: [0.22, 1, 0.36, 1],
                                  }}
                                  className="group flex flex-col rounded-lg border border-white/10 bg-card p-7 transition-colors duration-300 hover:border-ember-500/50 grain-surface"
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
                                              {isBarter(b) ? "What you get" : "Per creator"}
                                          </div>
                                          <div className="mt-1 flex items-baseline font-serif text-3xl">
                                              {isBarter(b) ? (
                                                  "Barter"
                                              ) : (
                                                  <>
                                                      <IndianRupee className="h-5 w-5 text-ember-500" />
                                                      {formatCompensation(b).amount ?? "—"}
                                                  </>
                                              )}
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
                    <Link to="/signup?role=creator" data-testid={SECTION_IDS.liveBriefsCta}>
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

// ---------------------------------------------------------------------------
// Closing CTA
// ---------------------------------------------------------------------------

const CLOSING = {
    creator: {
        eyebrow: "For creators",
        heading: ["Get paid properly", "for work you'd post anyway."],
        support:
            "Apply once, pitch on live briefs, and know the fee before you shoot. Signups are open to creators anywhere in India.",
        cta: "Join as a creator",
        to: "/signup?role=creator",
        testid: CLOSING_IDS.buttonCreator,
    },
    brand: {
        eyebrow: "For brands",
        heading: ["Post a brief.", "Meet the shortlist."],
        support:
            "Verified creators, fixed budgets, and one place to run the whole thing from brief to payment.",
        cta: "Post a campaign",
        to: "/signup?role=brand",
        testid: CLOSING_IDS.buttonBrand,
    },
};

/**
 * One closing CTA instead of three stacked ones.
 *
 * The page used to end with a brand block, a managed-service block and a
 * generic "get started" block in a row, which read as three people asking for
 * the same thing. A toggle asks once and lets the reader say which of the two
 * they are; the managed-service option stays as a line of text beneath,
 * because it's a real option for a small number of brands and a distraction
 * for everybody else.
 */
function ClosingCta() {
    const still = useReducedMotion();
    const [role, setRole] = useState("creator");
    const copy = CLOSING[role];

    return (
        <section
            data-testid={CLOSING_IDS.section}
            className="border-t border-white/10"
        >
            <div className="mx-auto max-w-7xl px-6 py-24 md:py-32">
                <div
                    data-testid={CLOSING_IDS.toggle}
                    role="tablist"
                    aria-label="Who you are"
                    className="inline-flex rounded-full border border-white/10 bg-white/[0.03] p-1"
                >
                    {["creator", "brand"].map((r) => {
                        const on = role === r;
                        return (
                            <button
                                key={r}
                                type="button"
                                role="tab"
                                aria-selected={on}
                                data-testid={CLOSING_IDS.toggleOption(r)}
                                onClick={() => setRole(r)}
                                className={
                                    "inline-flex min-h-[2.75rem] items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0 rounded-full px-5 py-2 text-xs uppercase tracking-[0.2em] transition-colors duration-200 " +
                                    (on
                                        ? "bg-ember-500 text-black"
                                        : "text-muted-foreground hover:text-foreground")
                                }
                            >
                                I'm a {r}
                            </button>
                        );
                    })}
                </div>

                <AnimatePresence mode="wait">
                    <motion.div
                        key={role}
                        initial={still ? false : { opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={still ? undefined : { opacity: 0, y: -10 }}
                        transition={{ duration: still ? 0 : 0.35, ease: [0.22, 1, 0.36, 1] }}
                        className="mt-10 grid gap-10 md:grid-cols-12 md:items-end"
                    >
                        <div className="md:col-span-8">
                            <p
                                data-testid={CLOSING_IDS.eyebrow}
                                className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500"
                            >
                                <span className="h-px w-8 bg-ember-500" />
                                {copy.eyebrow}
                            </p>
                            <h2
                                data-testid={CLOSING_IDS.heading}
                                className="mt-5 max-w-3xl font-serif text-fluid-5xl leading-[0.98] tracking-tight"
                            >
                                {copy.heading[0]}{" "}
                                <span className="italic">{copy.heading[1]}</span>
                            </h2>
                            <p
                                data-testid={CLOSING_IDS.support}
                                className="mt-6 max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base"
                            >
                                {copy.support}
                            </p>
                        </div>

                        <div className="md:col-span-4">
                            <div className="flex flex-col gap-4 md:items-end">
                                <Link
                                    to={copy.to}
                                    data-testid={CLOSING_IDS.button}
                                    className="w-full md:w-auto"
                                >
                                    <Button
                                        size="lg"
                                        data-testid={copy.testid}
                                        className="group h-12 w-full rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400 md:w-auto"
                                    >
                                        {copy.cta}
                                        <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                    </Button>
                                </Link>
                                <a
                                    href={MANAGED_MAILTO}
                                    data-testid={CLOSING_IDS.managedLink}
                                    className="-my-2 min-h-[2.75rem] py-2 md:my-0 md:min-h-0 md:py-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background inline-flex items-center text-sm text-muted-foreground underline-offset-4 transition-colors duration-200 hover:text-ember-500 hover:underline"
                                >
                                    Or have our team run the campaign for you
                                </a>
                            </div>
                        </div>
                    </motion.div>
                </AnimatePresence>
            </div>
        </section>
    );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Landing() {
    const verticals = useMemo(
        // One label per campaign category the server accepts (fnb, hospitality,
        // retail, real_estate, fashion, travel, wellness, lifestyle), worded the
        // way a brand would say it. A brief can only be filed under one of
        // these, so nothing here promises a vertical the product can't express.
        () => [
            "Fashion",
            "Beauty & Wellness",
            "Food & Drink",
            "Hotels",
            "Travel",
            "Retail",
            "Real Estate",
            "Lifestyle",
        ],
        [],
    );

    return (
        <div
            data-testid={PAGE_IDS.page}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <Navbar />

            <Hero />
            <Reach />

            {/* ------------------------ HOW IT WORKS ------------------------ */}
            <section
                id="how-it-works"
                data-testid={SECTION_IDS.howItWorks}
                className="bg-card/30"
            >
                <div className="mx-auto max-w-7xl px-6 py-24 md:py-32">
                    <div className="grid gap-12 md:grid-cols-12 md:items-end">
                        <div className="md:col-span-7">
                            <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                                <span className="h-px w-8 bg-ember-500" />
                                For creators
                            </p>
                            <h2 className="mt-5 max-w-2xl font-serif text-fluid-5xl leading-[0.98] tracking-tight">
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
                                data-testid={SECTION_IDS.step(idx + 1)}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-80px" }}
                                transition={{
                                    duration: 0.6,
                                    delay: idx * 0.08,
                                    ease: [0.22, 1, 0.36, 1],
                                }}
                                whileHover={{ y: -4 }}
                                className="group relative flex flex-col overflow-hidden rounded-lg border border-white/10 bg-card p-7 transition-colors duration-300 hover:border-ember-500/50 hover:bg-card-elevated grain-surface"
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
                        <Link to="/signup?role=creator" data-testid={SECTION_IDS.howCtaCreator}>
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

            <LiveBriefs />

            {/* ------------------------ TRUST / WHY ------------------------ */}
            <section
                id="why"
                data-testid={SECTION_IDS.why}
                className="mx-auto max-w-7xl px-6 py-24 md:py-32"
            >
                <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                    <span className="h-px w-8 bg-ember-500" />
                    Why WeAre
                </p>
                <h2 className="mt-5 max-w-3xl font-serif text-fluid-5xl leading-[0.98] tracking-tight">
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
                            className="group relative overflow-hidden rounded-lg border border-white/10 bg-card p-8 transition-colors duration-300 hover:border-ember-500/50 hover:bg-card-elevated grain-surface"
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

            {/* ------------------------ FOR BRANDS ------------------------ */}
            {/* Content only. Its two CTAs moved into the single closing
                section, so the page asks once rather than three times. */}
            <section
                data-testid={SECTION_IDS.forBrands}
                className="border-t border-white/10 bg-card/40"
            >
                <div className="mx-auto max-w-7xl px-6 py-24 md:py-32">
                    <div className="grid gap-10 md:grid-cols-12 md:items-end">
                        <div className="md:col-span-8">
                            <p className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                                <span className="h-px w-8 bg-ember-500" />
                                For brands
                            </p>
                            <h2 className="mt-5 max-w-3xl font-serif text-fluid-5xl leading-[0.98] tracking-tight">
                                Self-serve platform.{" "}
                                <span className="italic">Or a team</span> that runs
                                the whole thing.
                            </h2>
                        </div>
                        <p className="text-sm leading-relaxed text-muted-foreground md:col-span-4">
                            A label launching a collection, a studio filling classes,
                            a hotel with rooms to sell, a restaurant opening its doors
                            — post a brief and shortlist creators yourself, or hand it
                            to us and we'll take it from brief to reporting.
                        </p>
                    </div>

                    <div className="mt-14 grid grid-cols-2 gap-3 md:grid-cols-4">
                        {verticals.map((v, i) => (
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

            <ClosingCta />

            <footer data-testid={FOOTER_IDS.section} className="border-t border-white/10">
                <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-4 px-6 py-10 text-sm text-muted-foreground md:flex-row md:items-center">
                    <div className="flex flex-col gap-1">
                        <span
                            data-testid={FOOTER_IDS.wordmark}
                            className="font-serif text-lg text-foreground"
                        >
                            WeAre <span className="text-ember-500">Creators</span>
                        </span>
                        <StudioEndorsement testid={STUDIO_IDS.footer} />
                    </div>
                    <span>© {new Date().getFullYear()} WeAre Monk · Bengaluru, India</span>
                </div>
            </footer>
        </div>
    );
}
