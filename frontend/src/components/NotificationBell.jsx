import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";

const formatWhen = (iso) => {
    if (!iso) return "";
    try {
        const then = new Date(iso);
        const mins = Math.round((Date.now() - then.getTime()) / 60000);
        if (mins < 1) return "just now";
        if (mins < 60) return `${mins}m ago`;
        if (mins < 24 * 60) return `${Math.round(mins / 60)}h ago`;
        return then.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
    } catch {
        return "";
    }
};

/**
 * Every state change now writes a notification. This is where a creator finds
 * out they were accepted, or that their slot moved, without refreshing a
 * dashboard and guessing.
 */
export const NotificationBell = () => {
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const [items, setItems] = useState(null);
    const [unread, setUnread] = useState(0);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/notifications");
            setItems(data.notifications || []);
            setUnread(data.unread || 0);
        } catch {
            setItems([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const onOpenChange = async (v) => {
        setOpen(v);
        if (v) {
            await load();
            // Opening the panel is the read receipt.
            try {
                await api.post("/notifications/read");
                setUnread(0);
            } catch {
                /* the list is still readable if this fails */
            }
        }
    };

    const go = (n) => {
        setOpen(false);
        if (n.link) navigate(n.link);
    };

    return (
        <Popover open={open} onOpenChange={onOpenChange}>
            <PopoverTrigger asChild>
                <button
                    type="button"
                    data-testid="nav-notifications-btn"
                    aria-label={
                        unread > 0
                            ? `Notifications, ${unread} unread`
                            : "Notifications"
                    }
                    className="relative grid h-11 w-11 place-items-center rounded-full text-muted-foreground transition-colors duration-200 hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:h-9 md:w-9"
                >
                    <Bell className="h-4 w-4" />
                    {unread > 0 && (
                        <span
                            data-testid="nav-notifications-badge"
                            className="absolute right-0.5 top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-ember-500 px-1 text-[9px] font-semibold text-black"
                        >
                            {unread > 9 ? "9+" : unread}
                        </span>
                    )}
                </button>
            </PopoverTrigger>
            <PopoverContent
                align="end"
                data-testid="nav-notifications-panel"
                className="w-80 rounded-md border-white/10 bg-card p-0 grain-surface"
            >
                <div className="border-b border-white/10 px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                        Notifications
                    </p>
                </div>
                {items === null ? (
                    <div className="grid place-items-center py-10 text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                    </div>
                ) : items.length === 0 ? (
                    <p
                        data-testid="nav-notifications-empty"
                        className="px-4 py-8 text-center text-sm text-muted-foreground"
                    >
                        Nothing yet. We'll tell you here — and on WhatsApp — as things
                        move.
                    </p>
                ) : (
                    <ul className="max-h-96 divide-y divide-white/10 overflow-y-auto">
                        {items.map((n) => (
                            <li key={n.id}>
                                <button
                                    type="button"
                                    onClick={() => go(n)}
                                    data-testid={`notification-${n.id}`}
                                    className="w-full px-4 py-3 text-left transition-colors duration-200 hover:bg-white/5"
                                >
                                    <div className="flex items-baseline justify-between gap-3">
                                        <span className="text-sm font-medium text-foreground">
                                            {n.title}
                                        </span>
                                        <span className="flex-none text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                                            {formatWhen(n.created_at)}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                                        {n.body}
                                    </p>
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </PopoverContent>
        </Popover>
    );
};
