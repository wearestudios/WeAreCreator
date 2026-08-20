// What "too long" means, and who gets to say.
//
// **These are operating decisions, not constants.** How long a creator should
// wait for a verification decision depends on how many people are working the
// queue this month, and a target that needs a deploy to change is one that
// never changes — it gets argued about in a meeting and then lived with. So
// they are stored settings with an editor, and the defaults in the code are
// what a fresh install runs on rather than what it is stuck with.
//
// **Admin-only, deliberately, and not `CONSOLE_ROLES`.** An SLA is the
// standard a queue is measured against, and somebody whose queue is being
// measured is the wrong person to be able to move the line. The server holds
// that; this screen simply is not in a scoped console's navigation.
import React, { useCallback, useEffect, useState } from "react";
import { Loader2, RotateCcw, Timer } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ADMIN_SLA as IDS } from "@/constants/testIds";
import { TimeAgo } from "./console/format";
import { CALM, PANEL, TEXT } from "./console/tokens";

/** Hours, said the way somebody thinks about them. */
const inWords = (hours) => {
    if (!hours && hours !== 0) return "";
    if (hours < 48) return `${hours} hours`;
    const days = hours / 24;
    return Number.isInteger(days) ? `${days} days` : `${hours} hours`;
};

export default function SlaSettings() {
    const [data, setData] = useState(null);
    const [form, setForm] = useState({});
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data: payload } = await api.get("/admin/settings/sla");
            setData(payload);
            setForm(
                Object.fromEntries(
                    Object.entries(payload.targets).map(([k, v]) => [k, String(v)])
                )
            );
        } catch (err) {
            notifyError(err, { fallback: "The SLA settings couldn't load." });
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    if (!data) {
        return (
            <div data-testid={IDS.page} className="space-y-4">
                <div className={`${PANEL} h-64 animate-pulse`} />
            </div>
        );
    }

    const { defaults, labels, limits } = data;

    // What is actually different from what is stored. Sending the whole map
    // every time would write nine overrides the moment somebody changes one,
    // and then "back to default" would have nothing left to mean.
    const changed = Object.keys(form).filter(
        (key) => String(data.targets[key]) !== String(form[key]).trim()
    );

    const save = async () => {
        const targets = {};
        for (const key of changed) {
            const value = Number(form[key]);
            if (!Number.isInteger(value) || value < limits.min_hours || value > limits.max_hours) {
                notifyError(null, {
                    fallback: `${labels[key].label} must be a whole number of hours between ${limits.min_hours} and ${limits.max_hours}.`,
                });
                return;
            }
            targets[key] = value;
        }
        setBusy(true);
        try {
            const { data: saved } = await api.put("/admin/settings/sla", { targets });
            setData(saved);
            setForm(
                Object.fromEntries(
                    Object.entries(saved.targets).map(([k, v]) => [k, String(v)])
                )
            );
            notifySuccess("Targets updated");
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be saved." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div data-testid={IDS.page} className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
                <Timer className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>Response targets</h1>
                <p className={`${TEXT.meta} text-muted-foreground`}>
                    How long a record may sit in each state before it is chased and
                    escalated. Changing one takes effect on the next page load — nothing
                    already sent goes out again.
                </p>
            </div>

            <ul className="space-y-2">
                {Object.keys(defaults).map((key) => {
                    const meta = labels[key] || { label: key, blurb: "" };
                    const isDefault = String(form[key]) === String(defaults[key]);
                    return (
                        <li
                            key={key}
                            data-testid={IDS.row(key)}
                            className={`${PANEL} flex flex-wrap items-center gap-x-4 gap-y-2 p-4`}
                        >
                            <div className="min-w-0 flex-1">
                                <p className="text-sm">{meta.label}</p>
                                {/* Half of these measure our delay and half
                                    somebody else's, and an operator setting a
                                    number has to know which. */}
                                <p className={`mt-0.5 ${TEXT.meta} text-muted-foreground`}>
                                    {meta.blurb}
                                </p>
                            </div>

                            <div className="flex items-center gap-2">
                                <Input
                                    type="number"
                                    inputMode="numeric"
                                    min={limits.min_hours}
                                    max={limits.max_hours}
                                    value={form[key] ?? ""}
                                    onChange={(e) =>
                                        setForm((f) => ({ ...f, [key]: e.target.value }))
                                    }
                                    data-testid={IDS.input(key)}
                                    className="h-9 w-24 border-white/10 bg-background/60 text-right tabular-nums"
                                />
                                <span className={`${TEXT.meta} w-20 text-muted-foreground`}>
                                    hrs · {inWords(Number(form[key]))}
                                </span>
                                {/* **A way back.** A settings screen that
                                    cannot tell you what it started as is one
                                    nobody dares touch. */}
                                <button
                                    type="button"
                                    disabled={isDefault}
                                    onClick={() =>
                                        setForm((f) => ({ ...f, [key]: String(defaults[key]) }))
                                    }
                                    data-testid={IDS.reset(key)}
                                    title={`Back to the default, ${inWords(defaults[key])}`}
                                    className={`rounded border border-white/10 p-1.5 ${CALM} ${
                                        isDefault
                                            ? "opacity-30"
                                            : "text-muted-foreground hover:border-ember-500/40 hover:text-ember-500"
                                    }`}
                                >
                                    <RotateCcw className="h-3.5 w-3.5" />
                                    <span className="sr-only">Back to default</span>
                                </button>
                            </div>
                        </li>
                    );
                })}
            </ul>

            <div className="flex flex-wrap items-center gap-3">
                <Button
                    onClick={save}
                    disabled={busy || changed.length === 0}
                    data-testid={IDS.save}
                    className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600"
                >
                    {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {changed.length === 0
                        ? "Nothing changed"
                        : `Save ${changed.length} change${changed.length === 1 ? "" : "s"}`}
                </Button>
                {data.updated_at && (
                    <p className={`${TEXT.meta} text-muted-foreground`}>
                        Last changed by {data.updated_by_name || "somebody"}{" "}
                        <TimeAgo value={data.updated_at} />
                    </p>
                )}
            </div>
        </div>
    );
}
