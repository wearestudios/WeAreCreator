// The "?" overlay: what the keyboard does here.
//
// A keyboard flow nobody can discover is a keyboard flow nobody uses. "?" is
// the convention for this, and the overlay is the only place the shortcuts are
// written down — so it is generated from one list rather than typed twice, and
// the list is exported so a test can check the bindings it claims are the
// bindings that exist.
import React from "react";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from "@/components/ui/dialog";
import { DENSITY, PANEL, TEXT } from "@/components/admin/console/tokens";
import { ADMIN_SHORTCUTS as IDS } from "@/constants/testIds";

/** The bindings, in the order somebody learns them. */
export const SHORTCUTS = [
    { keys: ["↑", "↓"], alt: ["k", "j"], what: "Move between rows" },
    { keys: ["Enter"], what: "Open the peek panel on the focused row" },
    { keys: ["A"], what: "Approve — where the row offers it" },
    { keys: ["R"], what: "Reject — opens the reason dialog" },
    { keys: ["Esc"], what: "Close the panel, or clear row focus" },
    { keys: ["⌘", "K"], what: "Search creators, brands, campaigns, phone numbers" },
    { keys: ["?"], what: "This list" },
];

function Key({ children }) {
    return (
        <kbd className={`inline-grid min-w-[1.5rem] place-items-center rounded border border-white/15 bg-white/5 px-1.5 py-0.5 ${TEXT.meta} text-foreground`}>
            {children}
        </kbd>
    );
}

export function ShortcutsOverlay({ open, onOpenChange }) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={IDS.root}
                className={`${PANEL} max-w-lg`}
                aria-describedby={undefined}
            >
                <DialogTitle className={TEXT.heading}>Keyboard</DialogTitle>
                <DialogDescription className="sr-only">
                    Keyboard shortcuts for the admin console
                </DialogDescription>

                <ul className="mt-2">
                    {SHORTCUTS.map((s) => (
                        <li
                            key={s.what}
                            className={`flex items-center justify-between gap-6 border-b border-white/5 ${DENSITY.row}`}
                        >
                            <span className={TEXT.body}>{s.what}</span>
                            <span className="flex shrink-0 items-center gap-1">
                                {s.keys.map((k) => (
                                    <Key key={k}>{k}</Key>
                                ))}
                                {s.alt ? (
                                    <>
                                        <span className={`${TEXT.meta} px-1 text-muted-foreground`}>
                                            or
                                        </span>
                                        {s.alt.map((k) => (
                                            <Key key={k}>{k}</Key>
                                        ))}
                                    </>
                                ) : null}
                            </span>
                        </li>
                    ))}
                </ul>

                <p className={`mt-3 ${TEXT.meta} text-muted-foreground`}>
                    Letters do nothing while you are typing in a field.
                </p>
            </DialogContent>
        </Dialog>
    );
}

export default ShortcutsOverlay;
