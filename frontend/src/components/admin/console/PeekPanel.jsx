// The peek panel: a row's detail without leaving the list.
//
// The console's lists used to be a choice between a card that showed too
// little and a full page that cost the list. Working a queue is mostly
// "check this one, act, next" — and a full-page round trip per row means
// losing the filter, the sort and the scroll every time, forty times an hour.
//
// So: a slide-over. The list stays where it was, the panel carries the summary
// and the actions that apply, Esc closes it, and **"Open full page" is always
// there** for the cases the summary cannot answer. The panel is a shortcut,
// never a replacement — a peek that quietly became the only way to see
// something would be a detail page with less in it.
//
// **Built on the Radix dialog directly rather than on `components/ui/sheet`.**
// That primitive is on four other surfaces and is right for all of them, but
// it makes two decisions this panel cannot live with, and neither is
// overridable from a `className` on the content:
//
//   - **Its overlay blurs the page behind it.** Measured on a screenshot: the
//     list was unreadable, which is the one thing this panel exists to avoid.
//     "The list remains visible" is the whole difference between a peek and a
//     detail page.
//   - **It renders its own close button**, so the panel had two — mine in the
//     header and the primitive's on top of it, overlapping.
//
// Everything Radix actually does for us is still here: the focus moves into
// the panel on open and back to the row on close, Tab is trapped while it is
// open, Esc closes, and the page behind cannot be scrolled by accident.
import React from "react";
import { Link } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { ExternalLink, X } from "lucide-react";

import { CALM, DENSITY, FOCUS, TEXT } from "@/components/admin/console/tokens";
import { ADMIN_PEEK as IDS } from "@/constants/testIds";

/** A label and a value, the panel's one content primitive. */
export function PeekField({ label, children, testid }) {
    return (
        <div className="flex items-baseline justify-between gap-4 border-b border-white/5 py-2">
            <span className={`${TEXT.meta} shrink-0 text-muted-foreground`}>{label}</span>
            <span data-testid={testid} className={`${TEXT.body} text-right`}>
                {children ?? "—"}
            </span>
        </div>
    );
}

/**
 * @param {boolean}  open
 * @param {Function} onOpenChange
 * @param {string}   title
 * @param {string}   [subtitle]
 * @param {string}   [href]      the full entity route
 * @param {node}     [actions]   inline actions — approve, reject, advance
 * @param {node}     children    the summary
 */
export function PeekPanel({
    open,
    onOpenChange,
    title,
    subtitle,
    href,
    actions,
    children,
    testid = IDS.root,
}) {
    return (
        <Dialog.Root open={open} onOpenChange={onOpenChange}>
            <Dialog.Portal>
                {/* A scrim, not a curtain. It catches the click that closes the
                    panel and takes the contrast down a step; the rows behind
                    stay readable, which is the point of peeking rather than
                    opening. No blur, and nothing that fades in. */}
                <Dialog.Overlay className="fixed inset-0 z-50 bg-black/25" />
                <Dialog.Content
                    data-testid={testid}
                    aria-describedby={undefined}
                    // No grain and no translucency: this is a working panel
                    // over a working list, and a see-through one makes the
                    // rows behind it legible-but-not-quite, which is worse
                    // than either.
                    className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-white/10 bg-card sm:max-w-md"
                >
                    <div className={`flex items-start justify-between gap-3 border-b border-white/10 ${DENSITY.panel}`}>
                        <div className="min-w-0">
                            <Dialog.Title className={`${TEXT.heading} truncate`}>
                                {title}
                            </Dialog.Title>
                            {subtitle ? (
                                <Dialog.Description className={`${TEXT.meta} mt-0.5 truncate text-muted-foreground`}>
                                    {subtitle}
                                </Dialog.Description>
                            ) : (
                                <Dialog.Description className="sr-only">Details</Dialog.Description>
                            )}
                        </div>
                        <Dialog.Close
                            data-testid={IDS.close}
                            aria-label="Close"
                            className={`grid h-8 w-8 shrink-0 place-items-center rounded ${CALM} text-muted-foreground hover:bg-white/5 hover:text-foreground ${FOCUS}`}
                        >
                            <X className="h-4 w-4" />
                        </Dialog.Close>
                    </div>

                    <div className={`flex-1 overflow-y-auto ${DENSITY.panel}`}>{children}</div>

                    <div className={`flex flex-wrap items-center gap-2 border-t border-white/10 ${DENSITY.panel}`}>
                        {actions}
                        {href ? (
                            <Link
                                to={href}
                                data-testid={IDS.openFull}
                                className={`ml-auto inline-flex items-center gap-1.5 rounded px-2 py-1 ${TEXT.meta} ${CALM} text-muted-foreground hover:text-ember-500 ${FOCUS}`}
                            >
                                Open full page
                                <ExternalLink className="h-3 w-3" />
                            </Link>
                        ) : null}
                    </div>
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    );
}

export default PeekPanel;
