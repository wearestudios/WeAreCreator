// The console's keyboard flow.
//
// ⌘K already found things. This is the other half: moving through what it
// found and acting on it without reaching for the mouse. An admin clearing a
// review queue does the same four keystrokes a hundred times, and a hundred
// round trips to the trackpad is most of the hour.
//
//   ↑ ↓ / k j   move the focused row
//   Enter       open the peek panel on it
//   A / R       approve / reject, where the row offers them
//   Esc         close the panel, or clear focus
//   ?           the shortcuts overlay
//
// **A and R still open their confirmation dialogs.** The keyboard is a faster
// way to reach the same action, never a way around the confirmation — a
// rejection carries a reason the other person is told, and a keystroke that
// skipped that would be a rejection nobody wrote.
//
// **Typing is never intercepted.** Every handler bails when the event came
// from an input, a textarea, a select or anything `contentEditable`, so "j" in
// a search box is a letter and not a navigation.
import { useCallback, useEffect } from "react";

const TYPING = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/** True when the keystroke belongs to whatever the user is typing into. */
export function isTyping(e) {
    const el = e.target;
    if (!el) return false;
    if (TYPING.has(el.tagName)) return true;
    if (el.isContentEditable) return true;
    // A Radix dialog or sheet takes the keyboard while it is open; its own
    // handlers own Esc and Tab, and the list underneath must not also react.
    return Boolean(el.closest?.("[role='dialog']"));
}

/**
 * @param {object}   o
 * @param {number}   o.count      how many rows there are
 * @param {number}   o.focused    the focused index, or -1
 * @param {Function} o.setFocused
 * @param {Function} o.onOpen     Enter
 * @param {Function} [o.onApprove] A
 * @param {Function} [o.onReject]  R
 * @param {Function} [o.onEscape]  Esc
 * @param {Function} [o.onHelp]    ?
 * @param {boolean}  [o.enabled]   false while a dialog owns the keyboard
 */
export function useTableKeys({
    count,
    focused,
    setFocused,
    onOpen,
    onApprove,
    onReject,
    onEscape,
    onHelp,
    enabled = true,
}) {
    const move = useCallback(
        (delta) => {
            if (!count) return;
            setFocused((i) => {
                // From nothing, ↓ goes to the first row and ↑ to the last —
                // which is what somebody arriving with the keyboard expects,
                // rather than both landing on row one.
                if (i < 0) return delta > 0 ? 0 : count - 1;
                return Math.min(count - 1, Math.max(0, i + delta));
            });
        },
        [count, setFocused],
    );

    useEffect(() => {
        if (!enabled) return undefined;
        const onKey = (e) => {
            if (e.metaKey || e.ctrlKey || e.altKey) return;
            if (e.key === "?" && !isTyping(e)) {
                e.preventDefault();
                onHelp?.();
                return;
            }
            if (e.key === "Escape") {
                // Esc is allowed to reach a dialog; `isTyping` already covers
                // that case, so anything arriving here is the list's.
                if (isTyping(e)) return;
                onEscape?.();
                return;
            }
            if (isTyping(e)) return;

            switch (e.key) {
                case "ArrowDown":
                case "j":
                    e.preventDefault();
                    move(1);
                    break;
                case "ArrowUp":
                case "k":
                    e.preventDefault();
                    move(-1);
                    break;
                case "Enter":
                    if (focused >= 0) {
                        e.preventDefault();
                        onOpen?.(focused);
                    }
                    break;
                case "a":
                case "A":
                    if (focused >= 0 && onApprove) {
                        e.preventDefault();
                        onApprove(focused);
                    }
                    break;
                case "r":
                case "R":
                    if (focused >= 0 && onReject) {
                        e.preventDefault();
                        onReject(focused);
                    }
                    break;
                default:
                    break;
            }
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [enabled, focused, move, onOpen, onApprove, onReject, onEscape, onHelp]);

    // Keep the focused row on screen when the keyboard moved it. `nearest`
    // rather than `center`, so a row already visible does not jump the list.
    useEffect(() => {
        if (focused < 0) return;
        document
            .querySelector(`[data-row-index="${focused}"]`)
            ?.scrollIntoView({ block: "nearest" });
    }, [focused]);

    return { move };
}

export default useTableKeys;
