// "View as" — the support tool, from wherever the person is on screen.
//
// It asks first. Starting a view-as session is audited with the target's name
// and puts the admin into a read-only session where the console is no longer
// reachable, and none of that should happen because somebody's finger slipped
// next to Suspend.
import React, { useState } from "react";
import { Eye, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { IMPERSONATION as IDS } from "@/constants/testIds";

/**
 * @param userId  who to look as
 * @param name    what to call them in the confirmation
 * @param role    used only in the copy, so the admin knows which app they land in
 */
export function ViewAsButton({ userId, name, role, disabled }) {
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);

    const start = async () => {
        setBusy(true);
        try {
            await api.post(`/admin/impersonate/${userId}`);
            // A full navigation, not a router push. Every page currently
            // mounted holds data loaded as the admin; re-rendering with a new
            // identity over the top of it would put one person's numbers on
            // another person's screen. This also re-reads /auth/me, which is
            // what raises the banner.
            window.location.assign(
                role === "campaign_manager" ? "/manager" : "/dashboard",
            );
        } catch (err) {
            notifyError(err);
            setBusy(false);
            setOpen(false);
        }
    };

    return (
        <>
            <Button
                variant="outline"
                disabled={disabled || !userId}
                onClick={() => setOpen(true)}
                data-testid={IDS.start(userId)}
                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
            >
                <Eye className="mr-2 h-4 w-4" />
                View as
            </Button>

            <AlertDialog open={open} onOpenChange={setOpen}>
                <AlertDialogContent className="rounded-md border border-white/10 bg-card">
                    <AlertDialogHeader>
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            View as
                        </p>
                        <AlertDialogTitle className="mt-3 font-serif text-2xl leading-tight">
                            {name || "This user"}
                        </AlertDialogTitle>
                        <AlertDialogDescription className="mt-2 space-y-3 text-sm leading-relaxed text-muted-foreground">
                            <span className="block">
                                You'll see the app exactly as they do. It is{" "}
                                <span className="text-foreground">read-only</span> — the
                                server refuses anything that would change data, so you can
                                click freely.
                            </span>
                            <span className="block">
                                This is written to the audit log with their name, and the
                                session ends by itself. The admin console isn't reachable
                                until you stop.
                            </span>
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter className="gap-2">
                        <AlertDialogCancel className="rounded-full border-white/15 bg-transparent hover:bg-white/5">
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            onClick={(e) => {
                                e.preventDefault();
                                start();
                            }}
                            disabled={busy}
                            data-testid={IDS.start("confirm")}
                            className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {busy ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Starting…
                                </>
                            ) : (
                                "View as them"
                            )}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}

export default ViewAsButton;
