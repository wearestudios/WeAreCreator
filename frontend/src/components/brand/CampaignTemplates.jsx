// Briefing the same thing again.
//
// A brand's second campaign was as much work as its first: every field went
// back in by hand, including the twelve that were identical. A café running a
// tasting every month retyped its own brief twelve times a year.
//
// **Above the form, not beside it.** A template picker below the fields is one
// somebody finds after they have already filled them in, which is the one
// moment it is worth nothing. It renders nothing when a brand has no templates
// yet, because an empty box headed "Start from a template" is a feature
// advertising itself at somebody who has none.
import React, { useCallback, useEffect, useState } from "react";
import { Copy, Loader2, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CAMPAIGN_TEMPLATES as IDS } from "@/constants/testIds";
import { formatCompensation } from "@/lib/compensation";
import { DeliverableSummary } from "@/components/Deliverables";

/**
 * The picker.
 *
 * @param {(fields: object) => void} onUse  Called with the brief block. The
 *   parent fills its own form in — this component knows nothing about the
 *   shape of that form, which is what stops it becoming a second version of it.
 */
export default function CampaignTemplates({ onUse }) {
    const [templates, setTemplates] = useState(null);
    const [busy, setBusy] = useState(null);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/brand/campaign-templates");
            setTemplates(data.templates || []);
        } catch {
            // A shortcut, not the page. Failing to read it must not stop
            // somebody posting a campaign the ordinary way.
            setTemplates([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    if (!templates || templates.length === 0) return null;

    const use = async (template) => {
        setBusy(template.id);
        try {
            // The counter is a separate call because applying a template is a
            // form prefill: the campaign is created by the ordinary POST, with
            // the ordinary validation behind it.
            await api.post(`/brand/campaign-templates/${template.id}/used`);
        } catch {
            // A missed count is not worth losing the prefill over.
        } finally {
            setBusy(null);
        }
        onUse?.(template.brief_fields || {});
        notifySuccess(`Started from “${template.name}”`);
    };

    const remove = async (template) => {
        setBusy(template.id);
        try {
            await api.delete(`/brand/campaign-templates/${template.id}`);
            notifySuccess("Template removed");
            await load();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be removed." });
        } finally {
            setBusy(null);
        }
    };

    return (
        <section data-testid={IDS.picker} className="rounded-md border border-white/10 bg-card p-5">
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                Start from a template
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
                Everything except the dates, filled in. Change what's different.
            </p>

            <ul className="mt-4 space-y-2">
                {templates.map((t) => (
                    <li
                        key={t.id}
                        data-testid={IDS.option(t.id)}
                        className="flex flex-wrap items-center gap-3 rounded border border-white/10 p-3"
                    >
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-sm">{t.name}</p>
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                                {/* Enough to tell two tasting briefs apart
                                    without opening either — and the fee never
                                    without the word beside it. */}
                                <DeliverableSummary campaign={t} />
                                {" · "}
                                {/* `.text` — the formatter returns a block
                                    (text, amount, suffix, isBarter) so callers
                                    can style the figure separately. Rendering
                                    the object itself threw React #31 and took
                                    the whole post-campaign route down. */}
                                {formatCompensation(t).text}
                                {t.used_count > 0 ? ` · used ${t.used_count}×` : ""}
                            </p>
                        </div>
                        <Button
                            size="sm"
                            onClick={() => use(t)}
                            disabled={busy === t.id}
                            data-testid={IDS.use(t.id)}
                            className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                        >
                            {busy === t.id && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            <Copy className="mr-1.5 h-3.5 w-3.5" />
                            Use
                        </Button>
                        <button
                            type="button"
                            onClick={() => remove(t)}
                            disabled={busy === t.id}
                            data-testid={IDS.remove(t.id)}
                            title="Remove this template"
                            className="rounded border border-white/10 p-2 text-muted-foreground transition-colors duration-150 hover:border-destructive/40 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                        >
                            <Trash2 className="h-3.5 w-3.5" />
                            <span className="sr-only">Remove</span>
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
}

/**
 * Keeping a brief's shape under a name, from the campaign it was written on.
 *
 * Deliberately available on a **draft** as well as a finished campaign: the
 * moment somebody realises "we always brief it like this" is while writing
 * one, not months after it ran.
 */
export function SaveAsTemplate({ campaignId, defaultName = "" }) {
    const [open, setOpen] = useState(false);
    const [name, setName] = useState(defaultName);
    const [busy, setBusy] = useState(false);

    const save = async () => {
        if (!name.trim()) return;
        setBusy(true);
        try {
            await api.post(`/brand/campaigns/${campaignId}/save-as-template`, {
                name: name.trim(),
            });
            notifySuccess("Saved as a template");
            setOpen(false);
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be saved." });
        } finally {
            setBusy(false);
        }
    };

    if (!open) {
        return (
            <Button
                variant="outline"
                size="sm"
                onClick={() => setOpen(true)}
                data-testid={IDS.save}
                className="min-h-[2.75rem] border-white/20 bg-transparent sm:min-h-0"
            >
                Save as template
            </Button>
        );
    }

    return (
        <div className="flex flex-wrap items-center gap-2">
            <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Monthly tasting"
                maxLength={80}
                data-testid={IDS.saveName}
                className="h-10 w-56 border-white/10 bg-background/60"
            />
            <Button
                size="sm"
                onClick={save}
                disabled={busy || !name.trim()}
                data-testid={IDS.saveSubmit}
                className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
            >
                {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                Save
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
                Cancel
            </Button>
        </div>
    );
}
