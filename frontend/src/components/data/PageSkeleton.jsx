// Skeletons for whole pages, as opposed to the list and grid skeletons in
// DenseView.jsx.
//
// The distinction is not filing: a list skeleton stands in for *rows*, whose
// count is unknown and whose height is uniform, so approximating them is free.
// A page skeleton stands in for one specific arrangement of headings, prose and
// controls that will land in a known place — so it has to be measured against
// that page, not sketched, or it trades a spinner for a jump.
//
// Every shape here mirrors the real markup's box model: same spacing scale,
// same max-width, same grid split, same control heights. Where a real element's
// height is set by its content (a paragraph that wraps to two lines on a phone
// and one on a laptop) the skeleton reserves the same responsive height rather
// than a single guess, because the shift only shows up at one width otherwise.
//
// `aria-hidden` throughout: a screen reader should hear the page arrive once,
// not hear a description of its scaffolding first. The loading *fact* is
// announced by the live region on the page, not by these boxes.
import React from "react";

import { Skeleton } from "@/components/ui/skeleton";

/**
 * The eyebrow / headline / standfirst stack that opens every page here.
 *
 * `text-fluid-5xl` is a clamp, so the headline's height changes with the
 * viewport — hence the responsive heights rather than one number that is right
 * on a laptop and wrong on a phone.
 */
export function PageHeaderSkeleton({ lines = 1, className = "" }) {
    return (
        <div className={className} aria-hidden="true">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="mt-4 h-9 w-3/4 max-w-md md:h-12" />
            {Array.from({ length: lines }).map((_, i) => (
                <Skeleton
                    key={i}
                    className={
                        "h-3 max-w-xl " + (i === 0 ? "mt-6 w-full" : "mt-2 w-2/3")
                    }
                />
            ))}
        </div>
    );
}

/**
 * One labelled input: the label, then the control.
 *
 * `h-11` is the input height used across the forms — see the `h-11` on every
 * `<Input>` in PostCampaign and BrandOnboarding. If that changes, this has to.
 */
export function FieldSkeleton({ className = "" }) {
    return (
        <div className={className}>
            <Skeleton className="h-3 w-28" />
            <Skeleton className="mt-2 h-11 w-full rounded-md" />
        </div>
    );
}

/** A titled group of fields, matching the `space-y-5` sections in the forms. */
export function FormSectionSkeleton({ fields = 2, columns = false }) {
    return (
        <section className="space-y-5" aria-hidden="true">
            <Skeleton className="h-3 w-40" />
            <div className={columns ? "grid gap-5 md:grid-cols-2" : "space-y-5"}>
                {Array.from({ length: fields }).map((_, i) => (
                    <FieldSkeleton key={i} />
                ))}
            </div>
        </section>
    );
}

/**
 * A form page: header, sections, and the footer action bar.
 *
 * The footer matters as much as the fields. It is the tallest single element on
 * the page on a phone — `flex-col-reverse` stacks two full-width buttons — so
 * omitting it is what makes a "close enough" skeleton shift by 100px on mobile
 * and by 0 on a laptop, which is exactly the bug that only shows up in
 * production.
 */
export function FormPageSkeleton({
    sections = [{ fields: 2 }, { fields: 2, columns: true }],
    actions = 2,
    testid,
}) {
    return (
        <div data-testid={testid} aria-hidden="true">
            <PageHeaderSkeleton lines={1} />
            <div className="mt-12 space-y-8">
                {sections.map((s, i) => (
                    <FormSectionSkeleton key={i} {...s} />
                ))}
                <div className="flex flex-col-reverse items-stretch gap-3 border-t border-white/10 pt-8 md:flex-row md:items-center md:justify-between">
                    <Skeleton className="h-5 w-full max-w-xs" />
                    <div className="flex flex-col-reverse gap-3 md:flex-row">
                        {Array.from({ length: actions }).map((_, i) => (
                            <Skeleton
                                key={i}
                                className="h-12 w-full rounded-full md:w-36"
                            />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}

/**
 * A detail page: back link, status chips, a big title, then an 8/4 split of
 * body and sidebar.
 *
 * The sidebar card is `sticky top-24` in the real page. It is not sticky here —
 * there is nothing to scroll past yet, and a sticky skeleton that detaches on
 * the swap is a shift in its own right.
 */
export function DetailPageSkeleton({ testid }) {
    return (
        <div data-testid={testid} aria-hidden="true">
            <Skeleton className="h-3 w-28" />

            <div className="mt-6 flex flex-wrap items-center gap-2">
                <Skeleton className="h-6 w-20 rounded-full" />
                <Skeleton className="h-3 w-32" />
            </div>

            {/* text-fluid-6xl-wide: two lines on a phone, one on a laptop. */}
            <Skeleton className="mt-4 h-20 w-full max-w-3xl md:h-16" />

            <div className="mt-10 grid gap-10 md:grid-cols-12">
                <div className="md:col-span-8">
                    <section>
                        <Skeleton className="h-3 w-24" />
                        <div className="mt-4 space-y-2">
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-4/5" />
                        </div>
                    </section>
                    <section className="mt-12 rounded-md border border-white/10 bg-card p-8 grain-surface">
                        <Skeleton className="h-3 w-28" />
                        <Skeleton className="mt-4 h-7 w-3/4" />
                    </section>
                </div>

                <aside className="md:col-span-4">
                    <div className="space-y-4">
                        <div className="rounded-md border border-white/10 bg-card p-7 grain-surface">
                            <Skeleton className="h-3 w-32" />
                            <Skeleton className="mt-2 h-10 w-40" />
                            <Skeleton className="mt-2 h-3 w-full" />
                            <div className="mt-7 space-y-4 border-t border-white/10 pt-6">
                                {Array.from({ length: 3 }).map((_, i) => (
                                    <div key={i} className="flex items-start gap-3">
                                        <Skeleton className="mt-0.5 h-4 w-4 flex-none rounded" />
                                        <div className="min-w-0 flex-1">
                                            <Skeleton className="h-3 w-24" />
                                            <Skeleton className="mt-1 h-4 w-32" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        {/* The apply button, or whatever stands in its place. */}
                        <Skeleton className="h-12 w-full rounded-full" />
                    </div>
                </aside>
            </div>
        </div>
    );
}

/**
 * The one thing on the page that must not be `aria-hidden`.
 *
 * A skeleton is invisible to a screen reader by design, which means without
 * this a blind user gets silence between the click and the content — the exact
 * uncertainty the skeleton removes for everybody else.
 */
export function LoadingAnnouncement({ children = "Loading…", testid }) {
    return (
        <p role="status" aria-live="polite" className="sr-only" data-testid={testid}>
            {children}
        </p>
    );
}
