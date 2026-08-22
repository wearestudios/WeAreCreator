// What somebody is like to work with, in one word or in full.
//
// **Two components, because there are two audiences and one of them must not
// see counts.** `ReliabilityBadge` draws the band the server computed — a
// word and a sentence, with the denominator already applied. `ReliabilityPanel`
// draws the record behind it, and only ever renders on a staff screen, because
// the server only ever sends the counts to one.
//
// "2 no-shows" against forty campaigns is a good record read as a bad one, and
// a brand has no denominator to hand. The interpreting happens once, on the
// server, where it is known.
import React from "react";
import { CheckCircle2, CircleDashed, Info, TriangleAlert } from "lucide-react";

/**
 * The four bands, and what each looks like.
 *
 * **`new` is not a low band.** A creator on their first brief has no history,
 * which is the ordinary state of everybody the platform is trying to bring in.
 * Drawing them in amber would tell a brand something we did not mean and have
 * no evidence for, so it is the same neutral grey as any other unknown here.
 */
const BANDS = {
    strong: {
        Icon: CheckCircle2,
        wrap: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    },
    steady: {
        Icon: CheckCircle2,
        wrap: "border-white/15 text-foreground/80",
    },
    mixed: {
        Icon: TriangleAlert,
        wrap: "border-amber-400/30 bg-amber-400/10 text-amber-200",
    },
    new: {
        Icon: CircleDashed,
        wrap: "border-white/10 text-muted-foreground",
    },
};

export function ReliabilityBadge({ reliability, className = "", testid }) {
    if (!reliability?.band) return null;
    const band = BANDS[reliability.band] || BANDS.new;
    const { Icon } = band;
    return (
        <span
            data-testid={testid}
            data-band={reliability.band}
            title={reliability.blurb}
            className={
                "inline-flex max-w-full items-center gap-1.5 rounded border px-1.5 py-0.5 " +
                `text-xs leading-tight ${band.wrap} ${className}`
            }
        >
            <Icon aria-hidden="true" className="h-3 w-3 shrink-0" />
            <span className="truncate">{reliability.label}</span>
        </span>
    );
}

/** One figure, drawn as an em dash when we do not have it. */
const Figure = ({ label, value, suffix = "", testid }) => (
    <div>
        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
        <p data-testid={testid} className="mt-1 text-sm tabular-nums">
            {/* **Unknown is an em dash, never a zero.** A creator with no
                finished campaigns has an unknown on-time rate, not a 0% one,
                and the difference is the whole record. */}
            {value == null ? "—" : `${value}${suffix}`}
        </p>
    </div>
);

export function ReliabilityPanel({ stats, testid }) {
    if (!stats) {
        return (
            <p data-testid={testid} className="text-sm text-muted-foreground">
                No collaborations here yet, so there is nothing to say about how they work —
                which is true of everybody at the start.
            </p>
        );
    }

    const rate =
        stats.on_time_rate == null ? null : Math.round(stats.on_time_rate * 100);

    return (
        <div data-testid={testid} className="space-y-4">
            {/* **The sample size, said before the rates.** "100% on time" from
                one campaign and from forty are different claims, and the
                second number is what tells them apart. */}
            {!stats.enough_history && (
                <p className="flex items-start gap-2 rounded border border-white/10 p-3 text-sm text-muted-foreground">
                    <Info aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 flex-none" />
                    Only {stats.completed} finished {stats.completed === 1 ? "campaign" : "campaigns"} so
                    far — the rates below are a start, not a pattern.
                </p>
            )}

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Figure label="Completed" value={stats.completed} />
                <Figure label="On time" value={rate} suffix="%" />
                <Figure label="No-shows" value={stats.no_shows} />
                <Figure label="Late" value={stats.late_deliveries} />
                <Figure label="Cancelled" value={stats.cancellations} />
                <Figure label="Withdrawn" value={stats.withdrawals} />
                <Figure label="Reschedules" value={stats.reschedules} />
                <Figure label="Avg revisions" value={stats.avg_revisions} />
            </div>

            {stats.partial_deliveries > 0 && (
                <p className="text-sm text-muted-foreground">
                    {stats.partial_deliveries} accepted with a shortfall.
                </p>
            )}

            {/* Ratings, which are ours and stay ours. Absent rather than
                zeroed when nobody has rated them: an average of nothing is
                not a low score. */}
            <p className="text-sm text-muted-foreground">
                {stats.rating_avg == null
                    ? "Nobody has rated them yet."
                    : `Rated ${stats.rating_avg} out of 5 across ${stats.rating_count} ${
                          stats.rating_count === 1 ? "campaign" : "campaigns"
                      } — internal only.`}
            </p>
        </div>
    );
}

export default ReliabilityBadge;
