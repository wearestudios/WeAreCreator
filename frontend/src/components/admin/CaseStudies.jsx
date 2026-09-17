// Turning finished work into the thing that sells the next campaign.
//
// **This is the half that decides whether the feature exists at all.** The
// endpoints could all be perfect and, without a screen, a case study would be
// a chore somebody does in a database client — which means never, which is
// exactly why we had none. So the flow this screen is built around is the one
// that actually happens: a campaign closes, somebody opens this, picks it out
// of a list, and writes two paragraphs. Everything else is already filled in.
//
// Three decisions worth stating:
//
// - **"From a campaign" is the primary action and a blank one is the
//   secondary.** Most case studies are about work we did here, and the
//   prefill is the entire argument for the feature. A blank draft is still
//   offered, because some work predates the platform.
// - **Preview goes through the public projection**, not a second rendering.
//   A preview built any other way is a preview that can disagree with the
//   page, which makes it worse than none.
// - **Publish is disabled when it would 409, and says why.** The server sends
//   `missing_fields` as a list of things in words a person would use, and it
//   is rendered as a list — the rule the brand's verification checklist
//   learned: a greyed-out button with no explanation is how a form becomes a
//   support ticket.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ExternalLink, Eye, Loader2, Plus, Wand2 } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { useOptimisticAction } from "@/lib/useOptimistic";
import { DataTable } from "@/components/admin/console/DataTable";
import { StatusTag } from "@/components/admin/console/StatusTag";
import { PeekPanel } from "@/components/admin/console/PeekPanel";
import { DENSITY, TEXT } from "@/components/admin/console/tokens";
import { relative } from "@/components/admin/console/format";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { CATEGORY_OPTIONS, categoryLabel } from "@/lib/categories";
import { CITY_OPTIONS } from "@/lib/taxonomy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { CASE_STUDIES as IDS } from "@/constants/testIds";

const TYPE_LABELS = {
    launch: "Launch",
    group_event: "Group event",
    personal_table: "Personal table",
};

const field =
    "w-full rounded-md border border-tint/10 bg-tint/[0.03] px-3 py-2 text-sm " +
    "text-foreground outline-none transition-colors duration-150 focus:border-primary/60";

function Row({ label, hint, children }) {
    return (
        <div className="grid gap-1.5">
            <Label className={`${TEXT.meta} uppercase tracking-[0.15em] text-muted-foreground`}>
                {label}
            </Label>
            {children}
            {hint && <p className={`${TEXT.meta} text-muted-foreground/70`}>{hint}</p>}
        </div>
    );
}

/**
 * The editor.
 *
 * Every field is optional to *save* and a named few are required to
 * *publish*, which mirrors the server exactly — `PUT` is a partial save and
 * `POST /publish` is the one that judges. A form that refused to save a
 * half-written approach would be a form nobody could write a case study in
 * over two sittings, which is how long one actually takes.
 */
