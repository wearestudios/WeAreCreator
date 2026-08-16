// Telling somebody what happened.
//
// Every call to the server has three answers — working, done, or didn't work —
// and before this each of ~60 call sites picked its own wording, its own
// duration and its own idea of what an error should say. The result was a
// product where "it failed" and "nothing happened" looked identical.
//
// Three rules, enforced by the helpers below rather than by remembering:
//
//   1. A failure says what to do next. "Couldn't save" is a dead end;
//      "Couldn't save — check your connection and try again" is not, and a
//      Retry button is better than either.
//   2. Errors stay put longer than successes and can be dismissed. A success
//      is a receipt you glance at; an error is something you have to act on,
//      and four seconds is not long enough to read one and decide.
//   3. One position, one set of durations, one visual treatment per outcome.
import { toast } from "sonner";

import { formatApiError, apiErrorCode } from "@/lib/api";

// A success is a receipt. An error is a task. They get different lifetimes.
export const TOAST_DURATION = {
    success: 3500,
    error: 8000,
    info: 5000,
    // A pending toast is dismissed by its own resolution, never by a timer.
    pending: Infinity,
};

/**
 * What to tell someone when a request fails, and what they can do about it.
 *
 * The server's own message wins when it has one — it knows the actual reason
 * ("Accept the creator first", "Your slots are full"), and those are already
 * written as next steps. This only supplies the next step when the failure is
 * one the server never got to answer.
 */
export function describeFailure(err) {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail;

    // No response at all: the request never landed, so there is nothing the
    // server could have told us and nothing wrong with what was asked.
    if (err && !err.response) {
        return {
            message: "That didn't reach us — check your connection and try again.",
            retryable: true,
        };
    }
    if (status === 401) {
        return {
            message: "Your session has expired. Sign in again to carry on.",
            retryable: false,
        };
    }
    if (status === 403 && !detail) {
        return { message: "You don't have access to that.", retryable: false };
    }
    if (status === 404 && !detail) {
        return {
            message: "That's no longer there — reload and try again.",
            retryable: false,
        };
    }
    if (status === 409) {
        // Somebody else moved it. Retrying the same call would fail the same
        // way; what is needed is a fresh look at the current state.
        return {
            message: formatApiError(err) || "That just changed — reload and try again.",
            retryable: false,
        };
    }
    if (status === 429) {
        return {
            message: "Too many attempts. Wait a moment and try again.",
            retryable: true,
        };
    }
    if (status >= 500) {
        return {
            message: "Something broke on our side. Try again in a moment.",
            retryable: true,
        };
    }
    return { message: formatApiError(err), retryable: status !== 422 && status !== 400 };
}

export function notifySuccess(message, options = {}) {
    return toast.success(message, {
        duration: TOAST_DURATION.success,
        ...options,
    });
}

/** A partial success — some of it worked. Sits between the two on purpose:
 *  as long-lived as an error, because the untouched half needs a decision. */
export function notifyWarning(message, options = {}) {
    return toast.warning(message, { duration: TOAST_DURATION.error, ...options });
}

export function notifyInfo(message, options = {}) {
    return toast.info(message, { duration: TOAST_DURATION.info, ...options });
}

/**
 * Report a failure, with a way out of it.
 *
 * `onRetry` becomes a button on the toast — the shortest path from "that
 * didn't work" back to "try that again" — and is only offered when retrying
 * could actually help. Re-sending a 409 or a 422 would fail identically, so
 * those get the reason and no button rather than a button that lies.
 */
export function notifyError(err, options = {}) {
    const { onRetry, fallback, ...rest } = options;
    const { message, retryable } =
        typeof err === "string" ? { message: err, retryable: Boolean(onRetry) } : describeFailure(err);
    return toast.error(message || fallback || "Something went wrong.", {
        duration: TOAST_DURATION.error,
        action:
            onRetry && retryable
                ? { label: "Retry", onClick: () => onRetry() }
                : undefined,
        ...rest,
    });
}

/** The structured refusal code, when the server sent one. Re-exported so a
 *  call site needs one import rather than two. */
export { apiErrorCode, formatApiError };
