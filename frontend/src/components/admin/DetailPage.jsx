// The furniture every admin detail page shares.
//
// Four pages fetch one record by id and draw it. Without this they would each
// solve the same four things — the loading shape, the failure, the 404, and the
// way back — and would each solve them slightly differently, which is how a
// console starts feeling like four consoles.
import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ChevronRight } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import ErrorBoundary from "@/components/ErrorBoundary";
import { ADMIN_DETAIL as IDS, BREADCRUMBS } from "@/constants/testIds";

/**
 * Where you are, and every step back.
 *
 * The back link alone answers "how do I leave" but not "what am I inside" —
 * and a collaboration reached from a campaign reached from a brand is three
 * levels deep with nothing on screen saying so. Every crumb but the last is a
 * link, so any level can be jumped to directly.
 *
 * `crumbs` is [{ key, label, to? }]. The last one is the current page and is
 * never a link, even if it carries a `to`.
 */
export const Breadcrumbs = ({ crumbs }) => (
    <nav data-testid={BREADCRUMBS.nav} aria-label="Breadcrumb">
        <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs uppercase tracking-[0.15em] text-muted-foreground">
            {crumbs.filter(Boolean).map((c, i, all) => {
                const last = i === all.length - 1;
                return (
                    <li key={c.key} className="inline-flex min-w-0 items-center gap-1.5">
                        {i > 0 && (
                            <ChevronRight
                                aria-hidden="true"
                                className="h-3 w-3 flex-none opacity-50"
                            />
                        )}
                        {last || !c.to ? (
                            <span
                                data-testid={BREADCRUMBS.crumb(c.key)}
                                aria-current={last ? "page" : undefined}
                                className={
                                    "max-w-[14rem] truncate " + (last ? "text-foreground" : "")
                                }
                            >
                                {c.label}
                            </span>
                        ) : (
                            <Link
                                to={c.to}
                                data-testid={BREADCRUMBS.crumb(c.key)}
                                className="max-w-[14rem] truncate transition-colors duration-200 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                            >
                                {c.label}
                            </Link>
                        )}
                    </li>
                );
            })}
        </ol>
    </nav>
);

/**
 * A titled block. The console is read by scanning for the section you want, so
 * every one of them carries the same eyebrow at the same size, and the count
 * sits in the header rather than being something you work out by counting rows.
 */
export const Section = ({ id, title, count, action, children, className = "" }) => (
    <section data-testid={IDS.section(id)} className={"min-w-0 " + className}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            <h2 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {title}
                {typeof count === "number" && (
                    <span className="ml-2 text-ember-500">{count}</span>
                )}
            </h2>
            {action}
        </div>
        {/* Every panel on every detail page is boxed off here rather than at
          * the twenty-odd call sites. A detail page is several independent
          * endpoints stacked up — applicants, notes, performance, the audit
          * trail — and one of them returning a row nobody expected should cost
          * that panel, not the page. Doing it in the shared primitive is also
          * the only version that stays true: a panel added next month is
          * covered by using Section at all.
          *
          * The heading stays outside, so a broken panel still says which one. */}
        <ErrorBoundary variant="section" name={`detail-${id}`} label={`${title} couldn't load`}>
            <div className="mt-4">{children}</div>
        </ErrorBoundary>
    </section>
);

/** A label over a value. The unit of a detail page. */
export const Field = ({ label, children, testid, className = "" }) => (
    <div className={"min-w-0 " + className}>
        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {label}
        </dt>
        <dd data-testid={testid} className="mt-1.5 break-words text-sm">
            {children ?? "—"}
        </dd>
    </div>
);

/** A number worth its own box. */
export const Stat = ({ label, value, testid, highlight }) => (
    <div
        data-testid={testid}
        className={
            "rounded-md border p-5 " +
            (highlight
                ? "border-ember-500/40 bg-ember-500/10"
                : "border-white/10 bg-card grain-surface")
        }
    >
        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {label}
        </p>
        <p
            className={
                "mt-3 font-serif text-2xl leading-none md:text-3xl " +
                (highlight ? "text-ember-500" : "")
            }
        >
            {value}
        </p>
    </div>
);

/** A bordered surface. Cards on a dark ground are a hairline and a tint, never
 *  a shadow — see the design brief. */
export const Panel = ({ children, className = "", ...rest }) => (
    <div
        {...rest}
        className={
            "rounded-md border border-white/10 bg-card p-6 grain-surface " + className
        }
    >
        {children}
    </div>
);

/**
 * The shell: back link, title, and the three states before the content.
 *
 * `backTo` is a real link rather than history.back() — arriving from a pasted
 * URL has no history to go back to, and a dead button in that case is worse
 * than one that always goes to the list.
 */
