// What the manager needs to know about the network, and nothing more.
//
// Two states worth showing and one worth staying quiet about:
//
//   offline with nothing queued  — say so, because the next tap will queue
//   anything queued             — say how many, and that they are safe
//   online and empty            — say nothing at all
//
// The last one is the important one. A permanent "connected" badge is noise
// that trains the manager to stop looking at this corner of the screen, which
// is the corner that will one day say four check-ins have not gone through.
import React, { useEffect, useState } from "react";
import { CloudOff, RefreshCw, UploadCloud, WifiOff } from "lucide-react";

import { flush, subscribeQueue } from "@/lib/offlineQueue";
import { MANAGER_QUEUE as IDS } from "@/constants/testIds";

export function useOnline() {
    const [online, setOnline] = useState(
        typeof navigator === "undefined" ? true : navigator.onLine !== false,
    );
    useEffect(() => {
        const up = () => setOnline(true);
        const down = () => setOnline(false);
        window.addEventListener("online", up);
        window.addEventListener("offline", down);
        return () => {
            window.removeEventListener("online", up);
            window.removeEventListener("offline", down);
        };
    }, []);
    return online;
}

export function useQueue() {
    const [state, setState] = useState({ pending: 0, labels: [], blocked: false });
    useEffect(() => subscribeQueue(setState), []);
    return state;
}

export default function QueueBanner({ className = "" }) {
    const online = useOnline();
    const { pending, blocked } = useQueue();
    const [syncing, setSyncing] = useState(false);

    if (online && pending === 0) return null;

    const retry = async () => {
        setSyncing(true);
        try {
            await flush({ force: true });
        } finally {
            setSyncing(false);
        }
    };

    // Queued work is the more useful message when there is any: "3 waiting"
    // tells the manager both that the network is down and what it cost.
    const queued = pending > 0;
    const tone = blocked
        ? "border-red-500/30 bg-red-500/10 text-red-200"
        : queued
          ? "border-amber-500/30 bg-amber-500/10 text-amber-200"
          : "border-white/15 bg-white/5 text-muted-foreground";
    const Icon = blocked ? CloudOff : queued ? UploadCloud : WifiOff;

    return (
        <div
            data-testid={IDS.banner}
            data-pending={pending}
            data-online={online ? "true" : "false"}
            role="status"
            className={`flex items-start gap-3 rounded-md border p-4 ${tone} ${className}`}
        >
            <Icon className="mt-0.5 h-4 w-4 flex-none" />
            <div className="min-w-0 flex-1">
                <p data-testid={IDS.message} className="text-sm leading-relaxed">
                    {blocked
                        ? `${pending} ${pending === 1 ? "action" : "actions"} still haven't gone through. They're saved — tell the WeAre team if this doesn't clear.`
                        : queued
                          ? `${pending} ${pending === 1 ? "action is" : "actions are"} waiting to sync. They're saved on this phone and will go through on their own.`
                          : "You're offline. Carry on — check-ins are saved and sent when you're back."}
                </p>
                {queued && (
                    <button
                        type="button"
                        onClick={retry}
                        disabled={syncing}
                        data-testid={IDS.retry}
                        className="mt-3 inline-flex min-h-[2.75rem] items-center gap-2 rounded-full border border-current/30 px-4 text-xs uppercase tracking-[0.15em] opacity-90 transition-opacity duration-200 hover:opacity-100 disabled:opacity-60"
                    >
                        <RefreshCw className={"h-3.5 w-3.5 " + (syncing ? "animate-spin" : "")} />
                        {syncing ? "Syncing…" : "Try now"}
                    </button>
                )}
            </div>
        </div>
    );
}
