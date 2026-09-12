// What a brief has left to spend.
//
// One component on four surfaces — the brand's applicant board, the admin
// campaign page, the manager's campaign page and the shared application
// screen — because the whole point of a cap is that the brand, our team and
// the admin agree about what is left. Two meters would be two numbers.
//
// **It computes nothing.** Total, committed, remaining, the ratio and the two
// flags all arrive from `_campaign_budget`; a browser working out for itself
// whether 80% had been reached would be a second definition of "nearly
// spent", which is the mistake `isStale` made in the console and the reason
// there is a test banning threshold constants under `components/`.
//
// It renders **nothing** when there is no cap. A brief without one is the
// ordinary case — campaigns predate the field and plenty of brands will never
// set one — and an empty box headed "Budget" reads as a fact about the brief
// rather than a question nobody answered, the rule `ShootWindowNote` already
// holds.
import React from "react";
import { AlertTriangle, Wallet } from "lucide-react";

import { BUDGET as IDS } from "@/constants/testIds";
import { budgetPercent, budgetTone, formatMoney } from "@/lib/budget";

// Ember is the primary action on this platform and is deliberately not a
// status, so a healthy bar is neutral and only the two states somebody has to
// act on take a colour — the same rule `STATUS_TONE` holds in the console.
const BAR = {
    calm: "bg-foreground/40",
    warning: "bg-amber-400/80",
    exhausted: "bg-rose-400/80",
};

const NOTE = {
    warning: "text-amber-300/90",
    exhausted: "text-rose-300/90",
};

function Figure({ label, value, testId, emphasis }) {
    return (
        <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {label}
            </p>
            <p
                data-testid={testId}
                className={`mt-0.5 tabular-nums ${
                    emphasis ? "text-base font-medium text-foreground" : "text-sm text-foreground/80"
                }`}
            >
                {formatMoney(value)}
            </p>
        </div>
    );
}

export default function BudgetMeter({ budget, className = "", compact = false }) {
    if (!budget) return null;

    const tone = budgetTone(budget);
    const percent = budgetPercent(budget);

    return (
        <div
            data-testid={IDS.meter}
            className={`rounded-lg border border-white/10 bg-card p-4 ${className}`}
        >
            <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                <Wallet aria-hidden="true" className="h-3 w-3" />
                Campaign budget
            </p>

            <div className="mt-3 grid grid-cols-3 gap-3">
                <Figure label="Total" value={budget.total} testId={IDS.total} />
                <Figure label="Committed" value={budget.committed} testId={IDS.committed} />
                <Figure
                    label="Remaining"
                    value={budget.remaining}
                    testId={IDS.remaining}
                    emphasis
                />
            </div>

            {/* The ratio, drawn. A percentage on its own is a number somebody
                has to do arithmetic with; a bar is the one thing that says
                "nearly gone" without being read. */}
            <div
                className="mt-3 h-1.5 w-full overflow-hidden rounded-lg bg-white/10"
                role="progressbar"
                aria-valuenow={percent}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${percent}% of the campaign budget committed`}
            >
                <div
                    data-testid={IDS.bar}
                    data-tone={tone}
                    className={`h-full transition-[width] duration-300 ${BAR[tone]}`}
                    style={{ width: `${percent}%` }}
                />
            </div>

            {!compact && tone !== "calm" && (
                <p
                    data-testid={tone === "exhausted" ? IDS.exhausted : IDS.warning}
                    className={`mt-2 flex items-start gap-1.5 text-xs ${NOTE[tone]}`}
                >
                    <AlertTriangle aria-hidden="true" className="mt-0.5 h-3 w-3 shrink-0" />
                    <span>
                        {tone === "exhausted"
                            ? "This brief has committed its whole budget. Raise the total or take one fewer creator before agreeing another fee."
                            : `${percent}% of the budget is committed across ${
                                  budget.collaborations_counted
                              } creator${budget.collaborations_counted === 1 ? "" : "s"}.`}
                    </span>
                </p>
            )}

            {/* Barter never draws down, so a brief with both a cap and barter
                collaborations on it would otherwise read as underspent. Said
                rather than hidden: the figure is right, the reason it looks
                low is what needs explaining. */}
            <p className="mt-2 text-[11px] text-muted-foreground">
                Committed counts agreed fees on creators taken on and still
                going. A creator who cancels or withdraws releases theirs.
            </p>
        </div>
    );
}
