// Share a brief.
//
// Native share sheet where there is one — on a phone that is WhatsApp,
// Instagram DMs and everything else in one tap, which is how a brief actually
// travels. Copy to clipboard everywhere else.
//
// The link points at the server-rendered page at /c/{id}, not at the React
// route: a preview crawler does not run JavaScript, so a link into the SPA
// previews as a blank card whatever meta tags the app sets at runtime.
import React, { useCallback, useState } from "react";
import { Check, Link2, Share2 } from "lucide-react";

import { notifyError } from "@/lib/feedback";
import { SHARE } from "@/constants/testIds";

/** Where the shareable page lives. */
export const shareUrlFor = (campaignId) => {
    const base = (process.env.REACT_APP_SHARE_BASE_URL || "").trim().replace(/\/$/, "");
    // Same-origin by default, which is right when /c/* is proxied to the
    // backend — and is what makes a copied link look like the product rather
    // than like an API host.
    return `${base || window.location.origin}/c/${campaignId}`;
};

export default function ShareButton({
    campaignId,
    title,
    summary,
    variant = "button",
    className = "",
}) {
    const [copied, setCopied] = useState(false);

    const share = useCallback(
        async (e) => {
            // Cards are links; sharing one must not also open it.
            e?.preventDefault();
            e?.stopPropagation();
            const url = shareUrlFor(campaignId);

            if (navigator.share) {
                try {
                    await navigator.share({
                        title: title || "A paid brief on WeAre Creators",
                        text: summary || undefined,
                        url,
                    });
                    return;
                } catch (err) {
                    // Dismissing the sheet rejects with AbortError. That is a
                    // decision, not a failure, and must not raise a toast.
                    if (err?.name === "AbortError") return;
                    // Anything else falls through to copying, which always works.
                }
            }

            try {
                await navigator.clipboard.writeText(url);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            } catch {
                notifyError("Couldn't copy the link. Long-press the address bar instead.");
            }
        },
        [campaignId, title, summary],
    );

    const label = copied ? "Link copied" : "Share";
    const Icon = copied ? Check : variant === "icon" ? Link2 : Share2;

    if (variant === "icon") {
        return (
            <button
                type="button"
                onClick={share}
                data-testid={SHARE.button(campaignId)}
                aria-label={copied ? "Link copied" : "Share this brief"}
                title={label}
                className={
                    "grid h-11 w-11 flex-none place-items-center rounded-full border border-white/10 text-muted-foreground transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:h-9 md:w-9 " +
                    (copied ? "border-ember-500/40 text-ember-500 " : "") +
                    className
                }
            >
                <Icon className="h-4 w-4" />
            </button>
        );
    }

    return (
        <button
            type="button"
            onClick={share}
            data-testid={SHARE.button(campaignId)}
            className={
                "inline-flex min-h-[2.75rem] items-center gap-2 rounded-full border border-white/15 px-4 text-xs uppercase tracking-[0.15em] transition-colors duration-200 hover:border-ember-500/40 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
                (copied ? "border-ember-500/40 text-ember-500 " : "text-muted-foreground ") +
                className
            }
        >
            <Icon className="h-3.5 w-3.5" />
            {label}
        </button>
    );
}
