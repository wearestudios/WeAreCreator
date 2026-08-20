// Name the current filter combination.
//
// The named set appears under its section in the sidebar and outlives the
// session, unlike the filters themselves — those are a working context and are
// gone tomorrow. Naming one is the deliberate act that earns the persistence.
//
// One component rather than one per list, because "save filter" behaving
// differently on two screens is worse than not having it.
import React, { useState } from "react";
import { X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { CALM, FOCUS, TEXT } from "@/components/admin/console/tokens";
import { ADMIN_TABLE as IDS } from "@/constants/testIds";

export function SaveFilter({ onSave, disabled, savedNames = [] }) {
    const [open, setOpen] = useState(false);
    const [name, setName] = useState("");

    if (!open) {
        return (
            <button
                type="button"
                disabled={disabled}
                onClick={() => setOpen(true)}
                data-testid={IDS.saveFilter}
                // A disabled control with no explanation is a support ticket.
                title={disabled ? "Set a filter first" : "Save this filter set"}
                className={`rounded border border-white/10 px-2 py-1 ${TEXT.meta} ${CALM} hover:bg-white/5 disabled:opacity-40 ${FOCUS}`}
            >
                Save filter
            </button>
        );
    }

    return (
        <form
            onSubmit={(e) => {
                e.preventDefault();
                onSave(name);
                setName("");
                setOpen(false);
            }}
            className="flex items-center gap-1"
        >
            <Input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={savedNames.length ? "Name, or overwrite" : "Name this set"}
                aria-label="Name this filter set"
                data-testid={IDS.saveFilterName}
                className={`h-8 w-44 border-white/10 bg-transparent ${TEXT.body}`}
            />
            <button
                type="submit"
                data-testid={IDS.saveFilterConfirm}
                className={`rounded border border-ember-500/40 bg-ember-500/10 px-2 py-1 ${TEXT.meta} text-ember-500 ${CALM} hover:bg-ember-500/20 ${FOCUS}`}
            >
                Save
            </button>
            <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Cancel"
                className={`grid h-7 w-7 place-items-center rounded ${CALM} text-muted-foreground hover:bg-white/5 ${FOCUS}`}
            >
                <X className="h-3.5 w-3.5" />
            </button>
        </form>
    );
}

export default SaveFilter;
