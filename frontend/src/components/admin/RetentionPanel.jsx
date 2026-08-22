// What we keep, for how long, and what is still with a lawyer.
//
// **Served rather than only documented.** The privacy page and the code have
// to agree about this, and the only way to be sure of that is for one of them
// to come from the other — so this screen and `Legal.jsx` both quote
// `RETENTION_DAYS` rather than each stating a number somebody typed.
//
// The honest half is on screen too. Some of these periods are a considered
// reading of the statutory minimums and some are genuinely unsettled, and an
// operator answering "how long do you keep my PAN" needs to know which kind of
// answer they are giving.
import React, { useCallback, useEffect, useState } from "react";
import { Archive, Loader2, Scale, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { RETENTION as IDS } from "@/constants/testIds";
import { PANEL, TEXT } from "./console/tokens";

/**
 * The keys the server sends, in words. The server sends machine names and a
 * number of days; turning `brand_documents_after_decision` into a sentence is
 * presentation, and putting the sentence in the API would make the policy
 * harder to compare with the code that enforces it.
 */
const LABELS = {
    brand_documents_after_decision: {
        label: "Business documents",
        blurb:
            "GST certificates, registration papers, licences — after we have decided on the verification they were uploaded for.",
    },
    drafts_after_close: {
        label: "Unpublished drafts",
        blurb: "A creator's cut, from the moment the campaign closes.",
    },
    personal_data_after_erasure: {
        label: "Personal data after an erasure",
        blurb:
            "Nothing is held. Name, number, address, pin, PAN and bank details go on the request being carried out.",
    },
    payment_records: {
        label: "Payment records",
        blurb:
            "Amounts, dates, references and withholding — the arithmetic, with nobody in it once the person is erased.",
    },
    audit_records: {
        label: "Audit log",
        blurb: "Who did what and when, against the record it happened to.",
    },
};

/** Days, said the way somebody thinks about them. */
const inWords = (days) => {
    if (days === 0) return "Not kept";
    if (days % 365 === 0) {
        const years = days / 365;
        return `${years} ${years === 1 ? "year" : "years"}`;
    }
    if (days % 30 === 0) return `${days / 30} months`;
    return `${days} days`;
};

export default function RetentionPanel() {
    const [data, setData] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data: payload } = await api.get("/admin/retention");
            setData(payload);
        } catch (err) {
            notifyError(err, { fallback: "The retention policy couldn't load." });
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const purge = async () => {
        setBusy(true);
        try {
            const { data: report } = await api.post("/admin/jobs/retention");
            notifySuccess(
                report?.purged
                    ? `${report.purged} document${report.purged === 1 ? "" : "s"} removed`
                    : "Nothing was past its date"
            );
        } catch (err) {
            notifyError(err, { fallback: "The purge couldn't run." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.page} className="space-y-4">
            {/* **The heading renders before the data, always.** It used to sit
                inside the loaded branch behind a fixed-height skeleton, so the
                page's own title moved when the policy arrived — measured at
                0.043 CLS, and every pixel of it was this. A page's name is not
                something it has to fetch. */}
            <div className="flex flex-wrap items-center gap-3">
                <Archive className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>What we keep</h1>
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    The same numbers the privacy page quotes, from the same place. If
                    the two ever disagree, this is what actually happens.
                </p>
            </div>

            {!data ? (
                <div className={`${PANEL} h-64 animate-pulse`} />
            ) : (
                <>
                    <ul className="space-y-2">
                        {Object.entries(data.periods || {}).map(([key, days]) => {
                            const meta = LABELS[key] || { label: key, blurb: "" };
                            return (
                                <li
                                    key={key}
                                    data-testid={IDS.row(key)}
                                    className={`${PANEL} flex flex-wrap items-center gap-x-4 gap-y-2 p-4`}
                                >
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm">{meta.label}</p>
                                        <p className={`mt-0.5 ${TEXT.meta} text-muted-foreground`}>
                                            {meta.blurb}
                                        </p>
                                    </div>
                                    <span className="text-sm tabular-nums">
                                        {inWords(days)}
                                    </span>
                                </li>
                            );
                        })}
                    </ul>

                    <div className={`${PANEL} space-y-2 p-4`}>
                        <p
                            className={`${TEXT.meta} uppercase tracking-[0.14em] text-muted-foreground`}
                        >
                            On an erasure
                        </p>
                        <p className="text-sm text-muted-foreground">
                            Gone: {(data.purged_on_erasure || []).join(", ")}.
                        </p>
                        <p className="text-sm text-muted-foreground">
                            {/* Both halves, because "deleted" does not mean
                                everything vanishes, and somebody who finds
                                that out afterwards has met exactly the
                                surprise the right exists to prevent. */}
                            Kept with nobody in it:{" "}
                            {(data.kept_anonymised || []).join(", ")}.
                        </p>
                    </div>

                    {data.needs_legal_review && (
                        <p
                            data-testid={IDS.legal}
                            className="flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/10 p-4 text-sm text-amber-100/90"
                        >
                            <Scale
                                aria-hidden="true"
                                className="mt-0.5 h-4 w-4 flex-none text-amber-300"
                            />
                            {/* **Flagged, never invented.** These are a
                                considered reading of the statutory minimums
                                and not advice. The two genuinely open
                                questions are how long a rejected business's
                                documents may be held, and whether an audit
                                line naming a person is a record we must keep
                                or personal data we must erase. Where they
                                conflict the code keeps the line and erases
                                the name. */}
                            These periods have not been through a lawyer. Two are open
                            questions: how long a rejected business's documents may be
                            held, and whether an audit line naming somebody is a record
                            we must keep or personal data we must erase.
                        </p>
                    )}

                    <Button
                        variant="outline"
                        onClick={purge}
                        disabled={busy}
                        data-testid={IDS.purge}
                        className="min-h-[2.75rem] border-white/20 bg-transparent"
                    >
                        {busy ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <Trash2 className="mr-2 h-4 w-4" />
                        )}
                        Run the purge now
                    </Button>
                </>
            )}
        </div>
    );
}
