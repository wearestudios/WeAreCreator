import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
    ArrowRight,
    ShieldCheck,
    Compass,
    Send,
    Wallet,
    MapPin,
    Sparkles,
    IndianRupee,
    Lock,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";

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

const STEPS = [
    {
        n: "01",
        Icon: ShieldCheck,
        title: "Get vetted",
        body: "Apply once. Our Bengaluru team reviews your profile and confirms your niche, style and reach.",
    },
    {
        n: "02",
        Icon: Compass,
        title: "Find campaigns",
        body: "Browse live paid briefs from cafés, restaurants and lifestyle brands hand-picked for your city.",
    },
    {
        n: "03",
        Icon: Send,
        title: "Apply",
        body: "Send a short pitch and your rate in one tap. Brands review your profile and pick their shortlist.",
    },
    {
        n: "04",
        Icon: Wallet,
        title: "Deliver & get paid",
        body: "Shoot, publish, submit. Payment is released to you the moment content is approved — no chasing.",
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
        title: "Vetted both sides",
        body: "Every creator and every brand is reviewed by the WeAre team before they can transact.",
    },
    {
        Icon: Lock,
        title: "Payments held safely",
        body: "Brands fund the collab up-front. You get paid the moment deliverables are approved.",
    },
];

export default function Landing() {
    return (
        <div
            data-testid="landing-page"
            className="min-h-screen bg-background text-foreground"
        >
            <Navbar />

            {/* ------------------------ HERO ------------------------ */}
            <section className="relative overflow-hidden">
                <div className="absolute inset-0">
                    <img
                        src={IMG_HERO}
                        alt="Bengaluru food creator moment"
                        className="h-full w-full object-cover opacity-35"
                    />
                    <div className="absolute inset-0 bg-gradient-to-b from-background/40 via-background/75 to-background" />
                    <div className="grain absolute inset-0" />
                </div>

                <div className="relative mx-auto max-w-7xl px-6 pb-24 pt-20 md:pt-32">
                    <motion.p
                        initial="hidden"
                        animate="show"
                        variants={fadeUp}
                        className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs uppercase tracking-[0.2em] text-muted-foreground backdrop-blur"
                    >
                        <MapPin className="h-3.5 w-3.5 text-ember-500" />
                        Bengaluru · Invite-only network
                    </motion.p>

                    <motion.h1
                        data-testid="hero-heading"
                        initial="hidden"
                        animate="show"
                        custom={1}
                        variants={fadeUp}
                        className="h-fluid max-w-4xl font-serif tracking-tightest"
                    >
                        Paid collaborations between{" "}
                        <span className="italic text-ember-500">
                            Bengaluru creators
                        </span>{" "}
                        and the venues worth talking about.
                    </motion.h1>

                    <motion.p
                        data-testid="hero-subheading"
                        initial="hidden"
                        animate="show"
                        custom={2}
                        variants={fadeUp}
                        className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg"
                    >
                        One place to get vetted, discover live briefs from the city's
                        best cafés and lifestyle brands, and get paid on time.
                    </motion.p>

                    <motion.div
                        initial="hidden"
                        animate="show"
                        custom={3}
                        variants={fadeUp}
                        className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center"
                    >
                        <Link
                            to="/signup?role=creator"
                            data-testid="hero-cta-creator"
                        >
                            <Button
                                size="lg"
                                className="group h-12 w-full rounded-full bg-ember-500 px-7 text-black transition-colors duration-200 hover:bg-ember-400 sm:w-auto"
                            >
                                Join as a creator
                                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                            </Button>
                        </Link>
                        <Link
                            to="/signup?role=brand"
                            data-testid="hero-cta-brand"
                        >
                            <Button
                                size="lg"
                                variant="outline"
                                className="h-12 w-full rounded-full border-white/15 bg-transparent px-7 text-foreground hover:bg-white/5 sm:w-auto"
                            >
                                Post a campaign
                            </Button>
                        </Link>
                        <Link
                            to="/login"
                            data-testid="hero-login-link"
                            className="pt-2 text-sm text-muted-foreground underline-offset-4 transition-colors duration-200 hover:text-foreground hover:underline sm:pt-0 sm:pl-3"
                        >
                            Already a member? Log in
                        </Link>
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
                            { k: "500+", v: "vetted creators" },
                            { k: "80+", v: "partner venues" },
                            { k: "₹0", v: "hidden fees" },
                        ].map((s) => (
                            <div key={s.v}>
                                <div className="font-serif text-3xl text-foreground md:text-4xl">
                                    {s.k}
                                </div>
                                <div className="mt-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                    {s.v}
                                </div>
                            </div>
                        ))}
                    </motion.div>
                </div>
            </section>

            {/* ------------------------ HOW IT WORKS ------------------------ */}
            <section
                id="how-it-works"
                data-testid="how-it-works-section"
                className="border-t border-white/10 bg-card/30"
            >
                <div className="mx-auto max-w-7xl px-6 py-24 md:py-32">
                    <div className="grid gap-12 md:grid-cols-12 md:items-end">
                        <div className="md:col-span-7">
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                For Creators · How it works
                            </p>
                            <h2 className="mt-4 max-w-2xl font-serif text-4xl leading-none tracking-tight md:text-5xl">
                                Four steps from{" "}
                                <span className="italic">application</span> to
                                bank account.
                            </h2>
                        </div>
                        <p className="text-sm leading-relaxed text-muted-foreground md:col-span-5">
                            We built WeAre so the boring parts of collabs — pitching in
                            DMs, chasing payments, negotiating rates — disappear. You
                            focus on the shoot; we handle the rest.
                        </p>
                    </div>

                    <ol className="mt-16 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
                        {STEPS.map(({ n, Icon, title, body }, idx) => (
                            <li
                                key={n}
                                data-testid={`step-${idx + 1}`}
                                className="group relative flex flex-col rounded-md border border-white/10 bg-card p-7 transition-colors duration-200 hover:border-ember-500/50"
                            >
                                <div className="flex items-center justify-between">
                                    <span className="font-serif text-5xl text-ember-500">
                                        {n}
                                    </span>
                                    <Icon className="h-5 w-5 text-muted-foreground transition-colors duration-200 group-hover:text-ember-500" />
                                </div>
                                <div className="mt-8 font-serif text-2xl leading-tight">
                                    {title}
                                </div>
                                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                    {body}
                                </p>
                            </li>
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

            {/* ------------------------ TRUST / WHY ------------------------ */}
            <section
                id="why"
                data-testid="why-section"
                className="mx-auto max-w-7xl px-6 py-24 md:py-32"
            >
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Why WeAre
                </p>
                <h2 className="mt-4 max-w-3xl font-serif text-4xl leading-none tracking-tight md:text-5xl">
                    Built for people who take content{" "}
                    <span className="italic">and</span> payment seriously.
                </h2>

                <div className="mt-14 grid gap-6 md:grid-cols-3">
                    {TRUST_POINTS.map(({ Icon, title, body }) => (
                        <div
                            key={title}
                            className="rounded-md border border-white/10 bg-card p-8 transition-colors duration-200 hover:border-ember-500/40"
                        >
                            <Icon className="h-6 w-6 text-ember-500" />
                            <div className="mt-6 font-serif text-2xl leading-tight">
                                {title}
                            </div>
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                {body}
                            </p>
                        </div>
                    ))}
                </div>
            </section>

            {/* ------------------------ FOR BRANDS (small strip) ------------------------ */}
            <section className="border-t border-white/10 bg-card/40">
                <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-6 py-14 md:flex-row md:items-center">
                    <div className="flex items-start gap-4">
                        <span className="mt-1 hidden h-10 w-10 flex-none place-items-center rounded-md bg-ember-500/10 md:grid">
                            <Sparkles className="h-5 w-5 text-ember-500" />
                        </span>
                        <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                Running a café, restaurant or brand?
                            </p>
                            <p className="mt-2 max-w-xl font-serif text-2xl leading-tight md:text-3xl">
                                Post a campaign in minutes. Reach vetted Bengaluru
                                creators, skip the agency middleman.
                            </p>
                        </div>
                    </div>
                    <Link
                        to="/signup?role=brand"
                        data-testid="brand-cta"
                        className="w-full md:w-auto"
                    >
                        <Button
                            variant="outline"
                            size="lg"
                            className="group h-12 w-full rounded-full border-white/15 bg-transparent px-7 text-foreground hover:bg-white/5 md:w-auto"
                        >
                            Post a campaign
                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                        </Button>
                    </Link>
                </div>
            </section>

            {/* ------------------------ FOOTER ------------------------ */}
            <footer className="border-t border-white/10">
                <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-4 px-6 py-10 text-sm text-muted-foreground md:flex-row md:items-center">
                    <span className="font-serif text-lg text-foreground">
                        WeAre <span className="text-ember-500">Creators</span>
                    </span>
                    <span>© {new Date().getFullYear()} WeAre Monk · Bengaluru</span>
                </div>
            </footer>
        </div>
    );
}
