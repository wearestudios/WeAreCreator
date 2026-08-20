// Campaigns that look like this creator's work.
//
// Every tile leads with why it surfaced. A recommendation nobody can explain
// reads as an ad; one that says "you cover cafés, and it's in Indiranagar"
// reads as somebody having paid attention. The reason comes from the API,
// which is the only place that knows what actually matched.
import React from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { Compass, MapPin, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CREATOR_SUGGESTED as IDS } from "@/constants/testIds";
import { isBarter } from "@/lib/compensation";
import BrandAvatar from "@/components/BrandAvatar";
import { DeliverableSummary } from "@/components/Deliverables";
import CampaignCover from "@/components/CampaignCover";
import { CAT_LABEL, EmptyState, Money, SectionHead, formatRupees } from "./shared";

export default function Suggested({ campaigns }) {
    const still = useReducedMotion();
    const rows = campaigns || [];

    return (
        <>
            <SectionHead
                kicker="Might suit you"
                title="Briefs that match your work."
                aside={
                    rows.length > 0 && (
                        <span data-testid={IDS.count} className="text-xs text-muted-foreground">
                            {rows.length} {rows.length === 1 ? "match" : "matches"}
                        </span>
                    )
                }
            />

            <div className="mt-8">
                {rows.length === 0 ? (
                    <EmptyState
                        testid={IDS.empty}
                        Icon={Compass}
                        title="Nothing matched today."
                        action={
                            <Link to="/campaigns" className="mt-2">
                                <Button className="h-12 rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                    Browse everything
                                </Button>
                            </Link>
                        }
                    >
                        {/* The fix is usually the profile, so say so rather than
                            leaving an empty grid to read as "no work about". */}
                        Matches come from your niches, what you make and where you
                        are — filling those in on your profile widens what we can
                        put in front of you.
                    </EmptyState>
                ) : (
                    <ul
                        data-testid={IDS.grid}
                        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                    >
                        {rows.map((c) => (
                            <motion.li
                                key={c.id}
                                data-testid={IDS.tile(c.id)}
                                whileHover={still ? undefined : { y: -3 }}
                                transition={{ duration: 0.2, ease: "easeOut" }}
                                className="flex flex-col overflow-hidden rounded-md border border-white/10 bg-card transition-colors duration-200 hover:border-white/20 grain-surface"
                            >
                                <CampaignCover
                                    campaign={c}
                                    rounded="rounded-none"
                                    className="border-0 border-b"
                                />
                                <div className="flex flex-1 flex-col p-6">
                                <p className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                    <BrandAvatar brand={c} size="h-5 w-5" />
                                    <span className="truncate">{c.brand_name || "Brand"}</span>
                                </p>
                                <Link
                                    to={`/campaigns/${c.id}`}
                                    className="mt-2 font-serif text-xl leading-tight transition-colors duration-200 hover:text-ember-500"
                                >
                                    {c.title}
                                </Link>

                                <p
                                    data-testid={IDS.reason(c.id)}
                                    className="mt-4 inline-flex items-start gap-2 rounded-md border border-ember-500/25 bg-ember-500/10 px-3 py-2 text-xs leading-relaxed text-ember-500"
                                >
                                    <Sparkles className="mt-0.5 h-3.5 w-3.5 flex-none" />
                                    {c.match_reason}
                                </p>

                                <DeliverableSummary
                                    campaign={c}
                                    className="mt-4 line-clamp-3 block text-sm leading-relaxed text-muted-foreground"
                                />

                                <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
                                    {c.area && (
                                        <span className="inline-flex items-center gap-1.5">
                                            <MapPin className="h-3.5 w-3.5" />
                                            {c.area}
                                        </span>
                                    )}
                                    {c.category && (
                                        <span className="rounded-full bg-white/5 px-2.5 py-0.5 uppercase tracking-[0.15em]">
                                            {CAT_LABEL[c.category] || c.category}
                                        </span>
                                    )}
                                </div>

                                {/* mt-auto so every tile's price and button line up
                                    across the row however long the brief runs. */}
                                <div className="mt-auto flex items-end justify-between gap-3 pt-6">
                                    {/* Money renders the rupee symbol, so a
                                      * barter brief cannot go through it. */}
                                    {isBarter(c) ? (
                                        <span
                                            data-testid={IDS.budget(c.id)}
                                            className="font-serif text-2xl leading-none"
                                        >
                                            Barter
                                        </span>
                                    ) : (
                                        <Money
                                            symbolClass="h-4 w-4"
                                            className="font-serif text-2xl leading-none"
                                        >
                                            <span data-testid={IDS.budget(c.id)}>
                                                {formatRupees(c.budget_per_creator)}
                                            </span>
                                        </Money>
                                    )}
                                    {/* Applying needs a pitch and a rate, and that
                                        form lives on the brief. */}
                                    <Link to={`/campaigns/${c.id}`} data-testid={IDS.apply(c.id)}>
                                        <Button className="h-11 rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                            Apply
                                        </Button>
                                    </Link>
                                </div>
                                </div>
                            </motion.li>
                        ))}
                    </ul>
                )}
            </div>
        </>
    );
}
