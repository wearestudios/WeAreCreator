// One way to call the server from a button.
//
// Every mutation in the app needs the same three things and was getting them
// by hand, differently, at every call site: a pending state on the control the
// user pressed, a confirmation that it worked, and a failure that says what to
// do next. `useAction` is that, once.
//
// What it deliberately does NOT do is block the page. A full-screen spinner
// during a two-second POST takes the whole product away from somebody who
// pressed one button; the pending state belongs on the trigger.
import { useCallback, useRef, useState } from "react";

import { notifyError, notifySuccess } from "@/lib/feedback";

/**
 * @param {Function} fn      the request. Receives whatever you pass to `run`.
 * @param {object}   options
 *   success   string | (result, args) => string — the confirmation. Omit for
 *             actions whose result is visible on screen anyway.
 *   onSuccess (result, args) => void — usually a refetch.
 *   onError   (err, args) => void — for anything beyond the toast.
 *   retry     boolean (default true) — offer a Retry button on the failure.
 *   optimistic { apply, rollback } — see `useOptimisticAction` below.
 *
 * @returns { run, pending, error, reset }
 *   `pending` is a boolean for a single-target action, and `pendingId` names
 *   which row is in flight when the same action serves a list.
 */
export function useAction(fn, options = {}) {
    const { success, onSuccess, onError, retry = true } = options;
    // State, not a ref: a ref does not re-render, so the button would never
    // show that it was working. This has been got wrong here before.
    const [pending, setPending] = useState(false);
    const [pendingId, setPendingId] = useState(null);
    const [error, setError] = useState(null);
    // Guards a double-tap on a phone, where the second tap lands before the
    // disabled attribute has painted.
    const inFlight = useRef(false);

    const run = useCallback(
        async (...args) => {
            if (inFlight.current) return { ok: false, skipped: true };
            inFlight.current = true;
            setPending(true);
            setError(null);
            const id = options.idOf ? options.idOf(...args) : null;
            if (id != null) setPendingId(id);
            try {
                const result = await fn(...args);
                if (success) {
                    notifySuccess(
                        typeof success === "function" ? success(result, ...args) : success,
                    );
                }
                await onSuccess?.(result, ...args);
                return { ok: true, result };
            } catch (err) {
                setError(err);
                notifyError(err, {
                    // Retrying re-runs exactly what was asked, so the button
                    // is honest — it is the same call, not a page reload.
                    onRetry: retry ? () => run(...args) : undefined,
                });
                await onError?.(err, ...args);
                return { ok: false, error: err };
            } finally {
                inFlight.current = false;
                setPending(false);
                setPendingId(null);
            }
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [fn, success, onSuccess, onError, retry],
    );

    return {
        run,
        pending,
        pendingId,
        error,
        reset: useCallback(() => setError(null), []),
        /** True when this specific row is the one in flight. */
        isPending: useCallback((id) => pending && pendingId === id, [pending, pendingId]),
    };
}

/**
 * The same, but the screen changes before the server answers.
 *
 * For the small, near-certain moves — a toggle, an approval, marking a row
 * read — waiting 400ms to see the thing you just pressed take effect is the
 * difference between an app that feels immediate and one that feels remote.
 *
 * The bargain is that a failure has to put it back exactly as it was, which is
 * why `apply` returns the undo rather than the caller keeping a copy: the two
 * cannot drift apart if they are written in the same breath.
 *
 *     const toggle = useOptimisticAction(
 *         (row) => api.post(`/x/${row.id}/toggle`),
 *         {
 *             apply: (row) => {
 *                 const before = rows;
 *                 setRows((r) => r.map((x) => x.id === row.id ? {...x, on: !x.on} : x));
 *                 return () => setRows(before);   // the rollback
 *             },
 *         },
 *     );
 */
export function useOptimisticAction(fn, options = {}) {
    const { apply, ...rest } = options;
    const rollbackRef = useRef(null);

    const wrapped = useCallback(
        async (...args) => {
            rollbackRef.current = apply ? apply(...args) : null;
            return fn(...args);
        },
        [fn, apply],
    );

    return useAction(wrapped, {
        ...rest,
        onError: async (err, ...args) => {
            // Put it back before anything else runs, so the user never sees
            // the optimistic state and the error message at the same time.
            rollbackRef.current?.();
            rollbackRef.current = null;
            await rest.onError?.(err, ...args);
        },
        onSuccess: async (result, ...args) => {
            rollbackRef.current = null;
            await rest.onSuccess?.(result, ...args);
        },
    });
}

export default useAction;
