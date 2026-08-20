// Cmd+K / Ctrl+K — find anyone, fast.
//
// Built for one moment: somebody messages us mid-campaign and we have thirty
// seconds to work out who they are and what they are on. That shapes it more
// than anything else here does:
//
//   - a bare phone number has to work, because that is what a WhatsApp message
//     arrives as;
//   - results say which kind of thing each one is, rather than leaving the
//     reader to infer it from the shape of the row;
//   - it is entirely keyboard-driven, because the hand that opened it with a
//     shortcut has not gone back to the mouse.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, CornerDownLeft, Search, Sparkles, Users } from "lucide-react";

import { api } from "@/lib/api";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { COMMAND_PALETTE as IDS } from "@/constants/testIds";

const GROUP_ICON = { creators: Users, brands: Building2, campaigns: Sparkles };

/** The server's floor, repeated so the UI can explain itself before a round trip. */
const MIN_CHARS = 2;

export function CommandPalette() {
    const [open, setOpen] = useState(false);
    const [q, setQ] = useState("");
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [cursor, setCursor] = useState(0);
    const navigate = useNavigate();
    const inputRef = useRef(null);
    const listRef = useRef(null);
    // Guards against a slow response for an old query landing after a fast one
    // for a newer query and overwriting it.
    const seq = useRef(0);

    useEffect(() => {
        const onKey = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setOpen((v) => !v);
            }
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, []);

    useEffect(() => {
        if (open) {
            setQ("");
            setData(null);
            setCursor(0);
        }
    }, [open]);

    useEffect(() => {
        const term = q.trim();
        if (term.length < MIN_CHARS) {
            setData(null);
            setLoading(false);
            return undefined;
        }
        setLoading(true);
        const mine = ++seq.current;
        // Short debounce: long enough to skip the middle of a typed word, short
        // enough that the list feels attached to the keyboard.
        const t = setTimeout(async () => {
            try {
                const { data } = await api.get("/admin/search", { params: { q: term } });
                if (seq.current === mine) {
                    setData(data);
                    setCursor(0);
                }
            } catch {
                if (seq.current === mine) setData({ groups: [], total: 0 });
            } finally {
                if (seq.current === mine) setLoading(false);
            }
        }, 180);
        return () => clearTimeout(t);
    }, [q]);

    // The grouped results flattened into the order the arrow keys walk. One
    // list, so "down" never has to know about group boundaries.
    const flat = useMemo(() => {
        const out = [];
        (data?.groups || []).forEach((g) =>
            g.items.forEach((item) => out.push({ ...item, group: g.key, groupLabel: g.label })),
        );
        return out;
    }, [data]);

    const go = useCallback(
        (item) => {
            if (!item) return;
            setOpen(false);
            navigate(item.href);
        },
        [navigate],
    );

    const onKeyDown = (e) => {
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setCursor((c) => (flat.length ? (c + 1) % flat.length : 0));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setCursor((c) => (flat.length ? (c - 1 + flat.length) % flat.length : 0));
        } else if (e.key === "Enter") {
            e.preventDefault();
            go(flat[cursor]);
        }
        // Escape is Radix's; it closes the dialog.
    };

    // Keep the highlighted row in view when the arrows walk past the fold.
    useEffect(() => {
        listRef.current
            ?.querySelector('[data-active="true"]')
            ?.scrollIntoView({ block: "nearest" });
    }, [cursor]);

    const term = q.trim();

    return (
        <>
            {/* The visible way in, for people who do not know the shortcut.
                The shortcut is printed on it, which is how they learn it. */}
            <button
                type="button"
                onClick={() => setOpen(true)}
                data-testid={IDS.trigger}
                className="inline-flex min-h-[2.75rem] w-full items-center gap-2.5 rounded-md border border-white/10 bg-card px-3.5 text-sm text-muted-foreground transition-colors duration-150 hover:border-white/25 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0 md:h-10 md:w-72"
            >
                <Search className="h-4 w-4 flex-none" />
                <span className="min-w-0 flex-1 truncate text-left">
                    Search everything
                </span>
                <kbd className="hidden flex-none rounded border border-white/15 px-1.5 py-0.5 font-sans text-[10px] tracking-wider text-muted-foreground md:inline">
                    ⌘K
                </kbd>
            </button>

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent
                    data-testid={IDS.dialog}
                    aria-describedby={undefined}
                    // Anchored high rather than centred: the list grows
                    // downwards, and a centred box jumps as results arrive.
                    className="top-[8%] max-w-xl translate-y-0 gap-0 overflow-hidden rounded-md border border-white/10 bg-card p-0"
                >
                    <DialogTitle className="sr-only">Search everything</DialogTitle>

                    <div className="flex items-center gap-3 border-b border-white/10 px-4">
                        <Search className="h-4 w-4 flex-none text-muted-foreground" />
                        <input
                            ref={inputRef}
                            autoFocus
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            onKeyDown={onKeyDown}
                            data-testid={IDS.input}
                            aria-label="Search creators, brands, campaigns and phone numbers"
                            placeholder="Name, business, campaign, or a phone number…"
                            className="h-14 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                        />
                    </div>

                    <div ref={listRef} className="max-h-[60vh] overflow-y-auto">
                        {term.length < MIN_CHARS ? (
                            <p
                                data-testid={IDS.hint}
                                className="px-4 py-8 text-sm leading-relaxed text-muted-foreground"
                            >
                                Type at least {MIN_CHARS} characters. A phone number works —
                                paste the one they messaged from, with or without the country
                                code.
                            </p>
                        ) : loading && !data ? (
                            <p className="px-4 py-8 text-sm text-muted-foreground">Looking…</p>
                        ) : flat.length === 0 ? (
                            <p
                                data-testid={IDS.empty}
                                className="px-4 py-8 text-sm leading-relaxed text-muted-foreground"
                            >
                                Nothing matches “{term}”.
                                {data && data.matched_phone === false && /^\+?[\d\s-]+$/.test(term)
                                    ? " That looks like a number — a phone match needs the last 10 digits."
                                    : " Try a name, a business, or a campaign title."}
                            </p>
                        ) : (
                            (data?.groups || []).map((g) => {
                                const Icon = GROUP_ICON[g.key] || Search;
                                return (
                                    <div key={g.key} data-testid={IDS.group(g.key)}>
                                        <p className="sticky top-0 bg-card/95 px-4 py-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground backdrop-blur-sm">
                                            {g.label}
                                            <span className="ml-2 text-ember-500">
                                                {g.items.length}
                                            </span>
                                        </p>
                                        <ul>
                                            {g.items.map((item) => {
                                                const i = flat.findIndex(
                                                    (f) => f.group === g.key && f.id === item.id,
                                                );
                                                const active = i === cursor;
                                                return (
                                                    <li key={item.id}>
                                                        <button
                                                            type="button"
                                                            data-active={active}
                                                            data-testid={IDS.result(item.id)}
                                                            onMouseEnter={() => setCursor(i)}
                                                            onClick={() => go(item)}
                                                            className={
                                                                "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 " +
                                                                (active ? "bg-ember-500/10" : "")
                                                            }
                                                        >
                                                            <Icon
                                                                className={
                                                                    "h-4 w-4 flex-none " +
                                                                    (active
                                                                        ? "text-ember-500"
                                                                        : "text-muted-foreground")
                                                                }
                                                            />
                                                            <span className="min-w-0 flex-1">
                                                                <span className="block truncate text-sm">
                                                                    {item.label}
                                                                </span>
                                                                {item.sublabel && (
                                                                    <span className="block truncate text-sm text-muted-foreground">
                                                                        {item.sublabel}
                                                                    </span>
                                                                )}
                                                            </span>
                                                            {item.badge && (
                                                                <span className="flex-none rounded-full border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                                                                    {item.badge}
                                                                </span>
                                                            )}
                                                            {active && (
                                                                <CornerDownLeft className="h-3.5 w-3.5 flex-none text-ember-500" />
                                                            )}
                                                        </button>
                                                    </li>
                                                );
                                            })}
                                        </ul>
                                    </div>
                                );
                            })
                        )}
                    </div>

                    <div className="flex items-center gap-4 border-t border-white/10 px-4 py-2.5 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                        <span>↑↓ move</span>
                        <span>⏎ open</span>
                        <span>esc close</span>
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
}

export default CommandPalette;
