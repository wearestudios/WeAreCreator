// Whether barter briefs appear in this creator's feed. Off unless they say so.
//
// The public site leads creators with "Paid briefs", so a feed full of briefs
// that pay a meal would make that a sentence the product does not keep. The
// server holds the rule (`_shows_barter_briefs` on the feed, the suggestions
// and the filter options); this is the switch, on the feed, where the choice
// is actually being made. The words are the setting's own name, so what a
// creator turns on is exactly what they were told.
import React, { useEffect, useState } from "react";

import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { BARTER } from "@/constants/testIds";

export const BARTER_SETTING_LABEL = "Show barter briefs (a meal or product instead of a fee)";

export default function BarterFeedToggle({ onChanged, className = "" }) {
    const [on, setOn] = useState(null);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        let gone = false;
        api.get("/creator/profile")
            .then(({ data }) => {
                if (!gone) setOn(Boolean(data?.show_barter_briefs ?? data?.profile?.show_barter_briefs));
            })
            .catch(() => !gone && setOn(false));
        return () => {
            gone = true;
        };
    }, []);

    const change = async (next) => {
        const before = on;
        setOn(next);
        setSaving(true);
        try {
            await api.put("/creator/profile", { show_barter_briefs: next });
            onChanged?.(next);
        } catch (err) {
            setOn(before);
            notifyError(err, { fallback: "That didn't save." });
        } finally {
            setSaving(false);
        }
    };

    return (
        <label className={`flex items-start gap-3 text-meta text-muted-foreground ${className}`}>
            <Switch
                data-testid={BARTER.feedToggle}
                checked={Boolean(on)}
                disabled={on === null || saving}
                onCheckedChange={change}
                aria-describedby="barter-feed-toggle-note"
            />
            <span>
                <span className="font-medium text-foreground">{BARTER_SETTING_LABEL}</span>
                <span id="barter-feed-toggle-note" data-testid={BARTER.feedToggleNote} className="block">
                    {on
                        ? "Barter briefs are in your feed, each marked Barter."
                        : "Off — your feed shows paid briefs only. A brand can still invite you to a barter brief."}
                </span>
            </span>
        </label>
    );
}