function Editor({ study, onSaved, onClose }) {
    const [form, setForm] = useState(() => ({ ...study }));
    const [missing, setMissing] = useState([]);
    const [preview, setPreview] = useState(null);
    const { run, pending } = useOptimisticAction();

    useEffect(() => {
        setForm({ ...study });
    }, [study]);

    const set = (key) => (e) =>
        setForm((f) => ({ ...f, [key]: e?.target ? e.target.value : e }));

    const setResult = (key) => (e) =>
        setForm((f) => ({
            ...f,
            results: { ...(f.results || {}), [key]: e.target.value },
        }));

    const save = async () => {
        const ok = await run(
            () =>
                api
                    .put(`/admin/case-studies/${study.id}`, {
                        title: form.title,
                        brand_name: form.brand_name,
                        category: form.category || null,
                        city: form.city || null,
                        challenge: form.challenge,
                        approach: form.approach,
                        headline_result: form.headline_result,
                        results: form.results || {},
                        quote: form.quote || null,
                    })
                    .then(({ data }) => data),
            { onError: (e) => notifyError(formatApiError(e)) },
        );
        if (ok) {
            notifySuccess("Saved");
            onSaved(ok);
        }
    };

    const showPreview = async () => {
        try {
            const { data } = await api.get(`/admin/case-studies/${study.id}/preview`);
            setPreview(data.case_study);
            setMissing(data.missing_fields || []);
        } catch (e) {
            notifyError(formatApiError(e));
        }
    };

    useEffect(() => {
        showPreview();
        // Once per case study: the list is what refreshes after a save.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [study.id]);

    const publish = async () => {
        const ok = await run(
            () =>
                api
                    .post(`/admin/case-studies/${study.id}/publish`)
                    .then(({ data }) => data),
            {
                onError: (e) => {
                    const detail = e?.response?.data?.detail;
                    if (detail?.missing_fields) setMissing(detail.missing_fields);
                    notifyError(formatApiError(e));
                },
            },
        );
        if (ok) {
            notifySuccess("Published");
            onSaved(ok);
        }
    };

    const unpublish = async () => {
        const ok = await run(
            () =>
                api
                    .post(`/admin/case-studies/${study.id}/unpublish`)
                    .then(({ data }) => data),
            { onError: (e) => notifyError(formatApiError(e)) },
        );
        if (ok) {
            notifySuccess("Taken down");
            onSaved(ok);
        }
    };

    const published = study.status === "published";

    return (
        <div className="grid gap-5" data-testid={IDS.editor}>
            <Row label="Title">
                <Input
                    className={field}
                    data-testid={IDS.title}
                    value={form.title || ""}
                    onChange={set("title")}
                />
            </Row>
            <Row label="Brand" hint="Pre-filled from the campaign where there was one.">
                <Input
                    className={field}
                    data-testid={IDS.brand}
                    value={form.brand_name || ""}
                    onChange={set("brand_name")}
                />
            </Row>
            <div className="grid gap-5 sm:grid-cols-2">
                <Row label="Category">
                    <select
                        className={field}
                        data-testid={IDS.category}
                        value={form.category || ""}
                        onChange={set("category")}
                    >
                        <option value="">—</option>
                        {CATEGORY_OPTIONS.map((c) => (
                            <option key={c.value} value={c.value}>
                                {c.label}
                            </option>
                        ))}
                    </select>
                </Row>
                <Row label="City">
                    <select
                        className={field}
                        data-testid={IDS.city}
                        value={form.city || ""}
                        onChange={set("city")}
                    >
                        <option value="">—</option>
                        {CITY_OPTIONS.map((c) => (
                            <option key={c.value} value={c.value}>
                                {c.label}
                            </option>
                        ))}
                    </select>
                </Row>
            </div>

            {/* The two a person has to write. Everything above and below them
                came off the campaign. */}
            <Row
                label="What they needed"
                hint="The brand's problem, in your words rather than theirs."
            >
                <Textarea
                    rows={4}
                    className={field}
                    data-testid={IDS.challenge}
                    value={form.challenge || ""}
                    onChange={set("challenge")}
                />
            </Row>
            <Row label="What we did" hint="How the campaign was actually run.">
                <Textarea
                    rows={4}
                    className={field}
                    data-testid={IDS.approach}
                    value={form.approach || ""}
                    onChange={set("approach")}
                />
            </Row>

            <Row
                label="Headline result"
                hint="Leads the card and the share preview. Beats any number we can compute — 'sold out in four days'."
            >
                <Input
                    className={field}
                    data-testid={IDS.headline}
                    value={form.headline_result || ""}
                    onChange={set("headline_result")}
                />
            </Row>

            <div className="grid gap-5 sm:grid-cols-3">
                <Row label="Reach">
                    <Input
                        type="number"
                        className={field}
                        data-testid={IDS.reach}
                        value={form.results?.reach ?? ""}
                        onChange={setResult("reach")}
                    />
                </Row>
                <Row label="Engagement %">
                    <Input
                        type="number"
                        step="0.01"
                        className={field}
                        data-testid={IDS.engagement}
                        value={form.results?.engagement_rate ?? ""}
                        onChange={setResult("engagement_rate")}
                    />
                </Row>
                <Row label="Pieces">
                    <Input
                        type="number"
                        className={field}
                        data-testid={IDS.pieces}
                        value={form.results?.content_pieces ?? ""}
                        onChange={setResult("content_pieces")}
                    />
                </Row>
            </div>

            {/* The roster is read-only here on purpose: who is on it is
                decided by who delivered the campaign *and* consented, and a
                box an admin can type a name into is a box that gets a name
                typed into it. */}
            <Row
                label="Creators"
                hint="Only creators who opted into public featuring. Withdrawing consent removes them from the live page immediately."
            >
                <p data-testid={IDS.roster} className="text-sm text-muted-foreground">
                    {preview?.creators?.length
                        ? preview.creators
                              .map((c) => c.name || c.instagram_handle)
                              .join(", ")
                        : "Nobody on this campaign has opted in."}
                </p>
            </Row>

            {missing.length > 0 && (
                <div
                    data-testid={IDS.missing}
                    className="rounded-md border border-state-pending/30 bg-state-pending/10 p-4"
                >
                    <p className="text-sm text-state-pending">Before this can go live:</p>
                    <ul className="mt-2 list-disc pl-5 text-sm text-state-pending">
                        {missing.map((m) => (
                            <li key={m}>{m}</li>
                        ))}
                    </ul>
                </div>
            )}

            <div className="flex flex-wrap items-center gap-3 border-t border-tint/10 pt-4">
                <Button onClick={save} disabled={pending} data-testid={IDS.save}>
                    {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save
                </Button>
                {published ? (
                    <Button
                        variant="outline"
                        onClick={unpublish}
                        disabled={pending}
                        data-testid={IDS.unpublish}
                    >
                        Take it down
                    </Button>
                ) : (
                    <Button
                        variant="outline"
                        onClick={publish}
                        // Disabled when it would 409, with the list above
                        // saying what is in the way.
                        disabled={pending || missing.length > 0}
                        data-testid={IDS.publish}
                    >
                        Publish
                    </Button>
                )}
                {study.public_url && published && (
                    <a
                        href={study.public_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={IDS.viewLive}
                        className="inline-flex items-center gap-1.5 text-sm text-primary-ink"
                    >
                        <ExternalLink className="h-3.5 w-3.5" /> View live
                    </a>
                )}
                <button
                    type="button"
                    onClick={onClose}
                    className={`${TEXT.meta} ml-auto text-muted-foreground`}
                >
                    Close
                </button>
            </div>
        </div>
    );
}

export default function CaseStudies() {
    const [rows, setRows] = useState(null);
    const [focused, setFocused] = useState(-1);
    const [editing, setEditing] = useState(null);
    const [picking, setPicking] = useState(false);
    const [closed, setClosed] = useState([]);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/admin/case-studies");
            setRows(data.case_studies || []);
        } catch (e) {
            notifyError(formatApiError(e));
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const openPicker = async () => {
        setPicking(true);
        try {
            // The campaigns a case study can be written about: the ones that
            // finished. Anything still running would quote numbers that are
            // still moving, and the server refuses it anyway.
            const { data } = await api.get("/admin/campaigns", {
                params: { status: "closed", limit: 50 },
            });
            setClosed(data.campaigns || data || []);
        } catch (e) {
            notifyError(formatApiError(e));
        }
    };

    const createFrom = async (campaignId) => {
        try {
            const { data } = await api.post(
                `/admin/case-studies${campaignId ? `?from_campaign=${campaignId}` : ""}`,
                {},
            );
            setPicking(false);
            await load();
            setEditing(data);
            notifySuccess(
                campaignId
                    ? "Drafted from the campaign — the narrative is yours to write."
                    : "Blank draft created.",
            );
        } catch (e) {
            notifyError(formatApiError(e));
        }
    };

    const columns = useMemo(
        () => [
            {
                key: "title",
                header: "Case study",
                mobile: "primary",
                value: (r) => r.title || "",
                cell: (r) => (
                    <span className="truncate">{r.title || "Untitled"}</span>
                ),
            },
            {
                key: "brand",
                header: "Brand",
                mobile: "meta",
                value: (r) => r.brand_name || "",
            },
            {
                key: "category",
                header: "Category",
                value: (r) => categoryLabel(r.category),
            },
            {
                key: "type",
                header: "Type",
                value: (r) => TYPE_LABELS[r.campaign_type] || "",
            },
            {
                key: "status",
                header: "Status",
                mobile: "trailing",
                value: (r) => r.status,
                cell: (r) => <StatusTag state={r.status} />,
            },
            {
                key: "updated",
                header: "Updated",
                value: (r) => r.updated_at || "",
                cell: (r) => relative(r.updated_at),
            },
        ],
        [],
    );

    return (
        <div className="grid gap-4" data-testid={IDS.section}>
            <div className="flex flex-wrap items-center gap-3">
                <h1 className="font-serif text-fluid-2xl leading-tight">Case studies</h1>
                <div className="ml-auto flex gap-2">
                    {/* The primary action, and the whole argument for the
                        feature: a closed campaign already knows nine tenths
                        of this. */}
                    <Button onClick={openPicker} data-testid={IDS.fromCampaign}>
                        <Wand2 className="mr-2 h-4 w-4" /> From a campaign
                    </Button>
                    <Button
                        variant="outline"
                        onClick={() => createFrom(null)}
                        data-testid={IDS.blank}
                    >
                        <Plus className="mr-2 h-4 w-4" /> Blank
                    </Button>
                </div>
            </div>

            <DataTable
                columns={columns}
                rows={rows || []}
                rowKey={(r) => r.id}
                rowTestId={(r) => IDS.row(r.id)}
                focused={focused}
                onFocus={setFocused}
                onOpen={(i) => setEditing((rows || [])[i])}
                loading={!rows}
                settleKey="case-studies"
                testid={IDS.table}
            />

            {editing && (
                <PeekPanel
                    open
                    onOpenChange={(v) => !v && setEditing(null)}
                    title={editing.title || "Untitled"}
                    subtitle={editing.brand_name || undefined}
                    testid={IDS.peek}
                >
                    <Editor
                        study={editing}
                        onSaved={(saved) => {
                            setEditing(saved);
                            load();
                        }}
                        onClose={() => setEditing(null)}
                    />
                </PeekPanel>
            )}

            {/* A picker rather than a `ConfirmDialog`: that primitive is
                built around a reason box and a single destructive verb, and
                this is a list of fifty things to choose one of. Reaching for
                it here would mean bending a shared component to a shape it
                was not written for — the thing the marketing navbar variant
                exists to avoid. */}
            <Dialog open={picking} onOpenChange={(v) => !v && setPicking(false)}>
                <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Which campaign?</DialogTitle>
                        <DialogDescription>
                            Only campaigns that have closed. The brand, the creators
                            who consented, the deliverables and any performance we
                            captured are filled in; the narrative is yours.
                        </DialogDescription>
                    </DialogHeader>
                    <ul className="grid gap-2" data-testid={IDS.campaignList}>
                        {closed.length === 0 && (
                            <li className={`${TEXT.meta} text-muted-foreground`}>
                                No closed campaigns yet.
                            </li>
                        )}
                        {closed.map((c) => (
                            <li key={c.id}>
                                <button
                                type="button"
                                onClick={() => createFrom(c.id)}
                                data-testid={IDS.campaignOption(c.id)}
                                className={`w-full rounded-md border border-tint/10 bg-tint/[0.02] ${DENSITY.row} text-left text-sm transition-colors duration-150 hover:border-primary/40`}
                            >
                                <span className="block truncate">{c.title}</span>
                                <span className={`${TEXT.meta} text-muted-foreground`}>
                                    {[c.brand_name, categoryLabel(c.category), c.city]
                                        .filter(Boolean)
                                        .join(" · ")}
                                </span>
                            </button>
                        </li>
                        ))}
                    </ul>
                </DialogContent>
            </Dialog>
        </div>
    );
}
