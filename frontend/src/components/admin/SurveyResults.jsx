// The anonymous creator survey, read back.
//
// `GET /admin/survey/creator` had existed since the survey did and nothing
// called it: the CSV export was the only way to see a single answer, so
// "what are creators telling us" meant opening a spreadsheet. This is the
// screen — a count per closed question in the wording it was asked, and the
// open answers underneath.
//
// **Admin-only, like the export.** A respondent is not a creator we know and
// is attached to no brand, so a scoped console has nothing to be scoped to.
//
// **The rows stay intact on the server and in the export.** This screen draws
// the aggregates and the open text because that is what a person reads on a
// screen; cross-tabulating within one response — the reason the rows are kept
// whole — is what the CSV is for, and the download is one tap from here.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ClipboardList, Download, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { downloadCsv } from "@/lib/download";
import { notifyError } from "@/lib/feedback";
import { dayKey } from "@/lib/time";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ListEmptyState } from "@/components/data/DenseView";
import { ADMIN_SURVEY as IDS } from "@/constants/testIds";
import { PANEL, TEXT } from "./console/tokens";

// How many open answers to show per question before folding. They are the
// slowest thing on the page to read and the export carries every one.
const OPEN_VISIBLE = 12;

const pct = (n, of) => (of ? Math.round((n / of) * 100) : 0);

function ClosedQuestion({ field, block, question }) {
    const entries = Object.entries(block.counts || {});
    const label = (value) => question?.options?.[value] ?? value;
    return (
        <div data-testid={IDS.question(field)} className={`${PANEL} p-4`}>
            <p className="text-meta font-medium">{question?.text || field}</p>
            <p className={`mt-0.5 ${TEXT.meta} text-muted-foreground`}>
                {block.answered} answered
                {block.multi_select ? " · choose all that apply, so these add up to more" : ""}
            </p>
            {entries.length === 0 ? (
                <p className={`mt-3 ${TEXT.meta} text-muted-foreground`}>Nobody answered this yet.</p>
            ) : (
                <ul className="mt-3 space-y-2">
                    {entries.map(([value, n]) => (
                        <li key={value} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3">
                            <span className="min-w-0 truncate text-meta">{label(value)}</span>
                            <span className="text-meta tabular-nums text-muted-foreground">
                                {n} · {pct(n, block.answered)}%
                            </span>
                            <span className="col-span-2 h-1.5 overflow-hidden rounded-full bg-muted">
                                <span
                                    className="block h-full rounded-full bg-primary"
                                    style={{ width: `${pct(n, block.answered)}%` }}
                                />
                            </span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

function OpenQuestion({ field, question, answers }) {
    const [all, setAll] = useState(false);
    const shown = all ? answers : answers.slice(0, OPEN_VISIBLE);
    return (
        <div data-testid={IDS.open(field)} className={`${PANEL} p-4`}>
            <p className="text-meta font-medium">{question?.text || field}</p>
            <p className={`mt-0.5 ${TEXT.meta} text-muted-foreground`}>{answers.length} answered</p>
            {answers.length > 0 && (
                <ul className="mt-3 divide-y divide-divider">
                    {shown.map((a) => (
                        <li key={a.id} className="whitespace-pre-line py-2.5 text-body leading-relaxed">
                            {a.text}
                            <span className={`ml-2 ${TEXT.meta} text-muted-foreground`}>{a.on}</span>
                        </li>
                    ))}
                </ul>
            )}
            {answers.length > OPEN_VISIBLE && (
                <button
                    type="button"
                    onClick={() => setAll((v) => !v)}
                    className="mt-2 text-meta text-muted-foreground underline underline-offset-4 hover:text-primary-ink"
                >
                    {all ? "Show fewer" : `Show all ${answers.length}`}
                </button>
            )}
        </div>
    );
}

export default function SurveyResults() {
    const [data, setData] = useState(null);
    const [error, setError] = useState(false);
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data: payload } = await api.get("/admin/survey/creator");
            setData(payload);
            setError(false);
        } catch (err) {
            notifyError(err, { fallback: "The survey results couldn't load." });
            setError(true);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const byField = useMemo(
        () => Object.fromEntries((data?.questions || []).map((q) => [q.field, q])),
        [data],
    );
    const openAnswers = useMemo(() => {
        const out = {};
        for (const field of data?.open_text_fields || []) {
            out[field] = (data.responses || [])
                .filter((r) => (r[field] || "").trim())
                .map((r) => ({ id: r.id, text: r[field].trim(), on: r.submitted_on }));
        }
        return out;
    }, [data]);

    const download = async () => {
        setBusy(true);
        try {
            await downloadCsv("/admin/exports/survey", `survey-${dayKey(new Date())}.csv`);
        } catch (e) {
            notifyError(e);
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.page} className="space-y-section">
            <div className="flex flex-wrap items-center gap-3">
                <ClipboardList className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>Creator survey</h1>
                <p className={`${TEXT.meta} text-muted-foreground`} data-testid={IDS.total}>
                    {data ? `${data.total} responses` : "Anonymous responses"}
                </p>
                <Button
                    size="sm"
                    variant="outline"
                    onClick={download}
                    disabled={busy}
                    data-testid={IDS.export}
                    className="ml-auto"
                >
                    {busy ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                        <Download className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    Download every response
                </Button>
            </div>

            {error && !data && (
                <ListEmptyState
                    Icon={ClipboardList}
                    testid={IDS.error}
                    emptyTitle="The survey results couldn't load"
                    emptyBody="Reload to try again."
                />
            )}

            {!data && !error && (
                <div aria-hidden="true" className="grid gap-4 md:grid-cols-2">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-48 rounded-md" />
                    ))}
                </div>
            )}

            {data && data.total === 0 && (
                <ListEmptyState
                    Icon={ClipboardList}
                    testid={IDS.empty}
                    emptyTitle="No responses yet"
                    emptyBody="Answers appear here as they arrive. Nothing about who sent them is stored."
                />
            )}

            {data && data.total > 0 && (
                <>
                    <div className="grid gap-4 md:grid-cols-2">
                        {Object.entries(data.aggregates || {}).map(([field, block]) => (
                            <ClosedQuestion
                                key={field}
                                field={field}
                                block={block}
                                question={byField[field]}
                            />
                        ))}
                    </div>

                    <div className="space-y-4">
                        <h2 className={`${TEXT.body} font-medium`}>In their words</h2>
                        {/* Said where the text is read: these are the one part
                            of a response that may carry a name somebody typed. */}
                        <p
                            data-testid={IDS.warning}
                            className={`${TEXT.meta} text-muted-foreground`}
                        >
                            {data.open_text_warning}
                        </p>
                        {(data.open_text_fields || []).map((field) => (
                            <OpenQuestion
                                key={field}
                                field={field}
                                question={byField[field]}
                                answers={openAnswers[field] || []}
                            />
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
