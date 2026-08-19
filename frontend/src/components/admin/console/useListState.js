// Filters, sort and scroll position, remembered per section.
//
// The console's lists lost everything on navigation. Open a creator from a
// filtered, sorted, scrolled list, press back, and you were at the top of an
// unfiltered list — which meant the actual working pattern (filter down, then
// work through the rows one at a time) cost a re-filter per row. That is the
// single most expensive thing a list view can do to somebody using it for an
// hour.
//
// **`sessionStorage`, not `localStorage`.** A filter set is a working context,
// not a preference: it should survive a detail page and a refresh, and it
// should be gone tomorrow. `localStorage` would mean opening the console next
// week to a filter somebody set once and forgot, with an empty list and no
// obvious reason why.
//
// **Saved filter sets are the deliberate exception** and do persist, because
// naming one is an explicit act. They live under their section in the sidebar.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const SESSION_KEY = "weare.admin.list";
const SAVED_KEY = "weare.admin.savedFilters";

function readJson(storage, key, fallback) {
    try {
        const raw = storage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
    } catch {
        // A corrupt or unavailable store is not worth breaking a screen over;
        // the list simply starts from its defaults.
        return fallback;
    }
}

function writeJson(storage, key, value) {
    try {
        storage.setItem(key, JSON.stringify(value));
    } catch {
        /* Private mode, or a full quota. The list still works. */
    }
}

/**
 * One section's remembered state.
 *
 * @param {string} section  the sidebar key — "creators", "campaigns", …
 * @param {object} initial  the section's defaults, used on a first visit
 * @returns {{state, setState, patch, reset, scrollRef, saved, save, remove, apply}}
 */
export function useListState(section, initial) {
    const [state, setState] = useState(() => {
        const all = readJson(window.sessionStorage, SESSION_KEY, {});
        return { ...initial, ...(all[section] || {}) };
    });

    // Persist on every change rather than on unmount: an unmount handler does
    // not run if the tab is closed or the route throws, and losing the context
    // in exactly those cases is losing it when it matters most.
    useEffect(() => {
        const all = readJson(window.sessionStorage, SESSION_KEY, {});
        writeJson(window.sessionStorage, SESSION_KEY, { ...all, [section]: state });
    }, [section, state]);

    const patch = useCallback(
        (next) => setState((s) => ({ ...s, ...next })),
        [],
    );
    const reset = useCallback(() => setState(initial), [initial]);

    // --- scroll position -----------------------------------------------------
    //
    // Restored on mount, saved as you scroll. Kept out of `state` so a scroll
    // does not re-render the list sixty times a second.
    const scrollRef = useRef(null);
    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return undefined;
        const all = readJson(window.sessionStorage, `${SESSION_KEY}.scroll`, {});
        const y = all[section];
        // After paint, so the rows exist to scroll past.
        if (y) requestAnimationFrame(() => { el.scrollTop = y; });

        let frame = 0;
        const onScroll = () => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
                const now = readJson(window.sessionStorage, `${SESSION_KEY}.scroll`, {});
                writeJson(window.sessionStorage, `${SESSION_KEY}.scroll`, {
                    ...now,
                    [section]: el.scrollTop,
                });
            });
        };
        el.addEventListener("scroll", onScroll, { passive: true });
        return () => {
            cancelAnimationFrame(frame);
            el.removeEventListener("scroll", onScroll);
        };
    }, [section]);

    // --- saved filter sets ---------------------------------------------------
    const [saved, setSaved] = useState(() =>
        readJson(window.localStorage, SAVED_KEY, {}),
    );

    const persistSaved = useCallback((next) => {
        setSaved(next);
        writeJson(window.localStorage, SAVED_KEY, next);
        // So the sidebar picks it up without a prop drilling through the shell.
        window.dispatchEvent(new CustomEvent("weare:saved-filters"));
    }, []);

    const save = useCallback(
        (name) => {
            const trimmed = String(name || "").trim();
            if (!trimmed) return;
            const forSection = saved[section] || [];
            persistSaved({
                ...saved,
                // Re-saving a name overwrites it rather than making a second
                // entry with the same label, which nobody could tell apart.
                [section]: [
                    ...forSection.filter((f) => f.name !== trimmed),
                    { name: trimmed, state },
                ],
            });
        },
        [saved, section, state, persistSaved],
    );

    const remove = useCallback(
        (name) => {
            persistSaved({
                ...saved,
                [section]: (saved[section] || []).filter((f) => f.name !== name),
            });
        },
        [saved, section, persistSaved],
    );

    const apply = useCallback((next) => setState({ ...initial, ...next }), [initial]);

    const mine = useMemo(() => saved[section] || [], [saved, section]);

    return { state, setState, patch, reset, scrollRef, saved: mine, save, remove, apply };
}

/** Every saved set, for the sidebar. Kept here so the storage key has one
 *  reader and one writer. */
export function readSavedFilters() {
    return readJson(window.localStorage, SAVED_KEY, {});
}

export default useListState;
