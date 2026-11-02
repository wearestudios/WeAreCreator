// Where a brand stands with us, on the screen it lands on.
//
// Pending, rejected, lapsed and blocked-by-an-invoice were all decided on the
// server and said only at the moment somebody pressed publish — in a toast,
// after the work. The dashboard payload carries the verification block and
// `publish_block` (the same reader the publish route uses), and this draws
// them: a pill beside the brand's name, and one notice saying what to do.
//
// It computes nothing. Verified with no block renders the pill alone, which is
// the good news said quietly.
import React from "react";
import { Link } from "react-router-dom";
import { ShieldAlert, ShieldCheck } from "lucide-react";

import { BRAND_STANDING as IDS } from "@/constants/testIds";

const PILL = {
    verified: { label: "Verified", tone: "border-state-approved/30 bg-state-approved-wash text-state-approved" },
    pending_verification: { label: "Verification pending", tone: "border-state-pending/30 bg-state-pending-wash text-state-pending" },
    rejected: { label: "Not verified", tone: "border-state-rejected/30 bg-state-rejected-wash text-state-rejected" },
    unsubmitted: { label: "Not yet verified", tone: "border-border bg-muted text-muted-foreground" },
};

// The two blocks that sit on top of a verified brand get their own words on
// the pill — "Verified" beside a notice saying they cannot post would be the
// pill contradicting the page.
const BLOCK_PILL = {
    verification_lapsed: { label: "Check due", tone: "border-state-pending/30 bg-state-pending-wash text-state-pending" },
    invoice_overdue: { label: "Posting paused", tone: "border-state-rejected/30 bg-state-rejected-wash text-state-rejected" },
};

export function StandingPill({ verification, block }) {
    const state = verification?.state || "unsubmitted";
    const meta = BLOCK_PILL[block?.code] || PILL[state] || PILL.unsubmitted;
    const Icon = state === "verified" && !BLOCK_PILL[block?.code] ? ShieldCheck : ShieldAlert;
    return (
        <span
            data-testid={IDS.pill}
            data-state={block?.code || state}
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-eyebrow font-medium uppercase tracking-eyebrow ${meta.tone}`}
        >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {meta.label}
        </span>
    );
}

export function StandingNotice({ verification, block }) {
    if (!block) return null;
    const state = verification?.state;
    // Where to go to fix it. An invoice is settled with us, not on a form.
    const link =
        block.code === "invoice_overdue"
            ? null
            : block.code === "verification_lapsed"
              ? { to: "/onboarding/brand", label: "Confirm your details" }
              : state === "pending_verification"
                ? null
                : { to: "/onboarding/brand", label: state === "rejected" ? "Fix your details" : "Verify your business" };
    return (
        <div
            data-testid={IDS.notice}
            data-code={block.code}
            role="status"
            className={
                "mt-8 flex items-start gap-3 rounded-md border p-4 text-body leading-relaxed " +
                (block.code === "invoice_overdue" || state === "rejected"
                    ? "border-state-rejected/30 bg-state-rejected-wash text-state-rejected"
                    : "border-state-pending/30 bg-state-pending-wash text-state-pending")
            }
        >
            <ShieldAlert className="mt-1 h-4 w-4 flex-none" aria-hidden="true" />
            <p>
                {block.message}
                {link && (
                    <>
                        {" "}
                        <Link to={link.to} className="underline underline-offset-4 hover:no-underline">
                            {link.label}
                        </Link>
                    </>
                )}
            </p>
        </div>
    );
}
