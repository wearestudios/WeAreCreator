// Campaigns that look like this creator's work.
//
// Every tile leads with why it surfaced. A recommendation nobody can explain
// reads as an ad; one that says "you cover cafés, and it's in Indiranagar"
// reads as somebody having paid attention. The reason comes from the API,
// which is the only place that knows what actually matched.
import React from "react";
import { Link } from "react-router-dom";
import { Compass, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CREATOR_SUGGESTED as IDS } from "@/constants/testIds";
import { formatInr, isBarter } from "@/lib/compensation";
import { categoryLabel } from "@/lib/categories";
import { Pill } from "@/components/app/ui";
import BrandAvatar from "@/components/BrandAvatar";
import CampaignCover from "@/components/CampaignCover";
import { EmptyState, SectionHead } from "./shared";

export default function Suggested({ campaigns }) {
    const rows = campaigns || [];

    return (
        <>
            <SectionHead
                kicker="Might suit you"
                title="Briefs that match your work."
                aside={
                    rows.length > 0 && (
                        <span data-testid={IDS.count} className="text-meta text-muted-foreground">
                            {rows.length} {rows.length === 1 ? "match" : "matches"}
                        </span>
                    )
                }
            />

            <div className="mt-4">
                {rows.length === 0 ? (
                    <EmptyState
                        testid={IDS.empty}
                        Icon={Compass}
                        title="Nothing matched today."
                        action={
                            <Link to="/campaigns" className="mt-2">
                                <Button variant="solid" className="h-11">
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
                            <li
                                key={c.id}
                                data-testid={IDS.tile(c.id)}
                                className="flex min-w-0 flex-col overflow-hidden rounded-lg bg-card shadow-card"
                            >
                                {/* A strip of the cover, not a poster: 84px
                                    from `md`, so three tiles read as a row of
                                    briefs rather than a gallery. */}
                                <CampaignCover
                                    campaign={c}
                                    ratio="aspect-[16/5]"
                                    rounded="rounded-none"
                                    className="border-0 md:max-h-[5.25rem]"
                                />
                                <div className="flex flex-1 flex-col p-4 md:px-[18px]">
                                    <Link
                                        to={`/campaigns/${c.id}`}
                                        className="text-body font-extrabold leading-snug text-heading transition-colors duration-200 hover:text-primary"
                                    >
                                        {c.title}
                                    </Link>
                                    <p className="mt-1 flex min-w-0 items-center gap-1.5 text-meta font-semibold text-muted-foreground">
                                        <BrandAvatar brand={c} size="h-5 w-5" />
                                        <span className="truncate">
                                            {c.brand_name || "Brand"}
                                            {c.area ? ` · ${c.area}` : ""}
                                        </span>
                                    </p>

                                    {/* Why it surfaced, from the server — the
                                        only place that knows what matched. */}
                                    {c.match_reason && (
                                        <p
                                            data-testid={IDS.reason(c.id)}
                                            className="mt-2.5 flex items-start gap-1.5 text-meta leading-snug text-muted-foreground"
                                        >
                                            <Sparkles aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 flex-none text-accent-ink" />
                                            {c.match_reason}
                                        </p>
                                    )}

                                    {/* mt-auto so every tile's fee lines up
                                        across the row however long the reason
                                        runs. */}
                                    <div className="mt-auto flex items-center justify-between gap-3 pt-4">
                                        <div className="flex min-w-0 items-center gap-2">
                                            {c.category && (
                                                <Pill tone="neutral">{categoryLabel(c.category)}</Pill>
                                            )}
                                            {/* A barter brief has no rupee
                                                figure to print. */}
                                            <span
                                                data-testid={IDS.budget(c.id)}
                                                className="app-figure truncate text-body-lg text-heading"
                                            >
                                                {isBarter(c) ? "Barter" : formatInr(c.budget_per_creator)}
                                            </span>
                                        </div>
                                        {/* Applying needs a pitch and a rate,
                                            and that form lives on the brief. */}
                                        <Link to={`/campaigns/${c.id}`} data-testid={IDS.apply(c.id)}>
                                            <Button variant="quiet" size="sm">
                                                Apply
                                            </Button>
                                        </Link>
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </>
    );
}
