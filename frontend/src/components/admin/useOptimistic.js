// Optimistic list mutations with a real rollback.
//
// A review queue is worked through at speed: you look, you decide, you move on.
// Waiting for a round trip between each one turns a two-minute job into ten, so
// the row leaves the list the moment you act. If the request then fails, the
// row goes back exactly where it was — not appended to the end, which would
// quietly reorder somebody's queue — and the error says so.
import { useCallback, useState } from "react";
import { toast } from "sonner";
import { formatApiError } from "@/lib/api";

export function useOptimisticList(initial = null) {
    const [rows, setRows] = useState(initial);
    // Which ids are mid-flight. State rather than a ref, because the row's
    // buttons have to actually re-render as disabled — a ref would leave them
    // live and take the second tap.
    const [busy, setBusy] = useState(() => new Set());

    const removeOptimistically = useCallback(
        async (id, request, { successMessage, onDone } = {}) => {
            let alreadyRunning = false;
            setBusy((current) => {
                if (current.has(id)) {
                    alreadyRunning = true;
                    return current;
                }
                return new Set(current).add(id);
            });
            if (alreadyRunning) return false;

            let snapshot = null;
            let index = -1;
            setRows((current) => {
                if (!current) return current;
                index = current.findIndex((r) => (r.id ?? r.user_id) === id);
                if (index === -1) return current;
                snapshot = current[index];
                return current.filter((_, i) => i !== index);
            });

            try {
                const result = await request();
                if (successMessage) toast.success(successMessage);
                onDone?.(result);
                return true;
            } catch (e) {
                // Back into its own place, so the queue reads the same as before.
                if (snapshot) {
                    setRows((current) => {
                        if (!current) return current;
                        const restored = [...current];
                        restored.splice(Math.min(index, restored.length), 0, snapshot);
                        return restored;
                    });
                }
                toast.error(formatApiError(e));
                return false;
            } finally {
                setBusy((current) => {
                    const next = new Set(current);
                    next.delete(id);
                    return next;
                });
            }
        },
        [],
    );

    const isBusy = useCallback((id) => busy.has(id), [busy]);

    return { rows, setRows, removeOptimistically, isBusy };
}