export function DetailShell({
    backTo,
    backLabel,
    crumbs,
    kicker,
    title,
    subtitle,
    aside,
    loading,
    error,
    notFound,
    notFoundMessage,
    testid,
    children,
}) {
    return (
        <div data-testid={testid} className="min-w-0">
            {/* Both, and they do different jobs: the crumbs say what you are
                inside, the back link is the one-tap way out on a phone where
                a crumb is a small target. */}
            {crumbs && <Breadcrumbs crumbs={crumbs} />}
            <Link
                to={backTo}
                data-testid={IDS.back}
                className={
                    "inline-flex min-h-[2.75rem] items-center gap-1.5 text-xs uppercase tracking-[0.2em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0 " +
                    (crumbs ? "mt-2" : "")
                }
            >
                <ArrowLeft className="h-3.5 w-3.5" />
                {backLabel}
            </Link>

            {loading ? (
                // Shaped like the header it replaces, so nothing moves when the
                // record arrives.
                <div data-testid={IDS.skeleton} aria-hidden="true" className="mt-6">
                    <Skeleton className="h-3 w-32" />
                    <Skeleton className="mt-4 h-9 w-2/3" />
                    <Skeleton className="mt-4 h-3 w-1/2" />
                    <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <Skeleton key={i} className="h-[104px] rounded-md" />
                        ))}
                    </div>
                    <Skeleton className="mt-10 h-64 rounded-md" />
                </div>
            ) : notFound ? (
                <div
                    data-testid={IDS.notFound}
                    className="mt-10 rounded-md border border-white/10 bg-card px-6 py-12 grain-surface"
                >
                    <p className="font-serif text-2xl">Nothing here.</p>
                    <p className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
                        {notFoundMessage ||
                            "This record doesn't exist, or it was removed. The link may be out of date."}
                    </p>
                    <Link to={backTo} className="mt-6 inline-block">
                        <Button
                            variant="outline"
                            className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                        >
                            {backLabel}
                        </Button>
                    </Link>
                </div>
            ) : error ? (
                <div
                    data-testid={IDS.error}
                    className="mt-10 rounded-md border border-destructive/30 bg-destructive/10 px-6 py-8"
                >
                    <p className="text-sm text-destructive">{error}</p>
                </div>
            ) : (
                <>
                    <div className="mt-6 flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
                        <div className="min-w-0">
                            {kicker && (
                                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                    {kicker}
                                </p>
                            )}
                            <h1
                                data-testid={IDS.title}
                                className="mt-3 font-serif text-fluid-4xl leading-none tracking-tight"
                            >
                                {title}
                            </h1>
                            {subtitle && (
                                <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                                    {subtitle}
                                </div>
                            )}
                        </div>
                        {aside && (
                            <div className="flex flex-wrap items-center gap-2">{aside}</div>
                        )}
                    </div>
                    <div className="mt-10 space-y-12">{children}</div>
                </>
            )}
        </div>
    );
}

/**
 * The audit trail, drawn the same way on all four pages.
 *
 * `before`/`after` are rendered only where they differ — an entry that lists
 * every field of a record, unchanged ones included, is how a log becomes
 * something nobody reads.
 */
export const AuditTrail = ({ rows, emptyMessage, formatWhen }) => {
    if (!rows) return null;
    if (rows.length === 0) {
        return (
            <p
                data-testid={IDS.timelineEmpty}
                className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground grain-surface"
            >
                {emptyMessage || "Nothing has happened to this yet."}
            </p>
        );
    }
    return (
        <ol data-testid={IDS.timeline} className="divide-y divide-white/10 rounded-md border border-white/10 bg-card grain-surface">
            {rows.map((e) => (
                <li
                    key={e.id}
                    data-testid={IDS.auditRow(e.id)}
                    className="flex flex-col gap-1.5 px-5 py-4 md:flex-row md:items-baseline md:gap-6"
                >
                    <span className="w-40 flex-none text-xs text-muted-foreground">
                        {formatWhen(e.created_at)}
                    </span>
                    <span className="min-w-0 flex-1">
                        <span className="text-sm text-foreground">{e.action}</span>
                        {e.note && (
                            <span
                                title={e.note}
                                className="mt-1 block line-clamp-2 text-xs leading-relaxed text-muted-foreground"
                            >
                                {e.note}
                            </span>
                        )}
                    </span>
                    <span className="flex-none text-xs text-muted-foreground">
                        {e.actor_name || "—"}
                        {e.actor_role ? ` · ${e.actor_role}` : ""}
                    </span>
                </li>
            ))}
        </ol>
    );
};
