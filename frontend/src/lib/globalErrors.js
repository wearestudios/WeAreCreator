// The failures nobody was listening for.
//
// Two different silences existed here:
//
//   1. A request that failed inside a `.then()` chain with no `.catch()`. The
//      promise rejects, nothing handles it, and the UI simply never updates —
//      a spinner that spins forever, or a list that stays empty as if the
//      server had said "none".
//   2. A `throw` in a callback or a timer, outside React's render, which no
//      error boundary can see.
//
// Both now surface as a toast, and both are logged.
//
// **Why this does not live in an axios interceptor.** The obvious place to
// toast a failed request is a response interceptor — and it is the wrong place,
// because roughly sixty call sites already catch their own errors and show
// something better than a generic message ("Accept the creator first"). An
// interceptor cannot know whether a caller is about to handle the rejection, so
// it would double-toast every one of them.
//
// `unhandledrejection` knows exactly that, and it is the browser that decides:
// it fires only for rejections that reached the end of a microtask queue with
// no handler attached. So a caller that catches gets its own message and
// nothing from here; a caller that forgot gets covered. The deliberate
// `.catch(() => {})` sites — "the list on screen is still the last good one" —
// are handled, and correctly stay quiet.
import { toast } from "sonner";

import { describeFailure, TOAST_DURATION } from "@/lib/feedback";
import { logError } from "@/lib/errorLog";

/** Is this an axios error rather than a programming mistake? */
const isRequestError = (e) => Boolean(e && (e.isAxiosError || e.config || e.response));

/**
 * A stable id per message, so a burst collapses into one toast.
 *
 * A session expiring mid-screen fails every request on that page at once. Six
 * identical "Your session has expired" toasts stacked up the viewport is worse
 * than the silence this replaces — sonner dedupes on id, so the first one wins
 * and the rest refresh it.
 */
const toastId = (message) => "global:" + message.slice(0, 64);

// A 401 is not a bug and the app has its own answer to it (ProtectedRoute
// bounces to /login on the next render). Saying it once is right; logging a
// stack for it is noise.
const QUIET_STATUSES = new Set([401]);

function reportRequestFailure(error, source) {
    const status = error?.response?.status;
    const { message } = describeFailure(error);

    if (!QUIET_STATUSES.has(status)) {
        logError(error, {
            source,
            status,
            endpoint: error?.config?.url,
        });
    }

    toast.error(message, {
        id: toastId(message),
        duration: TOAST_DURATION.error,
    });
}

function reportCrash(error, source) {
    logError(error, { source });
    // No stack, no "TypeError", no endpoint. The person reading this cannot act
    // on any of it, and a UI that shows its own internals reads as broken twice.
    const message = "Something went wrong. Try that again.";
    toast.error(message, { id: toastId(message), duration: TOAST_DURATION.error });
}

let installed = false;

/**
 * Attach the handlers. Idempotent, because a hot reload would otherwise stack
 * a second copy and double every toast.
 */
export function installGlobalErrorHandlers() {
    if (installed || typeof window === "undefined") return;
    installed = true;

    window.addEventListener("unhandledrejection", (event) => {
        const reason = event.reason;
        if (isRequestError(reason)) reportRequestFailure(reason, "unhandled-rejection");
        else reportCrash(reason, "unhandled-rejection");
    });

    window.addEventListener("error", (event) => {
        // Fires for failed <img>/<script> loads too, which have a target and no
        // error object. A missing avatar is not worth a toast.
        if (!event.error) return;
        reportCrash(event.error, "window-error");
    });
}
