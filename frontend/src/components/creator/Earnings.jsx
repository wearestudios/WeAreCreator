// Money, by campaign.
//
// Paid and pending in one list rather than two, because the question a creator
// arrives with is "what happened to the Blue Tokai one?" — a question that has
// to be answerable without first knowing which of two tables to look in. Both
// figures are the payout, net of our fee, which is what actually lands.
import React from "react";
import { Wallet } from "lucide-react";
import { CREATOR_EARNINGS as IDS } from "@/constants/testIds";
import {
    EmptyState,
    Money,
    SectionHead,
    StatePill,
    formatDate,
    formatRupees,
} from "./shared";

export default function Earnings({ payments, inPaymentCollabs, earnings }) {
    const rows = [
        ...(payments || []).map((p) => ({
            id: p.id,
            campaign_title: p.campaign_title,
            brand_name: p.brand_name,
            amount: p.creator_payout ?? p.agreed_amount,
            state: p.state,
            paid_at: p.paid_at,
        })),
        // A collaboration in payment before its row exists still has money
        // attached to it, and leaving it out reads as the money vanishing.
        ...(inPaymentCollabs || []).map((c) => ({
            id: c.id,
            campaign_title: c.campaign_title,
            brand_name: c.brand_name,
            amount: c.agreed_amount ?? c.quoted_rate,
            state: "in_payment",
            paid_at: null,
        })),
    ];

    return (
        <>
            <SectionHead
                kicker="Earnings"
                title="Where your money is."
                aside={
                    rows.length > 0 && (
                        <div className="flex gap-6 text-right">
                            <div>
                                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                    Paid
                                </p>
                                <Money
                                    symbolClass="h-3.5 w-3.5"
                                    className="mt-1 font-serif text-xl leading-none"
                                >
                                    <span data-testid={IDS.paidTotal}>
                                        {formatRupees(earnings?.lifetime_earned ?? 0)}
                                    </span>
                                </Money>
                            </div>
                            <div>
                                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                    Pending
                                </p>
                                <Money
                                    symbolClass="h-3.5 w-3.5"
                                    className="mt-1 font-serif text-xl leading-none"
                                >
                                    <span data-testid={IDS.pendingTotal}>
                                        {formatRupees(earnings?.pending_earnings ?? 0)}
                                    </span>
                                </Money>
                            </div>
                        </div>
                    )
                }
            />

            <div className="mt-8">
                {rows.length === 0 ? (
                    <EmptyState testid={IDS.empty} Icon={Wallet} title="No payouts yet.">
                        Once a brand approves your content, the payment shows up here
                        with the date it went out.
                    </EmptyState>
                ) : (
                    <ul
                        data-testid={IDS.list}
                        className="divide-y divide-white/10 overflow-hidden rounded-md border border-white/10 bg-card grain-surface"
                    >
                        {rows.map((p) => (
                            <li
                                key={p.id}
                                data-testid={IDS.row(p.id)}
                                className="flex flex-col gap-3 px-5 py-5 sm:flex-row sm:items-center sm:gap-6 sm:px-6"
                            >
                                <div className="min-w-0 flex-1">
                                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        {p.brand_name || "Brand"}
                                    </p>
                                    <p className="mt-1 truncate font-serif text-lg leading-tight">
                                        {p.campaign_title || "—"}
                                    </p>
                                    {p.paid_at && (
                                        <p className="mt-1 text-xs text-muted-foreground">
                                            Paid {formatDate(p.paid_at)}
                                        </p>
                                    )}
                                </div>
                                <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end">
                                    <Money
                                        symbolClass="h-3.5 w-3.5"
                                        className="font-serif text-xl leading-none"
                                    >
                                        <span data-testid={IDS.rowAmount(p.id)}>
                                            {formatRupees(p.amount)}
                                        </span>
                                    </Money>
                                    <StatePill state={p.state} testid={IDS.rowState(p.id)} />
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </>
    );
}
