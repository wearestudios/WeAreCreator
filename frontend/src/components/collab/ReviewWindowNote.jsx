// The draft review window's countdown: "Auto-approves tomorrow", with the
// exact moment on hover.
//
// One line on every surface that reads the window — the reviewer's screen
// beside the send-back, the creator's own card, the admin's — and it never
// asks which of those it is on: the same window is the same sentence for all
// three. Its own file, apart from the admin's controls, so the creator's
// chunk does not download the console's dialogs to draw one sentence.
import React from "react";
import { Clock } from "lucide-react";

import { reviewWindowText } from "@/lib/reviewWindow";
import { REVIEW_WINDOW as IDS } from "@/constants/testIds";

const TONE = {
    calm: "text-muted-foreground",
    due: "text-state-pending",
    paused: "text-muted-foreground",
    done: "text-muted-foreground",
};

export default function ReviewWindowNote({ reviewWindow, testid = IDS.note, className = "" }) {
    const said = reviewWindowText(reviewWindow);
    if (!said) return null;
    return (
        <p
            data-testid={testid}
            title={said.exact || undefined}
            className={`inline-flex items-center gap-2 text-sm ${TONE[said.tone]} ${className}`}
        >
            <Clock className="h-4 w-4 flex-none" aria-hidden="true" />
            <span>
                {said.text}
                {/* The hover is a courtesy; a phone has no hover, so the
                    instant is also in the accessible name. */}
                {said.exact && <span className="sr-only"> ({said.exact})</span>}
            </span>
        </p>
    );
}
