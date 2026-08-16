// Applications: waiting, and not this time.
//
// Two lists rather than one, because they are read in completely different
// moods. The declined list is deliberately quiet — a brand picking somebody
// else is not a verdict on the creator, and a red row implying otherwise is
// the fastest way to lose one. It ends with somewhere to go next.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Hourglass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CREATOR_APPLICATIONS as IDS } from "@/constants/testIds";
import {
    CAT_LABEL,
    EmptyState,
    Money,
    SectionHead,
    StatePill,
    formatDate,
    formatRupees,
} from "./shared";

const Row = ({ row, testid, muted }) => (
    <li
        data-testid={testid}
        className="flex flex-col gap-3 px-5 py-5 sm:flex-row sm:items-center sm:gap-6 sm:px-6"
    >
        <Link
            to={`/campaigns/${row.campaign_id}`}
            className="group min-w-0 flex-1"
        >
            <span className="block text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {row.brand_name || "Brand"}
                {row.area ? ` · ${row.area}` : ""}
                {row.category ? ` · ${CAT_LABEL[row.category] || row.category}` : ""}
            </span>
            <span
                className={
                    "mt-1 block truncate font-serif text-lg leading-tight transition-colors duration-200 group-hover:text-ember-500 " +
                    (muted ? "text-muted-foreground" : "")
                }
            >
                {row.campaign_title || "Untitled campaign"}
            </span>
            <span className="mt-2 block text-xs text-muted-foreground">
                Applied {formatDate(row.created_at)}
            </span>
            {row.exit_reason && (
                <span
                    data-testid={IDS.note(row.id)}
                    className="mt-2 block text-xs leading-relaxed text-muted-foreground"
                >
                    {row.exit_reason}
                </span>
            )}
        </Link>

        <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end">
            <Money symbolClass="h-3.5 w-3.5" className="font-serif text-xl leading-none">
                {formatRupees(row.agreed_amount ?? row.quoted_rate)}
            </Money>
            <StatePill state={row.state} testid={IDS.state(row.id)} />
        </div>
    </li>
);

export default function Applications({ applied, declined }) {
    const waiting = applied || [];
    const notThisTime = declined || [];
    const total = waiting.length + notThisTime.length;

    return (
        <>
            <SectionHead
                kicker="Pitched"
                title="Waiting to hear back."
                aside={
                    total > 0 && (
                        <span data-testid={IDS.count} className="text-xs text-muted-foreground">
                            {total} {total === 1 ? "application" : "applications"}
                        </span>
                    )
                }
            />

            <div className="mt-8 space-y-4">
                {total === 0 ? (
                    <EmptyState
                        testid={IDS.empty}
                        Icon={Hourglass}
                        title="You haven't pitched on anything yet."
                        action={
                            <Link to="/campaigns" data-testid={IDS.browse} className="mt-2">
                                <Button className="h-12 rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                    Browse campaigns
                                </Button>
                            </Link>
                        }
                    >
                        Pick a brief that fits your work, tell the brand why in a line
                        or two, and name your rate.
                    </EmptyState>
                ) : (
                    <>
                        {waiting.length > 0 && (
                            <ul
                                data-testid={IDS.list}
                                className="divide-y divide-white/10 overflow-hidden rounded-md border border-white/10 bg-card grain-surface"
                            >
                                {waiting.map((row) => (
                                    <Row key={row.id} row={row} testid={IDS.row(row.id)} />
                                ))}
                            </ul>
                        )}

                        {notThisTime.length > 0 && (
                            <div className="overflow-hidden rounded-md border border-white/10 bg-card/50">
                                <p className="border-b border-white/10 px-5 py-4 text-xs uppercase tracking-[0.2em] text-muted-foreground sm:px-6">
                                    Went another way
                                </p>
                                <ul data-testid={IDS.declinedList} className="divide-y divide-white/10">
                                    {notThisTime.map((row) => (
                                        <Row
                                            key={row.id}
                                            row={row}
                                            testid={IDS.declinedRow(row.id)}
                                            muted
                                        />
                                    ))}
                                </ul>
                                <div className="border-t border-white/10 px-5 py-5 sm:px-6">
                                    <p className="text-sm leading-relaxed text-muted-foreground">
                                        Briefs get filled for all sorts of reasons —
                                        dates, budget, how many creators they needed.
                                        None of it changes what you make.
                                    </p>
                                    <Link
                                        to="/campaigns"
                                        data-testid={IDS.declinedBrowse}
                                        className="group mt-4 inline-flex items-center gap-2 text-sm text-ember-500 transition-colors duration-200 hover:text-ember-400"
                                    >
                                        See what else is open
                                        <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                    </Link>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </>
    );
}
