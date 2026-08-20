// Accounts worth a person's attention.
//
// **A prompt, never an action.** Three no-shows is a strong signal and it is
// not a verdict: it might be somebody who stopped turning up, or one venue
// that marked a whole week absent by mistake, or a creator whose phone broke
// on the day of three shoots in a fortnight. Suspending automatically on a
// count would take a decision about somebody's livelihood away from the person
// who can ring them up and ask.
//
// So this sits above the queue, names the account and the numbers, and links
// to the page where the decision — and the reason it requires — actually gets
// made. It renders nothing when nobody is over the line, because a permanent
// empty box headed "possible suspensions" is a heading that stops being read.
import React from "react";
import { Link } from "react-router-dom";
import { UserX } from "lucide-react";

import { SUSPENSION as IDS } from "@/constants/testIds";
import { TimeAgo } from "./console/format";
import { CALM, PANEL, TEXT } from "./console/tokens";

/**
 * @param {object} [props.data]  `{threshold, prompts}` from
 *   `GET /admin/suspension-prompts`. **Fetched by the queue, not here.** On its
 *   own fetch this band landed a beat after the rows below it and pushed the
 *   whole page down; a band that renders nothing most of the time cannot
 *   reserve height, so arriving in the same commit is the fix.
 */
export default function SuspensionPrompts({ data }) {
    const prompts = data?.prompts || [];
    if (prompts.length === 0) return null;

    return (
        <section
            data-testid={IDS.panel}
            className="mb-4 rounded-md border border-amber-400/30 bg-amber-400/10 p-4"
        >
            <div className="flex flex-wrap items-center gap-2">
                <UserX aria-hidden="true" className="h-4 w-4 text-amber-300" />
                <p className={`${TEXT.meta} uppercase tracking-[0.14em] text-amber-200`}>
                    Worth a look
                </p>
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    {prompts.length}{" "}
                    {prompts.length === 1 ? "creator has" : "creators have"}{" "}
                    {data?.threshold ?? 3} or more no-shows. Nothing has happened
                    automatically — open the page to decide.
                </p>
            </div>

            <ul className="mt-3 space-y-2">
                {prompts.map((p) => (
                    <li
                        key={p.user_id}
                        data-testid={IDS.row(p.user_id)}
                        className={`${PANEL} flex flex-wrap items-center gap-x-4 gap-y-1 p-3`}
                    >
                        <Link
                            to={p.href}
                            data-testid={IDS.suspend(p.user_id)}
                            className={`min-w-0 flex-1 truncate text-sm hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 ${CALM}`}
                        >
                            {p.name}
                            {p.reference ? (
                                <span className={`ml-2 ${TEXT.meta} text-muted-foreground`}>
                                    {p.reference}
                                </span>
                            ) : null}
                        </Link>

                        {/* **The denominator, always.** Three no-shows out of
                            four is a different account from three out of
                            forty, and a row that omits the second number is
                            asking somebody to decide blind. */}
                        <span className={`${TEXT.meta} tabular-nums text-amber-200`}>
                            {p.no_shows} no-show{p.no_shows === 1 ? "" : "s"}
                            {typeof p.completed === "number"
                                ? ` · ${p.completed} completed`
                                : ""}
                        </span>

                        {p.last_no_show_at && (
                            <span className={`${TEXT.meta} text-muted-foreground`}>
                                last <TimeAgo iso={p.last_no_show_at} />
                            </span>
                        )}
                    </li>
                ))}
            </ul>
        </section>
    );
}
