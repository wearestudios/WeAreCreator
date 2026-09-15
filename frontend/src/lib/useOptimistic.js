/**
 * Mutations that answer immediately, and undo themselves visibly when they
 * don't land.
 *
 * The pattern this replaces is everywhere in the product: set a busy flag,
 * await the request, refetch the list. On a good connection that reads as a
 * pause; on the connection a campaign manager actually has — a basement, a
 * venue, mobile data — it reads as a dead button, and the second press is a
 * second row in somebody's queue. `lib/offlineQueue.js` already made exactly
 * this argument about check-ins and solved it for that one screen; this is the
 * same argument for every other button.
 *
 * Three rules, all learned from the offline queue:
 *
 * - **The control goes pending on the same frame as the click.** Not when the
 *   request is sent, not when the first byte comes back.
 * - **The row shows the new value before the server confirms it**, because
 *   the overwhelming majority of these succeed and optimising for the failure
 *   makes every success feel slow.
 * - **A failure rolls back where the reader can see it.** Silently reverting
 *   is worse than never having moved: somebody who watched a row change and
 *   looked away believes it changed. So the value returns *and* the row is
 *   marked failed for a moment, which is what a caller draws a flash from.
 *
 * What this deliberately does **not** do is retry. That is the offline
 * queue's job and it is a different decision — a check-in is worth replaying
 * because the person is standing there; an approval is not, because by the
 * time it replays the reader has moved on and the outcome arrives unattached
 * to anything they did.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/** How long a rolled-back row stays marked as failed. Long enough to be seen
 *  at a glance away from the screen, short enough not to become state. */
export const ROLLBACK_FLASH_MS = 1600;

/**
 * Lay optimistic patches over a server-owned list.
 *
 * `rows` is whatever the last fetch returned and stays the source of truth:
 * when a refetch brings the server's own version of a patched row, the
 * override is dropped and the fresh value wins. That ordering matters — an
 * override that outlived its refetch would pin a stale value on screen
 * forever, which is the failure mode of every hand-rolled version of this.
 */
export function useOptimisticRows(rows, { idKey = "id" } = {}) {
    const [patches, setPatches] = useState({});
    const [pending, setPending] = useState({});
    const [failed, setFailed] = useState({});
    const timers = useRef({});
    const alive = useRef(true);

    useEffect(() => {
        alive.current = true;
        return () => {
            alive.current = false;
            Object.values(timers.current).forEach(clearTimeout);
            timers.current = {};
        };
    }, []);

    // A fresh fetch is the server's answer, so anything it covers stops being
    // a guess. Keyed on the rows identity rather than deep-compared: the
    // callers all replace the array wholesale.
    useEffect(() => {
        setPatches((current) => (Object.keys(current).length ? {} : current));
    }, [rows]);

    const view = useMemo(
        () =>
            (rows || []).map((row) => {
                const patch = patches[row?.[idKey]];
                return patch ? { ...row, ...patch } : row;
            }),
        [rows, patches, idKey],
    );

    const flashFailure = useCallback((id) => {
        setFailed((f) => ({ ...f, [id]: true }));
        clearTimeout(timers.current[id]);
        timers.current[id] = setTimeout(() => {
            if (!alive.current) return;
            setFailed((f) => {
                const { [id]: _gone, ...rest } = f;
                return rest;
            });
        }, ROLLBACK_FLASH_MS);
    }, []);

    /**
     * Run one mutation against one row.
     *
     * `patch` is what the row should look like straight away; `request` is the
     * promise that makes it true. Resolves to `true` on success and `false` on
     * failure, so a caller that wants to close a dialog or refetch can do
     * either without a second try/catch.
     *
     * Rethrowing is deliberately not an option: every caller would have to
     * catch it to avoid an unhandled rejection, and `globalErrors.js` would
     * toast the ones that forgot — on top of the message the caller already
     * showed.
     */
    const apply = useCallback(
        async (id, patch, request, { onError } = {}) => {
            setPending((p) => ({ ...p, [id]: true }));
            if (patch) setPatches((s) => ({ ...s, [id]: { ...s[id], ...patch } }));
            try {
                const out = await request();
                if (!alive.current) return true;
                // The patch stays until a refetch replaces the row, so the
                // screen does not flick back to the old value in the gap
                // between the response and the new list arriving.
                return out === undefined ? true : out;
            } catch (err) {
                if (alive.current) {
                    setPatches((s) => {
                        const { [id]: _gone, ...rest } = s;
                        return rest;
                    });
                    flashFailure(id);
                }
                if (onError) onError(err);
                return false;
            } finally {
                if (alive.current) {
                    setPending((p) => {
                        const { [id]: _gone, ...rest } = p;
                        return rest;
                    });
                }
            }
        },
        [flashFailure],
    );

    return { rows: view, pending, failed, apply };
}

/**
 * The single-control version: one button, one pending flag.
 *
 * Most mutation sites in this product are not a row in a list — they are a
 * dialog's submit, a panel's save, a toggle. Those need the immediate pending
 * state and the visible failure and have nothing to patch, and making them
 * invent an id to use the hook above is how a helper stops being used.
 */
export function useOptimisticAction() {
    const [pending, setPending] = useState(false);
    const [failed, setFailed] = useState(false);
    const timer = useRef(0);
    const alive = useRef(true);

    useEffect(() => {
        alive.current = true;
        return () => {
            alive.current = false;
            clearTimeout(timer.current);
        };
    }, []);

    const run = useCallback(async (request, { onError } = {}) => {
        setPending(true);
        setFailed(false);
        try {
            const out = await request();
            return out === undefined ? true : out;
        } catch (err) {
            if (alive.current) {
                setFailed(true);
                clearTimeout(timer.current);
                timer.current = setTimeout(() => {
                    if (alive.current) setFailed(false);
                }, ROLLBACK_FLASH_MS);
            }
            if (onError) onError(err);
            return false;
        } finally {
            if (alive.current) setPending(false);
        }
    }, []);

    return { run, pending, failed };
}
