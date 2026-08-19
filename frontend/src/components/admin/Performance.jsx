// Performance, as the console shows it.
//
// Two things live here: the rollup that goes on the campaign and brand pages,
// and the per-collaboration panel where a reading gets recorded.
//
// The rule running through both: **an unknown number is drawn as an em dash,
// never as a zero.** A post whose reach we could not read and a post that
// reached nobody are different, and a screen that renders them identically
// teaches its reader to distrust every figure on it.
import React, { useEffect, useState } from "react";
import { BarChart3, Download, Loader2, Printer, RefreshCw, Star } from "lucide-react";

import { api, API_BASE } from "@/lib/api";
import { notifyError, notifyInfo, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { PERFORMANCE as IDS } from "@/constants/testIds";
import { Panel, Section, Stat } from "@/components/admin/DetailPage";
import { formatCompact, formatDateTime, formatRupees } from "@/components/admin/shared";

/** Unknown is a dash. Zero is zero. */
const num = (v) => (typeof v === "number" ? formatCompact(v) : "—");
const pct = (v) => (typeof v === "number" ? `${v}%` : "—");
const rupees = (v) => (typeof v === "number" ? `₹${formatRupees(v)}` : "—");

const METRICS = [
    { key: "reach", label: "Reach", hint: "Unique accounts that saw it" },
    { key: "impressions", label: "Impressions", hint: "Total times it was shown" },
    { key: "views", label: "Views", hint: "Video plays" },
    { key: "likes", label: "Likes" },
    { key: "comments", label: "Comments" },
    { key: "saves", label: "Saves" },
];

/**
 * The campaign or brand rollup.
 *
 * `scope` only changes the copy — the arithmetic is identical, and it is done
 * on the server so the console and the client report cannot disagree.
 */
export function PerformanceRollup({ performance: p, scope = "campaign", action }) {
    if (!p) return null;
    const nothing = p.creators_delivered === 0;

    return (
        <Section id="performance" title="Performance" action={action}>
            {nothing ? (
                <p
                    data-testid={IDS.empty}
                    className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm leading-relaxed text-muted-foreground"
                >
                    Nothing measured yet. Once a creator submits content, record what the
                    post did — from Instagram where they've connected it, or by hand from
                    whatever they can see.
                </p>
            ) : (
                <div data-testid={IDS.rollup}>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                        <Stat testid={IDS.stat("reach")} label="Total reach" value={num(p.total_reach)} highlight />
                        <Stat testid={IDS.stat("engagements")} label="Engagements" value={num(p.total_engagements)} />
                        <Stat testid={IDS.stat("rate")} label="Engagement rate" value={pct(p.engagement_rate)} />
                        <Stat testid={IDS.stat("delivered")} label="Creators delivered" value={p.creators_delivered} />
                        <Stat testid={IDS.stat("spend")} label="Spend" value={rupees(p.total_spend)} />
                        <Stat
                            testid={IDS.stat("cpm")}
                            label="Cost / 1,000 reach"
                            value={rupees(p.cost_per_thousand_reach)}
                        />
                    </div>

                    {/* The caveats, on screen rather than only in the export.
                        Every one of these is a reason a number above is not
                        the whole story, and an admin about to quote it to a
                        client should see them at the same moment. */}
                    <div data-testid={IDS.note} className="mt-4 space-y-1.5">
                        {p.barter_reach > 0 && (
                            <p className="text-sm leading-relaxed text-muted-foreground">
                                {p.barter_deliveries} barter{" "}
                                {p.barter_deliveries === 1 ? "delivery" : "deliveries"}{" "}
                                contributed {num(p.barter_reach)} reach at no cost. Cost per
                                1,000 is over the {num(p.paid_reach)} paid reach only.
                            </p>
                        )}
                        {p.awaiting_payment_deliveries > 0 && (
                            <p className="text-sm leading-relaxed text-muted-foreground">
                                {p.awaiting_payment_deliveries}{" "}
                                {p.awaiting_payment_deliveries === 1 ? "delivery is" : "deliveries are"}{" "}
                                waiting on payment, so {p.awaiting_payment_deliveries === 1 ? "its" : "their"}{" "}
                                reach isn't in the cost figure yet.
                            </p>
                        )}
                        {p.creators_delivered > p.with_reach && (
                            <p className="text-sm leading-relaxed text-muted-foreground">
                                {p.with_reach} of {p.creators_delivered} deliveries have reach
                                figures — {scope === "brand" ? "these totals are" : "the totals above are"} a
                                floor, not a final number.
                            </p>
                        )}
                    </div>
                </div>
            )}
        </Section>
    );
}

/**
 * One collaboration's reading, with both ways of getting it.
 *
 * The Instagram button is offered first because it is faster when it works,
 * and the manual form sits beside it rather than behind a failure — the
 * automatic path not working is the ordinary case, not an error state.
 */
export function PerformancePanel({ collaborationId, performance, delivered, onSaved }) {
    const [open, setOpen] = useState(false);
    const [fetching, setFetching] = useState(false);

    const tryInstagram = async () => {
        setFetching(true);
        try {
            const { data } = await api.post(
                `/admin/collaborations/${collaborationId}/performance/fetch`,
            );
            if (data.fetched) {
                notifySuccess("Pulled from Instagram");
                onSaved?.(data.performance);
            } else {
                // Not a failure toast: this is the expected answer for anyone
                // who hasn't connected Instagram, and the reason says what to
                // do instead.
                notifyInfo(data.reason);
            }
        } catch (err) {
            notifyError(err);
        } finally {
            setFetching(false);
        }
    };

    if (!delivered) {
        return (
            <Panel data-testid={IDS.panel}>
                <p className="text-sm leading-relaxed text-muted-foreground">
                    Nothing to measure yet — performance is recorded once content has been
                    submitted.
                </p>
            </Panel>
        );
    }

    return (
        <>
            <Panel data-testid={IDS.panel}>
                {performance ? (
                    <>
                        <dl className="grid gap-5 sm:grid-cols-3 lg:grid-cols-6">
                            {METRICS.map((m) => (
                                <div key={m.key}>
                                    <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                        {m.label}
                                    </dt>
                                    <dd className="mt-1.5 font-serif text-xl">
                                        {num(performance[m.key])}
                                    </dd>
                                </div>
                            ))}
                        </dl>
                        <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/10 pt-5 text-sm text-muted-foreground">
                            <span className="text-sm text-foreground">
                                {pct(performance.engagement_rate)} engagement
                            </span>
                            <span data-testid={IDS.source}>
                                {performance.source === "instagram"
                                    ? "Measured via Instagram"
                                    : `Entered by ${performance.captured_by_name || "someone"}`}
                            </span>
                            <span>{formatDateTime(performance.captured_at)}</span>
                        </div>
                    </>
                ) : (
                    <p className="text-sm leading-relaxed text-muted-foreground">
                        No reading yet. Pull it from Instagram if they've connected their
                        account, or type in what they can see.
                    </p>
                )}

                <div className="mt-6 flex flex-wrap gap-2">
                    <Button
                        variant="outline"
                        onClick={tryInstagram}
                        disabled={fetching}
                        data-testid={IDS.fetch}
                        className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                    >
                        {fetching ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <RefreshCw className="mr-2 h-4 w-4" />
                        )}
                        Pull from Instagram
                    </Button>
                    <Button
                        variant="outline"
                        onClick={() => setOpen(true)}
                        data-testid={IDS.edit}
                        className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                    >
                        <BarChart3 className="mr-2 h-4 w-4" />
                        {performance ? "Correct by hand" : "Enter by hand"}
                    </Button>
                </div>
            </Panel>

            <PerformanceDialog
                open={open}
                onOpenChange={setOpen}
                collaborationId={collaborationId}
                performance={performance}
                onSaved={(p) => {
                    setOpen(false);
                    onSaved?.(p);
                }}
            />
        </>
    );
}

