// The numbers this operation runs on.
//
// Four groups, all the same kind of thing: an operating decision that depends
// on how many people are working this month, what the accounts team has agreed
// with a client, and how much slack the business has — and a number that needs
// a deploy to change is one that never changes. It gets argued about in a
// meeting and then lived with.
//
// The response targets are their own screen-sized thing and keep their own
// component; the other three are one number each, which is what `NumberSetting`
// is for. Three near-copies of the same form is how they drift apart.
//
// **Admin-only, and deliberately not `CONSOLE_ROLES`.** Somebody whose queue
// is being measured is the wrong person to move the line, and somebody whose
// brand owes us money is the wrong person to set the payment terms.
import React, { useCallback, useEffect, useState } from "react";
import { Loader2, RotateCcw, SlidersHorizontal } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ADMIN_SETTINGS as IDS } from "@/constants/testIds";
import SlaSettings from "./SlaSettings";
import { CALM, PANEL, TEXT } from "./console/tokens";

/**
 * One stored number, with a way back to what it started as.
 *
 * @param {string} props.field  Which key in the GET/PUT body holds it. The
 *   three endpoints disagree (`days`, `days`, `limit`), so it is named rather
 *   than guessed — a settings form that silently posts the wrong key saves
 *   nothing and says it saved.
 */
function NumberSetting({ settingKey, endpoint, field, label, blurb, unit }) {
    const [data, setData] = useState(null);
    const [value, setValue] = useState("");
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data: payload } = await api.get(endpoint);
            setData(payload);
            setValue(String(payload[field]));
        } catch (err) {
            notifyError(err, { fallback: `${label} couldn't load.` });
        }
    }, [endpoint, field, label]);

    useEffect(() => {
        load();
    }, [load]);

    const min = data?.min ?? 1;
    const max = data?.max ?? 10000;
    const changed = data ? String(data[field]) !== String(value).trim() : false;
    const isDefault = data ? String(value) === String(data.default) : true;

    const save = async () => {
        const n = Number(value);
        if (!Number.isInteger(n) || n < min || n > max) {
            notifyError(null, {
                fallback: `${label} must be a whole number between ${min} and ${max}.`,
            });
            return;
        }
        setBusy(true);
        try {
            const { data: saved } = await api.put(endpoint, { [field]: n });
            setData(saved);
            setValue(String(saved[field]));
            notifySuccess(`${label} updated`);
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be saved." });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            data-testid={IDS.group(settingKey)}
            className={`${PANEL} flex flex-wrap items-center gap-x-4 gap-y-2 p-4`}
        >
            {/* **The label renders before the number.** The row used to be
                replaced wholesale by a fixed-height skeleton, and a guessed
                height against real content is a shift every time the guess is
                wrong — measured at 0.11 CLS across three of these. Only the
                control waits, and it occupies its own box while it does. */}
            <div className="min-w-0 flex-1">
                <p className="text-sm">{label}</p>
                <p className={`mt-0.5 ${TEXT.meta} text-muted-foreground`}>{blurb}</p>
            </div>

            <div className="flex items-center gap-2">
                <Input
                    type="number"
                    inputMode="numeric"
                    min={min}
                    max={max}
                    disabled={!data}
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    data-testid={IDS.input(settingKey)}
                    className="h-9 w-24 border-white/10 bg-background/60 text-right tabular-nums"
                />
                <span className={`${TEXT.meta} w-16 text-muted-foreground`}>{unit}</span>
                <button
                    type="button"
                    disabled={!data || isDefault}
                    onClick={() => setValue(String(data.default))}
                    title={data ? `Back to the default, ${data.default} ${unit}` : "Back to the default"}
                    className={`rounded border border-white/10 p-1.5 ${CALM} ${
                        isDefault
                            ? "opacity-30"
                            : "text-muted-foreground hover:border-ember-500/40 hover:text-ember-500"
                    }`}
                >
                    <RotateCcw className="h-3.5 w-3.5" />
                    <span className="sr-only">Back to default</span>
                </button>
                <Button
                    size="sm"
                    onClick={save}
                    disabled={busy || !data || !changed}
                    data-testid={IDS.save(settingKey)}
                    className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                >
                    {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                    Save
                </Button>
            </div>
        </div>
    );
}

export default function PlatformSettings() {
    return (
        <div data-testid={IDS.page} className="space-y-8">
            {/* **The fixed-height section goes first and the variable-height
                one last.** The response targets are one row per target and
                nothing here knows how many that is until they load, so
                anything below them moves when they arrive — measured at 0.19
                CLS, and no skeleton height can be right for a list whose
                length is a server setting. Three single-line rows are a shape
                this page does know, so they go on top and stay put. */}
            <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                    <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
                    <h2 className={`${TEXT.body} font-medium`}>The operating numbers</h2>
                </div>

                <NumberSetting
                    settingKey="verification-validity"
                    endpoint="/admin/settings/verification-validity"
                    field="days"
                    label="How long a verification lasts"
                    // The honest framing: what runs out is our confidence that
                    // a check is still current, not the check itself.
                    blurb="After this, a creator or brand is asked to confirm their details are still right. It is a confirmation, not a re-verification — nothing already running is affected."
                    unit="days"
                />

                <NumberSetting
                    settingKey="payment-terms"
                    endpoint="/admin/settings/payment-terms"
                    field="days"
                    label="How long a brand has to settle an invoice"
                    // **Only new invoices.** Every issued one carries the date
                    // it was already given, so shortening the terms cannot
                    // make a brand late this afternoon for an invoice it was
                    // told it had a fortnight to pay.
                    blurb="From the day it is issued. Changing this applies to invoices issued from now on; the ones already out keep the date they were given."
                    unit="days"
                />

                <NumberSetting
                    settingKey="reschedule-limit"
                    endpoint="/admin/settings/reschedule-limit"
                    field="limit"
                    label="Reschedules before somebody has to approve"
                    blurb="A creator can move a booking this many times on their own. Past it, whoever runs the campaign has to agree — and every one is counted against reliability either way."
                    unit="times"
                />
            </div>

            <SlaSettings />
        </div>
    );
}
