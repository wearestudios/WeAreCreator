// Work that is done.
//
// `collaborations.completed` was on the dashboard payload from the start and
// no screen drew it, so a creator's finished work — the record they would
// point a brand at — existed only as a count in the header. Barter is here
// too, closed at approval with no payment rung, and it reads as finished
// rather than as "Paid", which on a brief that paid a dinner is false.
//
// **The takedown panel rides on every row**, because a request to pull a post
// lands on a closed collaboration as often as on a running one — `closed` is
// in `DELIVERED_COLLAB_STATES` — and this list is where finished work lives.
import React from "react";
import { Link } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";

import BrandAvatar from "@/components/BrandAvatar";
import Shortfall from "@/components/Shortfall";
import TakedownPanel from "@/components/TakedownPanel";
import { formatCollabMoney } from "@/lib/compensation";
import { CREATOR_FINISHED as IDS, SHORTFALL } from "@/constants/testIds";
import { EmptyState, SectionHead, StatePill, formatDate } from "./shared";

export default function Finished({ rows, onChanged }) {
    const list = rows || [];
    return (
        <section data-testid={IDS.section}>
            <SectionHead kicker="Done" title="Finished work" />
            {list.length === 0 ? (
                <EmptyState Icon={CheckCircle2} title="Nothing finished yet" testid={IDS.empty}>
                    Campaigns land here once the work is approved.
                </EmptyState>
            ) : (
                <ul className="mt-5 divide-y divide-divider overflow-hidden rounded-md border border-border bg-card grain-surface">
                    {list.map((row) => {
                        const money = formatCollabMoney({
                            compensationType: row.compensation_type,
                            agreed: row.agreed_amount,
                            quoted: row.quoted_rate,
                            barterTerms: row.barter_terms,
                        });
                        const state =
                            row.state === "closed" && money.isBarter ? "closed_barter" : row.state;
                        return (
                            <li
                                key={row.id}
                                data-testid={IDS.row(row.id)}
                                className="flex flex-col gap-3 px-5 py-5 sm:flex-row sm:items-start sm:gap-6 sm:px-6"
                            >
                                <Link to={`/campaigns/${row.campaign_id}`} className="group min-w-0 flex-1">
                                    <span className="flex items-center gap-2 text-eyebrow uppercase tracking-eyebrow text-muted-foreground">
                                        <BrandAvatar brand={row} size="h-5 w-5" />
                                        <span className="truncate">{row.brand_name || "Brand"}</span>
                                    </span>
                                    <span className="mt-1 block truncate font-serif text-body-lg leading-tight transition-colors duration-200 group-hover:text-primary">
                                        {row.campaign_title || "Untitled campaign"}
                                    </span>
                                    <span className="mt-2 block text-meta text-muted-foreground">
                                        {money.text}
                                        {row.created_at ? ` · pitched ${formatDate(row.created_at)}` : ""}
                                    </span>
                                </Link>
                                <div className="flex flex-col items-start gap-2 sm:items-end">
                                    <StatePill state={state} testid={IDS.state(row.id)} />
                                    <Shortfall
                                        shortfall={row.shortfall}
                                        note={row.partial_note}
                                        testid={SHORTFALL.block(row.id)}
                                    />
                                    <TakedownPanel
                                        collaborationId={row.id}
                                        takedown={row.takedown}
                                        canRespond={Boolean(row.can_respond_takedown)}
                                        onChanged={onChanged}
                                    />
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
        </section>
    );
}
