// The brand's days and hours, read back to whoever has to work around them.
//
// One component for the creator deciding whether to apply, the creator picking
// a time, and the manager building slots — because all three are answering the
// same question and the three of them disagreeing about it is how somebody
// turns up on a Monday.
//
// Renders nothing when the campaign said nothing, which is most of them. An
// empty box headed "Availability" is worse than no box: it reads as a fact
// about the venue rather than a question nobody answered.
import React from "react";
import { CalendarClock } from "lucide-react";

import { SCHEDULING as IDS } from "@/constants/testIds";
import {
    hasSchedulingPreferences,
    openDayLabels,
    windowLabel,
} from "@/lib/shootWindows";

export default function ShootWindowNote({ campaign, className = "" }) {
    if (!hasSchedulingPreferences(campaign)) return null;

    const open = openDayLabels(campaign.restricted_days);
    const windows = campaign.shoot_windows || [];

    return (
        <div
            data-testid={IDS.summary}
            className={
                "rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm leading-relaxed " +
                className
            }
        >
            <p className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-ember-500">
                <CalendarClock className="h-3.5 w-3.5" />
                When it shoots
            </p>
            {(campaign.restricted_days || []).length > 0 && (
                <p data-testid={IDS.openDays} className="mt-2 text-muted-foreground">
                    {/* The positive, always. "Not Mondays, not Tuesdays" is a
                        list to invert in your head; "Wed to Sun" is a fact. */}
                    {open.length === 1 ? `${open[0]}s only.` : `${open.join(", ")}.`}
                </p>
            )}
            {windows.length > 0 && (
                <p data-testid={IDS.windows} className="mt-1 text-muted-foreground">
                    {windows.map(windowLabel).join(" · ")} (IST)
                </p>
            )}
        </div>
    );
}
