// Work that must not be lost because the venue has one bar of signal.
//
// A manager checking twenty people into a basement restaurant is the worst
// network conditions in the product and the least forgiving moment to be in
// them: there is a person standing in front of them, and a check-in that
// silently failed is discovered at reconciliation, days later, as an
// attendance record that disagrees with what happened in the room.
//
// Before this, a failed check-in reverted the row and raised a toast with a
// Retry button. That is fine on a laptop and wrong here — it needs the manager
// to notice a toast, while looking at a queue of people, and to tap it before
// it expires. So the request is kept instead, on disk, and replayed until the
// server takes it.
//
// **The rule that makes replay safe.** `POST .../check-in` answers 409 "They're
// already checked in" when the state has already moved. For a replay that is
// success — the work is done, possibly by the request we thought had failed —
// so a 4xx drops the item. Retrying only makes sense for the two failures that
// are about the network rather than the request: no response at all, and 5xx.
// Treating 409 as retryable would loop forever on work that had already landed.
//
// Storage is localStorage, so the queue survives a reload, a browser kill and a
// phone locking itself. It holds the manager's own pending actions on the
// manager's own device — the same data the screen is already showing — and
// nothing is ever written to a log.
import { api } from "@/lib/api";

const KEY = "weare.offline.queue";
const MAX_ATTEMPTS = 8;
// Replay attempts back off, so a genuinely dead connection is not hammered
// while somebody walks to the door for signal.
const BACKOFF_MS = [0, 2000, 5000, 15000, 30000, 60000, 120000, 300000];
// A sweep in case neither `online` nor a user action fires — a phone that
// regains signal in a pocket does not always dispatch the event.
const SWEEP_MS = 20000;

const listeners = new Set();
let flushing = false;
let sweepTimer = null;

function read() {
    try {
        const raw = localStorage.getItem(KEY);
        const rows = raw ? JSON.parse(raw) : [];
        return Array.isArray(rows) ? rows : [];
    } catch {
        // A corrupt entry must not take the app down on load. Losing the queue
        // is bad; refusing to start is worse.
        return [];
    }
}

function write(rows) {
    try {
        localStorage.setItem(KEY, JSON.stringify(rows));
    } catch {
        /* private mode, or the quota. The in-flight replay still runs. */
    }
    listeners.forEach((fn) => {
        try {
            fn(summary(rows));
        } catch {
            /* a broken subscriber must not stop the queue */
        }
    });
}

function summary(rows = read()) {
    return {
        pending: rows.length,
        // Named so the UI can say "2 check-ins waiting" rather than "2 items".
        labels: rows.map((r) => r.label).filter(Boolean),
        oldestAt: rows.length ? rows[0].queuedAt : null,
        blocked: rows.some((r) => r.attempts >= MAX_ATTEMPTS),
    };
}

/** Subscribe to the pending count. Returns an unsubscribe. */
export function subscribeQueue(fn) {
    listeners.add(fn);
    fn(summary());
    return () => listeners.delete(fn);
}

export function queueSummary() {
    return summary();
}

/**
 * Put one request on the queue.
 *
 * `key` de-duplicates: tapping check-in twice on the same creator, or a retry
 * landing on top of a queued attempt, must not produce two entries. The second
 * enqueue replaces the first rather than stacking.
 */
export function enqueue({ key, method = "post", url, body = null, label }) {
    const rows = read().filter((r) => r.key !== key);
    rows.push({
        key: key || `${method}:${url}:${Date.now()}`,
        method,
        url,
        body,
        label,
        queuedAt: new Date().toISOString(),
        attempts: 0,
        nextAt: 0,
    });
    write(rows);
    // Try immediately: the failure that queued this may have been a single
    // dropped packet rather than a dead connection.
    flush();
    return summary();
}

/**
 * Is this failure worth keeping, or is the request itself the problem?
 *
 * **Exported, because the two ends have to agree.** A call site decides
 * whether to enqueue and the flusher decides whether to keep replaying; if
 * those were two copies of the rule, a caller could queue something the
 * flusher drops on its first pass — a request that vanishes while the UI says
 * it is waiting to sync, which is the exact failure the queue exists to
 * prevent. One function, both ends.
 */
export function shouldRetry(error) {
    // No response at all: the request never landed, so nothing about it is
    // known to be wrong.
    if (error && !error.response) return true;
    const status = error?.response?.status;
    // Timeouts and rate limits are temporary by definition.
    if (status === 408 || status === 429) return true;
    // 5xx is ours, not theirs.
    if (status >= 500) return true;
    // Everything else — 409 included, and 409 is the common one — means the
    // server has answered about this specific request and will answer the
    // same way next time. For a check-in, 409 usually means it already
    // succeeded.
    return false;
}

/**
 * Replay the queue, oldest first, one at a time.
 *
 * Sequential on purpose: these are state transitions on the same campaign, and
 * firing six at once at a server we have just established is unreachable is how
 * you turn a slow connection into a stampede.
 */
export async function flush({ force = false } = {}) {
    if (flushing) return summary();
    // `force` overrides the offline check as well as the backoff: `navigator.
    // onLine` is a hint, not a fact — it reports true on a captive portal and
    // has been known to report false on a working connection — so an explicit
    // tap must be allowed to find out for itself.
    if (!force && typeof navigator !== "undefined" && navigator.onLine === false) {
        return summary();
    }
    flushing = true;
    try {
        for (;;) {
            const rows = read();
            if (!rows.length) break;
            const now = Date.now();
            // Backoff exists to stop a dead connection being hammered by a
            // timer. It must not survive a person tapping "Try now" or the
            // browser saying the network came back — both are better evidence
            // than our own exponential guess, and honouring a two-minute wait
            // after an explicit tap makes the button look broken.
            const item = rows.find(
                (r) => r.attempts < MAX_ATTEMPTS && (force || (r.nextAt || 0) <= now),
            );
            if (!item) break;

            try {
                await api.request({
                    method: item.method,
                    url: item.url,
                    data: item.body ?? undefined,
                });
                write(read().filter((r) => r.key !== item.key));
            } catch (e) {
                if (!shouldRetry(e)) {
                    // Answered, and the answer will not change. Drop it — for a
                    // check-in this is almost always "already checked in",
                    // which is the state we wanted.
                    write(read().filter((r) => r.key !== item.key));
                    continue;
                }
                const attempts = item.attempts + 1;
                write(
                    read().map((r) =>
                        r.key === item.key
                            ? {
                                  ...r,
                                  attempts,
                                  nextAt:
                                      Date.now() +
                                      (BACKOFF_MS[Math.min(attempts, BACKOFF_MS.length - 1)]),
                              }
                            : r,
                    ),
                );
                // Stop the pass: if this one could not reach the server, the
                // next one cannot either.
                break;
            }
        }
    } finally {
        flushing = false;
    }
    return summary();
}

/** Give up on the queue. Only ever from an explicit user action. */
export function clearQueue() {
    write([]);
    return summary();
}

let installed = false;

export function installOfflineQueue() {
    if (installed || typeof window === "undefined") return;
    installed = true;
    window.addEventListener("online", () => flush({ force: true }));
    // Coming back to the tab is the other moment worth trying: a manager who
    // walked outside for signal will foreground the app before they do
    // anything else.
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") flush({ force: true });
    });
    sweepTimer = setInterval(() => flush(), SWEEP_MS);
    // Anything left from a previous session goes first.
    flush({ force: true });
}

export function stopOfflineQueue() {
    if (sweepTimer) clearInterval(sweepTimer);
    sweepTimer = null;
    installed = false;
}
