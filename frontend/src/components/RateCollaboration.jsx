// Saying how it went, once it has.
//
// **One component, both directions.** The runner rates the creator and the
// creator rates the experience, and the server decides which side the caller
// is on — so this never asks what role is looking, the same rule the shared
// application screen holds. What differs is one sentence of copy, taken from
// the side the server named.
//
// **It renders nothing until the collaboration closes**, because rating work
// still in flight is rating a prediction — and worse, a score sitting on the
// record while the person being scored still has to be worked with is leverage
// rather than a record.
import React, { useCallback, useEffect, useState } from "react";
import { Loader2, Star } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { RATINGS as IDS } from "@/constants/testIds";

/** What each side is being asked about, in their own words. */
const PROMPT = {
    runner: {
        title: "How did they do?",
        blurb:
            "Turning up, the work, and how easy it was to sort out. Only the WeAre team sees this — it is not on their profile and they never see the score.",
        placeholder: "e.g. On time, brought a tripod, sent the cut the same night.",
    },
    creator: {
        title: "How was this campaign?",
        blurb:
            "The brief, the venue, and whether it went the way you were told it would. Only the WeAre team sees this — the brand never sees your score.",
        placeholder: "e.g. Brief was clear, but the venue wasn't expecting me.",
    },
};

const Stars = ({ value, onChange, disabled, testid }) => (
    <div data-testid={testid} className="flex gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
            <button
                key={n}
                type="button"
                disabled={disabled}
                onClick={() => onChange(n)}
                aria-pressed={value === n}
                aria-label={`${n} out of 5`}
                data-testid={IDS.star(n)}
                className={
                    "min-h-[2.75rem] min-w-[2.75rem] rounded transition-colors duration-150 " +
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 " +
                    (value >= n ? "text-ember-500" : "text-muted-foreground hover:text-foreground")
                }
            >
                <Star
                    aria-hidden="true"
                    className="mx-auto h-5 w-5"
                    fill={value >= n ? "currentColor" : "none"}
                />
            </button>
        ))}
    </div>
);

export default function RateCollaboration({ collabId }) {
    const [data, setData] = useState(null);
    const [score, setScore] = useState(0);
    const [note, setNote] = useState("");
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data: payload } = await api.get(`/ratings/${collabId}`);
            setData(payload);
            const mine = payload.ratings?.[payload.side];
            if (mine) {
                setScore(mine.score);
                setNote(mine.note || "");
            }
        } catch {
            // A panel, not the page. Failing to read it must not cost somebody
            // the collaboration screen it sits at the bottom of.
            setData({ can_rate: false, ratings: {} });
        }
    }, [collabId]);

    useEffect(() => {
        load();
    }, [load]);

    if (!data?.can_rate && !data?.ratings?.[data?.side]) return null;

    const side = data.side || "runner";
    const copy = PROMPT[side] || PROMPT.runner;
    const existing = data.ratings?.[side];

    const submit = async () => {
        if (!score) return;
        setBusy(true);
        try {
            await api.post(`/ratings/${collabId}`, { score, note: note.trim() || null });
            notifySuccess(existing ? "Rating updated" : "Thanks — noted");
            await load();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be saved." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <section
            data-testid={IDS.panel}
            className="rounded-md border border-white/10 bg-card p-5 grain-surface"
        >
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {copy.title}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{copy.blurb}</p>

            <div className="mt-4">
                <Stars
                    value={score}
                    onChange={setScore}
                    disabled={busy}
                    testid={IDS.stars}
                />
            </div>

            <Textarea
                rows={2}
                maxLength={1000}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={copy.placeholder}
                data-testid={IDS.note}
                className="mt-4 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
            />

            <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button
                    onClick={submit}
                    disabled={busy || !score}
                    data-testid={IDS.submit}
                    className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600"
                >
                    {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {/* **Changeable, and the button says so.** A rating is an
                        opinion, and one that cannot be revised after the
                        payment landed late describes a moment rather than the
                        collaboration. */}
                    {existing ? "Update" : "Save"}
                </Button>
                {existing && (
                    <p data-testid={IDS.existing} className="text-xs text-muted-foreground">
                        You rated this {existing.score} out of 5. You can change it.
                    </p>
                )}
            </div>
        </section>
    );
}