function PerformanceDialog({ open, onOpenChange, collaborationId, performance, onSaved }) {
    const [values, setValues] = useState({});
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState("");

    useEffect(() => {
        if (!open) return;
        // Seeded from whatever is on record, so correcting one number does not
        // mean retyping the other five.
        setValues(
            Object.fromEntries(
                METRICS.map((m) => [
                    m.key,
                    performance?.[m.key] != null ? String(performance[m.key]) : "",
                ]),
            ),
        );
        setErr("");
    }, [open, performance]);

    const submit = async (e) => {
        e.preventDefault();
        const body = {};
        for (const m of METRICS) {
            const raw = (values[m.key] ?? "").trim();
            // Blank means "don't record this", not zero. Only a typed 0 is a
            // zero.
            if (raw === "") continue;
            const n = Number(raw);
            if (!Number.isFinite(n) || n < 0) {
                setErr(`${m.label} has to be a number, or left blank.`);
                return;
            }
            body[m.key] = Math.round(n);
        }
        if (Object.keys(body).length === 0) {
            setErr("Give at least one number — an empty reading isn't a reading.");
            return;
        }
        setBusy(true);
        try {
            const { data } = await api.post(
                `/admin/collaborations/${collaborationId}/performance`,
                body,
            );
            notifySuccess("Performance recorded");
            onSaved?.(data);
        } catch (error) {
            notifyError(error);
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={IDS.dialog}
                className="max-w-lg rounded-md border border-white/10 bg-card"
            >
                <DialogHeader className="text-left">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Performance
                    </p>
                    <DialogTitle className="mt-3 font-serif text-2xl leading-tight">
                        What did the post do?
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        Fill in whatever you can see. Leave anything you can't blank —
                        blank means "not known", which is different from zero and is
                        reported differently.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} noValidate className="mt-4 space-y-5">
                    <div className="grid gap-4 sm:grid-cols-3">
                        {METRICS.map((m) => (
                            <div key={m.key}>
                                <Label
                                    htmlFor={`perf-${m.key}`}
                                    className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                >
                                    {m.label}
                                </Label>
                                <Input
                                    id={`perf-${m.key}`}
                                    data-testid={IDS.input(m.key)}
                                    type="number"
                                    inputMode="numeric"
                                    min="0"
                                    value={values[m.key] ?? ""}
                                    onChange={(e) =>
                                        setValues((v) => ({ ...v, [m.key]: e.target.value }))
                                    }
                                    placeholder="—"
                                    className="mt-2 h-11 rounded-md border-white/10 bg-background/60 focus-visible:ring-ember-500"
                                />
                            </div>
                        ))}
                    </div>

                    <p className="text-sm leading-relaxed text-muted-foreground">
                        Engagement rate is worked out from likes, comments and saves
                        against reach — you don't enter it, so it can never disagree with
                        the numbers above it.
                    </p>

                    {err && <p className="text-sm text-destructive">{err}</p>}

                    <DialogFooter className="gap-2">
                        <DialogClose asChild>
                            <Button
                                type="button"
                                variant="outline"
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button
                            type="submit"
                            disabled={busy}
                            data-testid={IDS.submit}
                            className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {busy ? "Saving…" : "Save"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

/** The two exports and the showcase toggle, for the campaign page header. */
export function ReportActions({ campaignId, showcase, onToggleShowcase, busy }) {
    // Plain anchors: these are server-rendered documents, so the browser should
    // fetch them itself rather than axios pulling bytes into memory for us to
    // hand straight back to it.
    const href = (format) => `${API_BASE}/admin/campaigns/${campaignId}/report?format=${format}`;
    return (
        <div className="flex flex-wrap items-center gap-2">
            <a href={href("csv")} data-testid={IDS.reportCsv}>
                <Button
                    variant="outline"
                    className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                >
                    <Download className="mr-2 h-4 w-4" />
                    CSV
                </Button>
            </a>
            <a
                href={href("html")}
                target="_blank"
                rel="noreferrer noopener"
                data-testid={IDS.reportPrint}
            >
                <Button
                    variant="outline"
                    className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                >
                    <Printer className="mr-2 h-4 w-4" />
                    Printable report
                </Button>
            </a>
            <Button
                variant="outline"
                onClick={onToggleShowcase}
                disabled={busy}
                data-testid={IDS.showcase}
                className={
                    "rounded-full bg-transparent " +
                    (showcase
                        ? "border-ember-500/50 text-ember-500 hover:bg-ember-500/10"
                        : "border-white/15 hover:bg-white/5")
                }
            >
                <Star className={"mr-2 h-4 w-4 " + (showcase ? "fill-current" : "")} />
                {showcase ? "Showcase" : "Mark showcase"}
            </Button>
        </div>
    );
}
