// Why this brief cannot go out yet, said before the button is pressed.
//
// **Drafting was always open to an unverified brand; the wall was silent.**
// They filled the form, pressed "Send for review", and got a toast — which
// arrives after the work, names the state rather than the fix, and is gone in
// four seconds. The refusal was correct and the moment was wrong.
//
// So the same three answers `_why_brand_is_blocked` gives the server are
// rendered here, beside a disabled button, with the fields still needed listed
// out and a link to the page that collects them. And the draft still saves —
// that is the half worth protecting: writing the brief is not the part that
// has to wait on us.
import React from "react";
import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

import { BRAND_PUBLISH as IDS } from "@/constants/testIds";

/**
 * @param {object} props.verification  The block from `GET /brand/profile`:
 *   `state`, `missing_fields`, `document_count`. Decided server-side, so this
 *   never works out for itself whether somebody may publish.
 * @param {object} [props.trust]  When a brand has earned it, the same slot says
 *   the opposite thing: this one skips review entirely.
 */
export default function PublishGate({ verification, trust }) {
    const state = verification?.state || "unsubmitted";

    if (state === "verified") {
        // Nothing is in the way. The only thing worth saying here is the good
        // news, and only when there is some — a permanent green banner over
        // every brief is chrome.
        if (!trust?.trusted) return null;
        return (
            <p
                data-testid={IDS.trusted}
                className="rounded-md border border-emerald-400/30 bg-emerald-400/10 p-4 text-sm text-emerald-100/90"
            >
                This one goes live as soon as you send it — you've had{" "}
                {trust.approvals} campaigns approved without a single one sent back,
                so we don't hold them for review any more. We still read them
                afterwards.
            </p>
        );
    }

    const missing = verification?.missing_fields || [];
    const noDocuments = !(verification?.document_count > 0);

    // The same three situations with three different next steps that
    // `_why_brand_is_blocked` distinguishes. "Not verified" on its own is what
    // generates a support email.
    const body =
        state === "rejected" ? (
            <>
                Your business details weren't approved
                {verification?.verification_reason
                    ? `: ${verification.verification_reason}`
                    : "."}{" "}
                Fix that and send them again — this brief keeps everything you've
                written.
            </>
        ) : state === "pending_verification" ? (
            <>
                Your business details are with the WeAre team, usually back within 48
                hours. Save this as a draft and it'll be ready to send the moment
                you're verified.
            </>
        ) : (
            <>
                We check every business before its briefs reach creators.
                {missing.length > 0 && (
                    <>
                        {" "}Still needed:{" "}
                        <span className="text-foreground">
                            {missing.map((m) => m.label).join(", ")}
                        </span>
                        .
                    </>
                )}
                {noDocuments && " Plus a document proving you represent it."}
            </>
        );

    return (
        <div
            data-testid={IDS.gate}
            className="rounded-md border border-amber-400/30 bg-amber-400/10 p-4"
        >
            <p className="flex items-start gap-2 text-sm text-amber-100/90">
                <ShieldAlert
                    aria-hidden="true"
                    className="mt-0.5 h-4 w-4 flex-none text-amber-300"
                />
                <span>
                    <span className="block font-medium text-foreground">
                        You can write and save this now; sending it needs verification.
                    </span>
                    {body}
                </span>
            </p>
            {state !== "pending_verification" && (
                <Link
                    to="/onboarding/brand"
                    data-testid={IDS.gateLink}
                    className="mt-3 inline-block text-sm text-ember-500 underline underline-offset-4 hover:no-underline"
                >
                    {state === "rejected" ? "Fix your details" : "Verify your business"}
                </Link>
            )}
        </div>
    );
}
