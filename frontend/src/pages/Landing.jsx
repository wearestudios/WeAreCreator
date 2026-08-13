import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Utensils, Sparkles, MapPin } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";

const IMG_HERO =
    "https://images.unsplash.com/photo-1728910156510-77488f19b152?auto=format&fit=crop&w=1600&q=80";
const IMG_CAFE =
    "https://images.unsplash.com/photo-1709548145082-04d0cde481d4?auto=format&fit=crop&w=900&q=80";
const IMG_PLATE =
    "https://images.unsplash.com/photo-1621494268492-d01b98eba7e4?auto=format&fit=crop&w=900&q=80";

const fadeUp = {
    hidden: { opacity: 0, y: 16 },
    show: (i = 0) => ({
        opacity: 1,
        y: 0,
        transition: { delay: 0.08 * i, duration: 0.7, ease: [0.22, 1, 0.36, 1] },
    }),
};

export default function Landing() {
    return (
        <div data-testid="landing-page" className="min-h-screen bg-background text-foreground">
            <Navbar />

            {/* Hero */}
            <section className="relative overflow-hidden">
                <div className="absolute inset-0">
                    <img
                        src={IMG_HERO}
                        alt="Bengaluru food creator scene"
                        className="h-full w-full object-cover opacity-40"
                    />
                    <div className="absolute inset-0 bg-gradient-to-b from-background/40 via-background/70 to-background" />
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
                        Where Bengaluru's{" "}
                        <span className="italic text-ember-500">food & lifestyle</span>{" "}
                        creators meet the brands that matter.
                    </motion.h1>

                    <motion.p
                        initial="hidden"
                        animate="show"
                        custom={2}
                        variants={fadeUp}
                        className="mt-8 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg"
                    >
                        A curated marketplace for paid collaborations between the city's
                        sharpest creators and the restaurants, cafés and lifestyle brands
                        that want to be discovered by them.
                    </motion.p>

                    <motion.div
                        initial="hidden"
                        animate="show"
                        custom={3}
                        variants={fadeUp}
                        className="mt-10 flex flex-wrap gap-3"
                    >
                        <Link to="/signup" data-testid="hero-cta-primary">
                            <Button
                                size="lg"
                                className="group rounded-full bg-ember-500 px-7 text-black transition-colors duration-200 hover:bg-ember-400"
                            >
                                Apply to join
                                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                            </Button>
                        </Link>
                        <Link to="/login" data-testid="hero-cta-secondary">
                            <Button
                                size="lg"
                                variant="outline"
                                className="rounded-full border-white/15 bg-transparent px-7 text-foreground hover:bg-white/5"
                            >
                                I already have an account
                            </Button>
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
                            { k: "500+", v: "curated creators" },
                            { k: "80+", v: "partner venues" },
                            { k: "1", v: "city, done right" },
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

            {/* Two-sided value section */}
            <section id="creators" className="mx-auto max-w-7xl px-6 py-24">
                <div className="grid gap-8 md:grid-cols-12">
                    <div className="md:col-span-5">
                        <p className="mb-4 text-xs uppercase tracking-[0.2em] text-ember-500">
                            For Creators
                        </p>
                        <h2 className="font-serif text-4xl leading-none tracking-tight md:text-5xl">
                            Get paid to eat, review & tell stories.
                        </h2>
                        <p className="mt-6 text-base leading-relaxed text-muted-foreground">
                            No more DMs, no more chasing invoices. Browse open briefs,
                            apply in one tap, get approved, deliver, and get paid — all
                            in one place.
                        </p>
                        <ul className="mt-8 space-y-3 text-sm text-muted-foreground">
                            {[
                                "Transparent budgets — see the fee upfront",
                                "Direct chat with brand managers",
                                "Portfolio that grows with every campaign",
                            ].map((t) => (
                                <li key={t} className="flex items-start gap-3">
                                    <Sparkles className="mt-0.5 h-4 w-4 flex-none text-ember-500" />
                                    <span>{t}</span>
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="md:col-span-7">
                        <div className="relative overflow-hidden rounded-md border border-white/10">
                            <img
                                src={IMG_PLATE}
                                alt="Creator moment"
                                className="h-[420px] w-full object-cover"
                            />
                            <div className="pointer-events-none absolute inset-0 bg-gradient-to-tr from-background/70 via-transparent to-transparent" />
                        </div>
                    </div>
                </div>
            </section>

            <section
                id="brands"
                className="border-y border-white/10 bg-card/40"
            >
                <div className="mx-auto grid max-w-7xl gap-8 px-6 py-24 md:grid-cols-12">
                    <div className="md:order-2 md:col-span-5">
                        <p className="mb-4 text-xs uppercase tracking-[0.2em] text-ember-500">
                            For Brands
                        </p>
                        <h2 className="font-serif text-4xl leading-none tracking-tight md:text-5xl">
                            Book Bengaluru's best creators. Skip the agency tax.
                        </h2>
                        <p className="mt-6 text-base leading-relaxed text-muted-foreground">
                            Post a brief in minutes. Get matched with vetted creators who
                            actually fit your vibe. Approve deliverables, pay from the
                            dashboard, done.
                        </p>
                        <ul className="mt-8 space-y-3 text-sm text-muted-foreground">
                            {[
                                "Vetted, on-brand creator pool",
                                "Fixed pricing — no surprise negotiations",
                                "One dashboard for briefs, drafts, invoices",
                            ].map((t) => (
                                <li key={t} className="flex items-start gap-3">
                                    <Utensils className="mt-0.5 h-4 w-4 flex-none text-ember-500" />
                                    <span>{t}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div className="md:order-1 md:col-span-7">
                        <div className="relative overflow-hidden rounded-md border border-white/10">
                            <img
                                src={IMG_CAFE}
                                alt="Premium cafe interior"
                                className="h-[420px] w-full object-cover"
                            />
                            <div className="pointer-events-none absolute inset-0 bg-gradient-to-tl from-background/70 via-transparent to-transparent" />
                        </div>
                    </div>
                </div>
            </section>

            {/* How it works */}
            <section id="how" className="mx-auto max-w-7xl px-6 py-24">
                <p className="mb-4 text-xs uppercase tracking-[0.2em] text-ember-500">
                    How it works
                </p>
                <h2 className="max-w-3xl font-serif text-4xl leading-none tracking-tight md:text-5xl">
                    A cleaner way to collaborate.
                </h2>
                <div className="mt-14 grid gap-6 md:grid-cols-3">
                    {[
                        {
                            n: "01",
                            title: "Apply",
                            body: "Creators and brands apply. Our team hand-picks who's in.",
                        },
                        {
                            n: "02",
                            title: "Match",
                            body: "Brands post briefs. Creators apply. WeAre curates the shortlist.",
                        },
                        {
                            n: "03",
                            title: "Deliver",
                            body: "Content is drafted, approved, published. Payment happens instantly.",
                        },
                    ].map((s) => (
                        <div
                            key={s.n}
                            className="group rounded-md border border-white/10 bg-card p-8 transition-colors duration-200 hover:border-ember-500/50"
                        >
                            <div className="font-serif text-5xl text-ember-500">
                                {s.n}
                            </div>
                            <div className="mt-6 font-serif text-2xl">{s.title}</div>
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                {s.body}
                            </p>
                        </div>
                    ))}
                </div>
            </section>

            {/* CTA */}
            <section className="mx-auto max-w-7xl px-6 pb-32">
                <div className="relative overflow-hidden rounded-md border border-white/10 bg-card p-10 md:p-16">
                    <div className="grain absolute inset-0" />
                    <div className="relative grid gap-8 md:grid-cols-2 md:items-end">
                        <h2 className="font-serif text-4xl leading-none tracking-tight md:text-5xl">
                            The Bengaluru creator economy,{" "}
                            <span className="italic text-ember-500">unlocked.</span>
                        </h2>
                        <div className="flex flex-wrap gap-3 md:justify-end">
                            <Link to="/signup?role=creator" data-testid="cta-creator">
                                <Button
                                    size="lg"
                                    className="rounded-full bg-ember-500 px-7 text-black hover:bg-ember-400"
                                >
                                    I'm a creator
                                </Button>
                            </Link>
                            <Link to="/signup?role=brand" data-testid="cta-brand">
                                <Button
                                    size="lg"
                                    variant="outline"
                                    className="rounded-full border-white/15 bg-transparent px-7 text-foreground hover:bg-white/5"
                                >
                                    I'm a brand
                                </Button>
                            </Link>
                        </div>
                    </div>
                </div>
            </section>

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
